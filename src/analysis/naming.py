"""
src/analysis/naming.py
Title pattern performance analysis.

Classify each game name into one of:
  idle_x    – name (lowercased) contains "idle"
  x_clicker – name (lowercased) contains "clicker"  (only if not already idle_x)
  creative  – all other names

Per pattern: count + mean review_pct_positive.
"""
from __future__ import annotations

import math

import pandas as pd

from src.analysis.base import to_records

_PATTERN_ORDER = ["idle_x", "x_clicker", "creative"]


def _classify(name) -> str:
    """Return pattern label for a game name."""
    if not isinstance(name, str):
        return "creative"
    lower = name.lower()
    if "idle" in lower:
        return "idle_x"
    if "clicker" in lower:
        return "x_clicker"
    return "creative"


def run(df: pd.DataFrame) -> dict:
    """Return title pattern performance.

    Returns:
        {"by_pattern": [ {pattern, count, mean_positive} ... ]}
    """
    work = df.copy()
    work["_pattern"] = work["name"].apply(_classify)

    results = []
    for label in _PATTERN_ORDER:
        sub = work[work["_pattern"] == label]
        count = len(sub)
        scores = sub["review_pct_positive"].dropna()
        mean_positive = float(scores.mean()) if len(scores) > 0 else None
        if mean_positive is not None and math.isnan(mean_positive):
            mean_positive = None
        results.append({
            "pattern": label,
            "count": count,
            "mean_positive": mean_positive,
        })

    return {"by_pattern": results}
