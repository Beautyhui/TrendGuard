from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import List

import numpy as np
import pandas as pd


PATTERN_NAMES = [
    "闪电爆发-速衰型",
    "缓慢发酵-持续型",
    "反转振荡型",
    "争议升级型",
    "平稳消退型",
]


@dataclass
class TopicSeed:
    topic_key: str
    pattern: str
    keywords: List[str]
    start_at: datetime
    life_steps: int


def _pattern_curve(name: str, n_steps: int) -> np.ndarray:
    x = np.linspace(0, 1, n_steps)
    if name == "闪电爆发-速衰型":
        y = np.exp(-10 * (x - 0.1) ** 2) * (1 - 0.6 * x)
    elif name == "缓慢发酵-持续型":
        y = 0.3 + 0.8 * (1 - np.exp(-3 * x))
    elif name == "反转振荡型":
        y = 0.6 + 0.25 * np.sin(7 * np.pi * x) + 0.18 * np.sin(13 * np.pi * x)
    elif name == "争议升级型":
        y = 0.2 + 0.5 * x + 0.6 * (x > 0.6) * (x - 0.6)
    else:  # 平稳消退型
        y = 1.0 - 0.7 * x
    y = np.maximum(y, 0.05)
    return y / y.max()


def _sentiment_curve(name: str, n_steps: int) -> np.ndarray:
    x = np.linspace(0, 1, n_steps)
    if name == "争议升级型":
        s = 0.1 - 0.8 * x
    elif name == "反转振荡型":
        s = 0.1 * np.sin(10 * np.pi * x)
    elif name == "闪电爆发-速衰型":
        s = 0.1 - 0.2 * x
    elif name == "缓慢发酵-持续型":
        s = 0.15 - 0.1 * x
    else:
        s = 0.08 - 0.15 * x
    return np.clip(s, -1, 1)


def _build_seeds(start_at: datetime, n_topics: int = 40) -> List[TopicSeed]:
    base_words = [
        "电影",
        "明星",
        "科技",
        "发布会",
        "游戏",
        "新能源",
        "教育",
        "考试",
        "地铁",
        "赛事",
        "旅游",
        "景区",
        "外卖",
        "打车",
        "手机",
        "AI",
        "隐私",
        "裁员",
        "价格",
        "直播",
        "短视频",
        "医疗",
        "政策",
    ]
    seeds: List[TopicSeed] = []
    for i in range(n_topics):
        pattern = random.choice(PATTERN_NAMES)
        kws = random.sample(base_words, k=3)
        seed = TopicSeed(
            topic_key=f"T{i:03d}",
            pattern=pattern,
            keywords=kws,
            start_at=start_at + timedelta(hours=random.randint(0, 24)),
            life_steps=random.randint(14, 60),  # >=7h, keep runtime manageable
        )
        seeds.append(seed)
    return seeds


def generate_snapshots(
    days: int = 5, interval_minutes: int = 30, seed: int = 7
) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    begin = datetime.now() - timedelta(days=days)
    seeds = _build_seeds(begin)

    rows = []
    for s in seeds:
        heat_curve = _pattern_curve(s.pattern, s.life_steps)
        sent_curve = _sentiment_curve(s.pattern, s.life_steps)
        for idx in range(s.life_steps):
            ts = s.start_at + timedelta(minutes=interval_minutes * idx)
            if ts < begin:
                continue
            heat = max(5, int(800 * heat_curve[idx] + np.random.normal(0, 30)))
            rank = int(max(1, 100 - heat / 10 + np.random.normal(0, 2)))
            sentiment = float(np.clip(sent_curve[idx] + np.random.normal(0, 0.07), -1, 1))

            # same topic may appear with slight title drift
            drift_word = random.choice(["热议", "回应", "后续", "进展", "讨论"])
            title = f"{s.keywords[0]}{s.keywords[1]}{drift_word}{s.keywords[2]}"
            if random.random() < 0.18:
                # mild lexical change to simulate noisy snapshots
                title = f"{s.keywords[1]}{s.keywords[0]}{drift_word}{s.keywords[2]}"

            rows.append(
                {
                    "snapshot_time": ts,
                    "topic_title": title,
                    "heat": heat,
                    "rank": rank,
                    "sentiment": sentiment,
                    "true_pattern": s.pattern,
                    "true_topic_key": s.topic_key,
                }
            )

    df = pd.DataFrame(rows).sort_values("snapshot_time").reset_index(drop=True)
    return df
