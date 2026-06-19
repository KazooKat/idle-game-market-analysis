"""
Task 8b: test that build() survives one bad app without aborting the whole run.

Design:
- 3 fake appids: "111", "222" (succeed), "333" (raises on steam.fetch_details).
- steamspy.fetch_tag, steamspy.fetch_appdetails, steam.fetch_details, steam.fetch_news,
  steam.update_cadence are all monkeypatched so NO network calls are made.
- build() runs in a tmp_path dir so parquet is written there, not to real data/.
- Config dict is constructed inline from the real sources.yaml values so no file I/O
  after chdir.

Also tests (Task: appdetails enrichment):
- build_art_style_via_appdetails_tags: appdetails records WITH tags flow through
  parse_app → merge_records → taxonomy → art_style is non-null for a pixel-tagged game.
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
        "pixel": ["pixel", "pixel graphics", "8-bit", "16-bit", "retro"],
        "hand_drawn": ["hand-drawn", "hand drawn", "cartoon", "comic-book", "doodle"],
        "anime": ["anime", "manga", "jrpg"],
        "minimalist": ["minimalist", "minimal", "clean", "abstract"],
        "three_d": ["3d", "3-d"],
        "two_d": ["2d", "2-d"],
        "cute": ["cute", "kawaii", "adorable", "colorful", "cartoony"],
        "stylized": ["stylized", "low-poly", "voxel", "pixel art"],
    },
}

BAD_APPID = "333"

# ── fake SteamSpy tag payload — 3 apps ──────────────────────────────────────
# NOTE: tag-endpoint records have NO tags (that was the bug). Discovery only.
FAKE_TAG_RESULT = {
    "111": {
        "appid": 111, "name": "Good Idle One", "owners": "20000 .. 50000",
        "positive": 100, "negative": 10, "ccu": 5, "price": "0", "tags": {},
    },
    "222": {
        "appid": 222, "name": "Good Idle Two", "owners": "50000 .. 100000",
        "positive": 200, "negative": 20, "ccu": 10, "price": "499", "tags": {},
    },
    BAD_APPID: {
        "appid": 333, "name": "Broken App", "owners": "0 .. 0",
        "positive": 0, "negative": 0, "ccu": 0, "price": None, "tags": {},
    },
}

# ── fake SteamSpy appdetails payload — includes tags ────────────────────────
# App 111 has "Pixel Graphics" tag → should produce art_style="pixel"
FAKE_APPDETAILS = {
    "111": {
        "appid": 111, "name": "Good Idle One", "owners": "20000 .. 50000",
        "positive": 100, "negative": 10, "ccu": 5, "price": "0",
        "tags": {"Idler": 50, "Pixel Graphics": 30, "Clicker": 10},
    },
    "222": {
        "appid": 222, "name": "Good Idle Two", "owners": "50000 .. 100000",
        "positive": 200, "negative": 20, "ccu": 10, "price": "499",
        "tags": {"Clicker": 30, "RPG": 10},
    },
    BAD_APPID: {
        "appid": 333, "name": "Broken App", "owners": "0 .. 0",
        "positive": 0, "negative": 0, "ccu": 0, "price": None,
        "tags": {},
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


def make_fake_fetch_appdetails():
    """fetch_appdetails returns the per-app record WITH tags dict.
    This is the appdetails enrichment — includes real Steam tags.
    """
    def _fetch(appid, refresh=False):
        return FAKE_APPDETAILS[str(appid)]
    return _fetch


def make_fake_fetch_news():
    """fetch_news in the real scraper returns a list of newsitems directly."""
    def _fetch(appid, count=20, refresh=False):
        return []
    return _fetch


# ── test: resilience (original) ──────────────────────────────────────────────

def test_build_skips_bad_app_and_returns_good_rows(monkeypatch, tmp_path):
    """
    With one bad app (fetch_details raises), build() must:
    - NOT raise an exception itself
    - Return a DataFrame containing exactly 2 rows (the 2 good apps)
    - Write games.parquet to data/processed/ (in tmp_path)
    """
    # chdir to tmp_path so parquet writes land in tmp and not real data/
    monkeypatch.chdir(tmp_path)

    import src.pipeline.build_master as bm
    import src.scrapers.steamspy as spy_mod
    import src.scrapers.steam as steam_mod

    monkeypatch.setattr(spy_mod, "fetch_tag", make_fake_fetch_tag())
    monkeypatch.setattr(spy_mod, "fetch_appdetails", make_fake_fetch_appdetails())
    monkeypatch.setattr(steam_mod, "fetch_details", make_fake_fetch_details())
    monkeypatch.setattr(steam_mod, "fetch_news", make_fake_fetch_news())

    df = bm.build(CFG, limit=None, refresh=False)

    assert isinstance(df, pd.DataFrame), "build() must return a DataFrame"
    assert len(df) == 2, (
        f"Expected 2 rows (good apps only), got {len(df)}. "
        "If this is 3, error handling is missing. If this is 0, something else broke."
    )
    parquet_path = tmp_path / "data" / "processed" / "games.parquet"
    assert parquet_path.exists(), "games.parquet was not written"


# ── test: art_style flows from appdetails tags ───────────────────────────────

def test_build_art_style_via_appdetails_tags(monkeypatch, tmp_path):
    """
    Red-before-green: before the appdetails change, parse_app received the tag-endpoint
    record (no tags dict) → art_style was always None. After the change, parse_app
    receives the appdetails record WITH tags → pick_art_style returns 'pixel' for
    app 111 (which has 'Pixel Graphics' in its tags).

    Asserts:
    - tags column is non-empty for the pixel-tagged game
    - art_style is non-null ('pixel') for the pixel-tagged game
    """
    monkeypatch.chdir(tmp_path)

    import src.pipeline.build_master as bm
    import src.scrapers.steamspy as spy_mod
    import src.scrapers.steam as steam_mod

    monkeypatch.setattr(spy_mod, "fetch_tag", make_fake_fetch_tag())
    monkeypatch.setattr(spy_mod, "fetch_appdetails", make_fake_fetch_appdetails())
    monkeypatch.setattr(steam_mod, "fetch_details", make_fake_fetch_details())
    monkeypatch.setattr(steam_mod, "fetch_news", make_fake_fetch_news())

    df = bm.build(CFG, limit=None, refresh=False)

    assert len(df) == 2, f"Expected 2 rows, got {len(df)}"

    # Find the pixel-tagged game (appid 111)
    pixel_rows = df[df["id"] == "111"]
    assert len(pixel_rows) == 1, "App 111 should be in results"
    pixel_row = pixel_rows.iloc[0]

    # Tags must be non-empty (flows from appdetails record)
    assert pixel_row["tags"] and len(pixel_row["tags"]) > 0, (
        f"Expected non-empty tags for app 111, got {pixel_row['tags']!r}. "
        "Tags must flow from fetch_appdetails into parse_app."
    )
    assert "Pixel Graphics" in pixel_row["tags"], (
        f"'Pixel Graphics' tag missing from app 111 tags: {pixel_row['tags']!r}"
    )

    # art_style must be 'pixel' (from 'Pixel Graphics' tag via art_keywords)
    assert pixel_row["art_style"] == "pixel", (
        f"Expected art_style='pixel' for app 111 (has 'Pixel Graphics' tag), "
        f"got {pixel_row['art_style']!r}. "
        "Check fetch_appdetails is patched and art_keywords includes 'pixel graphics'."
    )
