import yaml
from src.pipeline.normalize import merge_records

CFG = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))

def test_merge_produces_full_schema_row():
    ss = {"id":"1","source":"steam","name":"Space Idle","owners_est":750000,
          "owners_confidence":"medium","ccu_peak":10,"review_count":100,
          "review_pct_positive":90.0,"price":None,"is_free":True,
          "tags":["Idler"],"platform":"pc"}
    st = {"id":"1","release_date":"2022","short_desc":"Mine ore in space, offline progress",
          "is_free":True,"price":0.0,"screenshot_count":5,"has_iap":True,
          "raw_genres":["Casual"]}
    row = merge_records(ss, st, CFG)
    from src.common.schema import COLUMNS
    assert set(row) >= set(COLUMNS)
    assert row["business_model"] == "f2p+iap"
    assert row["theme"] in ("space", "mining")
    assert "offline_progress" in row["mechanics"]
