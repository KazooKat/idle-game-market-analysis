"""TDD tests for src/analysis/trends.py"""
import pandas as pd
import pytest

from src.analysis.trends import run


@pytest.fixture
def trends_df():
    """
    max_year = 2024
    last 3 years = 2022, 2023, 2024
    older = 2019, 2020, 2021

    theme 'rising':
      older (2019-2021): 3 games, scores 50, 55, 60 → mean = 55
      recent (2022-2024): 3 games, scores 80, 85, 90 → mean = 85
      → recent > older → rising

    theme 'declining':
      older (2019-2021): 3 games, scores 80, 85, 90 → mean = 85
      recent (2022-2024): 3 games, scores 50, 55, 60 → mean = 55
      → recent < older → NOT rising

    year counts: 2019,2020,2021,2022,2023,2024 each have 2 releases (1 rising + 1 declining)
    """
    return pd.DataFrame({
        "release_date": [
            "2019-01-01", "2019-06-01",
            "2020-03-01", "2020-08-01",
            "2021-05-01", "2021-11-01",
            "2022-02-01", "2022-07-01",
            "2023-04-01", "2023-09-01",
            "2024-01-01", "2024-06-01",
        ],
        "theme": [
            "rising", "declining",
            "rising", "declining",
            "rising", "declining",
            "rising", "declining",
            "rising", "declining",
            "rising", "declining",
        ],
        "review_pct_positive": [
            50.0, 80.0,
            55.0, 85.0,
            60.0, 90.0,
            80.0, 50.0,
            85.0, 55.0,
            90.0, 60.0,
        ],
        "owners_est": pd.array([1000]*12, dtype="Int64"),
        "owners_confidence": ["high"]*12,
    })


def test_trends_has_by_year_and_rising_themes(trends_df):
    result = run(trends_df)
    assert "by_year" in result
    assert "rising_themes" in result


def test_trends_year_count_per_year(trends_df):
    """Each year should have 2 releases."""
    result = run(trends_df)
    by_year = {r["year"]: r for r in result["by_year"]}
    for yr in [2019, 2020, 2021, 2022, 2023, 2024]:
        assert by_year[yr]["releases"] == 2, f"Year {yr} count wrong"


def test_trends_rising_theme_detected(trends_df):
    """'rising' theme has higher recent mean than older → should be in rising_themes."""
    result = run(trends_df)
    assert "rising" in result["rising_themes"]


def test_trends_declining_theme_not_rising(trends_df):
    """'declining' theme has lower recent mean → must NOT be in rising_themes."""
    result = run(trends_df)
    assert "declining" not in result["rising_themes"]


def test_trends_year_parsing_invalid_date():
    """Rows with unparseable release_date should be dropped (not raise)."""
    df = pd.DataFrame({
        "release_date": ["2020-01-01", "not-a-date", None, "2021-03-15"],
        "theme": ["x", "x", "x", "x"],
        "review_pct_positive": [70.0, 80.0, 60.0, 75.0],
        "owners_est": pd.array([100, 100, 100, 100], dtype="Int64"),
        "owners_confidence": ["high", "high", "high", "high"],
    })
    result = run(df)
    years = [r["year"] for r in result["by_year"]]
    assert 2020 in years
    assert 2021 in years
    # Rows with unparseable dates are dropped
    assert len(result["by_year"]) == 2


def test_trends_no_nan_leaks(trends_df):
    import math
    result = run(trends_df)
    for r in result["by_year"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"
