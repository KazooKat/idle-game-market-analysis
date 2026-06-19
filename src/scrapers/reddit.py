"""Reddit qualitative scraper.

fetch_top(sub, refresh=False) -> list[dict]
    Fetches top posts from r/{sub} for the past year.
    Returns a list of post-data dicts: the `.data` field of each child node,
    i.e. [child["data"] for child in response["data"]["children"]].
    Each dict has at minimum "title" and "selftext" keys.

extract_sentiment_terms(posts, vocab) -> dict[str, int]
    Counts, case-insensitively, how many posts mention at least one term from
    each vocab category across title + selftext.
    posts  : list[dict] — same shape fetch_top returns.
    vocab  : dict[str, list[str]] — e.g. {"loved": ["addictive", "offline"],
                                           "hated": ["paywall", "ads"]}
    Returns : dict[str, int] — {category: post_count_with_any_term}.
"""

from src.common.http import cached_get

_BASE = "https://www.reddit.com/r/{sub}/top.json"
_HEADERS = {"User-Agent": "idle-market-analysis/0.1"}


def fetch_top(sub: str, refresh: bool = False) -> list[dict]:
    """Return list of post-data dicts for the top 100 posts in r/{sub} (past year)."""
    url = _BASE.format(sub=sub)
    resp = cached_get(
        url,
        source="reddit",
        params={"t": "year", "limit": 100},
        headers=_HEADERS,
        rate_key="reddit",
        refresh=refresh,
    )
    payload = resp.json()
    children = payload["data"]["children"]
    return [child["data"] for child in children]


def extract_sentiment_terms(
    posts: list[dict],
    vocab: dict[str, list[str]],
) -> dict[str, int]:
    """Count posts (by category) that mention any term from that category.

    Matching is case-insensitive substring search over title + selftext.
    A post is counted once per category regardless of how many terms it matches.
    """
    counts: dict[str, int] = {category: 0 for category in vocab}
    for post in posts:
        text = ((post.get("title") or "") + " " + (post.get("selftext") or "")).lower()
        for category, terms in vocab.items():
            if any(term.lower() in text for term in terms):
                counts[category] += 1
    return counts
