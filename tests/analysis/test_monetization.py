"""TDD tests for src/analysis/monetization.py"""
import pandas as pd
import pytest

from src.analysis.monetization import run


@pytest.fixture
def mono_df():
    return pd.DataFrame({
        "business_model": ["free_to_play", "paid", "paid", "free_to_play", "paid"],
        "price": [0.0, 2.99, 14.99, 0.0, 4.99],
        "is_free": pd.array([True, False, False, True, False], dtype="boolean"),
        "review_pct_positive": [80.0, 70.0, 60.0, 90.0, 75.0],
        "owners_est": pd.array([5000, 1000, 500, 3000, 800], dtype="Int64"),
        "owners_confidence": ["high", "high", "medium", "medium", "high"],
    })


def test_monetization_has_keys(mono_df):
    result = run(mono_df)
    assert "by_business_model" in result
    assert "price_buckets" in result


def test_monetization_business_model_rows(mono_df):
    result = run(mono_df)
    models = {r["business_model"]: r for r in result["by_business_model"]}
    assert "free_to_play" in models
    assert "paid" in models


def test_monetization_price_bucket_counts(mono_df):
    """
    Buckets:
      0 (free): price=0.0, is_free=True → rows 0,3 → count=2
      0.01-1:   no games
      1-3:      price=2.99 → count=1
      3-5:      price=4.99 → count=1
      5-10:     none
      10-20:    price=14.99 → count=1
      20+:      none
    """
    result = run(mono_df)
    buckets = {r["bucket"]: r for r in result["price_buckets"]}
    assert buckets["free"]["count"] == 2
    assert buckets["1-3"]["count"] == 1
    assert buckets["3-5"]["count"] == 1
    assert buckets["10-20"]["count"] == 1


def test_monetization_price_buckets_ordered(mono_df):
    """Price buckets must be returned in logical order (free first, 20+ last)."""
    result = run(mono_df)
    bucket_names = [r["bucket"] for r in result["price_buckets"]]
    expected_order = ["free", "0.01-1", "1-3", "3-5", "5-10", "10-20", "20+"]
    assert bucket_names == expected_order


def test_monetization_no_nan_leaks(mono_df):
    import math
    result = run(mono_df)
    all_records = result["by_business_model"] + result["price_buckets"]
    for r in all_records:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"
