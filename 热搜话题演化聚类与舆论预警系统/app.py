from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template
import pandas as pd

from src.alerts import build_realtime_alerts
from src.analysis import train_pipeline
from src.bilibili_hot import DEFAULT_BILIBILI_CSV
from src.data_simulator import generate_snapshots
from src.douyin_hot import DEFAULT_DOUYIN_CSV
from src.topic_chain import build_topic_chains
from src.weibo_loader import (
    DEFAULT_SNAPSHOT_CSV,
    load_snapshots_with_platform,
)

app = Flask(__name__)


def _build_scatter_points(feat: pd.DataFrame, sequences: dict) -> list[dict]:
    """
    为散点图生成二维坐标与卡片展示用字段。
    横轴：峰值出现相对位置 time_to_peak_ratio（0≈链开端即达峰，1≈末端达峰）
    纵轴：热度衰减比例 decay_ratio（越大表示相对峰值掉得越多）
    轻微抖动减轻完全重合点。
    """
    rows: list[dict] = []
    if feat.empty:
        return rows
    for _, r in feat.iterrows():
        cid = str(r["chain_id"])
        seq = sequences.get(cid, {})
        title = str(seq.get("title", cid))
        platform = str(seq.get("platform", "weibo"))
        pattern = str(r.get("pattern", ""))
        h = (abs(hash(cid)) % 10001) / 1_000_000.0 - 0.0005
        x = float(r["time_to_peak_ratio"]) + h * 0.25
        y = float(r["decay_ratio"]) + h * 0.25
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        rows.append(
            {
                "chain_id": cid,
                "title": title,
                "pattern": pattern,
                "platform": platform,
                "cluster": int(r.get("cluster", 0)),
                "n_points": int(r["n_points"]),
                "peak_heat": round(float(r["peak_heat"]), 2),
                "heat_slope": round(float(r["heat_slope"]), 6),
                "heat_volatility": round(float(r["heat_volatility"]), 4),
                "decay_ratio": round(float(r["decay_ratio"]), 4),
                "sentiment_volatility": round(float(r["sentiment_volatility"]), 4),
                "rank_change": round(float(r["rank_change"]), 2),
                "negative_end": round(float(r["negative_end"]), 4),
                "x": x,
                "y": y,
            }
        )
    return rows


def _merge_platform_snapshots() -> tuple[pd.DataFrame, dict[str, int], dict[str, str]]:
    """
    合并微博 / B站 / 抖音 三个 CSV（列格式一致），并打上 platform 列。
    返回 (merged_df, 各平台行数, 各平台 CSV 绝对路径)。
    """
    paths: dict[str, Path] = {
        "weibo": Path(os.environ.get("WEIBO_SNAPSHOT_CSV", str(DEFAULT_SNAPSHOT_CSV))).expanduser(),
        "bilibili": Path(
            os.environ.get("BILIBILI_SNAPSHOT_CSV", str(DEFAULT_BILIBILI_CSV))
        ).expanduser(),
        "douyin": Path(os.environ.get("DOUYIN_SNAPSHOT_CSV", str(DEFAULT_DOUYIN_CSV))).expanduser(),
    }
    parts: list[pd.DataFrame] = []
    counts: dict[str, int] = {}
    resolved: dict[str, str] = {}
    for name, p in paths.items():
        resolved[name] = str(p.resolve())
        df = load_snapshots_with_platform(p, name)
        counts[name] = len(df)
        if not df.empty:
            parts.append(df)
    if not parts:
        return pd.DataFrame(), counts, resolved
    merged = (
        pd.concat(parts, ignore_index=True)
        .sort_values(["snapshot_time", "platform"])
        .reset_index(drop=True)
    )
    return merged, counts, resolved


def build_dashboard_data():
    seed = int(datetime.now().timestamp() * 1000) % 1_000_000
    raw_df, platform_counts, csv_paths = _merge_platform_snapshots()

    if raw_df.empty:
        raw_df = generate_snapshots(days=5, interval_minutes=30, seed=seed)
        data_source = "simulated"
        data_source_label = "模拟数据（三个平台 CSV 均无有效行）"
        platform_counts = {"weibo": 0, "bilibili": 0, "douyin": 0}
    else:
        data_source = "merged_csv"
        data_source_label = (
            f"合并：微博 {platform_counts['weibo']} 条，"
            f"B站 {platform_counts['bilibili']} 条，"
            f"抖音 {platform_counts['douyin']} 条"
        )

    chain_df = build_topic_chains(raw_df, max_gap_hours=6)
    bundle = train_pipeline(chain_df, n_clusters=5)
    alerts = build_realtime_alerts(bundle)

    feat = bundle.chain_features.copy()
    scatter_points: list[dict] = []
    if feat.empty:
        cluster_dist = []
        curve_items = []
    else:
        feat["pattern"] = feat["cluster"].map(bundle.pattern_name_by_cluster)
        cluster_dist = (
            feat["pattern"].value_counts().rename_axis("pattern").reset_index(name="count")
        ).to_dict(orient="records")

        scatter_points = _build_scatter_points(feat, bundle.chain_sequences)

        curve_items = []
        for row in cluster_dist:
            pattern = row["pattern"]
            cids = feat[feat["pattern"] == pattern]["chain_id"].tolist()[:3]
            for cid in cids:
                seq = bundle.chain_sequences[cid]
                curve_items.append(
                    {
                        "chain_id": cid,
                        "pattern": pattern,
                        "platform": seq.get("platform", "weibo"),
                        "title": seq["title"],
                        "heat": [float(x) for x in seq["heat"].tolist()],
                        "rank": [float(x) for x in seq["rank"].tolist()],
                        "sentiment": [float(x) for x in seq["sentiment"].tolist()],
                        "time": [pd.Timestamp(t).strftime("%m-%d %H:%M") for t in seq["time"]],
                    }
                )

    return {
        "alerts": alerts,
        "cluster_distribution": cluster_dist,
        "scatter_points": scatter_points,
        "curves": curve_items,
        "meta": {
            "seed": seed,
            "refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_source": data_source,
            "data_source_label": data_source_label,
            "platform_counts": platform_counts,
            "snapshot_csv_paths": csv_paths,
        },
        "stats": {
            "raw_points": int(len(raw_df)),
            "chains": (
                int(chain_df["chain_id"].nunique())
                if not chain_df.empty and "chain_id" in chain_df.columns
                else 0
            ),
            "active_alerts": int(len(alerts)),
        },
    }


_dashboard_cache = build_dashboard_data()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def dashboard():
    return jsonify(_dashboard_cache)


@app.route("/api/refresh")
def refresh():
    global _dashboard_cache
    _dashboard_cache = build_dashboard_data()
    return jsonify({"ok": True, "message": "refreshed"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
