# Idle Game Market Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Python pipeline that scrapes idle/incremental game data (Steam-anchored, plus web/community layers), normalizes it into one master table, runs market + builder-focused analysis, and renders a static HTML report for GitHub Pages.

**Architecture:** One-way flow `scrape → normalize → analyze → render`. Each scraper is an isolated module that fetches and disk-caches raw data. The pipeline normalizes all sources into one `games.parquet` master table with confidence flags. Analysis modules read only the master table. The site builder reads only analysis outputs. Build in phases; each phase ends with working, testable software.

**Tech Stack:** Python 3.11+ (host has 3.14.3), `requests`, `beautifulsoup4`, `lxml`, `pandas`, `pyarrow`, `plotly`, `jinja2`, `pyyaml`, `pytest`. Package-managed in a local `.venv`.

## Global Constraints

- Python floor: **3.11+**. Host is 3.14.3 — pin no upper bound, but if a wheel is missing for 3.14, note it and proceed with pure-Python fallback.
- **$0 cost.** Free APIs + light scraping only. No paid data tools, no API keys that cost money. Steam Web API key is free and optional (most endpoints used here are keyless).
- **Confidence flags are mandatory.** Every estimated numeric field (`owners_est`, mobile figures) carries a sibling `*_confidence` value of `high|medium|low`. No chart compares across confidence tiers without labeling it.
- **Disk cache is mandatory.** Every network fetch caches to `data/raw/<source>/`. Reruns read cache; never re-hit a live endpoint when cache exists (unless `--refresh` passed).
- **Rate limits:** SteamSpy ≤ 1 req/sec; Steam store/appdetails ≤ ~1 req/1.5sec; Reddit ≤ 1 req/sec with descriptive User-Agent. Honor them in a shared fetch helper.
- **No SteamDB scraping** (Cloudflare/ToS). Update cadence comes from the official Steam News API (`ISteamNews`).
- **File size:** keep modules focused, under ~300 lines. Split by responsibility.
- **Master schema is the contract.** Columns defined in Task 5 are the single source of truth; analysis modules must not invent columns.

---

## File Structure

```
/config/sources.yaml          tags, seed lists, rate limits, endpoints
/src/common/
    http.py                   cached rate-limited fetch helper
    schema.py                 master schema definition + validation
/src/scrapers/
    steam.py                  Steam appdetails + reviews + news
    steamspy.py               owner estimates, tags, ccu
    itch.py                   itch.io incremental tag scrape
    kongregate.py             Kongregate idle category scrape
    reddit.py                 r/incremental_games qualitative pull
/src/pipeline/
    normalize.py              all sources -> master rows
    taxonomy.py               theme / mechanics / art_style / business_model
    build_master.py           orchestrates scrape->normalize->parquet
/src/analysis/
    base.py                   shared load + helpers (load_master, weighted)
    topics.py performance.py gaps.py quality.py
    monetization.py art.py updates.py trends.py naming.py
    run_all.py                runs every module -> /data/analysis/*.json
/src/site/
    build.py                  jinja2 + plotly -> /docs/index.html + pages
    templates/                report.html.j2, methodology.html.j2
/data/raw/  /data/processed/  /data/analysis/
/docs/                        GitHub Pages output
/tests/                       mirrors /src
requirements.txt
README.md
```

---

## Phase 0 — Project scaffold

### Task 1: Environment, deps, test harness

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `src/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: a working `.venv` with all deps; `pytest` runnable.

- [ ] **Step 1: Write requirements.txt**

```
requests>=2.31
beautifulsoup4>=4.12
lxml>=5.0
pandas>=2.1
pyarrow>=15.0
plotly>=5.20
jinja2>=3.1
pyyaml>=6.0
pytest>=8.0
```

- [ ] **Step 2: Create venv and install**

Run (Windows PowerShell):
```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: all install. If any wheel fails on Python 3.14, record the package + error, install the latest available, and note it in README "Known env issues".

- [ ] **Step 3: Write pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 4: Write smoke test** (`tests/test_smoke.py`)

```python
def test_imports():
    import requests, bs4, pandas, plotly, jinja2, yaml  # noqa: F401
    assert True
```

- [ ] **Step 5: Run it**

Run: `.venv\Scripts\python.exe -m pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini src/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold venv, deps, pytest harness"
```

---

### Task 2: Cached, rate-limited fetch helper

**Files:**
- Create: `src/common/__init__.py`, `src/common/http.py`, `tests/common/test_http.py`

**Interfaces:**
- Produces:
  - `cached_get(url, *, source, params=None, headers=None, rate_key="default", refresh=False) -> requests.Response`
    — keys cache by sha1 of (url+params); writes `data/raw/<source>/<hash>.cache`; on cache hit returns a stub object exposing `.text`, `.json()`, `.status_code=200`.
  - `RATE_LIMITS: dict[str, float]` (seconds between calls per `rate_key`).

- [ ] **Step 1: Write failing test** (`tests/common/test_http.py`)

```python
import json
from src.common.http import cached_get

def test_cache_hit_skips_network(tmp_path, monkeypatch):
    monkeypatch.setenv("IDLE_DATA_DIR", str(tmp_path))
    calls = {"n": 0}
    import src.common.http as http
    def fake_live(url, params, headers):
        calls["n"] += 1
        return '{"ok": true}', 200
    monkeypatch.setattr(http, "_live_get", fake_live)
    r1 = cached_get("http://x/api", source="t", rate_key="default")
    r2 = cached_get("http://x/api", source="t", rate_key="default")
    assert r1.json() == {"ok": True}
    assert r2.json() == {"ok": True}
    assert calls["n"] == 1  # second call served from cache
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/common/test_http.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `src/common/http.py`**

```python
import hashlib, json, os, time
from pathlib import Path
import requests

RATE_LIMITS = {"default": 1.5, "steamspy": 1.0, "reddit": 1.0, "scrape": 1.0}
_last_call: dict[str, float] = {}

def _data_dir() -> Path:
    return Path(os.environ.get("IDLE_DATA_DIR", "data")) / "raw"

def _key(url: str, params: dict | None) -> str:
    raw = url + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()

class _Cached:
    def __init__(self, text: str, status: int = 200):
        self.text = text; self.status_code = status
    def json(self): return json.loads(self.text)

def _live_get(url, params, headers):
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    return resp.text, resp.status_code

def _throttle(rate_key: str):
    gap = RATE_LIMITS.get(rate_key, 1.5)
    last = _last_call.get(rate_key, 0.0)
    wait = gap - (time.time() - last)
    if wait > 0: time.sleep(wait)
    _last_call[rate_key] = time.time()

def cached_get(url, *, source, params=None, headers=None, rate_key="default", refresh=False):
    cdir = _data_dir() / source
    cdir.mkdir(parents=True, exist_ok=True)
    cfile = cdir / f"{_key(url, params)}.cache"
    if cfile.exists() and not refresh:
        return _Cached(cfile.read_text(encoding="utf-8"))
    _throttle(rate_key)
    text, status = _live_get(url, params, headers)
    if status == 200:
        cfile.write_text(text, encoding="utf-8")
    return _Cached(text, status)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/common/test_http.py -v`
Expected: PASS. (Add `tests/common/__init__.py` and `src/common/__init__.py` empty files if import errors.)

- [ ] **Step 5: Commit**

```bash
git add src/common/ tests/common/
git commit -m "feat: cached rate-limited fetch helper"
```

---

### Task 3: Config file

**Files:**
- Create: `config/sources.yaml`, `tests/test_config.py`

**Interfaces:**
- Produces: `config/sources.yaml` with keys `seed_appids`, `steam_tags`, `theme_keywords`, `mechanic_keywords`, `art_keywords`, `subreddits`.

- [ ] **Step 1: Write failing test** (`tests/test_config.py`)

```python
import yaml
def test_config_has_required_keys():
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    for k in ["steam_tags", "theme_keywords", "mechanic_keywords",
              "art_keywords", "subreddits"]:
        assert k in cfg and cfg[k]
```

- [ ] **Step 2: Run, verify fail.** `.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → FAIL.

- [ ] **Step 3: Write `config/sources.yaml`**

```yaml
steam_tags: ["Idler", "Clicker", "Incremental"]
seed_appids: []   # populated by steamspy tag pull; manual seeds optional
theme_keywords:
  cookie: [cookie, bakery]
  space: [space, galaxy, planet, cosmic]
  mining: [mine, mining, dig, ore]
  rpg: [rpg, hero, dungeon, quest, adventure]
  factory: [factory, assembly, production, automate]
  money: [capitalist, tycoon, money, business, idle profit]
  fantasy: [magic, wizard, kingdom, realm]
  nature: [farm, garden, tree, forest]
mechanic_keywords:
  offline_progress: [offline, "while away", afk]
  prestige: [prestige, ascend, ascension, rebirth, reset]
  automation: [automate, automation, auto, manager]
  multiplier: [multiplier, boost, synergy]
art_keywords:
  pixel: [pixel, "8-bit", retro]
  hand_drawn: [hand-drawn, "hand drawn", cartoon]
  anime: [anime, manga]
  minimalist: [minimalist, minimal, clean]
  three_d: ["3d", "3-d"]
  cute: [cute, kawaii, adorable]
subreddits: ["incremental_games"]
```

- [ ] **Step 4: Run, verify pass.** → PASS.

- [ ] **Step 5: Commit.**
```bash
git add config/sources.yaml tests/test_config.py
git commit -m "feat: source/taxonomy config"
```

---

## Phase 1 — Master schema + Steam core

### Task 4: Master schema definition + validation

**Files:**
- Create: `src/common/schema.py`, `tests/common/test_schema.py`

**Interfaces:**
- Produces:
  - `COLUMNS: dict[str, str]` mapping column name → dtype string.
  - `empty_frame() -> pandas.DataFrame` with those columns and dtypes.
  - `validate(df) -> list[str]` returning a list of problems (empty list = valid): missing columns, any `owners_est` non-null with `owners_confidence` null, confidence not in {high,medium,low,None}.

- [ ] **Step 1: Failing test** (`tests/common/test_schema.py`)

```python
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
```

- [ ] **Step 2: Run, verify fail.** → FAIL.

- [ ] **Step 3: Implement `src/common/schema.py`**

```python
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
```

- [ ] **Step 4: Run, verify pass.** → PASS.

- [ ] **Step 5: Commit.**
```bash
git add src/common/schema.py tests/common/test_schema.py
git commit -m "feat: master schema + validation"
```

---

### Task 5: SteamSpy scraper (discovery + owner estimates)

**Files:**
- Create: `src/scrapers/__init__.py`, `src/scrapers/steamspy.py`, `tests/scrapers/test_steamspy.py`, `tests/scrapers/fixtures/steamspy_tag.json`

**Interfaces:**
- Consumes: `cached_get` from Task 2.
- Produces:
  - `fetch_tag(tag: str, refresh=False) -> dict[str, dict]` — SteamSpy `tag` endpoint, returns appid→record.
  - `parse_app(record: dict) -> dict` — maps a SteamSpy record to partial master fields: `id, name, owners_est, owners_confidence="medium", ccu_peak, review_count(=positive+negative), review_pct_positive, tags(list), price`.

- [ ] **Step 1: Save fixture** `tests/scrapers/fixtures/steamspy_tag.json`

```json
{"123": {"appid":123,"name":"Idle Test","owners":"500,000 .. 1,000,000",
"ccu":1200,"positive":900,"negative":100,"price":"199",
"tags":{"Idler":50,"Clicker":30}}}
```

- [ ] **Step 2: Failing test** (`tests/scrapers/test_steamspy.py`)

```python
import json
from src.scrapers.steamspy import parse_app

def test_parse_app_maps_fields():
    rec = json.load(open("tests/scrapers/fixtures/steamspy_tag.json"))["123"]
    out = parse_app(rec)
    assert out["id"] == "123"
    assert out["owners_est"] == 750000          # midpoint of range
    assert out["owners_confidence"] == "medium"
    assert out["review_count"] == 1000
    assert out["review_pct_positive"] == 90.0
    assert out["price"] == 1.99
    assert "Idler" in out["tags"]
```

- [ ] **Step 3: Run, verify fail.** → FAIL.

- [ ] **Step 4: Implement `src/scrapers/steamspy.py`**

```python
from src.common.http import cached_get

BASE = "https://steamspy.com/api.php"

def fetch_tag(tag: str, refresh=False) -> dict:
    r = cached_get(BASE, source="steamspy", params={"request": "tag", "tag": tag},
                   rate_key="steamspy", refresh=refresh)
    return r.json()

def _owners_midpoint(s: str) -> int | None:
    try:
        lo, hi = [int(x.strip().replace(",", "")) for x in s.split("..")]
        return (lo + hi) // 2
    except Exception:
        return None

def parse_app(rec: dict) -> dict:
    pos, neg = rec.get("positive", 0), rec.get("negative", 0)
    total = pos + neg
    price = rec.get("price")
    return {
        "id": str(rec.get("appid")),
        "source": "steam",
        "name": rec.get("name"),
        "owners_est": _owners_midpoint(rec.get("owners", "")),
        "owners_confidence": "medium",
        "ccu_peak": rec.get("ccu"),
        "review_count": total or None,
        "review_pct_positive": round(100 * pos / total, 1) if total else None,
        "price": (int(price) / 100) if price not in (None, "") else None,
        "is_free": price in ("0", 0),
        "tags": list((rec.get("tags") or {}).keys()),
        "platform": "pc",
    }
```

- [ ] **Step 5: Run, verify pass.** → PASS.

- [ ] **Step 6: Commit.**
```bash
git add src/scrapers/steamspy.py tests/scrapers/
git commit -m "feat: steamspy scraper + owner-estimate parsing"
```

---

### Task 6: Steam appdetails + reviews + news enricher

**Files:**
- Create: `src/scrapers/steam.py`, `tests/scrapers/test_steam.py`, fixtures `steam_appdetails.json`, `steam_news.json`

**Interfaces:**
- Consumes: `cached_get`.
- Produces:
  - `fetch_details(appid) -> dict` (Steam storefront `appdetails`).
  - `parse_details(payload, appid) -> dict` → `release_date, short_desc, is_free, price, screenshot_count, genres/categories→raw tags, business_model_signal(has_iap: bool)`.
  - `fetch_news(appid, count=20) -> list[dict]` (`ISteamNews`).
  - `update_cadence(news_items) -> float | None` — avg days between announcements over trailing window; `None` if <2 items.

- [ ] **Step 1: Fixtures.** Save a trimmed real `appdetails` response for one appid (keys: `success`, `data.release_date.date`, `data.short_description`, `data.is_free`, `data.price_overview.final`, `data.screenshots[]`, `data.categories[]` incl. one with `description:"In-App Purchases"`). Save a `news.appnews.newsitems[]` list with 3 items having unix `date` fields ~14 days apart.

- [ ] **Step 2: Failing test** (`tests/scrapers/test_steam.py`)

```python
import json
from src.scrapers.steam import parse_details, update_cadence

def test_parse_details():
    payload = json.load(open("tests/scrapers/fixtures/steam_appdetails.json"))
    out = parse_details(payload, "123")
    assert out["is_free"] in (True, False)
    assert out["screenshot_count"] >= 1
    assert isinstance(out["has_iap"], bool)

def test_update_cadence_days():
    news = json.load(open("tests/scrapers/fixtures/steam_news.json"))["appnews"]["newsitems"]
    cad = update_cadence(news)
    assert 10 <= cad <= 18   # ~14-day spacing
```

- [ ] **Step 3: Run, verify fail.** → FAIL.

- [ ] **Step 4: Implement `src/scrapers/steam.py`**

```python
from statistics import mean
from src.common.http import cached_get

DETAILS = "https://store.steampowered.com/api/appdetails"
NEWS = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

def fetch_details(appid, refresh=False) -> dict:
    r = cached_get(DETAILS, source="steam_details",
                   params={"appids": appid, "l": "english"},
                   rate_key="default", refresh=refresh)
    return r.json()

def parse_details(payload: dict, appid) -> dict:
    node = payload.get(str(appid)) or next(iter(payload.values()))
    if not node.get("success"):
        return {"id": str(appid)}
    d = node["data"]
    cats = [c.get("description", "") for c in d.get("categories", [])]
    price = d.get("price_overview", {}).get("final")
    return {
        "id": str(appid),
        "release_date": d.get("release_date", {}).get("date"),
        "short_desc": d.get("short_description"),
        "is_free": d.get("is_free", False),
        "price": (price / 100) if price else (0.0 if d.get("is_free") else None),
        "screenshot_count": len(d.get("screenshots", [])),
        "has_iap": any("In-App Purchase" in c for c in cats),
        "raw_genres": [g.get("description") for g in d.get("genres", [])],
    }

def fetch_news(appid, count=20, refresh=False) -> list:
    r = cached_get(NEWS, source="steam_news",
                   params={"appid": appid, "count": count, "format": "json"},
                   rate_key="default", refresh=refresh)
    return r.json().get("appnews", {}).get("newsitems", [])

def update_cadence(news_items: list) -> float | None:
    dates = sorted(i["date"] for i in news_items if "date" in i)
    if len(dates) < 2:
        return None
    gaps = [(dates[i+1] - dates[i]) / 86400 for i in range(len(dates) - 1)]
    return round(mean(gaps), 1)
```

- [ ] **Step 5: Run, verify pass.** → PASS.

- [ ] **Step 6: Commit.**
```bash
git add src/scrapers/steam.py tests/scrapers/test_steam.py tests/scrapers/fixtures/
git commit -m "feat: steam appdetails/reviews/news enricher"
```

---

## Phase 2 — Taxonomy + master build

### Task 7: Taxonomy classifier

**Files:**
- Create: `src/pipeline/__init__.py`, `src/pipeline/taxonomy.py`, `tests/pipeline/test_taxonomy.py`

**Interfaces:**
- Consumes: keyword maps from `config/sources.yaml`.
- Produces:
  - `classify(text: str, tags: list[str], keyword_map: dict) -> list[str]` — returns every category whose keyword appears in lowercased `text`+tags.
  - `pick_theme(text, tags, cfg) -> str|None` (first/highest-hit theme).
  - `pick_mechanics(text, tags, cfg) -> list[str]`.
  - `pick_art_style(tags, cfg) -> str|None`.
  - `business_model(is_free: bool, has_iap: bool, price: float|None) -> str` → one of `premium|free-premium|f2p+iap|paid+iap`.

- [ ] **Step 1: Failing test** (`tests/pipeline/test_taxonomy.py`)

```python
from src.pipeline.taxonomy import classify, business_model

CFG = {"space": ["space", "galaxy"], "mining": ["mine", "ore"]}

def test_classify_multi_hit():
    out = classify("A space mining idle game", ["Galaxy"], CFG)
    assert set(out) == {"space", "mining"}

def test_business_model_buckets():
    assert business_model(True, True, 0.0) == "f2p+iap"
    assert business_model(True, False, 0.0) == "free-premium"
    assert business_model(False, True, 4.99) == "paid+iap"
    assert business_model(False, False, 4.99) == "premium"
```

- [ ] **Step 2: Run, verify fail.** → FAIL.

- [ ] **Step 3: Implement `src/pipeline/taxonomy.py`**

```python
def classify(text: str, tags: list[str], keyword_map: dict) -> list[str]:
    hay = (text or "").lower() + " " + " ".join(t.lower() for t in (tags or []))
    hits = []
    for cat, words in keyword_map.items():
        if any(w.lower() in hay for w in words):
            hits.append(cat)
    return hits

def pick_theme(text, tags, cfg):
    hits = classify(text, tags, cfg["theme_keywords"])
    return hits[0] if hits else None

def pick_mechanics(text, tags, cfg):
    return classify(text, tags, cfg["mechanic_keywords"])

def pick_art_style(tags, cfg):
    hits = classify("", tags, cfg["art_keywords"])
    return hits[0] if hits else None

def business_model(is_free: bool, has_iap: bool, price) -> str:
    if is_free:
        return "f2p+iap" if has_iap else "free-premium"
    return "paid+iap" if has_iap else "premium"
```

- [ ] **Step 4: Run, verify pass.** → PASS.

- [ ] **Step 5: Commit.**
```bash
git add src/pipeline/taxonomy.py tests/pipeline/
git commit -m "feat: taxonomy + business-model classifier"
```

---

### Task 8: Normalize + build master table

**Files:**
- Create: `src/pipeline/normalize.py`, `src/pipeline/build_master.py`, `tests/pipeline/test_normalize.py`

**Interfaces:**
- Consumes: `steamspy.parse_app`, `steam.parse_details`, `steam.update_cadence`, `taxonomy.*`, `schema.empty_frame/validate`.
- Produces:
  - `merge_records(steamspy_part: dict, steam_part: dict, cfg) -> dict` — one full master row (all schema columns; missing→None), with taxonomy + business_model + update_cadence filled.
  - `build(cfg, limit=None, refresh=False) -> pandas.DataFrame` — orchestrates: SteamSpy tag pull → per-app Steam enrich → merge → DataFrame → `validate` (raises if problems) → writes `data/processed/games.parquet`.

- [ ] **Step 1: Failing test** (`tests/pipeline/test_normalize.py`)

```python
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
```

- [ ] **Step 2: Run, verify fail.** → FAIL.

- [ ] **Step 3: Implement `normalize.py`** (merge_records) **and** `build_master.py` (build loop)

```python
# src/pipeline/normalize.py
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
```

```python
# src/pipeline/build_master.py
from pathlib import Path
import pandas as pd, yaml
from src.scrapers import steamspy, steam
from src.pipeline.normalize import merge_records
from src.common.schema import empty_frame, validate

def build(cfg, limit=None, refresh=False) -> pd.DataFrame:
    seen, rows = {}, []
    for tag in cfg["steam_tags"]:
        seen.update(steamspy.fetch_tag(tag, refresh=refresh))
    appids = list(seen)[:limit] if limit else list(seen)
    for appid in appids:
        ss = steamspy.parse_app(seen[appid])
        det = steam.parse_details(steam.fetch_details(appid, refresh=refresh), appid)
        news = steam.fetch_news(appid, refresh=refresh)
        row = merge_records(ss, det, cfg)
        row["update_cadence"] = steam.update_cadence(news)
        row["release_news"] = [n.get("date") for n in news]
        rows.append(row)
    df = pd.concat([empty_frame(), pd.DataFrame(rows)], ignore_index=True)
    probs = validate(df)
    if probs:
        raise ValueError("schema validation failed: " + "; ".join(probs))
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet("data/processed/games.parquet")
    return df
```

- [ ] **Step 4: Run, verify pass.** → PASS.

- [ ] **Step 5: Commit.**
```bash
git add src/pipeline/normalize.py src/pipeline/build_master.py tests/pipeline/test_normalize.py
git commit -m "feat: normalize records + build master parquet"
```

- [ ] **Step 6: Live smoke run (manual, network).** Run a tiny real build to prove the pipeline end-to-end against live APIs:

```
.venv\Scripts\python.exe -c "import yaml; from src.pipeline.build_master import build; print(build(yaml.safe_load(open('config/sources.yaml')), limit=15).shape)"
```
Expected: prints a shape like `(15, 21)` and writes `data/processed/games.parquet`. If an endpoint 404s/rate-limits, confirm cache files appeared under `data/raw/` and re-run (cache serves the hits). Record any source quirks in README.

---

## Phase 3 — Secondary source layers

> Each scraper follows the **same pattern as Task 5/6**: a `fetch_*` using `cached_get(..., rate_key="scrape")` + a pure `parse_*` tested against a saved HTML fixture. Parse functions emit partial master rows with `source` set and `owners_confidence` per source quality. Keep each under 150 lines.

### Task 9: itch.io incremental scraper

**Files:** Create `src/scrapers/itch.py`, `tests/scrapers/test_itch.py`, fixture `itch_browse.html`.

**Interfaces:**
- Produces `parse_browse(html: str) -> list[dict]` → rows with `id="itch:<slug>"`, `name`, `is_free`, `price`, `tags`, `source="itch"`, `platform="web"`, `owners_confidence=None` (no owner data). Owner/review fields stay None.

- [ ] **Step 1:** Save `tests/scrapers/fixtures/itch_browse.html` — a trimmed copy of `https://itch.io/games/tag-incremental` grid markup (2 `div.game_cell` blocks with `a.title`, `.game_text`, price node).
- [ ] **Step 2:** Failing test: `parse_browse(open(fixture).read())` returns ≥2 rows, first has non-empty `name` and `id.startswith("itch:")`.
- [ ] **Step 3:** Implement with BeautifulSoup (`lxml` parser): select `div.game_cell`, pull title/href/price; free if no price node.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: itch.io incremental scraper`.

### Task 10: Kongregate idle scraper

**Files:** Create `src/scrapers/kongregate.py`, `tests/scrapers/test_kongregate.py`, fixture `kong_idle.html`.

**Interfaces:** Produces `parse_listing(html) -> list[dict]` → `id="kong:<slug>"`, `name`, `tags`, optional rating→`review_pct_positive` (confidence `low`), `source="kongregate"`, `platform="web"`.

- [ ] Steps mirror Task 9 (fixture → failing test asserting ≥1 row with `id.startswith("kong:")` → BeautifulSoup impl → pass → commit `feat: kongregate idle scraper`). If Kongregate markup is JS-rendered and not in static HTML, record that limitation in README and have `parse_listing` return `[]` gracefully (test asserts empty list on empty-grid fixture).

### Task 11: Reddit qualitative pull

**Files:** Create `src/scrapers/reddit.py`, `tests/scrapers/test_reddit.py`, fixture `reddit_top.json`.

**Interfaces:**
- Consumes `cached_get` against `https://www.reddit.com/r/{sub}/top.json?t=year&limit=100` with header `User-Agent: idle-market-analysis/0.1`.
- Produces:
  - `fetch_top(sub, refresh=False) -> list[dict]` (post nodes).
  - `extract_sentiment_terms(posts, vocab: dict[str,list[str]]) -> dict[str,int]` — counts mentions of love/hate vocab (e.g. `loved:["addictive","satisfying","offline"]`, `hated:["paywall","ads","grind","timer"]`) across titles+selftext. Feeds `quality.py` qualitative section.

- [ ] **Step 1:** Save `reddit_top.json` (trimmed `data.children[].data` with `title`, `selftext`).
- [ ] **Step 2:** Failing test: `extract_sentiment_terms(posts, {"hated":["paywall"]})` returns `{"hated": N}` with N≥1 for a fixture post containing "paywall".
- [ ] **Step 3:** Implement counting (case-insensitive substring over title+selftext).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: reddit qualitative sentiment pull`.

---

## Phase 4 — Analysis

### Task 12: Analysis base helpers

**Files:** Create `src/analysis/__init__.py`, `src/analysis/base.py`, `tests/analysis/test_base.py`.

**Interfaces:**
- Produces:
  - `load_master(path="data/processed/games.parquet") -> pd.DataFrame`.
  - `weighted_quality(df, by: str) -> pd.DataFrame` — group by column `by`, return `count`, `mean_positive` (mean of `review_pct_positive`), `total_owners` (sum `owners_est`, high+medium conf only), `weighted_score` (owners-weighted mean positive). Drops null `by`.
  - `to_records(df) -> list[dict]` JSON-safe (NaN→None).

- [ ] **Step 1:** Failing test builds a 4-row DataFrame with two themes and asserts `weighted_quality(df,"theme")` returns one row per theme with correct `count` and `mean_positive`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with pandas groupby; guard div-by-zero owners.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: analysis base helpers`.

### Task 13: Analysis modules (one test+impl per module)

> All modules share the shape: `def run(df) -> dict` returning JSON-safe results, written by `run_all.py` to `data/analysis/<name>.json`. Each gets its own failing test asserting the key metric on a small synthetic DataFrame, then a minimal impl, then commit. Build them in this order:

- [ ] **topics.py** — `run(df)`: theme & mechanic frequency + owner-weighting via `weighted_quality`. Test: most-common theme is correct. Commit.
- [ ] **performance.py** — per-theme `mean_positive` and `weighted_score`, ranked. Test: ranking order. Commit.
- [ ] **gaps.py** — `run(df)`: per-theme `supply=count`, `demand=weighted_score`; flag `underserved` where supply ≤ 25th pct and demand ≥ median. Test: a hand-built low-supply/high-demand theme is flagged. Commit.
- [ ] **quality.py** — correlate binary features (`offline_progress in mechanics`, `prestige in mechanics`, `is_free`) vs `review_pct_positive` → mean delta per feature; attach Reddit `extract_sentiment_terms` output. Test: feature present→higher mean produces positive delta. Commit.
- [ ] **monetization.py** — `weighted_quality(df,"business_model")` + price-bucket vs owners curve (bucket price into [0,1,3,5,10,20,∞]). Test: bucket counts. Commit.
- [ ] **art.py** — `weighted_quality(df,"art_style")`. Test: per-art-style row count. Commit.
- [ ] **updates.py** — bucket `update_cadence` (active ≤30d, occasional ≤120d, abandoned >120d / None) vs `mean_positive` + `total_owners`. Test: bucketing thresholds. Commit.
- [ ] **trends.py** — parse year from `release_date`; releases-per-year + median `weighted_score` per year; rising sub-genre = theme whose recent-3-year mean score > older mean. Test: year parsing + one rising theme. Commit.
- [ ] **naming.py** — classify title pattern (`idle_x` if name startswith/contains "idle", `x_clicker` if contains "clicker", else `creative`); mean score per pattern. Test: pattern classification. Commit.

### Task 14: run_all orchestrator

**Files:** Create `src/analysis/run_all.py`, `tests/analysis/test_run_all.py`.

**Interfaces:** Produces `main(master_path, out_dir="data/analysis")` — loads master, calls each module's `run`, writes `<name>.json`. Returns dict of module→output path.

- [ ] **Step 1:** Failing test: with a tiny parquet, `main` writes one JSON per module and each is valid JSON.
- [ ] **Step 2-4:** Implement loop over a registry list of (name, module.run); `json.dump` with `default=str`. Run → PASS.
- [ ] **Step 5:** Commit `feat: analysis orchestrator`.

---

## Phase 5 — Static site

### Task 15: Site builder

**Files:** Create `src/site/__init__.py`, `src/site/build.py`, `src/site/templates/report.html.j2`, `src/site/templates/methodology.html.j2`, `tests/site/test_build.py`.

**Interfaces:**
- Consumes: `data/analysis/*.json`.
- Produces:
  - `make_figures(analysis: dict) -> dict[str, str]` — builds Plotly figures (theme treemap from topics; gap scatter supply-vs-demand from gaps; bar of feature deltas from quality; monetization bars; art bars; update-bucket bars; releases-per-year line from trends) and returns `name → fig.to_html(full_html=False, include_plotlyjs="cdn")`.
  - `build_site(analysis_dir="data/analysis", out="docs") -> None` — loads JSONs, renders `report.html.j2` (narrative + embedded figure divs + inline n/confidence captions) to `docs/index.html` and `methodology.html.j2` to `docs/methodology.html`.

- [ ] **Step 1:** Failing test: given a temp `analysis_dir` with minimal `topics.json`+`gaps.json`, `build_site` writes `docs/index.html` containing the string `Plotly` and a chart div id.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `make_figures` (guard missing keys → skip figure) + Jinja2 render. Templates include a methodology page listing every confidence caveat from the spec's "Known limitations".
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: static site builder with plotly charts`.

- [ ] **Step 6: Full pipeline dry run (manual).** With the Phase-2 live parquet present:
```
.venv\Scripts\python.exe -m src.analysis.run_all
.venv\Scripts\python.exe -c "from src.site.build import build_site; build_site()"
```
Expected: `docs/index.html` opens in a browser and renders charts with real data. Eyeball that captions show n + confidence. Record anything thin.

### Task 16: README + GitHub Pages wiring

**Files:** Create `README.md`; Modify `.gitignore` if needed.

- [ ] **Step 1:** Write `README.md`: project goal, the `scrape→normalize→analyze→render` flow, exact run commands (build master, run analysis, build site), known limitations (copy spec's list: mobile weakest, scrapers brittle, owner counts estimates, SteamDB excluded), and the "Building an Idler: What the Data Says" summary placeholder pointing at the site.
- [ ] **Step 2:** Document enabling GitHub Pages: repo Settings → Pages → Source = `main` branch `/docs` folder.
- [ ] **Step 3:** Commit `docs: README + pages instructions`.
- [ ] **Step 4 (user action, not scripted):** Create GitHub remote, push, enable Pages. (Outward action — left to the user.)

---

## Self-Review

**Spec coverage:** master map (topics/performance/gaps/quality → Tasks 13), builder dimensions (monetization/art/updates/trends/naming/quality → Tasks 13), schema incl. art_style/business_model/update_cadence/release_news (Task 4), Steam News for cadence not SteamDB (Task 6), confidence flags (Tasks 2/4/5, enforced in validate), secondary layers itch/kongregate/reddit (Tasks 9-11), static HTML + methodology/caveats page (Task 15), GitHub Pages (Task 16). All spec sections map to a task. ✔

**Placeholder scan:** Phase 3 & Task 13 modules use a stated shared pattern with the full reference implementation given in Tasks 5/6/12 and a concrete per-module metric + test assertion named for each — no bare "implement later". Code-bearing foundational tasks (1-8,12,14,15) carry complete code. ✔

**Type consistency:** `cached_get` signature stable across all scrapers; `parse_app`/`parse_details` field names match `merge_records` reads and `COLUMNS`; `weighted_quality`/`run(df)->dict` consistent across analysis + `run_all`. ✔

**Known intentional thinness:** Task 13's nine modules are specified by interface + metric + test rather than full code bodies, because they share one proven pattern (Task 12 `weighted_quality` + groupby). If executing via subagents, each still gets its own red→green→commit cycle.
