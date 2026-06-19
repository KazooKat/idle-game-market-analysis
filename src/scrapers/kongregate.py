"""Kongregate idle-games scraper.

Fetches https://www.kongregate.com/idle-games (redirects to /en/idle-games).
The visible game grid is populated via JavaScript at runtime, but the page
embeds a JSON-LD <script type="application/ld+json"> block containing an
ItemList of up to 50 games -- this IS present in static HTML and is parsed here.

Rating note: Kongregate uses a 1-5 star scale (aggregateRating.ratingValue).
We convert it to review_pct_positive with confidence="low" because the scale
is not directly comparable to Steam's thumbs-up percentage.
  formula: pct = (ratingValue - 1) / 4 * 100   (maps 1→0%, 5→100%)
"""
import json
import re
from bs4 import BeautifulSoup

from src.common.http import cached_get

_URL = "https://www.kongregate.com/idle-games"
_HEADERS = {"User-Agent": "idle-market-analysis/0.1"}


def fetch_listing(refresh: bool = False) -> str:
    """Return HTML of the Kongregate idle category page (cached)."""
    r = cached_get(_URL, source="kongregate", rate_key="scrape",
                   headers=_HEADERS, refresh=refresh)
    return r.text


def parse_listing(html: str) -> list[dict]:
    """Parse JSON-LD ItemList from Kongregate category page HTML.

    Returns one partial row dict per game, or [] if no ItemList found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the JSON-LD script block
    ld_tag = soup.find("script", {"type": "application/ld+json"})
    if not ld_tag:
        return []

    try:
        data = json.loads(ld_tag.string or "")
    except (json.JSONDecodeError, TypeError):
        return []

    graph = data.get("@graph", []) if isinstance(data, dict) else []

    # Find the ItemList node
    item_list = next(
        (node for node in graph if node.get("@type") == "ItemList"),
        None,
    )
    if item_list is None:
        return []

    rows: list[dict] = []
    for entry in item_list.get("itemListElement", []):
        game = entry.get("item", {})
        url: str = game.get("url", "")
        if not url:
            continue

        # Slug is the last path segment: .../games/<author>/<slug>
        slug = url.rstrip("/").split("/")[-1]
        name: str = game.get("name", "")
        if not name:
            continue

        # Genre → tags
        genre = game.get("genre")
        tags: list[str] = [genre] if genre else []

        # aggregateRating: 1-5 star scale → 0-100 pct (confidence low)
        review_pct: float | None = None
        confidence: str | None = None
        agg = game.get("aggregateRating")
        if agg:
            try:
                rv = float(agg["ratingValue"])
                # map [1, 5] → [0, 100]
                review_pct = round((rv - 1.0) / 4.0 * 100.0, 1)
                confidence = "low"
            except (KeyError, ValueError, TypeError):
                pass

        rows.append({
            "id": f"kong:{slug}",
            "name": name,
            "source": "kongregate",
            "platform": "web",
            "tags": tags,
            "review_pct_positive": review_pct,
            "owners_confidence": confidence,
        })

    return rows
