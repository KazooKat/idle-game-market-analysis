"""Tests for src/scrapers/reddit.py.

fetch_top returns a list of post-data dicts (the .data field of each child node).
extract_sentiment_terms accepts that same list.
"""
import json
import pathlib
import pytest
from unittest.mock import patch, MagicMock

from src.scrapers.reddit import extract_sentiment_terms, fetch_top


_FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "reddit_top.json"


def _load_posts() -> list[dict]:
    """Load fixture and return list of post-data dicts (same shape fetch_top produces)."""
    with open(_FIXTURE_PATH) as f:
        raw = json.load(f)
    return [child["data"] for child in raw["data"]["children"]]


# ---------------------------------------------------------------------------
# extract_sentiment_terms
# ---------------------------------------------------------------------------

def test_extract_hated_paywall():
    """Fixture has a post mentioning 'paywall' — hated count must be >= 1."""
    posts = _load_posts()
    result = extract_sentiment_terms(posts, {"hated": ["paywall"]})
    assert result["hated"] >= 1


def test_extract_case_insensitive():
    """Term matching must be case-insensitive."""
    posts = [{"title": "PAYWALL ruined it", "selftext": ""}]
    result = extract_sentiment_terms(posts, {"hated": ["paywall"]})
    assert result["hated"] == 1


def test_extract_counts_title_and_selftext():
    """A term in selftext (not title) must still be counted."""
    posts = [{"title": "Nothing here", "selftext": "it was very addictive"}]
    result = extract_sentiment_terms(posts, {"loved": ["addictive"]})
    assert result["loved"] == 1


def test_extract_multi_category():
    """Multiple vocab categories are returned with correct counts."""
    posts = _load_posts()
    vocab = {
        "loved": ["addictive", "satisfying", "offline"],
        "hated": ["paywall", "ads", "grind", "timer"],
    }
    result = extract_sentiment_terms(posts, vocab)
    assert set(result.keys()) == {"loved", "hated"}
    # post 1 has "paywall", post 3 has "ads"/"grind"/"timer" → 2 posts hit hated
    assert result["hated"] >= 2
    # post 2 has "satisfying"/"offline"/"addictive" → 1 post hits loved
    assert result["loved"] >= 1


def test_extract_empty_posts():
    """Empty post list returns zero counts for all categories."""
    result = extract_sentiment_terms([], {"loved": ["fun"], "hated": ["ads"]})
    assert result == {"loved": 0, "hated": 0}


def test_extract_no_match():
    """Term not present in any post returns zero for that category."""
    posts = _load_posts()
    result = extract_sentiment_terms(posts, {"rare": ["xyzzy_not_found"]})
    assert result["rare"] == 0


# ---------------------------------------------------------------------------
# fetch_top (integration — mocked)
# ---------------------------------------------------------------------------

def test_fetch_top_returns_post_dicts():
    """fetch_top should return a list of post-data dicts (not raw children)."""
    with open(_FIXTURE_PATH) as f:
        raw = json.load(f)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw

    with patch("src.scrapers.reddit.cached_get", return_value=mock_resp):
        posts = fetch_top("incremental_games")

    assert isinstance(posts, list)
    assert len(posts) == 4
    # each element must be a post-data dict (has title key, no 'kind' key)
    assert "title" in posts[0]
    assert "kind" not in posts[0]


# ---------------------------------------------------------------------------
# Null selftext guard (finding 1)
# ---------------------------------------------------------------------------

def test_extract_handles_null_selftext_via_fixture():
    """Fixture includes a link post with selftext=null; must not crash."""
    posts = _load_posts()
    # The link post title contains 'paywall', so hated count must be >= 2
    result = extract_sentiment_terms(posts, {"hated": ["paywall"]})
    assert result["hated"] >= 2


def test_extract_handles_null_selftext_direct():
    """Directly passing selftext=None must not raise TypeError and must count correctly."""
    posts = [{"title": "has paywall", "selftext": None}]
    result = extract_sentiment_terms(posts, {"hated": ["paywall"]})
    assert result == {"hated": 1}
