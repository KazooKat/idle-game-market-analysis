"""TDD tests for src/analysis/quality.py"""
import pandas as pd
import pytest

from src.analysis.quality import run


@pytest.fixture
def quality_df():
    """
    4 games:
      - rows 0,1 have offline_progress in mechanics → mean review 80
      - rows 2,3 do NOT have offline_progress → mean review 60
      → delta for offline_progress should be positive (80-60=+20)

      - rows 0,2 have prestige → mean review 70
      - rows 1,3 do NOT → mean review 70
      → delta for prestige should be 0

      - rows 0,1 are free (is_free=True) → mean review 80
      - rows 2,3 are not → mean review 60
      → delta for is_free should be positive
    """
    return pd.DataFrame({
        "mechanics": [
            ["offline_progress", "prestige"],
            ["offline_progress"],
            ["prestige"],
            [],
        ],
        "is_free": pd.array([True, True, False, False], dtype="boolean"),
        "review_pct_positive": [80.0, 80.0, 60.0, 60.0],
        "owners_est": pd.array([1000, 1000, 1000, 1000], dtype="Int64"),
        "owners_confidence": ["high", "high", "high", "high"],
    })


def test_quality_has_features_key(quality_df):
    result = run(quality_df)
    assert "features" in result


def test_quality_has_reddit_sentiment_key(quality_df):
    result = run(quality_df)
    assert "reddit_sentiment" in result


def test_quality_offline_progress_positive_delta(quality_df):
    """Games WITH offline_progress have higher review % → delta > 0."""
    result = run(quality_df)
    features = {r["feature"]: r for r in result["features"]}
    assert "offline_progress" in features
    assert features["offline_progress"]["delta"] > 0


def test_quality_is_free_positive_delta(quality_df):
    """Free games have higher review % → delta > 0."""
    result = run(quality_df)
    features = {r["feature"]: r for r in result["features"]}
    assert "is_free" in features
    assert features["is_free"]["delta"] > 0


def test_quality_feature_record_structure(quality_df):
    result = run(quality_df)
    for r in result["features"]:
        assert "feature" in r
        assert "mean_with" in r
        assert "mean_without" in r
        assert "delta" in r
        assert "n_with" in r
        assert "n_without" in r


def test_quality_offline_progress_counts(quality_df):
    """offline_progress: 2 games with, 2 without."""
    result = run(quality_df)
    features = {r["feature"]: r for r in result["features"]}
    assert features["offline_progress"]["n_with"] == 2
    assert features["offline_progress"]["n_without"] == 2


def test_quality_reddit_sentiment_is_dict(quality_df):
    result = run(quality_df)
    assert isinstance(result["reddit_sentiment"], dict)


def test_quality_no_nan_in_features(quality_df):
    """No NaN values in feature records."""
    import math
    result = run(quality_df)
    for r in result["features"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"


def test_quality_empty_comparison_group_delta_is_none():
    """When ALL games have offline_progress (n_without==0), delta must be None, not 0.0.

    Red-before-green: this test catches the bug where delta was set to 0.0
    instead of None when one comparison group is empty.
    """
    df = pd.DataFrame({
        "mechanics": [
            ["offline_progress"],
            ["offline_progress", "prestige"],
            ["offline_progress"],
        ],
        "is_free": pd.array([True, False, True], dtype="boolean"),
        "review_pct_positive": [75.0, 80.0, 85.0],
        "owners_est": pd.array([500, 1000, 750], dtype="Int64"),
        "owners_confidence": ["high", "high", "medium"],
    })
    result = run(df)
    features = {r["feature"]: r for r in result["features"]}
    op = features["offline_progress"]
    # All 3 games have offline_progress → n_without==0 → comparison undefined
    assert op["n_without"] == 0
    assert op["mean_without"] is None
    # delta must be None (undefined), NOT 0.0
    assert op["delta"] is None, f"Expected delta=None, got delta={op['delta']!r}"
