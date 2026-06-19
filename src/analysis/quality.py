"""
src/analysis/quality.py
Feature correlation analysis: binary features vs review_pct_positive.

Binary features examined:
  - offline_progress : "offline_progress" in mechanics list
  - prestige         : "prestige" in mechanics list
  - is_free          : bool column

Per feature:
  mean_with    – mean review_pct_positive for games that have the feature
  mean_without – mean review_pct_positive for games that don't
  delta        – mean_with - mean_without  (positive = feature correlates with higher reviews)
  n_with       – count of games with feature
  n_without    – count of games without feature

Reddit sentiment is attached IF the local fixture is available (guarded).
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from src.analysis.base import to_records


def _mechanic_flag(df: pd.DataFrame, mechanic: str) -> pd.Series:
    """Boolean Series: True where *mechanic* appears in the mechanics list."""
    return df["mechanics"].apply(
        lambda lst: mechanic in lst if isinstance(lst, list) else False
    )


def _feature_stats(df: pd.DataFrame, mask: pd.Series, name: str) -> dict:
    """Compute delta stats for a binary boolean mask."""
    with_df = df.loc[mask, "review_pct_positive"].dropna()
    without_df = df.loc[~mask, "review_pct_positive"].dropna()

    mean_with = float(with_df.mean()) if len(with_df) > 0 else None
    mean_without = float(without_df.mean()) if len(without_df) > 0 else None

    if mean_with is not None and mean_without is not None:
        delta = mean_with - mean_without
    else:
        # One or both comparison groups are empty — delta is undefined, not zero.
        delta = None

    def _safe(v: Any) -> Any:
        if v is None:
            return None
        try:
            return None if math.isnan(v) else v
        except (TypeError, ValueError):
            return v

    return {
        "feature": name,
        "mean_with": _safe(mean_with),
        "mean_without": _safe(mean_without),
        "delta": _safe(delta),
        "n_with": int(mask.sum()),
        "n_without": int((~mask).sum()),
    }


VOCAB = {
    "loved": ["addictive", "satisfying", "offline", "progress", "relaxing"],
    "hated": ["paywall", "ads", "grind", "timer", "energy", "pay to win", "p2w"],
}


def _reddit_sentiment() -> dict:
    """Return Reddit sentiment counts from real cached reddit responses, else {}.

    cached_get(source="reddit", ...) writes JSON cache files to data/raw/reddit/*.cache.
    Each file is the raw Reddit API JSON response with shape:
      data["data"]["children"][i]["data"] → post dict.
    If the directory is absent or empty (e.g. no OAuth yet), returns {}.
    """
    try:
        import json
        import pathlib

        cache_dir = pathlib.Path("data/raw/reddit")
        cache_files = list(cache_dir.glob("*.cache")) if cache_dir.exists() else []
        if not cache_files:
            return {}

        posts: list[dict] = []
        for f in cache_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "data" in data:
                children = data["data"].get("children", [])
                posts.extend(child.get("data", {}) for child in children)

        if not posts:
            return {}

        from src.scrapers.reddit import extract_sentiment_terms

        return extract_sentiment_terms(posts, VOCAB)

    except Exception:
        return {}


def run(df: pd.DataFrame) -> dict:
    """Return feature correlation stats and optional Reddit sentiment.

    Returns:
        {
            "features": [
                {feature, mean_with, mean_without, delta, n_with, n_without},
                ...
            ],
            "reddit_sentiment": {category: count, ...}  # empty if fixture absent
        }
    """
    features = []

    # Mechanic-based features
    for mechanic in ("offline_progress", "prestige"):
        mask = _mechanic_flag(df, mechanic)
        features.append(_feature_stats(df, mask, mechanic))

    # Column-based features
    is_free_mask = df["is_free"].fillna(False).astype(bool)
    features.append(_feature_stats(df, is_free_mask, "is_free"))

    sentiment = _reddit_sentiment()

    return {"features": features, "reddit_sentiment": sentiment}
