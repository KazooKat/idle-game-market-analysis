"""
src/analysis/performance.py
Per-theme performance ranked by weighted_score (descending).
Groups with NaN weighted_score are dropped from the ranking.
"""
from __future__ import annotations

import pandas as pd

from src.analysis.base import weighted_quality, to_records


def run(df: pd.DataFrame) -> dict:
    """Return per-theme performance ranked by weighted_score DESC.

    Returns:
        {"by_theme": [ {theme, count, mean_positive, total_owners, weighted_score} ... ]}

    NaN-weighted_score groups are excluded from the result (they cannot be ranked).
    """
    wq = weighted_quality(df, "theme")

    # Drop groups whose weighted_score is NaN — they have no meaningful rank signal.
    ranked = wq[wq["weighted_score"].notna()].sort_values(
        "weighted_score", ascending=False, kind="stable"
    ).reset_index(drop=True)

    return {"by_theme": to_records(ranked)}
