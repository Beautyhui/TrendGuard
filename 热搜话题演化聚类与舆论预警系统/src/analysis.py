from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering


PATTERN_ORDER = [
    "闪电爆发-速衰型",
    "缓慢发酵-持续型",
    "反转振荡型",
    "争议升级型",
    "平稳消退型",
]


@dataclass
class ModelBundle:
    chain_features: pd.DataFrame
    chain_sequences: Dict[str, dict]
    cluster_label_by_chain: Dict[str, int]
    pattern_name_by_cluster: Dict[int, str]
    distance_matrix: np.ndarray


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    n, m = len(a), len(b)
    dp = np.full((n + 1, m + 1), np.inf)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(a[i - 1] - b[j - 1])
            dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    return float(dp[n, m] / (n + m))


def _zscore(x: np.ndarray) -> np.ndarray:
    if x.std() < 1e-9:
        return np.zeros_like(x)
    return (x - x.mean()) / x.std()


def _compress_series(x: np.ndarray, max_len: int = 36) -> np.ndarray:
    if len(x) <= max_len:
        return x
    idx = np.linspace(0, len(x) - 1, max_len).astype(int)
    return x[idx]


def _prototype_curve(name: str, n_steps: int) -> np.ndarray:
    x = np.linspace(0, 1, n_steps)
    if name == "闪电爆发-速衰型":
        y = np.exp(-10 * (x - 0.1) ** 2) * (1 - 0.6 * x)
    elif name == "缓慢发酵-持续型":
        y = 0.3 + 0.8 * (1 - np.exp(-3 * x))
    elif name == "反转振荡型":
        y = 0.6 + 0.25 * np.sin(7 * np.pi * x) + 0.18 * np.sin(13 * np.pi * x)
    elif name == "争议升级型":
        y = 0.2 + 0.5 * x + 0.6 * (x > 0.6) * (x - 0.6)
    else:
        y = 1.0 - 0.7 * x
    y = np.maximum(y, 0.05)
    return y / y.max()


def build_chain_sequences(chain_df: pd.DataFrame) -> Dict[str, dict]:
    seq = {}
    for cid, g in chain_df.sort_values("snapshot_time").groupby("chain_id"):
        g = g.sort_values("snapshot_time")
        plat = str(g["platform"].iloc[-1]) if "platform" in g.columns else "weibo"
        seq[cid] = {
            "time": g["snapshot_time"].to_list(),
            "heat": g["heat"].to_numpy(dtype=float),
            "rank": g["rank"].to_numpy(dtype=float),
            "sentiment": g["sentiment"].to_numpy(dtype=float),
            "title": g["topic_title"].iloc[-1],
            "platform": plat,
        }
    return seq


_FEATURE_COLS = (
    "chain_id",
    "n_points",
    "peak_heat",
    "time_to_peak_ratio",
    "heat_volatility",
    "sentiment_volatility",
    "negative_end",
    "rank_change",
    "heat_slope",
    "decay_ratio",
)


def build_chain_features(sequences: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for cid, seq in sequences.items():
        heat = seq["heat"]
        rank = seq["rank"]
        sent = seq["sentiment"]
        n = len(heat)
        peak_idx = int(np.argmax(heat))
        rows.append(
            {
                "chain_id": cid,
                "n_points": n,
                "peak_heat": float(heat.max()),
                "time_to_peak_ratio": peak_idx / max(1, n - 1),
                "heat_volatility": float(np.std(np.diff(heat))) if n > 1 else 0.0,
                "sentiment_volatility": float(np.std(np.diff(sent))) if n > 1 else 0.0,
                "negative_end": float(-sent[-1]),
                "rank_change": float(rank[0] - rank[-1]),
                "heat_slope": float((heat[-1] - heat[0]) / max(1, n - 1)),
                "decay_ratio": float((heat.max() - heat[-1]) / max(1, heat.max())),
            }
        )
    if not rows:
        return pd.DataFrame(columns=list(_FEATURE_COLS))
    return pd.DataFrame(rows)


def dtw_distance_matrix(sequences: Dict[str, dict], chain_ids: List[str]) -> np.ndarray:
    n = len(chain_ids)
    dist = np.zeros((n, n), dtype=float)
    for i in range(n):
        a = _zscore(_compress_series(sequences[chain_ids[i]]["heat"]))
        for j in range(i + 1, n):
            b = _zscore(_compress_series(sequences[chain_ids[j]]["heat"]))
            d = dtw_distance(a, b)
            dist[i, j] = d
            dist[j, i] = d
    return dist


def _name_clusters(feat: pd.DataFrame, labels: np.ndarray) -> Dict[int, str]:
    tmp = feat.copy()
    tmp["cluster"] = labels
    by_cluster = tmp.groupby("cluster").mean(numeric_only=True)
    mapping: Dict[int, str] = {}

    # heuristic naming by centroid behavior
    for c, row in by_cluster.iterrows():
        if row["sentiment_volatility"] > 0.11 and row["heat_volatility"] > 85:
            mapping[c] = "反转振荡型"
        elif row["negative_end"] > 0.45 and row["heat_slope"] > 8:
            mapping[c] = "争议升级型"
        elif row["time_to_peak_ratio"] < 0.25 and row["decay_ratio"] > 0.65:
            mapping[c] = "闪电爆发-速衰型"
        elif row["heat_slope"] > 0 and row["decay_ratio"] < 0.35:
            mapping[c] = "缓慢发酵-持续型"
        else:
            mapping[c] = "平稳消退型"
    return mapping


def train_pipeline(chain_df: pd.DataFrame, n_clusters: int = 5) -> ModelBundle:
    sequences = build_chain_sequences(chain_df)
    feat = build_chain_features(sequences)
    if feat.empty:
        empty = feat.copy()
        empty["cluster"] = pd.Series(dtype="int64")
        return ModelBundle(
            chain_features=empty,
            chain_sequences=sequences,
            cluster_label_by_chain={},
            pattern_name_by_cluster={},
            distance_matrix=np.zeros((0, 0), dtype=float),
        )

    chain_ids = feat["chain_id"].tolist()

    dist = dtw_distance_matrix(sequences, chain_ids)
    clustering = AgglomerativeClustering(
        n_clusters=min(n_clusters, len(chain_ids)),
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(dist)
    feat["cluster"] = labels

    name_map = _name_clusters(feat, labels)
    cluster_label_by_chain = {
        cid: int(lb) for cid, lb in zip(chain_ids, labels.tolist(), strict=False)
    }
    return ModelBundle(
        chain_features=feat,
        chain_sequences=sequences,
        cluster_label_by_chain=cluster_label_by_chain,
        pattern_name_by_cluster=name_map,
        distance_matrix=dist,
    )


def classify_partial(
    bundle: ModelBundle, partial_heat: np.ndarray, partial_sentiment: np.ndarray
) -> Tuple[str, float, str]:
    partial = _zscore(_compress_series(partial_heat))

    # Use pattern prototypes for robust early-stage recognition,
    # rather than relying only on cluster naming.
    proto_scores: Dict[str, float] = {}
    for p in PATTERN_ORDER:
        proto = _zscore(_prototype_curve(p, len(partial)))
        proto_scores[p] = dtw_distance(partial, proto)

    sent = _compress_series(partial_sentiment)
    heat_slope = float((partial_heat[-1] - partial_heat[0]) / max(1, len(partial_heat) - 1))
    sent_vol = float(np.std(np.diff(sent))) if len(sent) > 1 else 0.0
    sent_tail = float(np.mean(sent[-4:])) if len(sent) >= 4 else float(np.mean(sent))

    # Small behavior-based adjustments to reduce pattern collapse.
    proto_scores["争议升级型"] -= 0.08 * max(0.0, heat_slope / 20.0) + 0.06 * max(
        0.0, -sent_tail
    )
    proto_scores["反转振荡型"] -= 0.10 * min(1.0, sent_vol / 0.2)
    if heat_slope < -4:
        proto_scores["平稳消退型"] -= 0.06
    if heat_slope > 3:
        proto_scores["缓慢发酵-持续型"] -= 0.05

    ranked = sorted(proto_scores.items(), key=lambda kv: kv[1])
    pattern = ranked[0][0]
    best, second = ranked[0][1], ranked[1][1]
    confidence = float(np.clip(0.55 + (second - best) * 0.8, 0.5, 0.98))

    phase = "早期"
    if len(partial_heat) > 14:
        phase = "中期"
    if len(partial_heat) > 30:
        phase = "后期"
    if np.mean(partial_sentiment[-4:]) < -0.35 and pattern == "争议升级型":
        phase += "-风险上行"
    return pattern, confidence, phase
