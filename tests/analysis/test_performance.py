"""TDD tests for src/analysis/performance.py"""
import pandas as pd
import pytest

from src.analysis.performance import run


@pytest.fixture
def perf_df():
    """Three themes with distinct weighted scores after accounting for owners."""
    return pd.DataFrame({
        "theme": ["action", "puzzle", "idle", "idle", "action"],
        "review_pct_positive": [90.0, 50.0, 80.0, 70.0, 85.0],
        "owners_est": pd.array([10000, 5000, 3000, 2000, 8000], dtype="Int64"),
        "owners_confidence": ["high", "high", "high", "medium", "high"],
    })


def test_performance_has_by_theme(perf_df):
    result = run(perf_df)
    assert "by_theme" in result


def test_performance_ranking_order(perf_df):
    """
    action: (90*10000 + 85*8000) / 18000 = (900000 + 680000) / 18000 = 87.78
    idle:   (80*3000 + 70*2000) / 5000 = (240000 + 140000) / 5000 = 76.0
    puzzle: 50.0
    Expected rank: action > idle > puzzle
    """
    result = run(perf_df)
    themes = [r["theme"] for r in result["by_theme"]]
    assert themes.index("action") < themes.index("idle") < themes.index("puzzle")


def test_performance_no_nan_in_ranking(perf_df):
    """weighted_score must not be None for any ranked row."""
    result = run(perf_df)
    for r in result["by_theme"]:
        assert r["weighted_score"] is not None


def test_performance_nan_score_group_dropped():
    """A theme with all-low-confidence and no reviews gets NaN weighted_score — must be dropped."""
    df = pd.DataFrame({
        "theme": ["good", "mystery"],
        "review_pct_positive": [80.0, None],
        "owners_est": pd.array([1000, 500], dtype="Int64"),
        "owners_confidence": ["high", "low"],
    })
    result = run(df)
    themes = [r["theme"] for r in result["by_theme"]]
    assert "good" in themes
    # mystery has NaN weighted_score (low conf + no review): either dropped or at bottom with None
    # Per spec: drop NaN groups from ranking
    assert "mystery" not in themes


def test_performance_no_nan_leaks():
    """No NaN should appear in the returned dict."""
    import math
    df = pd.DataFrame({
        "theme": ["a", "b"],
        "review_pct_positive": [75.0, 85.0],
        "owners_est": pd.array([100, 200], dtype="Int64"),
        "owners_confidence": ["high", "high"],
    })
    result = run(df)
    for r in result["by_theme"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v)
