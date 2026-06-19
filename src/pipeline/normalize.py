from src.common.schema import COLUMNS
from src.pipeline import taxonomy as tax


def merge_records(ss: dict, st: dict, cfg) -> dict:
    row = {c: None for c in COLUMNS}
    row.update({k: v for k, v in (ss or {}).items() if k in COLUMNS})
    text = (st or {}).get("short_desc") or ss.get("name", "")
    tags = ss.get("tags", [])
    for k in ("release_date", "short_desc", "screenshot_count", "price", "is_free"):
        if (st or {}).get(k) is not None:
            row[k] = st[k]
    row["theme"] = tax.pick_theme(text, tags, cfg)
    row["mechanics"] = tax.pick_mechanics(text, tags, cfg)
    row["art_style"] = tax.pick_art_style(tags, cfg)
    row["business_model"] = tax.business_model(
        bool(row.get("is_free")), bool((st or {}).get("has_iap")), row.get("price"))
    return row
