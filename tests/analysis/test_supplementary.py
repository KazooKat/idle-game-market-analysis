"""TDD tests for src/analysis/supplementary.py

Strategy:
- Monkeypatch itch.fetch_browse and kongregate.fetch_listing to return
  the saved real fixtures (offline, no network calls).
- Reddit: data/raw/reddit/ is empty in the test environment -> available=False.
- Verify the gather() shape matches the interface spec.
"""
from pathlib import Path

import pytest

ITCH_FIXTURE = Path("tests/scrapers/fixtures/itch_browse.html")
KONG_FIXTURE = Path("tests/scrapers/fixtures/kong_idle.html")


@pytest.fixture()
def patched_gather(monkeypatch):
    """Return gather() result with scrapers monkeypatched to use local fixtures."""
    itch_html = ITCH_FIXTURE.read_text(encoding="utf-8")
    kong_html = KONG_FIXTURE.read_text(encoding="utf-8")

    import src.analysis.supplementary as sup

    monkeypatch.setattr(sup._itch, "fetch_browse", lambda refresh=False: itch_html)
    monkeypatch.setattr(sup._kong, "fetch_listing", lambda refresh=False: kong_html)

    return sup.gather(refresh=False)


# ---------------------------------------------------------------------------
# Top-level shape
# ---------------------------------------------------------------------------

def test_gather_returns_dict(patched_gather):
    assert isinstance(patched_gather, dict)


def test_gather_top_level_keys(patched_gather):
    result = patched_gather
    for key in ("itch", "kongregate", "reddit", "caveats"):
        assert key in result, f"Missing top-level key: {key!r}"


# ---------------------------------------------------------------------------
# itch section
# ---------------------------------------------------------------------------

def test_itch_count_gte_2(patched_gather):
    assert patched_gather["itch"]["count"] >= 2


def test_itch_free_pct_is_numeric(patched_gather):
    fp = patched_gather["itch"]["free_pct"]
    assert isinstance(fp, float), f"free_pct should be float, got {type(fp)}"


def test_itch_free_count_lte_count(patched_gather):
    itch = patched_gather["itch"]
    assert itch["free_count"] <= itch["count"]


def test_itch_top_tags_is_list(patched_gather):
    tags = patched_gather["itch"]["top_tags"]
    assert isinstance(tags, list)


def test_itch_top_tags_pairs(patched_gather):
    """Each top_tag entry is a [str, int] pair."""
    for pair in patched_gather["itch"]["top_tags"]:
        assert len(pair) == 2, f"Expected [tag, count] pair, got {pair!r}"
        assert isinstance(pair[0], str)
        assert isinstance(pair[1], int)


# ---------------------------------------------------------------------------
# kongregate section
# ---------------------------------------------------------------------------

def test_kong_count_gte_1(patched_gather):
    assert patched_gather["kongregate"]["count"] >= 1


def test_kong_rated_count_lte_count(patched_gather):
    kong = patched_gather["kongregate"]
    assert kong["rated_count"] <= kong["count"]


def test_kong_mean_rating_is_float_or_none(patched_gather):
    mr = patched_gather["kongregate"]["mean_rating_pct"]
    assert mr is None or isinstance(mr, float), (
        f"mean_rating_pct should be float or None, got {type(mr)}"
    )


def test_kong_top_tags_is_list(patched_gather):
    assert isinstance(patched_gather["kongregate"]["top_tags"], list)


# ---------------------------------------------------------------------------
# reddit section
# ---------------------------------------------------------------------------

def test_reddit_available_is_false_when_no_cache(patched_gather):
    """data/raw/reddit/ has no .cache files → available must be False."""
    assert patched_gather["reddit"]["available"] is False


def test_reddit_sentiment_empty_when_no_cache(patched_gather):
    """No cache → sentiment dict must be empty."""
    assert patched_gather["reddit"]["sentiment"] == {}


def test_reddit_note_is_string(patched_gather):
    note = patched_gather["reddit"]["note"]
    assert isinstance(note, str) and len(note) > 0


# ---------------------------------------------------------------------------
# caveats
# ---------------------------------------------------------------------------

def test_caveats_is_non_empty_list(patched_gather):
    caveats = patched_gather["caveats"]
    assert isinstance(caveats, list)
    assert len(caveats) >= 1


def test_caveats_are_strings(patched_gather):
    for c in patched_gather["caveats"]:
        assert isinstance(c, str), f"caveat should be str, got {c!r}"
