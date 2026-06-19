from pathlib import Path
import pandas as pd
from src.scrapers import steamspy, steam
from src.pipeline.normalize import merge_records
from src.common.schema import empty_frame, validate


def build(cfg, limit=None, refresh=False) -> pd.DataFrame:
    seen, rows = {}, []
    for tag in cfg["steam_tags"]:
        seen.update(steamspy.fetch_tag(tag, refresh=refresh))
    appids = list(seen)[:limit] if limit else list(seen)
    total = len(appids)
    skipped = 0
    skipped_apps = []
    for i, appid in enumerate(appids, 1):
        try:
            ss = steamspy.parse_app(steamspy.fetch_appdetails(appid, refresh=refresh))
            det = steam.parse_details(steam.fetch_details(appid, refresh=refresh), appid)
            news = steam.fetch_news(appid, refresh=refresh)
            row = merge_records(ss, det, cfg)
            row["update_cadence"] = steam.update_cadence(news)
            row["release_news"] = [n.get("date") for n in news]
            rows.append(row)
        except Exception as exc:
            skipped += 1
            skipped_apps.append((appid, str(exc)[:120]))
            continue
        if i % 25 == 0:
            print(f"[build] {i}/{total} processed, {skipped} skipped")
    print(f"[build] done: {len(rows)} rows, {skipped} skipped")
    df = pd.concat([empty_frame(), pd.DataFrame(rows)], ignore_index=True)
    probs = validate(df)
    if probs:
        raise ValueError("schema validation failed: " + "; ".join(probs))
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet("data/processed/games.parquet")
    return df

