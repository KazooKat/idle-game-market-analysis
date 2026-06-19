import pandas as pd

COLUMNS = {
    "id": "string", "source": "string", "name": "string",
    "release_date": "string", "price": "float64", "is_free": "boolean",
    "tags": "object", "short_desc": "string", "screenshot_count": "Int64",
    "review_count": "Int64", "review_pct_positive": "float64",
    "owners_est": "Int64", "owners_confidence": "string",
    "ccu_peak": "Int64",
    "theme": "string", "mechanics": "object",
    "art_style": "string", "business_model": "string",
    "release_news": "object", "update_cadence": "float64",
    "platform": "string",
}
_VALID_CONF = {"high", "medium", "low", None}

def empty_frame() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype=t) for c, t in COLUMNS.items()})
    return df

def validate(df: pd.DataFrame) -> list[str]:
    problems = []
    for c in COLUMNS:
        if c not in df.columns:
            problems.append(f"missing column: {c}")
    if "owners_est" in df and "owners_confidence" in df:
        bad = df[df["owners_est"].notna() & df["owners_confidence"].isna()]
        if len(bad):
            problems.append(f"{len(bad)} rows have owners_est without confidence")
    if "owners_confidence" in df:
        invalid = set(df["owners_confidence"].dropna().unique()) - {"high","medium","low"}
        if invalid:
            problems.append(f"invalid confidence values: {invalid}")
    return problems
