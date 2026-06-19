import yaml
from src.pipeline.taxonomy import classify, business_model, pick_art_style, pick_theme

CFG = {"space": ["space", "galaxy"], "mining": ["mine", "mining", "ore"]}


def test_classify_multi_hit():
    out = classify("A space mining idle game", ["Galaxy"], CFG)
    assert set(out) == {"space", "mining"}


def test_business_model_buckets():
    assert business_model(True, True, 0.0) == "f2p+iap"
    assert business_model(True, False, 0.0) == "free-premium"
    assert business_model(False, True, 4.99) == "paid+iap"
    assert business_model(False, False, 4.99) == "premium"


# ---------------------------------------------------------------------------
# Word-boundary tests (FIX 1)
# ---------------------------------------------------------------------------

def test_word_boundary_no_false_match_ore_in_explore_store():
    """'ore' must NOT match in 'explore', 'store', 'more', 'before' (substring bug)."""
    CFG_ORE = {"mining": ["ore"]}
    result = classify("explore the galaxy and store items before more", [], CFG_ORE)
    assert result == [], (
        f"Expected [], got {result!r}. 'ore' should not match inside 'explore'/'store'/'before'/'more'."
    )


def test_word_boundary_true_match_ore_standalone():
    """'ore' MUST match when it appears as a standalone word."""
    CFG_ORE = {"mining": ["ore", "mine"]}
    result = classify("mine the ore deposits", [], CFG_ORE)
    assert result == ["mining"], (
        f"Expected ['mining'], got {result!r}. 'ore' and 'mine' should match as whole words."
    )


def test_word_boundary_mine_not_in_determine():
    """'mine' must NOT match in 'determine' or 'undermine'."""
    CFG_MINE = {"mining": ["mine"]}
    result = classify("players can determine the undermine factor", [], CFG_MINE)
    assert result == [], (
        f"Expected [], got {result!r}. 'mine' should not match inside 'determine'/'undermine'."
    )


def test_word_boundary_multiword_keyword():
    """Multi-word keywords ('pay to win') must match at word boundaries."""
    CFG_PAY = {"monetize": ["pay to win"]}
    result = classify("this game has pay to win mechanics", [], CFG_PAY)
    assert result == ["monetize"], (
        f"Expected ['monetize'], got {result!r}."
    )


def test_word_boundary_hyphenated_keyword():
    """Hyphenated keywords ('8-bit') must match correctly."""
    CFG_ART = {"art": ["8-bit"]}
    result = classify("beautiful 8-bit pixel art style", [], CFG_ART)
    assert result == ["art"], (
        f"Expected ['art'], got {result!r}."
    )


def test_word_boundary_case_insensitive():
    """Word-boundary matching must remain case-insensitive."""
    CFG_SPACE = {"space": ["galaxy"]}
    result = classify("Explore the GALAXY beyond", [], CFG_SPACE)
    assert result == ["space"], (
        f"Expected ['space'], got {result!r}."
    )


# ---------------------------------------------------------------------------
# pick_art_style with real sources.yaml art_keywords (Steam tag names)
# ---------------------------------------------------------------------------

def test_pick_art_style_pixel_graphics_tag():
    """'Pixel Graphics' Steam tag → art_style = 'pixel' via sources.yaml keywords."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_art_style(["Pixel Graphics"], cfg)
    assert result == "pixel", (
        f"Expected 'pixel' from tag 'Pixel Graphics', got {result!r}. "
        "Check art_keywords.pixel includes 'pixel graphics'."
    )


def test_pick_art_style_none_when_no_art_tags():
    """No art tags → art_style is None."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_art_style(["Idler", "Clicker", "RPG"], cfg)
    assert result is None, (
        f"Expected None for non-art tags, got {result!r}."
    )


# ---------------------------------------------------------------------------
# Expanded theme taxonomy tests (PART A)
# ---------------------------------------------------------------------------

def test_pick_theme_scifi_from_tag():
    """A game tagged 'Sci-fi' should classify as 'scifi'."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_theme("an incremental game", ["Sci-fi", "Idler"], cfg)
    assert result == "scifi", (
        f"Expected 'scifi' for tag 'Sci-fi', got {result!r}. "
        "Check theme_keywords.scifi includes 'sci-fi'."
    )


def test_pick_theme_horror_from_tag():
    """A game tagged 'Horror' should classify as 'horror'."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_theme("a dark incremental game", ["Horror", "Idler"], cfg)
    assert result == "horror", (
        f"Expected 'horror' for tag 'Horror', got {result!r}. "
        "Check theme_keywords.horror includes 'horror'."
    )


def test_pick_theme_scifi_from_description():
    """A game description containing 'cyberpunk' should classify as 'scifi'."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_theme("a cyberpunk idle clicker", [], cfg)
    assert result == "scifi", (
        f"Expected 'scifi' for 'cyberpunk' in description, got {result!r}."
    )


def test_pick_theme_horror_from_description():
    """A game description containing 'zombie' should classify as 'horror'."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    result = pick_theme("survive the zombie apocalypse clicker", [], cfg)
    assert result == "horror", (
        f"Expected 'horror' for 'zombie' in description, got {result!r}."
    )


def test_all_expanded_themes_present_in_config():
    """All 23 expanded themes must appear in config/sources.yaml."""
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    expected = {
        "cookie", "space", "scifi", "robot", "fantasy", "medieval",
        "mythology", "horror", "postapoc", "military", "pirate", "mining",
        "factory", "farming", "city", "economy", "rpg", "monster", "nature",
        "ocean", "food", "steampunk", "crime",
    }
    actual = set(cfg["theme_keywords"].keys())
    missing = expected - actual
    assert not missing, f"Missing themes in config: {missing}"
