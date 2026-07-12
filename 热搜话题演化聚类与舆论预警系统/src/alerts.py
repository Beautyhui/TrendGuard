from __future__ import annotations

from typing import Dict, List

import numpy as np

from .analysis import ModelBundle, classify_partial


def build_realtime_alerts(bundle: ModelBundle) -> List[Dict]:
    alerts = []
    for cid, seq in bundle.chain_sequences.items():
        n = len(seq["heat"])
        cut = max(8, int(n * 0.45))
        partial_heat = seq["heat"][:cut]
        partial_sent = seq["sentiment"][:cut]
        pred, conf, phase = classify_partial(bundle, partial_heat, partial_sent)

        neg = float(-np.mean(partial_sent[-4:]))
        speed = float((partial_heat[-1] - partial_heat[0]) / max(1, len(partial_heat) - 1))
        heat_diff = np.diff(partial_heat)
        sent_diff = np.diff(partial_sent)
        turnings = int(np.sum(np.sign(heat_diff[1:]) * np.sign(heat_diff[:-1]) < 0)) if len(heat_diff) > 1 else 0
        sent_vol = float(np.std(sent_diff)) if len(sent_diff) > 0 else 0.0

        # Risk-pattern attribution is based on local behavior to avoid
        # all alerts collapsing into one label.
        if turnings >= 3 or sent_vol > 0.12:
            risk_pattern = "反转振荡型"
        else:
            risk_pattern = "争议升级型"

        # Keep high-risk candidates even if global class is noisy.
        if conf < 0.58 or (neg < 0.18 and speed < 2 and turnings < 2 and pred not in {"争议升级型", "反转振荡型"}):
            continue

        score = 0.5 * conf + 0.2 * min(1, neg) + 0.15 * min(1, speed / 30) + 0.15 * min(
            1.0, turnings / 5
        )

        if score > 0.78:
            level = "高"
        elif score > 0.66:
            level = "中"
        else:
            level = "低"

        alerts.append(
            {
                "chain_id": cid,
                "platform": seq.get("platform", "weibo"),
                "topic_title": seq["title"],
                "predicted_pattern": risk_pattern,
                "phase": phase,
                "confidence": round(conf, 3),
                "level": level,
                "risk_score": round(score, 3),
            }
        )

    alerts.sort(key=lambda x: x["risk_score"], reverse=True)
    return alerts[:20]
