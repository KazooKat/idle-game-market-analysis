"""TDD tests for src/analysis/run_all.py — analysis orchestrator."""
import json
import pathlib

import pandas as pd
import pytest


@pytest.fixture
def master_df():
    """Minimal synthetic master DataFrame with all columns the 9 modules need."""
    return pd.DataFrame({
        # topics, performance, gaps: theme + review scores + ownership
        "theme": ["space", "space", "fantasy", "fantasy", "horror", "sci-fi"],
        # quality, topics: mechanics list
        "mechanics": [
            ["offline_progress", "prestige"],
            ["offline_progress"],
            ["idle_loop", "prestige"],
            ["idle_loop"],
            ["offline_progress"],
            ["prestige"],
        ],
        # most modules: review score
        "review_pct_positive": [85.0, 70.0, 90.0, 60.0, 75.0, 80.0],
        # base weighted_quality: ownership
        "owners_est": pd.array([10000, 5000, 20000, 3000, 8000, 12000], dtype="Int64"),
        "owners_confidence": ["high", "medium", "high", "low", "high", "medium"],
        # monetization: business model + price + free flag
        "business_model": ["premium", "free", "premium", "free", "premium", "free"],
        # art: art style
        "art_style": ["pixel", "2d", "pixel", "3d", "2d", "pixel"],
        "price": [9.99, 0.0, 14.99, 0.0, 4.99, 0.0],
        "is_free": [False, True, False, True, False, True],
        # updates: update cadence in days
        "update_cadence": [15.0, 60.0, None, 200.0, 25.0, 90.0],
        # trends: release date string
        "release_date": [
            "Jan 1, 2020",
            "Mar 5, 2021",
            "Jun 10, 2022",
            "Nov 3, 2018",
            "Aug 14, 2023",
            "Feb 20, 2019",
        ],
        # naming: game name
        "name": [
            "Idle Space Farm",
            "Clicker Hero",
            "Fantasy Quest",
            "Space Clicker",
            "Horror Idle",
            "Galaxy Builder",
        ],
    })


@pytest.fixture
def master_parquet(master_df, tmp_path):
    """Write the synthetic master DataFrame to a temp parquet and return its path."""
    parquet_path = tmp_path / "games.parquet"
    master_df.to_parquet(parquet_path, index=False)
    return str(parquet_path)


def test_run_all_writes_nine_json_files(master_parquet, tmp_path):
    """main() must write exactly one JSON file per module (9 total)."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    # Returned dict must have 9 entries
    assert len(result) == 9, f"Expected 9 entries, got {len(result)}: {list(result.keys())}"

    # 9 files must exist on disk
    written = list(pathlib.Path(out_dir).glob("*.json"))
    assert len(written) == 9, f"Expected 9 JSON files, got {len(written)}"


def test_run_all_files_are_valid_json(master_parquet, tmp_path):
    """Every JSON file written by main() must be valid JSON (json.load succeeds)."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    for name, path in result.items():
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict), f"{name}.json is not a JSON object"


def test_run_all_module_names_match_registry(master_parquet, tmp_path):
    """The returned dict keys must be the canonical module names in order."""
    from src.analysis.run_all import main, REGISTRY

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    expected_names = [name for name, _ in REGISTRY]
    assert list(result.keys()) == expected_names


def test_run_all_creates_out_dir_if_missing(master_parquet, tmp_path):
    """main() must create out_dir when it doesn't already exist."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "nested" / "analysis")
    assert not pathlib.Path(out_dir).exists()

    main(master_path=master_parquet, out_dir=out_dir)

    assert pathlib.Path(out_dir).exists()
