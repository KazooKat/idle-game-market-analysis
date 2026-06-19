"""
Task 8b: test that build() survives one bad app without aborting the whole run.

Design:
- 3 fake appids: "111", "222" (succeed), "333" (raises on steam.fetch_details).
- steamspy.fetch_tag, steam.fetch_details, steam.fetch_news, steam.update_cadence
  are all monkeypatched so NO network calls are made.
- build() runs in a tmp_path dir so parquet is written there, not to real data/.
- Config dict is constructed inline from the real sources.yaml values so no file I/O
  after chdir.
"""

import pytest
import pandas as pd
import sys
import os

# ── inline config matching config/sources.yaml ──────────────────────────────
CFG = {
    "steam_tags": ["Idler"],          # one tag → fetch_tag called once
    "theme_keywords": {
        "space": ["space", "galaxy", "planet", "cosmic"],
        "mining": ["mine", "mining", "dig", "ore"],
        "rpg": ["rpg", "hero", "dungeon", "quest", "adventure"],
        "factory": ["factory", "assembly", "production", "automate"],
        "money": ["capitalist", "tycoon", "money", "business", "idle profit"],
        "fantasy": ["magic", "wizard", "kingdom", "realm"],
        "nature": ["farm", "garden", "tree", "forest"],
        "cookie": ["cookie", "bakery"],
    },
    "mechanic_keywords": {
        "offline_progress": ["offline", "while away", "afk"],
        "prestige": ["prestige", "ascend", "ascension", "rebirth", "reset"],
        "automation": ["automate", "automation", "auto", "manager"],
        "multiplier": ["multiplier", "boost", "synergy"],
    },
    "art_keywords": {
        "pixel": ["pixel", "8-bit", "retro"],
        "hand_drawn": ["hand-drawn", "hand drawn", "cartoon"],
        "anime": ["anime", "manga"],
        "minimalist": ["minimalist", "minimal", "clean"],
        "three_d": ["3d", "3-d"],
        "cute": ["cute", "kawaii", "adorable"],
    },
}

BAD_APPID = "333"

# ── fake SteamSpy tag payload — 3 apps ──────────────────────────────────────
FAKE_TAG_RESULT = {
    "111": {
        "appid": 111, "name": "Good Idle One", "owners": "20000 .. 50000",
        "positive": 100, "negative": 10, "ccu": 5, "price": "0", "tags": {"Idler": 50},
    },
    "222": {
        "appid": 222, "name": "Good Idle Two", "owners": "50000 .. 100000",
        "positive": 200, "negative": 20, "ccu": 10, "price": "499", "tags": {"Clicker": 30},
    },
    BAD_APPID: {
        "appid": 333, "name": "Broken App", "owners": "0 .. 0",
        "positive": 0, "negative": 0, "ccu": 0, "price": None, "tags": {},
    },
}

# ── fake Steam details payload (success shape) ───────────────────────────────
def _fake_details_payload(appid):
    return {
        str(appid): {
            "success": True,
            "data": {
                "release_date": {"date": "2021"},
                "short_description": "An idle game",
                "is_free": appid == 111,
                "price_overview": {"final": 0} if appid == 111 else {"final": 499},
                "screenshots": [],
                "categories": [],
                "genres": [],
            },
        }
    }


def make_fake_fetch_details():
    """Return a fetch_details replacement that raises for BAD_APPID.

    The real steam.fetch_details returns r.json() — a plain dict that parse_details
    then calls .get() on.  So we return the dict directly.
    For BAD_APPID we raise immediately (simulating a network / parse error).
    """
    def _fetch(appid, refresh=False):
        if str(appid) == BAD_APPID:
            raise RuntimeError(f"Simulated network error for appid {appid}")
        return _fake_details_payload(int(appid))
    return _fetch


def make_fake_fetch_tag():
    """fetch_tag in the real scraper returns r.json() — a plain dict.
    build_master does seen.update(steamspy.fetch_tag(...)) so we must return a dict.
    """
    def _fetch(tag, refresh=False):
        return FAKE_TAG_RESULT
    return _fetch


def make_fake_fetch_news():
    """fetch_news in the real scraper returns a list of newsitems directly."""
    def _fetch(appid, count=20, refresh=False):
        return []
    return _fetch


# ── test ─────────────────────────────────────────────────────────────────────

def test_build_skips_bad_app_and_returns_good_rows(monkeypatch, tmp_path):
    """
    With one bad app (fetch_details raises), build() must:
    - NOT raise an exception itself
    - Return a DataFrame containing exactly 2 rows (the 2 good apps)
    - Write games.parquet to data/processed/ (in tmp_path)
    """
    # chdir to tmp_path so parquet writes land in tmp and not real data/
    monkeypatch.chdir(tmp_path)
    # We also need data/processed/ to exist (build makes it with mkdir parents)
    # build() calls Path("data/processed").mkdir(parents=True, exist_ok=True) — fine.

    # Patch the module-level steam and steamspy references used in build_master
    import src.pipeline.build_master as bm
    import src.scrapers.steamspy as spy_mod
    import src.scrapers.steam as steam_mod

    # patch steamspy.fetch_tag via the scrapers module AND the reference in build_master
    monkeypatch.setattr(spy_mod, "fetch_tag", make_fake_fetch_tag())
    # patch steam.fetch_details to raise for BAD_APPID
    monkeypatch.setattr(steam_mod, "fetch_details", make_fake_fetch_details())
    # patch steam.fetch_news to return []
    monkeypatch.setattr(steam_mod, "fetch_news", make_fake_fetch_news())

    df = bm.build(CFG, limit=None, refresh=False)

    # 2 good apps should be in result; bad app skipped
    assert isinstance(df, pd.DataFrame), "build() must return a DataFrame"
    assert len(df) == 2, (
        f"Expected 2 rows (good apps only), got {len(df)}. "
        "If this is 3, error handling is missing. If this is 0, something else broke."
    )
    # Verify the parquet was written
    parquet_path = tmp_path / "data" / "processed" / "games.parquet"
    assert parquet_path.exists(), "games.parquet was not written"
