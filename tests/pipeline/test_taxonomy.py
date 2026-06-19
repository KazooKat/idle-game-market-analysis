from src.pipeline.taxonomy import classify, business_model

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
