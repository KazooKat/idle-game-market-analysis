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
