"""
抖音热搜榜（网页端公开接口，无签名参数时多数环境可用）。

接口示例：
https://www.douyin.com/aweme/v1/web/hot/search/list/
  ?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1

若返回空或 status_code 非 0，可尝试在浏览器打开抖音网页后复制 Cookie，
设置环境变量 DOUYIN_COOKIE 后重试。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_DOUYIN_CSV = Path(__file__).resolve().parent.parent / "data" / "douyin_snapshots.csv"

_REQUIRED = ("snapshot_time", "topic_title", "rank", "heat", "sentiment")

_DOUYIN_HOT_URL = (
    "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    "?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
)


def fetch_douyin_hot_once(timeout: int = 20) -> pd.DataFrame:
    """
    抓取当前时刻抖音热搜词列表，返回与微博快照相同列名的 DataFrame。
    """
    import os
    import requests

    headers = {
        "User-Agent": os.environ.get(
            "DOUYIN_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
        "Referer": "https://www.douyin.com/",
    }
    cookie = os.environ.get("DOUYIN_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie

    res = requests.get(_DOUYIN_HOT_URL, headers=headers, timeout=timeout)
    res.raise_for_status()
    payload: dict[str, Any] = res.json()

    data = payload.get("data") or {}
    word_list = data.get("word_list") or []
    if not word_list:
        return pd.DataFrame(columns=list(_REQUIRED))

    now = datetime.now()
    rows: list[dict[str, Any]] = []
    for it in word_list:
        title = (it.get("word") or "").strip()
        if not title:
            continue
        pos = int(it.get("position") or it.get("max_rank") or len(rows) + 1)
        heat = float(it.get("hot_value") or 0.0)
        rows.append(
            {
                "snapshot_time": now,
                "topic_title": title,
                "rank": pos,
                "heat": heat,
                "sentiment": 0.0,
            }
        )

    rows.sort(key=lambda x: x["rank"])
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=list(_REQUIRED))
