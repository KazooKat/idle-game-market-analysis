# Idle / Incremental Game Market Analysis

A data-driven analysis of the idle/incremental game market on Steam, with
supplementary coverage from itch.io, Kongregate, and Reddit. The project
produces an interactive static report hosted on GitHub Pages — both a market
map (popular themes, underserved niches, performance by topic) and a
builder's guide ("what the data says to someone making an idle game").

---

## Architecture

```
scrape  →  normalize  →  analyze  →  render
(raw)      (master)      (outputs)   (site)
```

**Steam is the quantitative spine.** SteamSpy tag pulls (`Idler`, `Clicker`,
`Incremental`) seed the catalogue; the Steam Details and News APIs add price,
reviews, release date, and update history. All of this normalizes into a single
`games.parquet` master table.

**Supplementary sources** — itch.io, Kongregate, Reddit — are layered on top
for breadth and qualitative context. They are *not* mixed into Steam comparison
tables because their data is thinner and of different confidence.

Nine analysis modules (`topics`, `performance`, `gaps`, `quality`,
`monetization`, `art`, `updates`, `trends`, `naming`) each read the master
table and write a JSON file. The site builder reads those JSONs and renders
two HTML pages (report + methodology) with Plotly charts via Jinja2 templates.

---

## Setup

Requires **Python 3.11+** (development host: 3.14).

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell
# or: .venv\Scripts\activate.bat  (cmd)

# Install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## How to Run

Run these steps in order from the project root.

### 1. Build the master dataset (Steam scrape)

```powershell
.venv\Scripts\python.exe -c "import yaml; from src.pipeline.build_master import build; build(yaml.safe_load(open('config/sources.yaml')))"
```

This hits the SteamSpy tag API and Steam Details/News APIs. It is
**rate-limited** — the full catalogue (hundreds of games) can take a long time.
Raw responses are cached to `data/raw/` so a resumed run skips already-fetched
apps. Output: `data/processed/games.parquet`.

### 2. Run analysis modules

```powershell
.venv\Scripts\python.exe -m src.analysis.run_all
```

Reads `games.parquet`, runs all nine analysis modules, writes JSON files to
`data/analysis/`. Per-module errors are caught and written as `{"error": ...}`
so the orchestration always completes.

### 3. Gather supplementary data

```powershell
.venv\Scripts\python.exe -m src.analysis.supplementary
```

Scrapes itch.io and Kongregate browse pages, reads cached Reddit data if
present, writes `data/analysis/supplementary.json`.

### 4. Build the site

```powershell
.venv\Scripts\python.exe -c "from src.site.build import build_site; build_site()"
```

Reads all `data/analysis/*.json` files and renders `docs/index.html` and
`docs/methodology.html` via Jinja2 + Plotly.

### 5. Open the report

Open `docs/index.html` in a browser.

---

## Project Layout

```
src/
  scrapers/     steam.py, steamspy.py, itch.py, kongregate.py, reddit.py
  pipeline/     build_master.py, normalize.py, enrich.py, taxonomy.py
  analysis/     run_all.py, base.py, topics.py, performance.py, gaps.py,
                quality.py, monetization.py, art.py, updates.py, trends.py,
                naming.py, supplementary.py
  site/         build.py, templates/
config/
  sources.yaml  Steam tags, theme/mechanic/art keywords, subreddits
data/           (gitignored)
  raw/          per-source cached HTTP responses
  processed/    games.parquet (master table)
  analysis/     per-module JSON outputs
docs/           GitHub Pages root — built HTML files live here
tests/
```

---

## Testing

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The test suite covers scrapers, pipeline normalization, analysis modules, and
the site builder (approximately 130 passing tests).

---

## Known Limitations (be honest)

- **Owner counts are estimates.** SteamSpy models owner counts from
  achievement data; they are not verified sales figures. Treat them as
  order-of-magnitude indicators only.

- **Mobile not covered.** iOS/Android stores have no free, reliable data
  source. The entire mobile idle market is absent from this analysis.

- **Kongregate ratings are low-confidence and not comparable to Steam
  review percentages.** Kongregate uses 1–5 star ratings; these are mapped
  to a percentage for display only. Do not compare them to Steam's
  `review_pct_positive`.

- **Reddit live data unavailable.** `r/incremental_games` `top.json` returns
  HTTP 403 without OAuth. Qualitative sentiment is not collected unless you
  supply cached Reddit API responses in `data/raw/reddit/`.

- **Scrapers are brittle.** itch.io and Kongregate scrapers parse static HTML
  and JSON-LD. If either site changes its markup, the parsers will break.
  Coverage also reflects one page of results, not the full catalogue.

- **SteamDB deliberately excluded.** SteamDB patch history is protected by
  Cloudflare and has restrictive ToS. Update cadence in this project uses the
  official Steam News API instead.

- **Weighted score biases toward popular games.** The formula
  `review_pct_positive × log(1 + total_owners)` rewards games that are both
  popular and well-reviewed; a niche gem with few owners will score lower than
  a mediocre hit.

---

## "Building an Idler: What the Data Says"

The rendered report (`docs/index.html`) contains a full builder's guide drawn
from the analysis: which mechanics correlate with positive reviews, which
themes are underserved, how update cadence and art style relate to player
sentiment, and how pricing and business model affect performance. Open the site
to read the findings — no statistics are hardcoded here because the data
harvest drives the narrative dynamically.

---

## GitHub Pages Setup

1. Push the repository to GitHub (with `docs/` committed — it is the Pages
   root, not gitignored).
2. Go to **Settings → Pages** in your GitHub repository.
3. Under **Source**, select **Deploy from a branch**.
4. Set branch to `main` and folder to `/docs`.
5. Save. GitHub will publish the site at
   `https://<your-username>.github.io/<repo-name>/`.

The report lands at `docs/index.html`; the methodology page at
`docs/methodology.html`. Both are built by `src/site/build.py` and should be
committed after each pipeline run that produces new results.
