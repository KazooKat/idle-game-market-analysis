import json
from src.scrapers.steam import parse_details, update_cadence

def test_parse_details():
    payload = json.load(open("tests/scrapers/fixtures/steam_appdetails.json"))
    out = parse_details(payload, "123")
    assert out["is_free"] in (True, False)
    assert out["screenshot_count"] >= 1
    assert isinstance(out["has_iap"], bool)

def test_update_cadence_days():
    news = json.load(open("tests/scrapers/fixtures/steam_news.json"))["appnews"]["newsitems"]
    cad = update_cadence(news)
    assert 10 <= cad <= 18   # ~14-day spacing
