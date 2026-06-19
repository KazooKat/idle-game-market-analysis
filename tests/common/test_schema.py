import pandas as pd
from src.common.schema import empty_frame, validate, COLUMNS

def test_empty_frame_has_columns():
    df = empty_frame()
    assert set(df.columns) == set(COLUMNS)

def test_validate_flags_missing_confidence():
    df = empty_frame()
    df.loc[0] = {c: None for c in COLUMNS}
    df.loc[0, "owners_est"] = 5000
    df.loc[0, "owners_confidence"] = None
    probs = validate(df)
    assert any("confidence" in p for p in probs)
