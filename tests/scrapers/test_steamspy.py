import json
from unittest.mock import patch, MagicMock
from src.scrapers.steamspy import parse_app, fetch_appdetails

def test_parse_app_maps_fields():
    rec = json.load(open("tests/scrapers/fixtures/steamspy_tag.json"))["123"]
    out = parse_app(rec)
    assert out["id"] == "123"
    assert out["owners_est"] == 750000          # midpoint of range
    assert out["owners_confidence"] == "medium"
    assert out["review_count"] == 1000
    assert out["review_pct_positive"] == 90.0
    assert out["price"] == 1.99
    assert "Idler" in out["tags"]


def test_parse_app_appdetails_shaped_record_includes_tags():
    """parse_app on an appdetails-shaped record (with tags dict) returns all tag keys."""
    rec = {
        "appid": 456,
        "name": "Pixel Idle Adventure",
        "owners": "100,000 .. 200,000",
        "positive": 800,
        "negative": 50,
        "ccu": 25,
        "price": "0",
        "tags": {"Idler": 50, "Pixel Graphics": 30, "RPG": 20},
    }
    out = parse_app(rec)
    assert out["id"] == "456"
    assert set(out["tags"]) == {"Idler", "Pixel Graphics", "RPG"}, (
        f"Expected tags from appdetails record, got {out['tags']!r}"
    )


def test_fetch_appdetails_calls_correct_endpoint(monkeypatch):
    """fetch_appdetails calls cached_get with appdetails request params."""
    fake_record = {
        "appid": 789, "name": "Test Game", "owners": "0 .. 0",
        "positive": 0, "negative": 0, "ccu": 0, "price": "0",
        "tags": {"Clicker": 10},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_record

    captured = {}

    def fake_cached_get(url, *, source, params=None, headers=None, rate_key="default", refresh=False):
        captured["url"] = url
        captured["source"] = source
        captured["params"] = params
        captured["rate_key"] = rate_key
        return mock_response

    monkeypatch.setattr("src.scrapers.steamspy.cached_get", fake_cached_get)

    result = fetch_appdetails(789, refresh=False)

    assert captured["source"] == "steamspy_appdetails"
    assert captured["params"] == {"request": "appdetails", "appid": 789}
    assert captured["rate_key"] == "steamspy"
    assert result == fake_record
