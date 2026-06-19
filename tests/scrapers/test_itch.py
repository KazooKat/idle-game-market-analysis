from pathlib import Path
from src.scrapers.itch import parse_browse

FIXTURE = Path("tests/scrapers/fixtures/itch_browse.html")


def test_parse_browse_returns_rows():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_browse(html)
    assert len(rows) >= 2, f"Expected >=2 rows, got {len(rows)}"


def test_parse_browse_first_row_fields():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_browse(html)
    row = rows[0]
    assert row["name"], "name must be non-empty"
    assert row["id"].startswith("itch:"), f"id must start with 'itch:', got {row['id']!r}"
    assert row["source"] == "itch"
    assert row["platform"] == "web"
    assert row["owners_confidence"] is None
    assert isinstance(row["is_free"], bool)
    assert isinstance(row["tags"], list)


def test_parse_browse_paid_game():
    """Fixture contains one paid game (Scritchy Scratchy at $6.99)."""
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_browse(html)
    paid = [r for r in rows if r["price"] is not None and r["price"] > 0]
    assert paid, "Expected at least one paid game in fixture"
    row = paid[0]
    assert row["is_free"] is False
    assert row["price"] > 0.0


def test_parse_browse_free_game():
    """Free games should have is_free=True and price=0.0."""
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_browse(html)
    free = [r for r in rows if r["is_free"] is True]
    assert free, "Expected at least one free game in fixture"
