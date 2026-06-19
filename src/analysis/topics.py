"""
src/analysis/topics.py
Theme and mechanic frequency analysis.
"""
from __future__ import annotations

import pandas as pd

from src.analysis.base import weighted_quality, to_records


def run(df: pd.DataFrame) -> dict:
    """Return theme frequency and mechanic frequency.

    Returns:
        {
            "themes": [ {theme, count, mean_positive, total_owners, weighted_score} ... ],
            "mechanics": [ {mechanic, count, mean_positive} ... ],
        }
    """
    # --- themes ---
    themes = to_records(weighted_quality(df, "theme"))

    # --- mechanics ---
    # Explode the list column so each mechanic gets its own row.
    exploded = df[["mechanics", "review_pct_positive"]].copy()
    exploded = exploded.explode("mechanics")
    # Drop rows where mechanics is NaN/None (empty lists produce NaN after explode).
    exploded = exploded[exploded["mechanics"].notna()]

    if len(exploded) == 0:
        mechanics = []
    else:
        agg = (
            exploded.groupby("mechanics", sort=False)
            .agg(
                count=("mechanics", "count"),
                mean_positive=("review_pct_positive", "mean"),
            )
            .reset_index()
            .rename(columns={"mechanics": "mechanic"})
            .sort_values("count", ascending=False, kind="stable")
            .reset_index(drop=True)
        )
        mechanics = to_records(agg)

    return {"themes": themes, "mechanics": mechanics}
