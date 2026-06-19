"""TDD tests for src/analysis/topics.py"""
import pandas as pd
import pytest

from src.analysis.topics import run


@pytest.fixture
def small_df():
    return pd.DataFrame({
        "theme": ["action", "action", "puzzle", "action"],
        "mechanics": [
            ["offline_progress", "prestige"],
            ["offline_progress"],
            ["idle_loop"],
            ["prestige"],
        ],
        "review_pct_positive": [80.0, 60.0, 90.0, 70.0],
        "owners_est": pd.array([1000, 500, 2000, 300], dtype="Int64"),
        "owners_confidence": ["high", "medium", "high", "low"],
    })


def test_topics_returns_themes_and_mechanics(small_df):
    result = run(small_df)
    assert "themes" in result
    assert "mechanics" in result


def test_topics_most_common_theme(small_df):
    """'action' appears 3 times; 'puzzle' appears once — action should be first."""
    result = run(small_df)
    themes = result["themes"]
    assert themes[0]["theme"] == "action"


def test_topics_theme_count(small_df):
    result = run(small_df)
    themes_by_name = {r["theme"]: r for r in result["themes"]}
    assert themes_by_name["action"]["count"] == 3
    assert themes_by_name["puzzle"]["count"] == 1


def test_topics_mechanic_count(small_df):
    """offline_progress appears in 2 rows, prestige in 2 rows, idle_loop in 1."""
    result = run(small_df)
    mechanics = {r["mechanic"]: r for r in result["mechanics"]}
    assert mechanics["offline_progress"]["count"] == 2
    assert mechanics["prestige"]["count"] == 2
    assert mechanics["idle_loop"]["count"] == 1


def test_topics_mechanic_mean_positive(small_df):
    """offline_progress appears in rows 0 (80) and 1 (60) → mean = 70.0"""
    result = run(small_df)
    mechanics = {r["mechanic"]: r for r in result["mechanics"]}
    assert mechanics["offline_progress"]["mean_positive"] == pytest.approx(70.0)


def test_topics_no_nan_in_output(small_df):
    """All values in the returned dict must be JSON-safe (no NaN)."""
    import math
    result = run(small_df)
    for record in result["themes"] + result["mechanics"]:
        for v in record.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN found in record: {record}"
