"""TDD tests for src/analysis/gaps.py"""
import pandas as pd
import pytest

from src.analysis.gaps import run


@pytest.fixture
def gaps_df():
    """
    Themes designed so:
    - 'niche_hot':   supply=1 (low), demand=90 (high) → underserved
    - 'saturated':   supply=5 (high), demand=40 (low) → NOT underserved
    - 'mid1':        supply=3 (mid), demand=70 (high)
    - 'mid2':        supply=3 (mid), demand=60 (mid)

    After weighted_quality (all high conf, 1 owner each so weighted=mean):
      counts: niche_hot=1, saturated=5, mid1=3, mid2=3
      weighted_scores: niche_hot=90, saturated=40, mid1=70, mid2=60

    supply_p25 = 25th pct of [1, 3, 3, 5] = 1.5 (between 1 and 3)
      → only niche_hot (supply=1) is <= 1.5
    demand_median = median of [40, 60, 70, 90] = 65.0
      → niche_hot(90), mid1(70) are >= 65

    underserved: niche_hot ONLY (supply=1 <=1.5 AND demand=90 >=65)
    """
    rows = (
        [("niche_hot", 90.0, 1000, "high")] * 1 +
        [("saturated", 40.0, 1000, "high")] * 5 +
        [("mid1",      70.0, 1000, "high")] * 3 +
        [("mid2",      60.0, 1000, "high")] * 3
    )
    themes, scores, owners, confs = zip(*rows)
    return pd.DataFrame({
        "theme": list(themes),
        "review_pct_positive": list(scores),
        "owners_est": pd.array(list(owners), dtype="Int64"),
        "owners_confidence": list(confs),
    })


def test_gaps_has_themes_key(gaps_df):
    result = run(gaps_df)
    assert "themes" in result


def test_gaps_underserved_flagged(gaps_df):
    """niche_hot must be flagged underserved=True."""
    result = run(gaps_df)
    by_theme = {r["theme"]: r for r in result["themes"]}
    assert by_theme["niche_hot"]["underserved"] is True


def test_gaps_saturated_not_underserved(gaps_df):
    """saturated has high supply and low demand → underserved=False."""
    result = run(gaps_df)
    by_theme = {r["theme"]: r for r in result["themes"]}
    assert by_theme["saturated"]["underserved"] is False


def test_gaps_record_has_required_keys(gaps_df):
    result = run(gaps_df)
    for r in result["themes"]:
        assert "theme" in r
        assert "supply" in r
        assert "demand" in r
        assert "underserved" in r


def test_gaps_nan_demand_theme_included_with_none():
    """Themes with NaN weighted_score MUST still appear in output with demand=None."""
    df = pd.DataFrame({
        "theme": ["good", "nodata"],
        "review_pct_positive": [80.0, None],
        "owners_est": pd.array([1000, 500], dtype="Int64"),
        "owners_confidence": ["high", "low"],
    })
    result = run(df)
    theme_names = [r["theme"] for r in result["themes"]]
    assert "nodata" in theme_names, "no-data theme must appear in output"
    by_theme = {r["theme"]: r for r in result["themes"]}
    assert by_theme["nodata"]["demand"] is None
    assert by_theme["nodata"]["underserved"] is False


def test_gaps_insufficient_data_key():
    """Result must have 'insufficient_data' key listing themes with demand=None."""
    df = pd.DataFrame({
        "theme": ["good", "nodata"],
        "review_pct_positive": [80.0, None],
        "owners_est": pd.array([1000, 500], dtype="Int64"),
        "owners_confidence": ["high", "low"],
    })
    result = run(df)
    assert "insufficient_data" in result
    assert "nodata" in result["insufficient_data"]
    assert "good" not in result["insufficient_data"]


def test_gaps_all_themes_present(gaps_df):
    """All themes in the input must appear in the output."""
    result = run(gaps_df)
    theme_names = {r["theme"] for r in result["themes"]}
    assert {"niche_hot", "saturated", "mid1", "mid2"}.issubset(theme_names)


def test_gaps_underserved_is_bool(gaps_df):
    result = run(gaps_df)
    for r in result["themes"]:
        assert isinstance(r["underserved"], bool)
