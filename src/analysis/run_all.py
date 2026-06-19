"""
src/analysis/run_all.py
Analysis orchestrator — loads master once, runs every module, writes JSON.

Public API:
    main(master_path, out_dir) -> dict[str, str]
        Loads the master table via base.load_master, runs each registered
        module's run(df), writes out_dir/<name>.json, returns {name: path}.

REGISTRY:
    Explicit ordered list of (name, run_fn) pairs.  All 9 analysis modules
    appear here in canonical order (Phase 5 site builder consumes in this order).
"""
from __future__ import annotations

import json
import pathlib
import sys
import warnings
from datetime import datetime, timezone

import src.analysis.topics as _topics
import src.analysis.performance as _performance
import src.analysis.gaps as _gaps
import src.analysis.quality as _quality
import src.analysis.monetization as _monetization
import src.analysis.art as _art
import src.analysis.updates as _updates
import src.analysis.trends as _trends
import src.analysis.naming as _naming

from src.analysis.base import load_master

# ---------------------------------------------------------------------------
# Registry — ordered, explicit.  Phase 5 relies on this order for navigation.
# ---------------------------------------------------------------------------

REGISTRY: list[tuple[str, object]] = [
    ("topics",       _topics.run),
    ("performance",  _performance.run),
    ("gaps",         _gaps.run),
    ("quality",      _quality.run),
    ("monetization", _monetization.run),
    ("art",          _art.run),
    ("updates",      _updates.run),
    ("trends",       _trends.run),
    ("naming",       _naming.run),
]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(
    master_path: str = "data/processed/games.parquet",
    out_dir: str = "data/analysis",
) -> dict[str, str]:
    """Load master, run each module, write <out_dir>/<name>.json.

    Args:
        master_path: Path to the master games parquet file.
        out_dir:     Directory for JSON output (created if absent).

    Returns:
        dict mapping module name → absolute output file path (as str).

    Per-module errors are caught, a ``{"error": "..."}`` JSON is written,
    and a warning is printed — the orchestration continues to completion.
    """
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    df = load_master(master_path)

    # -- Dataset summary (written unconditionally, before per-module loop) --
    dataset_summary = {
        "total_games": int(len(df)),
        "with_reviews": int(df["review_pct_positive"].notna().sum()),
        "with_owner_est": int(df["owners_est"].notna().sum()),
        "themed": int(df["theme"].notna().sum()),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    dataset_file = out_path / "dataset.json"
    with open(dataset_file, "w", encoding="utf-8") as fh:
        json.dump(dataset_summary, fh, ensure_ascii=False, indent=2)

    results: dict[str, str] = {"dataset": str(dataset_file)}

    for name, run_fn in REGISTRY:
        out_file = out_path / f"{name}.json"
        try:
            data = run_fn(df)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"[run_all] module '{name}' raised {type(exc).__name__}: {exc}",
                RuntimeWarning,
                stacklevel=1,
            )
            data = {"error": str(exc)}

        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)

        results[name] = str(out_file)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = main()
    print(f"[run_all] wrote {len(result)} analysis files to data/analysis")
