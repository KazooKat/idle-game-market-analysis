"""
src/analysis/trends.py
Release-year trend analysis.

by_year:
  Parse 4-digit year from release_date via regex.
  Drop rows with no parseable year.
  Per year: releases (count) + median review_pct_positive.

rising_themes:
  For each theme, compare mean review_pct_positive for games released in
  the last 3 years (relative to max year in data) vs older games.
  A theme is "rising" if recent_mean > older_mean AND both sides have >= 1 game.
"""
from __future__ import annotations

import math
import re

import pandas as pd

from src.analysis.base import to_records

_YEAR_RE = re.compile(r"(\d{4})")


def _parse_year(date_str) -> int | None:
    """Extract first 4-digit year from a string. Returns None if unparseable."""
    if not isinstance(date_str, str):
        return None
    m = _YEAR_RE.search(date_str)
    return int(m.group(1)) if m else None


def run(df: pd.DataFrame) -> dict:
    """Return release-year trends and rising themes.

    Returns:
        {
            "by_year": [ {year, releases, median_positive} ... ],
            "rising_themes": [ theme, ... ]
        }
    """
    work = df.copy()
    work["_year"] = work["release_date"].apply(_parse_year)

    # Drop rows with no parseable year.
    work = work[work["_year"].notna()].copy()
    work["_year"] = work["_year"].astype(int)

    # --- by_year ---
    by_year_rows = []
    if len(work) > 0:
        for year, grp in work.groupby("_year", sort=True):
            releases = len(grp)
            scores = grp["review_pct_positive"].dropna()
            median_positive = float(scores.median()) if len(scores) > 0 else None
            if median_positive is not None and math.isnan(median_positive):
                median_positive = None
            by_year_rows.append({
                "year": int(year),
                "releases": releases,
                "median_positive": median_positive,
            })

    # --- rising themes ---
    rising_themes: list[str] = []
    if len(work) > 0:
        max_year = int(work["_year"].max())
        cutoff = max_year - 2  # recent window = years cutoff..max_year inclusive (3 years)

        themes = work["theme"].dropna().unique()
        for theme in themes:
            sub = work[work["theme"] == theme]
            recent = sub[sub["_year"] >= cutoff]["review_pct_positive"].dropna()
            older = sub[sub["_year"] < cutoff]["review_pct_positive"].dropna()
            if len(recent) >= 1 and len(older) >= 1:
                if float(recent.mean()) > float(older.mean()):
                    rising_themes.append(str(theme))

    return {"by_year": by_year_rows, "rising_themes": rising_themes}
