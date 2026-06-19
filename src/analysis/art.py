"""
src/analysis/art.py
Art style performance analysis using weighted_quality.
"""
from __future__ import annotations

import pandas as pd

from src.analysis.base import weighted_quality, to_records


def run(df: pd.DataFrame) -> dict:
    """Return per-art-style quality aggregates.

    Returns:
        {"by_art_style": [ {art_style, count, mean_positive, total_owners, weighted_score} ... ]}
    """
    return {"by_art_style": to_records(weighted_quality(df, "art_style"))}
