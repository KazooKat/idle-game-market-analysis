"""TDD tests for src/analysis/naming.py"""
import pandas as pd
import pytest

from src.analysis.naming import run


@pytest.fixture
def naming_df():
    return pd.DataFrame({
        "name": [
            "Idle Miner",       # idle_x
            "Idle Clicker",     # idle_x (contains "idle", checked first)
            "Cookie Clicker",   # x_clicker
            "Zenith Quest",     # creative
            "idle lands",       # idle_x (lowercase)
            "Planet Clicker 2", # x_clicker
            "Merchant Guild",   # creative
        ],
        "review_pct_positive": [80.0, 75.0, 70.0, 85.0, 90.0, 65.0, 80.0],
        "owners_est": pd.array([1000, 800, 600, 1200, 900, 700, 1100], dtype="Int64"),
        "owners_confidence": ["high", "high", "high", "high", "medium", "high", "medium"],
    })


def test_naming_has_by_pattern(naming_df):
    result = run(naming_df)
    assert "by_pattern" in result


def test_naming_idle_x_classification(naming_df):
    """'Idle Miner', 'Idle Clicker', 'idle lands' → idle_x, count=3."""
    result = run(naming_df)
    patterns = {r["pattern"]: r for r in result["by_pattern"]}
    assert "idle_x" in patterns
    assert patterns["idle_x"]["count"] == 3


def test_naming_x_clicker_classification(naming_df):
    """'Cookie Clicker', 'Planet Clicker 2' → x_clicker, count=2."""
    result = run(naming_df)
    patterns = {r["pattern"]: r for r in result["by_pattern"]}
    assert "x_clicker" in patterns
    assert patterns["x_clicker"]["count"] == 2


def test_naming_creative_classification(naming_df):
    """'Zenith Quest', 'Merchant Guild' → creative, count=2."""
    result = run(naming_df)
    patterns = {r["pattern"]: r for r in result["by_pattern"]}
    assert "creative" in patterns
    assert patterns["creative"]["count"] == 2


def test_naming_mean_positive(naming_df):
    """idle_x: scores 80, 75, 90 → mean=81.67"""
    result = run(naming_df)
    patterns = {r["pattern"]: r for r in result["by_pattern"]}
    assert patterns["idle_x"]["mean_positive"] == pytest.approx((80.0+75.0+90.0)/3, rel=1e-3)


def test_naming_record_structure(naming_df):
    result = run(naming_df)
    for r in result["by_pattern"]:
        assert "pattern" in r
        assert "count" in r
        assert "mean_positive" in r


def test_naming_no_nan_leaks(naming_df):
    import math
    result = run(naming_df)
    for r in result["by_pattern"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"
