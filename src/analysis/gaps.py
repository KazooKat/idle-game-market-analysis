"""
src/analysis/gaps.py
Supply vs demand gap map per theme.

supply  = count of games (from weighted_quality)
demand  = weighted_score (from weighted_quality)

underserved flag:
    supply <= supply_p25  AND  demand >= demand_median

ALL themes are included in output regardless of NaN weighted_score.
Themes with NaN demand are listed in "insufficient_data" and have
demand=None and underserved=False.
Thresholds (supply_p25, demand_median) are computed only over themes
with valid (non-NaN) demand so that no-review themes don't distort them.
"""
from __future__ import annotations

import pandas as pd

from src.analysis.base import weighted_quality, to_records


def run(df: pd.DataFrame) -> dict:
    """Return per-theme supply/demand gap map, including ALL themes.

    Returns:
        {
            "themes": [
                {theme, supply(int), demand(float|None), underserved(bool)},
                ...
            ],
            "insufficient_data": [theme, ...]   # themes with demand=None
        }
    """
    wq = weighted_quality(df, "theme")

    if len(wq) == 0:
        return {"themes": [], "insufficient_data": []}

    # Split into themes with and without valid demand
    has_demand = wq["weighted_score"].notna()
    wq_valid = wq[has_demand].copy()
    wq_nodata = wq[~has_demand].copy()

    # Compute thresholds only over themes with valid demand
    if len(wq_valid) > 0:
        supply_valid = wq_valid["count"].astype(float)
        demand_valid = wq_valid["weighted_score"]
        supply_p25 = supply_valid.quantile(0.25)
        demand_median = demand_valid.median()

        wq_valid["supply"] = wq_valid["count"]
        wq_valid["demand"] = wq_valid["weighted_score"]
        wq_valid["underserved"] = (
            (supply_valid <= supply_p25) & (demand_valid >= demand_median)
        )
        wq_valid["underserved"] = wq_valid["underserved"].astype(bool)
    else:
        wq_valid["supply"] = wq_valid["count"]
        wq_valid["demand"] = wq_valid["weighted_score"]
        wq_valid["underserved"] = False

    # Build records for themes with valid demand
    valid_records = to_records(wq_valid[["theme", "supply", "demand", "underserved"]])

    # Build records for no-data themes (demand=None, underserved=False)
    nodata_records = []
    insufficient_themes = []
    for _, row in wq_nodata.iterrows():
        nodata_records.append({
            "theme": row["theme"],
            "supply": int(row["count"]),
            "demand": None,
            "underserved": False,
        })
        insufficient_themes.append(row["theme"])

    all_records = valid_records + nodata_records

    return {
        "themes": all_records,
        "insufficient_data": insufficient_themes,
    }
