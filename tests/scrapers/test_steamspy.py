import json
from src.scrapers.steamspy import parse_app

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
