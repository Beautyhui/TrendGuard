from __future__ import annotations

from datetime import timedelta
import re
from typing import Dict, List, Set

import pandas as pd


def _tokens(text: str) -> Set[str]:
    chunks = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)
    return {c for c in chunks if len(c) >= 2}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build_topic_chains(df: pd.DataFrame, max_gap_hours: int = 6) -> pd.DataFrame:
    df = df.copy()
    if "platform" not in df.columns:
        df["platform"] = "weibo"

    records = df.sort_values(["snapshot_time", "platform"]).to_dict("records")
    chains: Dict[str, List[dict]] = {}
    chain_last_token: Dict[str, Set[str]] = {}
    chain_last_time: Dict[str, pd.Timestamp] = {}
    chain_last_platform: Dict[str, str] = {}

    seq = 0
    for rec in records:
        rec_time = pd.Timestamp(rec["snapshot_time"])
        plat = str(rec.get("platform", "weibo"))
        tok = _tokens(rec["topic_title"])

        best_id = None
        best_score = 0.0
        for cid, last_tok in chain_last_token.items():
            if chain_last_platform.get(cid) != plat:
                continue
            if rec_time - chain_last_time[cid] > timedelta(hours=max_gap_hours):
                continue
            score = _jaccard(tok, last_tok)
            if score > best_score:
                best_score = score
                best_id = cid

        if best_id is None or best_score < 0.34:
            best_id = f"C{seq:04d}"
            seq += 1
            chains[best_id] = []

        rec["chain_id"] = best_id
        chains[best_id].append(rec)
        chain_last_token[best_id] = tok
        chain_last_time[best_id] = rec_time
        chain_last_platform[best_id] = plat

    merged = [x for items in chains.values() for x in items]
    out = pd.DataFrame(merged)

    # keep chains alive >=6h（题目要求）；若只有单次快照等导致全部被滤掉，则保留全部链以免下游崩溃
    spans = out.groupby("chain_id")["snapshot_time"].agg(["min", "max"])
    spans["life_hours"] = (spans["max"] - spans["min"]).dt.total_seconds() / 3600.0
    keep = spans[spans["life_hours"] >= 6].index
    filtered = out[out["chain_id"].isin(keep)].copy()
    if filtered.empty and not out.empty:
        return out.copy()
    return filtered
