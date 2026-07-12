"""
微博热搜数据接入：只通过「函数」对外提供数据，避免在 import 时执行爬虫或死循环。

推荐流程：
1. 用定时任务（每 30 分钟）调用 `fetch_weibo_top_once()` 或你自己的爬虫，
   把结果 append 到 `data/weibo_snapshots.csv`（多时间点累积）。
2. Flask 启动时用 `load_weibo_snapshots()` 读该文件；若没有文件或为空，在 app.py 里回退模拟数据。

CSV 建议列（表头一致即可，多余列会忽略）：
  snapshot_time,topic_title,rank,heat,sentiment
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from itertools import zip_longest
from typing import Sequence

import pandas as pd

# 项目根目录下的默认快照文件（与 app.py 同级 data 目录）
DEFAULT_SNAPSHOT_CSV = Path(__file__).resolve().parent.parent / "data" / "weibo_snapshots.csv"

_REQUIRED = ("snapshot_time", "topic_title", "rank", "heat", "sentiment")


def _parse_heat_value(raw: object) -> float:
    """把 '123万'、'1,234' 等转成数值，失败则 0。"""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "")
    if not s:
        return 0.0
    m = re.match(r"^([\d.]+)\s*万", s)
    if m:
        return float(m.group(1)) * 1e4
    m = re.match(r"^([\d.]+)\s*亿", s)
    if m:
        return float(m.group(1)) * 1e8
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_weibo_snapshots(csv_path: str | Path | None = None) -> pd.DataFrame:
    """
    从 CSV 读取多时间点热搜快照，返回与模拟器相同列名的 DataFrame。

    若文件不存在、为空、或缺少必要列，返回空表（列结构齐全），由 app 决定是否回退模拟数据。
    """
    path = Path(csv_path) if csv_path is not None else DEFAULT_SNAPSHOT_CSV
    if not path.exists() or path.stat().st_size < 5:
        return pd.DataFrame(columns=list(_REQUIRED))

    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return pd.DataFrame(columns=list(_REQUIRED))

    missing = [c for c in _REQUIRED if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=list(_REQUIRED))

    out = df[list(_REQUIRED)].copy()
    out["snapshot_time"] = pd.to_datetime(out["snapshot_time"], errors="coerce")
    out["topic_title"] = out["topic_title"].astype(str)
    out["rank"] = pd.to_numeric(out["rank"], errors="coerce").fillna(99).astype(int)
    if out["heat"].dtype == object:
        out["heat"] = out["heat"].map(_parse_heat_value)
    else:
        out["heat"] = pd.to_numeric(out["heat"], errors="coerce").fillna(0.0)
    out["sentiment"] = pd.to_numeric(out["sentiment"], errors="coerce").fillna(0.0).clip(-1, 1)
    out = out.dropna(subset=["snapshot_time", "topic_title"]).sort_values("snapshot_time")
    return out.reset_index(drop=True)


def load_snapshots_with_platform(csv_path: str | Path, platform: str) -> pd.DataFrame:
    """
    读取与微博相同格式的 CSV，并增加 platform 列（weibo / bilibili / douyin），供多源合并与分平台拼链。
    """
    base = load_weibo_snapshots(csv_path)
    if base.empty:
        return pd.DataFrame(columns=list(_REQUIRED) + ("platform",))
    out = base.copy()
    out["platform"] = str(platform)
    return out


def append_snapshot_rows(
    rows: Sequence[dict] | pd.DataFrame,
    csv_path: str | Path | None = None,
) -> Path:
    """
    把一批快照行追加写入 CSV。每行 dict 需含：snapshot_time, topic_title, rank, heat, sentiment。
    heat 可为字符串（如「123万」）。
    """
    path = Path(csv_path) if csv_path is not None else DEFAULT_SNAPSHOT_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(rows, pd.DataFrame):
        chunk = rows.copy()
    else:
        chunk = pd.DataFrame(list(rows))

    for c in _REQUIRED:
        if c not in chunk.columns:
            raise ValueError(f"append_snapshot_rows: 缺少列 {c}")

    chunk = chunk[list(_REQUIRED)].copy()
    chunk["snapshot_time"] = pd.to_datetime(chunk["snapshot_time"])
    if chunk["heat"].dtype == object:
        chunk["heat"] = chunk["heat"].map(_parse_heat_value)

    header = not path.exists() or path.stat().st_size == 0
    chunk.to_csv(path, mode="a", index=False, header=header, encoding="utf-8-sig")
    return path


def fetch_weibo_top_once(
    url: str = "https://s.weibo.com/top/summary/",
    timeout: int = 15,
) -> pd.DataFrame:
    """
    单次抓取当前微博热搜页，返回「这一刻」的一张表（一行一个词条）。

    需要环境变量 WEIBO_COOKIE（浏览器里复制 Cookie 整串）。不要在代码里写死 Cookie 提交到仓库。

    依赖：requests, lxml
    """
    cookie = os.environ.get("WEIBO_COOKIE", "").strip()
    if not cookie:
        return pd.DataFrame(columns=list(_REQUIRED))

    import requests
    from lxml import etree

    headers = {
        "User-Agent": os.environ.get(
            "WEIBO_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
        "Referer": "https://s.weibo.com/",
        "Cookie": cookie,
    }
    res = requests.get(url, headers=headers, timeout=timeout)
    res.raise_for_status()
    tree = etree.HTML(res.text)
    titles = tree.xpath("//td[@class='td-02']/a/text()")
    heats = tree.xpath("//td[@class='td-02']/span/text()")
    now = datetime.now()

    rows = []
    rank = 1
    for title, heat_raw in zip_longest(titles, heats, fillvalue=""):
        t = (title or "").strip()
        if not t:
            continue
        rows.append(
            {
                "snapshot_time": now,
                "topic_title": t,
                "rank": rank,
                "heat": heat_raw,
                "sentiment": 0.0,
            }
        )
        rank += 1
    return pd.DataFrame(rows)


def run_standalone_crawl_loop(
    interval_seconds: int = 20 * 60,
    csv_path: str | Path | None = None,
) -> None:
    """
    单独用「python -m src.weibo_loader」跑定时抓取时可用；不要在 Flask import 时调用。
    """
    import time

    path = Path(csv_path) if csv_path is not None else DEFAULT_SNAPSHOT_CSV
    while True:
        df = fetch_weibo_top_once()
        if not df.empty:
            append_snapshot_rows(df, path)
            print(f"[{datetime.now()}] 已写入 {len(df)} 条 -> {path}")
        else:
            print(f"[{datetime.now()}] 未抓取到数据（检查 WEIBO_COOKIE）")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_standalone_crawl_loop()
