"""
src/analysis/updates.py
Update cadence bucket analysis.

Buckets:
  active     – update_cadence <= 30 days
  occasional – update_cadence > 30 and <= 120 days
  abandoned  – update_cadence > 120 OR None/NaN (no recent update detected)

Per bucket: count, mean review_pct_positive, total_owners (high+medium conf).
"""
from __future__ import annotations

import math

import pandas as pd

_TRUSTED_CONF = {"high", "medium"}

_BUCKET_ORDER = ["active", "occasional", "abandoned"]


def _cadence_bucket(cadence) -> str:
    """Classify a cadence value (float, None, NaN) into a bucket label."""
    if cadence is None or (isinstance(cadence, float) and math.isnan(cadence)):
        return "abandoned"
    if cadence <= 30:
        return "active"
    if cadence <= 120:
        return "occasional"
    return "abandoned"


def run(df: pd.DataFrame) -> dict:
    """Return update cadence bucket stats.

    Returns:
        {
            "by_cadence": [
                {cadence, count, mean_positive, total_owners},
                ...
            ]  # ordered: active, occasional, abandoned
        }
    """
    work = df.copy()
    work["_bucket"] = work["update_cadence"].apply(_cadence_bucket)
    work["_trusted"] = work["owners_confidence"].isin(_TRUSTED_CONF)
    work["_owners_f"] = work["owners_est"].astype("float64")

    results = []
    for label in _BUCKET_ORDER:
        sub = work[work["_bucket"] == label]
        count = len(sub)
        scores = sub["review_pct_positive"].dropna()
        mean_positive = float(scores.mean()) if len(scores) > 0 else None
        if mean_positive is not None and math.isnan(mean_positive):
            mean_positive = None
        total_owners = int(sub.loc[sub["_trusted"], "_owners_f"].sum())
        results.append({
            "cadence": label,
            "count": count,
            "mean_positive": mean_positive,
            "total_owners": total_owners,
        })

    return {"by_cadence": results}
