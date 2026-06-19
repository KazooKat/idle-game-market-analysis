"""
TDD tests for src/site/build.py

Strategy:
- Write minimal valid JSONs to a temp analysis_dir.
- Call build_site(analysis_dir=<tmp>, out=<tmp_out>).
- Assert index.html exists and contains Plotly markers + supplementary note.
- Assert methodology.html exists and contains a caveat string.
- No writes to the real docs/ directory.
"""
from __future__ import annotations

import json
import pathlib

import pytest


# ---------------------------------------------------------------------------
# Fixtures: minimal valid analysis JSON data
# ---------------------------------------------------------------------------

TOPICS_JSON = {
    "themes": [
        {
            "theme": "space",
            "count": 3,
            "mean_positive": 80.0,
            "total_owners": 1000,
            "weighted_score": 80.0,
        }
    ],
    "mechanics": [{"mechanic": "idle", "count": 2, "mean_positive": 75.0}],
}

GAPS_JSON = {
    "themes": [
        {"theme": "space", "supply": 3, "demand": 80.0, "underserved": True}
    ]
}

SUPPLEMENTARY_JSON = {
    "itch": {
        "count": 5,
        "free_count": 4,
        "free_pct": 80.0,
        "top_tags": [["idle", 3]],
    },
    "kongregate": {
        "count": 2,
        "rated_count": 1,
        "mean_rating_pct": 85.0,
        "top_tags": [["clicker", 1]],
    },
    "reddit": {
        "available": False,
        "sentiment": {},
        "note": "unavailable - test fixture",
    },
    "caveats": ["x - test caveat string"],
}

PERFORMANCE_JSON = {
    "by_theme": [
        {
            "theme": "space",
            "count": 3,
            "mean_positive": 80.0,
            "total_owners": 1000,
            "weighted_score": 80.0,
        }
    ]
}

QUALITY_JSON = {
    "features": [
        {
            "feature": "offline_progress",
            "mean_with": 82.0,
            "mean_without": 75.0,
            "delta": 7.0,
            "n_with": 5,
            "n_without": 10,
        }
    ],
    "reddit_sentiment": {},
}

MONETIZATION_JSON = {
    "by_business_model": [
        {
            "business_model": "free_to_play",
            "count": 8,
            "mean_positive": 70.0,
            "total_owners": 5000,
            "weighted_score": 70.0,
        }
    ],
    "price_buckets": [
        {"bucket": "free", "count": 8, "mean_positive": 70.0, "total_owners": 5000}
    ],
}

ART_JSON = {
    "by_art_style": [
        {
            "art_style": "pixel",
            "count": 5,
            "mean_positive": 78.0,
            "total_owners": 2000,
            "weighted_score": 78.0,
        }
    ]
}

UPDATES_JSON = {
    "by_cadence": [
        {"cadence": "active", "count": 3, "mean_positive": 85.0, "total_owners": 3000},
        {"cadence": "occasional", "count": 2, "mean_positive": 75.0, "total_owners": 1000},
        {"cadence": "abandoned", "count": 1, "mean_positive": 60.0, "total_owners": 200},
    ]
}

TRENDS_JSON = {
    "by_year": [
        {"year": 2020, "releases": 5, "median_positive": 72.0},
        {"year": 2021, "releases": 8, "median_positive": 78.0},
    ],
    "rising_themes": ["space"],
}

DATASET_JSON = {
    "total_games": 123,
    "with_reviews": 100,
    "with_owner_est": 120,
    "themed": 80,
    "generated_utc": "2026-06-19",
}


@pytest.fixture()
def analysis_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write minimal valid JSONs to a temporary analysis directory."""
    d = tmp_path / "analysis"
    d.mkdir()
    files = {
        "topics.json": TOPICS_JSON,
        "gaps.json": GAPS_JSON,
        "supplementary.json": SUPPLEMENTARY_JSON,
        "performance.json": PERFORMANCE_JSON,
        "quality.json": QUALITY_JSON,
        "monetization.json": MONETIZATION_JSON,
        "art.json": ART_JSON,
        "updates.json": UPDATES_JSON,
        "trends.json": TRENDS_JSON,
        "dataset.json": DATASET_JSON,
    }
    for name, data in files.items():
        (d / name).write_text(json.dumps(data), encoding="utf-8")
    return d


@pytest.fixture()
def out_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Temporary output directory (does NOT touch docs/)."""
    return tmp_path / "out"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_site_creates_index(analysis_dir, out_dir):
    """build_site must produce docs/index.html in the output dir."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    assert (out_dir / "index.html").exists()


def test_index_contains_plotly(analysis_dir, out_dir):
    """index.html must reference Plotly (charts embedded)."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    # Plotly is loaded via CDN or embedded as 'plotly' lowercase too
    assert "plotly" in content.lower()


def test_index_contains_supplementary_note(analysis_dir, out_dir):
    """index.html must include the reddit note from supplementary.json."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    # The reddit note from the fixture must appear
    assert "unavailable - test fixture" in content


def test_build_site_creates_methodology(analysis_dir, out_dir):
    """build_site must produce docs/methodology.html."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    assert (out_dir / "methodology.html").exists()


def test_methodology_contains_caveat(analysis_dir, out_dir):
    """methodology.html must include at least one caveat string."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    content = (out_dir / "methodology.html").read_text(encoding="utf-8")
    # The caveat from the fixture must appear
    assert "x - test caveat string" in content


def test_build_site_no_crash_with_minimal_data(tmp_path):
    """build_site must not crash when only topics.json + gaps.json are present."""
    d = tmp_path / "analysis_min"
    d.mkdir()
    (d / "topics.json").write_text(json.dumps(TOPICS_JSON), encoding="utf-8")
    (d / "gaps.json").write_text(json.dumps(GAPS_JSON), encoding="utf-8")
    # No supplementary.json — must still succeed
    out = tmp_path / "out_min"

    from src.site.build import build_site

    build_site(analysis_dir=str(d), out=str(out))
    assert (out / "index.html").exists()
    assert (out / "methodology.html").exists()


def test_make_figures_guards_missing_keys():
    """make_figures must return a dict and not crash with an empty analysis dict."""
    from src.site.build import make_figures

    result = make_figures({})
    assert isinstance(result, dict)
    # No figures generated when analysis is empty — that's fine
    assert len(result) == 0


def test_make_figures_returns_html_divs(analysis_dir):
    """make_figures returns figure-name -> html-string for valid data."""
    import json as _json

    from src.site.build import make_figures

    analysis = {}
    for p in analysis_dir.glob("*.json"):
        analysis[p.stem] = _json.loads(p.read_text(encoding="utf-8"))

    result = make_figures(analysis)
    assert isinstance(result, dict)
    # At least some figures should be built with the full fixture set
    assert len(result) > 0
    for name, html in result.items():
        assert isinstance(html, str), f"figure {name!r} is not a string"
        assert len(html) > 0, f"figure {name!r} is empty"


def test_index_contains_dataset_total_games(analysis_dir, out_dir):
    """index.html must render the dataset total_games count (123 from fixture)."""
    from src.site.build import build_site

    build_site(analysis_dir=str(analysis_dir), out=str(out_dir))
    content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "123" in content, (
        "index.html does not contain dataset.total_games value '123'"
    )


def test_build_site_no_crash_without_dataset(tmp_path):
    """build_site must not crash when dataset.json is absent (older runs)."""
    d = tmp_path / "analysis_no_dataset"
    d.mkdir()
    (d / "topics.json").write_text(json.dumps(TOPICS_JSON), encoding="utf-8")
    (d / "gaps.json").write_text(json.dumps(GAPS_JSON), encoding="utf-8")
    out = tmp_path / "out_no_dataset"

    from src.site.build import build_site

    build_site(analysis_dir=str(d), out=str(out))
    assert (out / "index.html").exists()
    # Headline must be absent (no dataset key) — no crash
    content = (out / "index.html").read_text(encoding="utf-8")
    assert "games analyzed" not in content
