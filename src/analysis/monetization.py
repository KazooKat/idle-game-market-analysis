"""
src/analysis/monetization.py
Business model and price bucket performance analysis.
"""
from __future__ import annotations

import math

import pandas as pd

from src.analysis.base import weighted_quality, to_records

# Ordered bucket definitions: (label, low_inclusive, high_exclusive)
# "free" is a special bucket for is_free=True or price==0.
_PRICE_BUCKETS = [
    ("free",   None,  None),    # special
    ("0.01-1", 0.01,  1.0),
    ("1-3",    1.0,   3.0),
    ("3-5",    3.0,   5.0),
    ("5-10",   5.0,   10.0),
    ("10-20",  10.0,  20.0),
    ("20+",    20.0,  None),
]

_TRUSTED_CONF = {"high", "medium"}


def _classify_price(price: float | None, is_free) -> str:
    """Return the bucket label for a given price/is_free combination."""
    if is_free is True or is_free == 1 or price == 0.0:
        return "free"
    if price is None or (isinstance(price, float) and math.isnan(price)):
        return "0.01-1"  # Unknown price, keep in lowest paid bucket
    for label, lo, hi in _PRICE_BUCKETS[1:]:  # skip "free"
        if lo is not None and hi is None:
            if price >= lo:
                return label
        elif lo is not None and hi is not None:
            if lo <= price < hi:
                return label
    return "20+"


def _price_buckets(df: pd.DataFrame) -> list[dict]:
    """Compute per-bucket stats in defined order."""
    df = df.copy()
    df["_bucket"] = [
        _classify_price(row["price"], row["is_free"])
        for _, row in df.iterrows()
    ]
    df["_trusted"] = df["owners_confidence"].isin(_TRUSTED_CONF)
    df["_owners_f"] = df["owners_est"].astype("float64")

    results = []
    for label, _, _ in _PRICE_BUCKETS:
        sub = df[df["_bucket"] == label]
        count = len(sub)
        scores = sub["review_pct_positive"].dropna()
        mean_positive = float(scores.mean()) if len(scores) > 0 else None
        if mean_positive is not None and math.isnan(mean_positive):
            mean_positive = None
        total_owners = int(sub.loc[sub["_trusted"], "_owners_f"].sum())
        results.append({
            "bucket": label,
            "count": count,
            "mean_positive": mean_positive,
            "total_owners": total_owners,
        })
    return results


def run(df: pd.DataFrame) -> dict:
    """Return business model and price bucket performance.

    Returns:
        {
            "by_business_model": [ {business_model, count, mean_positive,
                                     total_owners, weighted_score} ... ],
            "price_buckets": [ {bucket, count, mean_positive, total_owners} ... ]
        }
    """
    by_bm = to_records(weighted_quality(df, "business_model"))
    buckets = _price_buckets(df)

    return {"by_business_model": by_bm, "price_buckets": buckets}
