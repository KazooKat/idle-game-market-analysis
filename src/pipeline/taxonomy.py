import re as _re


def classify(text: str, tags: list[str], keyword_map: dict) -> list[str]:
    hay = (text or "").lower() + " " + " ".join(t.lower() for t in (tags or []))
    hits = []
    for cat, words in keyword_map.items():
        if any(_re.search(r"\b" + _re.escape(w.lower()) + r"\b", hay) for w in words):
            hits.append(cat)
    return hits


def pick_theme(text, tags, cfg):
    hits = classify(text, tags, cfg["theme_keywords"])
    return hits[0] if hits else None


def pick_mechanics(text, tags, cfg):
    return classify(text, tags, cfg["mechanic_keywords"])


def pick_art_style(tags, cfg):
    hits = classify("", tags, cfg["art_keywords"])
    return hits[0] if hits else None


def business_model(is_free: bool, has_iap: bool, price) -> str:
    if is_free:
        return "f2p+iap" if has_iap else "free-premium"
    return "paid+iap" if has_iap else "premium"
