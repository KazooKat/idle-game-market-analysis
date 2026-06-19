"""
TDD tests for src/analysis/base.py

Synthetic 4-row DataFrame with two themes:
  theme "action" has 2 rows, theme "puzzle" has 2 rows.
  One row has owners_confidence="low" (excluded from total_owners / weighted_score).
  One row has review_pct_positive=NaN (web game without rating).

Row layout:
  idx | theme  | review_pct_positive | owners_est | owners_confidence
   0  | action | 80.0                | 1000       | high
   1  | action | 60.0                | 500        | medium
   2  | puzzle | 90.0                | 2000       | high
   3  | puzzle | NaN                 | 300        | low     <- excluded from owners sum
"""
import math
import pandas as pd
import pytest

from src.analysis.base import load_master, weighted_quality, to_records


# ---------------------------------------------------------------------------
# Synthetic fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def small_df():
    return pd.DataFrame({
        "theme": ["action", "action", "puzzle", "puzzle"],
        "review_pct_positive": [80.0, 60.0, 90.0, None],
        "owners_est": pd.array([1000, 500, 2000, 300], dtype="Int64"),
        "owners_confidence": ["high", "medium", "high", "low"],
    })


# ---------------------------------------------------------------------------
# weighted_quality tests
# ---------------------------------------------------------------------------

def test_weighted_quality_row_count(small_df):
    result = weighted_quality(small_df, "theme")
    assert len(result) == 2, "Expected one row per theme"


def test_weighted_quality_columns(small_df):
    result = weighted_quality(small_df, "theme")
    for col in ("theme", "count", "mean_positive", "total_owners", "weighted_score"):
        assert col in result.columns, f"Missing column: {col}"


def test_weighted_quality_count(small_df):
    result = weighted_quality(small_df, "theme").set_index("theme")
    assert result.loc["action", "count"] == 2
    assert result.loc["puzzle", "count"] == 2


def test_weighted_quality_mean_positive(small_df):
    """mean_positive skips NaN — puzzle row 3 has NaN so mean is just 90.0"""
    result = weighted_quality(small_df, "theme").set_index("theme")
    assert result.loc["action", "mean_positive"] == pytest.approx(70.0)   # (80+60)/2
    assert result.loc["puzzle", "mean_positive"] == pytest.approx(90.0)   # NaN skipped


def test_weighted_quality_total_owners_excludes_low(small_df):
    """
    total_owners sums owners_est only where owners_confidence is high or medium.
    puzzle row 3 has confidence=low, so only row 2 (2000) counts.
    """
    result = weighted_quality(small_df, "theme").set_index("theme")
    assert result.loc["action", "total_owners"] == 1500   # 1000 + 500
    assert result.loc["puzzle", "total_owners"] == 2000   # 2000 only (row 3 excluded)


def test_weighted_quality_weighted_score(small_df):
    """
    weighted_score = owners-weighted mean of review_pct_positive using high+med confidence.

    action:
      weights = [1000, 500], scores = [80, 60]
      weighted_score = (80*1000 + 60*500) / (1000+500) = (80000+30000)/1500 = 110000/1500
                     = 73.333...

    puzzle:
      Only row 2 qualifies (high conf). Row 3 has low conf AND NaN score.
      weights = [2000], scores = [90]
      weighted_score = 90*2000/2000 = 90.0
    """
    result = weighted_quality(small_df, "theme").set_index("theme")
    assert result.loc["action", "weighted_score"] == pytest.approx(110000 / 1500)
    assert result.loc["puzzle", "weighted_score"] == pytest.approx(90.0)


def test_weighted_quality_weighted_score_differs_from_mean(small_df):
    """Confirm weighted_score != mean_positive for 'action' (checks it's actually weighted)."""
    result = weighted_quality(small_df, "theme").set_index("theme")
    assert result.loc["action", "weighted_score"] != result.loc["action", "mean_positive"]


def test_weighted_quality_sorted_by_count_desc(small_df):
    """Result is sorted by count descending (stable)."""
    # Both themes have count=2, so order is stable; add an extra row to make it unambiguous
    extra = pd.DataFrame({
        "theme": ["rpg"],
        "review_pct_positive": [75.0],
        "owners_est": pd.array([100], dtype="Int64"),
        "owners_confidence": ["medium"],
    })
    df = pd.concat([small_df, extra], ignore_index=True)
    result = weighted_quality(df, "theme")
    counts = list(result["count"])
    assert counts == sorted(counts, reverse=True), "Result not sorted by count descending"


def test_weighted_quality_drops_null_theme(small_df):
    """Rows where the group-by column is null should be dropped before grouping."""
    df = small_df.copy()
    df.loc[0, "theme"] = None
    result = weighted_quality(df, "theme")
    # action now has 1 row (idx 1), puzzle has 2 rows — null row is gone
    result_idx = result.set_index("theme")
    assert result_idx.loc["action", "count"] == 1


def test_weighted_quality_zero_weight_fallback():
    """
    If ALL qualifying owners in a group are 0 (weight sum = 0), fall back to mean_positive.
    """
    df = pd.DataFrame({
        "theme": ["x", "x"],
        "review_pct_positive": [50.0, 70.0],
        "owners_est": pd.array([0, 0], dtype="Int64"),
        "owners_confidence": ["high", "high"],
    })
    result = weighted_quality(df, "theme").set_index("theme")
    # weight sum = 0 → fallback to mean = (50+70)/2 = 60
    assert result.loc["x", "weighted_score"] == pytest.approx(60.0)


def test_weighted_quality_all_low_confidence_fallback():
    """
    If a group has no high/medium confidence rows at all, total_owners=0 and
    weighted_score falls back to mean_positive.
    """
    df = pd.DataFrame({
        "theme": ["z", "z"],
        "review_pct_positive": [40.0, 80.0],
        "owners_est": pd.array([500, 500], dtype="Int64"),
        "owners_confidence": ["low", "low"],
    })
    result = weighted_quality(df, "theme").set_index("theme")
    assert result.loc["z", "total_owners"] == 0
    assert result.loc["z", "weighted_score"] == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# to_records tests
# ---------------------------------------------------------------------------

def test_to_records_nan_becomes_none():
    df = pd.DataFrame({"a": [1.0, float("nan")], "b": ["x", "y"]})
    records = to_records(df)
    assert records[1]["a"] is None


def test_to_records_returns_list_of_dicts():
    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    records = to_records(df)
    assert isinstance(records, list)
    assert all(isinstance(r, dict) for r in records)


def test_to_records_json_safe():
    """Verify result can be json.dumps'd without error."""
    import json
    df = pd.DataFrame({"val": [1.0, float("nan"), None], "name": ["a", "b", "c"]})
    records = to_records(df)
    # Should not raise
    json.dumps(records)


# ---------------------------------------------------------------------------
# Bug fix: weighted_quality on an all-null grouping column (Bug 1)
#
# Red-before-green evidence (preserved as a comment):
#   BEFORE the fix, calling weighted_quality(df, "theme") on a DataFrame where
#   every "theme" value is None would produce an empty groupby result that had
#   NO columns at all.  Accessing result["count"] then raised KeyError: 'count',
#   which in turn crashed art.py (art_style all-null on the real 3479-game
#   dataset) with KeyError: 'count' propagated through to_records().
#
#   The test below was confirmed to raise KeyError BEFORE the guard was added
#   to weighted_quality.  After the guard it must pass.
# ---------------------------------------------------------------------------

@pytest.fixture
def all_null_theme_df():
    """DataFrame whose entire 'theme' column is null — simulates art_style=all-null."""
    return pd.DataFrame({
        "theme": [None, None, None],
        "review_pct_positive": [80.0, 60.0, 90.0],
        "owners_est": pd.array([1000, 500, 2000], dtype="Int64"),
        "owners_confidence": ["high", "medium", "high"],
    })


def test_weighted_quality_all_null_by_returns_empty_df_with_correct_columns(all_null_theme_df):
    """weighted_quality on all-null group column returns empty DataFrame with correct schema."""
    result = weighted_quality(all_null_theme_df, "theme")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0, "Expected zero rows when all group keys are null"
    expected_cols = {"theme", "count", "mean_positive", "total_owners", "weighted_score"}
    assert expected_cols.issubset(set(result.columns)), (
        f"Missing columns: {expected_cols - set(result.columns)}"
    )


def test_to_records_on_all_null_by_returns_empty_list(all_null_theme_df):
    """to_records(weighted_quality(...)) on all-null group column yields [] without KeyError."""
    result = weighted_quality(all_null_theme_df, "theme")
    records = to_records(result)
    assert records == [], f"Expected [], got {records}"


# ---------------------------------------------------------------------------
# load_master smoke test (no real parquet required — just checks it raises
# FileNotFoundError on missing path, not some unexpected error)
# ---------------------------------------------------------------------------

def test_load_master_missing_file_raises():
    with pytest.raises((FileNotFoundError, Exception)):
        load_master("nonexistent_path_xyz.parquet")
