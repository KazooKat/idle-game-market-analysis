"""
src/analysis/base.py
Shared helpers for all analysis modules.

Public API:
    load_master(path) -> pd.DataFrame
    weighted_quality(df, by) -> pd.DataFrame
    to_records(df) -> list[dict]
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Confidence levels whose owner counts are trusted for weighting.
_TRUSTED_CONF = {"high", "medium"}


# ---------------------------------------------------------------------------
# load_master
# ---------------------------------------------------------------------------

def load_master(path: str = "data/processed/games.parquet") -> pd.DataFrame:
    """Read the master games parquet and return a DataFrame.

    Raises FileNotFoundError (or pyarrow/fastparquet equivalent) when the
    file is absent.  Callers should handle missing-file errors gracefully.
    """
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# weighted_quality
# ---------------------------------------------------------------------------

def weighted_quality(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Group *df* by column *by* and compute quality aggregates.

    Returns one row per group (by as a plain column, not index) with:
        count         – number of games in the group
        mean_positive – mean of review_pct_positive (NaN rows skipped)
        total_owners  – sum of owners_est where owners_confidence in {high, medium}
        weighted_score – owners-weighted mean of review_pct_positive using the same
                         high+medium-confidence rows as weights.
                         Falls back to mean_positive when the qualifying weight
                         sum is zero (prevents NaN/inf).

    Rows where *by* is null are dropped before grouping.
    Result is sorted by count descending (stable sort).
    """
    # Drop rows where the group key is null.
    df = df[df[by].notna()].copy()

    # Guard: if no rows remain after dropping nulls, return an empty DataFrame
    # with the correct schema so callers (e.g. to_records) get [] without KeyError.
    if df.empty:
        return pd.DataFrame(columns=[by, "count", "mean_positive", "total_owners", "weighted_score"])

    # Boolean mask: row qualifies for owner-weight contribution.
    df["_trusted"] = df["owners_confidence"].isin(_TRUSTED_CONF)

    # Safely cast owners_est to float (handles nullable Int64 and NaN).
    df["_owners_f"] = df["owners_est"].astype("float64")

    # Owner weight for trusted rows only (used as denominator).
    df["_weight"] = df["_owners_f"] * df["_trusted"]

    # --- aggregation ---
    def _agg(g: pd.DataFrame) -> pd.Series:
        count = len(g)
        mean_positive = g["review_pct_positive"].mean()  # skips NaN by default
        total_owners = int(g.loc[g["_trusted"], "_owners_f"].sum())

        weight_sum = g["_weight"].sum()
        if weight_sum > 0:
            # Weighted mean: only include rows that BOTH have trusted ownership
            # AND a non-NaN score in the numerator.
            # We zero out NaN scores in _score_x_owners, but if a row has no score
            # it should not dilute the weight either — exclude it from weight_sum too.
            valid_mask = g["_trusted"] & g["review_pct_positive"].notna()
            numer = (g.loc[valid_mask, "review_pct_positive"] * g.loc[valid_mask, "_owners_f"]).sum()
            denom = g.loc[valid_mask, "_owners_f"].sum()
            weighted_score = (numer / denom) if denom > 0 else mean_positive
        else:
            weighted_score = mean_positive

        return pd.Series({
            "count": count,
            "mean_positive": mean_positive,
            "total_owners": total_owners,
            "weighted_score": weighted_score,
        })

    result = df.groupby(by, sort=False).apply(_agg, include_groups=False)
    result = result.reset_index()

    # Sort by count descending, stable (preserves original group order on ties).
    result = result.sort_values("count", ascending=False, kind="stable").reset_index(drop=True)

    # Cast count to plain int for cleanliness.
    result["count"] = result["count"].astype(int)
    result["total_owners"] = result["total_owners"].astype(int)

    return result


# ---------------------------------------------------------------------------
# to_records
# ---------------------------------------------------------------------------

def _nan_to_none(value: Any) -> Any:
    """Convert float NaN / pd.NA / pd.NaT to None; leave other values as-is."""
    if value is pd.NA or value is pd.NaT:
        return None
    try:
        if math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to a JSON-safe list of dicts (NaN/NA → None).

    Suitable for direct use with json.dumps without custom encoders.
    """
    raw = df.to_dict(orient="records")
    return [
        {k: _nan_to_none(v) for k, v in row.items()}
        for row in raw
    ]
