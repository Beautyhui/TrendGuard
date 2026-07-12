"""
哔哩哔哩搜索热搜榜（非登录接口）。

接口：https://s.search.bilibili.com/main/hotword?limit=N
返回 JSON 中 list[] 含 show_name / keyword、heat_score 等。

说明：这是「搜索热搜词」榜；与「全站排行榜视频」不是同一数据源。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_BILIBILI_CSV = Path(__file__).resolve().parent.parent / "data" / "bilibili_snapshots.csv"

_REQUIRED = ("snapshot_time", "topic_title", "rank", "heat", "sentiment")


def fetch_bilibili_hot_once(limit: int = 50, timeout: int = 15) -> pd.DataFrame:
    """
    抓取当前时刻 B 站搜索热搜，返回与微博快照相同列名的 DataFrame。
    一般无需 Cookie；若遇风控可设置环境变量 BILIBILI_COOKIE（可选）。
    """
    import os
    import requests

    url = f"https://s.search.bilibili.com/main/hotword?limit={int(limit)}"
    headers = {
        "User-Agent": os.environ.get(
            "BILIBILI_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
        "Referer": "https://www.bilibili.com/",
    }
    cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie

    res = requests.get(url, headers=headers, timeout=timeout)
    res.raise_for_status()
    payload: dict[str, Any] = res.json()
    if payload.get("code") != 0:
        return pd.DataFrame(columns=list(_REQUIRED))

    items = payload.get("list") or []
    now = datetime.now()
    rows: list[dict[str, Any]] = []
    rank = 1
    for it in items:
        title = (it.get("show_name") or it.get("keyword") or "").strip()
        if not title:
            continue
        heat = float(it.get("heat_score") or it.get("score") or 0.0)
        rows.append(
            {
                "snapshot_time": now,
                "topic_title": title,
                "rank": rank,
                "heat": heat,
                "sentiment": 0.0,
            }
        )
        rank += 1

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=list(_REQUIRED))
