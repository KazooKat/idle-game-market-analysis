"""TDD tests for src/analysis/art.py"""
import pandas as pd
import pytest

from src.analysis.art import run


@pytest.fixture
def art_df():
    return pd.DataFrame({
        "art_style": ["pixel", "pixel", "vector", "3d", "pixel"],
        "review_pct_positive": [80.0, 75.0, 90.0, 60.0, 85.0],
        "owners_est": pd.array([1000, 800, 2000, 500, 1200], dtype="Int64"),
        "owners_confidence": ["high", "high", "high", "medium", "high"],
    })


def test_art_has_by_art_style(art_df):
    result = run(art_df)
    assert "by_art_style" in result


def test_art_style_row_count(art_df):
    """3 distinct art styles: pixel, vector, 3d."""
    result = run(art_df)
    assert len(result["by_art_style"]) == 3


def test_art_pixel_count(art_df):
    """pixel appears 3 times."""
    result = run(art_df)
    styles = {r["art_style"]: r for r in result["by_art_style"]}
    assert styles["pixel"]["count"] == 3


def test_art_sorted_by_count_desc(art_df):
    """Rows sorted by count descending — pixel(3) > vector(1) == 3d(1)."""
    result = run(art_df)
    counts = [r["count"] for r in result["by_art_style"]]
    assert counts[0] == 3  # pixel is first


def test_art_no_nan_leaks(art_df):
    import math
    result = run(art_df)
    for r in result["by_art_style"]:
        for v in r.values():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN in {r}"
