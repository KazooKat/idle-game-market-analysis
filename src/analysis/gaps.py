"""
src/analysis/gaps.py
Supply vs demand gap map per theme.

supply  = count of games (from weighted_quality)
demand  = weighted_score (from weighted_quality)

underserved flag:
    supply <= supply_p25  AND  demand >= demand_median

Themes with NaN demand (weighted_score) are dropped before thresholds are computed.
"""
from __future__ import annotations

import pandas as pd

from src.analysis.base import weighted_quality, to_records


def run(df: pd.DataFrame) -> dict:
    """Return per-theme supply/demand gap map.

    Returns:
        {
            "themes": [
                {theme, supply(int), demand(float|None), underserved(bool)},
                ...
            ]
        }
    """
    wq = weighted_quality(df, "theme")

    # Drop NaN-demand themes — they have no signal for ranking/thresholding.
    wq = wq[wq["weighted_score"].notna()].copy()

    if len(wq) == 0:
        return {"themes": []}

    supply = wq["count"].astype(float)
    demand = wq["weighted_score"]

    supply_p25 = supply.quantile(0.25)
    demand_median = demand.median()

    wq["supply"] = wq["count"]
    wq["demand"] = wq["weighted_score"]
    wq["underserved"] = (supply <= supply_p25) & (demand >= demand_median)

    out = wq[["theme", "supply", "demand", "underserved"]].copy()
    # Ensure underserved is Python bool in records, not numpy bool_
    out["underserved"] = out["underserved"].astype(bool)

    return {"themes": to_records(out)}
