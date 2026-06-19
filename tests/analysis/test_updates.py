"""TDD tests for src/analysis/updates.py"""
import pandas as pd
import pytest

from src.analysis.updates import run


@pytest.fixture
def updates_df():
    return pd.DataFrame({
        "update_cadence": [20.0, 90.0, 200.0, None, 5.0, 30.0, 150.0],
        "review_pct_positive": [80.0, 70.0, 50.0, 60.0, 90.0, 85.0, 45.0],
        "owners_est": pd.array([1000, 800, 500, 300, 1200, 900, 400], dtype="Int64"),
        "owners_confidence": ["high", "high", "medium", "low", "high", "medium", "high"],
    })


def test_updates_has_by_cadence(updates_df):
    result = run(updates_df)
    assert "by_cadence" in result


def test_updates_three_buckets(updates_df):
    """All three buckets must be present: active, occasional, abandoned."""
    result = run(updates_df)
    buckets = {r["cadence"]: r for r in result["by_cadence"]}
    assert "active" in buckets
    assert "occasional" in buckets
    assert "abandoned" in buckets


def test_updates_active_bucket_count(updates_df):
    """active (<=30): cadence 20, 5, 30 → count=3"""
    result = run(updates_df)
    buckets = {r["cadence"]: r for r in result["by_cadence"]}
    assert buckets["active"]["count"] == 3


def test_updates_occasional_bucket_count(updates_df):
    """occasional (>30 and <=120): cadence 90 → count=1"""
    result = run(updates_df)
    buckets = {r["cadence"]: r for r in result["by_cadence"]}
    assert buckets["occasional"]["count"] == 1


def test_updates_abandoned_bucket_count(updates_df):
    """abandoned (>120 or None): cadence 200, None, 150 → count=3"""
    result = run(updates_df)
    buckets = {r["cadence"]: r for r in result["by_cadence"]}
    assert buckets["abandoned"]["count"] == 3


def test_updates_record_has_required_keys(updates_df):
    result = run(updates_df)
    for r in result["by_cadence"]:
        assert "cadence" in r
        assert "count" in r
        assert "mean_positive" in r
        assert "total_owners" in r


def test_updates_no_nan_leaks(updates_df):
    import math
    result = run(updates_df)
    for r in result["by_cadence"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"
