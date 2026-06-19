"""Tests for the Kongregate idle-games scraper.

Fixture: tests/scrapers/fixtures/kong_idle.html
  Real trimmed static HTML with 3 games from JSON-LD (fetched 2026-06-18).
  Kongregate's game grid renders in JavaScript at runtime, but the page
  embeds a JSON-LD <script type="application/ld+json"> ItemList that IS
  present in the static HTML -- so parse_listing extracts data from that.
"""
from pathlib import Path
from src.scrapers.kongregate import parse_listing

FIXTURE = Path("tests/scrapers/fixtures/kong_idle.html")


def test_parse_listing_returns_rows():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_listing(html)
    assert len(rows) >= 1, f"Expected >=1 rows, got {len(rows)}"


def test_parse_listing_ids_start_with_kong():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_listing(html)
    for row in rows:
        assert row["id"].startswith("kong:"), f"id must start with 'kong:', got {row['id']!r}"


def test_parse_listing_required_fields():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_listing(html)
    row = rows[0]
    assert row["name"], "name must be non-empty"
    assert row["source"] == "kongregate"
    assert row["platform"] == "web"
    assert isinstance(row["tags"], list)
    assert len(row["tags"]) >= 1, "tags must have at least one entry"


def test_parse_listing_rating_field():
    """aggregateRating maps to review_pct_positive; review_confidence='low'; owners_confidence=None."""
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_listing(html)
    row = rows[0]  # Incremancer has ratingValue 4.53, ratingCount 29625
    assert row.get("review_pct_positive") is not None, "review_pct_positive should be present"
    pct = row["review_pct_positive"]
    assert 0.0 <= pct <= 100.0, f"review_pct_positive out of range: {pct}"
    # review_confidence carries the star-rating softness signal
    assert row.get("review_confidence") == "low", "review_confidence should be 'low' for rated game"
    # owners_confidence must always be None (Kongregate provides no owner data)
    assert row.get("owners_confidence") is None, "owners_confidence must be None (no owner data)"


def test_parse_listing_known_game():
    """Fixture contains Incremancer and NGU IDLE."""
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_listing(html)
    names = {r["name"] for r in rows}
    assert "Incremancer" in names, f"Expected Incremancer in names, got {names}"
    assert "NGU IDLE" in names, f"Expected NGU IDLE in names, got {names}"


def test_parse_listing_empty_html_returns_empty():
    """parse_listing must not crash on HTML with no JSON-LD ItemList."""
    rows = parse_listing("<html><body>No games here</body></html>")
    assert rows == [], f"Expected [], got {rows}"
