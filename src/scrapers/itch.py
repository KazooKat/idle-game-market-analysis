"""itch.io incremental-tag browse scraper.

Fetches/parses https://itch.io/games/tag-incremental.
No owner, review, or CCU data available; those fields are omitted / None.
"""
import re
from bs4 import BeautifulSoup
from src.common.http import cached_get

_URL = "https://itch.io/games/tag-incremental"
_HEADERS = {"User-Agent": "idle-market-analysis/0.1"}


def fetch_browse(refresh: bool = False) -> str:
    r = cached_get(_URL, source="itch", rate_key="scrape",
                   headers=_HEADERS, refresh=refresh)
    return r.text


def parse_browse(html: str) -> list[dict]:
    """Parse the browse grid HTML; return one partial row dict per game cell."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    for cell in soup.select("div.game_cell"):
        title_el = cell.select_one("a.title.game_link")
        if not title_el:
            continue

        name: str = title_el.get_text(strip=True)
        href: str = title_el.get("href", "")
        slug: str = href.rstrip("/").split("/")[-1]

        price_el = cell.select_one(".price_value")
        if price_el:
            raw = price_el.get_text(strip=True)
            # strip currency symbols and parse float
            digits = re.sub(r"[^\d.]", "", raw)
            price = float(digits) if digits else None
            is_free = (price == 0.0)
        else:
            price = 0.0
            is_free = True

        genre_el = cell.select_one(".game_genre")
        tags: list[str] = [genre_el.get_text(strip=True)] if genre_el else []

        rows.append({
            "id": f"itch:{slug}",
            "name": name,
            "source": "itch",
            "platform": "web",
            "is_free": is_free,
            "price": price,
            "tags": tags,
            "owners_confidence": None,
        })

    return rows
