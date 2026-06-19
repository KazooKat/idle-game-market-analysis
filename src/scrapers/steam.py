from statistics import mean
from src.common.http import cached_get

DETAILS = "https://store.steampowered.com/api/appdetails"
NEWS = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

def fetch_details(appid, refresh=False) -> dict:
    r = cached_get(DETAILS, source="steam_details",
                   params={"appids": appid, "l": "english"},
                   rate_key="default", refresh=refresh)
    return r.json()

def parse_details(payload: dict, appid) -> dict:
    node = payload.get(str(appid)) or next(iter(payload.values()))
    if not node.get("success"):
        return {"id": str(appid)}
    d = node["data"]
    cats = [c.get("description", "") for c in d.get("categories", [])]
    price = d.get("price_overview", {}).get("final")
    return {
        "id": str(appid),
        "release_date": d.get("release_date", {}).get("date"),
        "short_desc": d.get("short_description"),
        "is_free": d.get("is_free", False),
        "price": (price / 100) if price else (0.0 if d.get("is_free") else None),
        "screenshot_count": len(d.get("screenshots", [])),
        "has_iap": any("In-App Purchase" in c for c in cats),
        "raw_genres": [g.get("description") for g in d.get("genres", [])],
    }

def fetch_news(appid, count=20, refresh=False) -> list:
    r = cached_get(NEWS, source="steam_news",
                   params={"appid": appid, "count": count, "format": "json"},
                   rate_key="default", refresh=refresh)
    return r.json().get("appnews", {}).get("newsitems", [])

def update_cadence(news_items: list) -> float | None:
    dates = sorted(i["date"] for i in news_items if "date" in i)
    if len(dates) < 2:
        return None
    gaps = [(dates[i+1] - dates[i]) / 86400 for i in range(len(dates) - 1)]
    return round(mean(gaps), 1)
