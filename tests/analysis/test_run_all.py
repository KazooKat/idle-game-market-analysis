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
    """main() must write dataset.json + one JSON file per module (10 total)."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    # Returned dict must have 10 entries: dataset + 9 modules
    assert len(result) == 10, f"Expected 10 entries, got {len(result)}: {list(result.keys())}"

    # 10 files must exist on disk
    written = list(pathlib.Path(out_dir).glob("*.json"))
    assert len(written) == 10, f"Expected 10 JSON files, got {len(written)}"


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
    """The returned dict keys must be dataset first, then canonical module names."""
    from src.analysis.run_all import main, REGISTRY

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    registry_names = [name for name, _ in REGISTRY]
    expected_names = ["dataset"] + registry_names
    assert list(result.keys()) == expected_names


def test_run_all_creates_out_dir_if_missing(master_parquet, tmp_path):
    """main() must create out_dir when it doesn't already exist."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "nested" / "analysis")
    assert not pathlib.Path(out_dir).exists()

    main(master_path=master_parquet, out_dir=out_dir)

    assert pathlib.Path(out_dir).exists()


def test_run_all_error_fallback_writes_error_json_and_continues(master_parquet, tmp_path, monkeypatch):
    """If one module raises, its JSON contains {error:...}, others still written, main() doesn't raise."""
    import src.analysis.run_all as _run_all

    # Patch the first module in the registry to raise
    original_registry = list(_run_all.REGISTRY)
    failing_name = original_registry[0][0]

    def _boom(df):
        raise ValueError("simulated module failure")

    patched = [(_run_all.REGISTRY[0][0], _boom)] + original_registry[1:]
    monkeypatch.setattr(_run_all, "REGISTRY", patched)

    out_dir = str(tmp_path / "analysis_err")

    # Must not raise
    result = _run_all.main(master_path=master_parquet, out_dir=out_dir)

    # The failing module's JSON must contain {"error": ...}
    failing_path = pathlib.Path(result[failing_name])
    assert failing_path.exists(), f"Expected {failing_path} to be written"
    with open(failing_path, encoding="utf-8") as fh:
        failing_data = json.load(fh)
    assert "error" in failing_data, (
        f"Expected 'error' key in {failing_name}.json, got: {failing_data}"
    )
    assert "simulated module failure" in failing_data["error"]

    # All other modules must still have been written (no error key for them)
    for name, _ in original_registry[1:]:
        p = pathlib.Path(result[name])
        assert p.exists(), f"Expected {p} to exist even after module '{failing_name}' failed"
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        assert "error" not in data, (
            f"{name}.json has unexpected 'error' key: {data}"
        )


def test_run_all_writes_dataset_json(master_parquet, master_df, tmp_path):
    """main() must write dataset.json with total_games == len(master_df) and all required keys."""
    from src.analysis.run_all import main

    out_dir = str(tmp_path / "analysis")
    result = main(master_path=master_parquet, out_dir=out_dir)

    # dataset key must be present in the returned dict
    assert "dataset" in result, "main() did not return a 'dataset' key"

    dataset_path = pathlib.Path(result["dataset"])
    assert dataset_path.exists(), f"dataset.json was not written to {dataset_path}"

    with open(dataset_path, encoding="utf-8") as fh:
        data = json.load(fh)

    # total_games must equal the actual row count of the synthetic DataFrame
    assert data["total_games"] == len(master_df), (
        f"Expected total_games={len(master_df)}, got {data['total_games']}"
    )

    # All required keys must be present
    for key in ("total_games", "with_reviews", "with_owner_est", "themed", "generated_utc"):
        assert key in data, f"dataset.json missing key '{key}'"

    # Values must be JSON-safe plain types (int or str), not numpy types
    assert isinstance(data["total_games"], int)
    assert isinstance(data["with_reviews"], int)
    assert isinstance(data["with_owner_est"], int)
    assert isinstance(data["themed"], int)
    assert isinstance(data["generated_utc"], str)
