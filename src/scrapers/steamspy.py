from src.common.http import cached_get

BASE = "https://steamspy.com/api.php"

def fetch_appdetails(appid, refresh=False) -> dict:
    r = cached_get(BASE, source="steamspy_appdetails",
                   params={"request": "appdetails", "appid": appid},
                   rate_key="steamspy", refresh=refresh)
    return r.json()

def fetch_tag(tag: str, refresh=False) -> dict:
    r = cached_get(BASE, source="steamspy", params={"request": "tag", "tag": tag},
                   rate_key="steamspy", refresh=refresh)
    return r.json()

def _owners_midpoint(s: str) -> int | None:
    try:
        lo, hi = [int(x.strip().replace(",", "")) for x in s.split("..")]
        return (lo + hi) // 2
    except Exception:
        return None

def parse_app(rec: dict) -> dict:
    pos, neg = rec.get("positive", 0), rec.get("negative", 0)
    total = pos + neg
    price = rec.get("price")
    return {
        "id": str(rec.get("appid")),
        "source": "steam",
        "name": rec.get("name"),
        "owners_est": _owners_midpoint(rec.get("owners", "")),
        "owners_confidence": "medium",
        "ccu_peak": rec.get("ccu"),
        "review_count": total or None,
        "review_pct_positive": round(100 * pos / total, 1) if total else None,
        "price": (int(price) / 100) if price not in (None, "") else None,
        "is_free": price in ("0", 0),
        "tags": list((rec.get("tags") or {}).keys()),
        "platform": "pc",
    }
