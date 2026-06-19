"""
src/analysis/supplementary.py
Supplementary-sources analysis: itch.io, Kongregate, Reddit.

Steam is the quantitative SPINE of this project (games.parquet, analyzed by
the 9 modules in src/analysis/).  The secondary sources here are SUPPLEMENTARY:
they provide coverage counts and qualitative context for the report.  They are
NOT fed into the main comparison tables because their data is thinner and of
different confidence; forcing them into one table would produce a dishonest
cross-confidence comparison.

Public API:
    gather(refresh=False) -> dict
    main(out_dir="data/analysis") -> None   (writes supplementary.json)
"""
from __future__ import annotations

import collections
import json
import pathlib

import src.scrapers.itch as _itch
import src.scrapers.kongregate as _kong
from src.scrapers.reddit import extract_sentiment_terms

# ---------------------------------------------------------------------------
# Vocab for Reddit sentiment analysis (same categories as quality.py)
# ---------------------------------------------------------------------------

_REDDIT_VOCAB: dict[str, list[str]] = {
    "loved": [
        "addictive", "satisfying", "offline", "progress",
        "relaxing", "chill",
    ],
    "hated": [
        "paywall", "ads", "grind", "timer", "energy",
        "pay to win", "p2w", "predatory",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _top_tags(rows: list[dict], n: int = 10) -> list[list]:
    """Return the top-N tags across all rows as [[tag, count], ...] pairs."""
    counter: collections.Counter = collections.Counter()
    for row in rows:
        for tag in (row.get("tags") or []):
            if tag:
                counter[tag] += 1
    return [[tag, count] for tag, count in counter.most_common(n)]


def _reddit_from_cache() -> dict:
    """Read real cached Reddit API responses from data/raw/reddit/*.cache.

    Returns:
        {available: True,  sentiment: {...}, note: "..."} when cache files present.
        {available: False, sentiment: {},    note: "..."} when none present.

    IMPORTANT: does NOT read the synthetic test fixture at
    tests/scrapers/fixtures/reddit_top.json.  Real-cache-or-nothing.
    """
    _NO_CACHE_NOTE = (
        "Live Reddit data unavailable (r/incremental_games top.json returns 403 "
        "without OAuth); qualitative sentiment not collected."
    )

    try:
        cache_dir = pathlib.Path("data/raw/reddit")
        cache_files = list(cache_dir.glob("*.cache")) if cache_dir.exists() else []
        if not cache_files:
            return {"available": False, "sentiment": {}, "note": _NO_CACHE_NOTE}

        posts: list[dict] = []
        for f in cache_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "data" in data:
                children = data["data"].get("children", [])
                posts.extend(child.get("data", {}) for child in children)

        if not posts:
            return {"available": False, "sentiment": {}, "note": _NO_CACHE_NOTE}

        sentiment = extract_sentiment_terms(posts, _REDDIT_VOCAB)
        note = (
            f"Sentiment counted across {len(posts)} posts from "
            "r/incremental_games (top/year, cached)."
        )
        return {"available": True, "sentiment": sentiment, "note": note}

    except Exception:  # noqa: BLE001
        return {
            "available": False,
            "sentiment": {},
            "note": _NO_CACHE_NOTE,
        }


# ---------------------------------------------------------------------------
# gather()
# ---------------------------------------------------------------------------

def gather(refresh: bool = False) -> dict:
    """Collect supplementary source data and return a structured dict.

    Args:
        refresh: When True, bypass HTTP cache and re-fetch live pages.

    Returns:
        {
          "itch":       {count, free_count, free_pct, top_tags},
          "kongregate": {count, rated_count, mean_rating_pct, top_tags},
          "reddit":     {available, sentiment, note},
          "caveats":    [str, ...]
        }
    """
    # -- itch.io --
    itch_html = _itch.fetch_browse(refresh=refresh)
    itch_rows = _itch.parse_browse(itch_html)
    itch_count = len(itch_rows)
    itch_free_count = sum(1 for r in itch_rows if r.get("is_free") is True)
    itch_free_pct = round(100.0 * itch_free_count / itch_count, 1) if itch_count else 0.0

    itch_section: dict = {
        "count": itch_count,
        "free_count": itch_free_count,
        "free_pct": itch_free_pct,
        "top_tags": _top_tags(itch_rows),
    }

    # -- Kongregate --
    kong_html = _kong.fetch_listing(refresh=refresh)
    kong_rows = _kong.parse_listing(kong_html)
    kong_count = len(kong_rows)
    rated = [
        r for r in kong_rows if r.get("review_pct_positive") is not None
    ]
    kong_rated_count = len(rated)
    if rated:
        mean_rating_pct: float | None = round(
            sum(r["review_pct_positive"] for r in rated) / len(rated), 1
        )
    else:
        mean_rating_pct = None

    kong_section: dict = {
        "count": kong_count,
        "rated_count": kong_rated_count,
        "mean_rating_pct": mean_rating_pct,
        "top_tags": _top_tags(kong_rows),
    }

    # -- Reddit --
    reddit_section = _reddit_from_cache()

    # -- Caveats (honesty notes) --
    caveats: list[str] = [
        "itch.io provides no owner/revenue data — coverage counts only.",
        (
            "Kongregate ratings are 1-5 stars mapped to %positive (low confidence); "
            "not comparable to Steam review %."
        ),
        "Mobile stores not covered (no free data source).",
        (
            "itch.io and Kongregate data are scraped from static HTML / JSON-LD; "
            "counts reflect one page of results, not full catalogue."
        ),
    ]

    return {
        "itch": itch_section,
        "kongregate": kong_section,
        "reddit": reddit_section,
        "caveats": caveats,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(out_dir: str = "data/analysis") -> None:
    """Write gather() output to <out_dir>/supplementary.json."""
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    data = gather()
    out_file = out_path / "supplementary.json"
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)

    itch_count = data["itch"]["count"]
    kong_count = data["kongregate"]["count"]
    reddit_ok = data["reddit"]["available"]
    print(
        f"[supplementary] itch={itch_count} games, "
        f"kongregate={kong_count} games, "
        f"reddit={'available' if reddit_ok else 'unavailable'} "
        f"→ {out_file}"
    )


if __name__ == "__main__":
    main()
