# Idle / Incremental Game Market Analysis — Design Spec

**Date:** 2026-06-18
**Status:** Approved (brainstorming complete)

## Goal

Produce a data-driven analysis + interactive report of the idle/incremental game
market. Two audiences in one deliverable:

1. **Market map** — popular topics, performance by topic, untapped niches.
2. **Builder's guide** — what the data says to someone *making* an idle game:
   mechanics, art, monetization, update cadence, pricing, timing.

Ships as a static HTML site on GitHub Pages, plus reproducible data pipeline.

## Decisions (locked during brainstorming)

| Axis | Decision |
|------|----------|
| Data sources | Wide net, reputable. Steam-anchored, other sources layered by data quality. |
| Acquisition | Free + light scraping. $0, mostly reproducible. No paid data tools. |
| Deliverable | Static HTML site (Plotly charts + written report) for GitHub Pages. |
| Pipeline shape | Approach A: Steam-anchored, layered, confidence-flagged. |
| Stack | Python: requests, BeautifulSoup, pandas, plotly. Windows host. |

## Architecture — Approach A (Steam-anchored, layered)

One-way data flow:

```
scrape  →  normalize  →  analyze  →  render
(raw)      (master)      (outputs)   (site)
```

Steam is the core dataset (free API + SteamSpy: tags, reviews, price, owner
estimates, dates, news/updates). Other sources are layers ranked by data
quality. Every estimate carries a confidence flag so weak data is never
silently compared to strong.

### Repo structure

```
/src
  /scrapers      steam.py, steamspy.py, itch.py, kongregate.py, reddit.py
  /pipeline      normalize.py, enrich.py, taxonomy.py
  /analysis      topics.py, performance.py, gaps.py, quality.py,
                 monetization.py, art.py, updates.py, trends.py
  /site          build.py  (renders HTML + Plotly)
/data
  /raw           per-source cached dumps (large files gitignored)
  /processed     games.parquet (master table), *.csv
/docs            GitHub Pages root (built HTML)
/config          sources.yaml (tags, rate limits, endpoints)
/tests
```

- Each scraper: isolated, one job — fetch + cache raw. Caches to disk so reruns
  never re-hit an API.
- Pipeline: normalize all sources into one master schema; derive taxonomy.
- Analysis: reads master table only. Each module answers a question group.
- Site: reads analysis outputs only.

## Master data schema (one row per game)

```
id, source, name, release_date, price, is_free,
tags[], short_desc, screenshot_count,
review_count, review_pct_positive,
owners_est, owners_confidence, ccu_peak,
theme, mechanics[], art_style, business_model,
release_news[], update_cadence,
platform
```

- `*_confidence` on every estimate. Steam = high; mobile = low; web = medium.
- `theme` (cookie/space/mining/RPG/factory/…) and `mechanics[]`
  (prestige, offline-progress, automation, …) derived in `taxonomy.py` from
  tags + description keywords.
- `art_style` derived from Steam art tags (pixel/hand-drawn/anime/minimalist/
  3D/retro/cute). Confidence medium — tags noisy.
- `business_model` bucket: premium / free-premium / f2p+IAP / paid+IAP, from
  Steam `is_free` + IAP flag + price. High confidence on Steam, low on mobile.
- `update_cadence` from Steam News API (`ISteamNews`) announcement history —
  proxy for update frequency + dev communication. Confidence medium.

## Analysis modules → questions answered

### Market map (original 4)
- **topics.py** — theme/mechanic frequency, weighted by owners + reviews. What's crowded.
- **performance.py** — review-positivity + owner estimate per theme. Loved vs merely numerous.
- **gaps.py** — high demand (engagement/positivity) × low supply (few titles). The gap map; supply-vs-quality scatter.
- **quality.py** — feature correlations vs review score (offline progress, prestige depth, price, free-vs-paid). Plus Reddit qualitative.

### Builder's guide (dev-facing)

**Market entry**
- Saturated vs starving themes (gap map, framed "where do I build").
- Free vs paid: which monetization wins by score AND owners, per theme.
- Best launch window: release-month vs first-year trajectory.

**Retention / what's loved**
- Mechanics correlated with high positivity (offline progress, prestige/ascension, automation depth, multi-layer prestige).
- Mechanics correlated with negative reviews (forced ads, energy timers, paywalls, p2w) — pulled from Reddit + negative review text.
- Offline-progress presence → score delta (binary feature test).

**Scope / cost**
- Solo-dev viability: review-count distribution, realistic ceiling.
- Price sweet spot: price vs owners curve, revenue-maximizing point.
- Does polish matter: screenshot count / "graphics" mentions vs score (weak, flagged).

**Trend / timing**
- Genre growing or saturating: releases/year + median success over time.
- Rising vs declining sub-genres: recent-release momentum, not just volume.
- Tag co-occurrence: which combos with "incremental" punch above weight (RPG, factory, clicker).

**Naming / discovery**
- Title/keyword patterns in top performers ("Idle X" vs "X Clicker" vs creative names).

**Art / business model / updates (added dimensions)**
- **art.py** — art-style → score + owners. Does pixel-art / minimalist help or hurt in idle space.
- **monetization.py** — full business-model buckets vs score and owners, per theme. Free-with-IAP vs honest-premium.
- **updates.py** — News-API update cadence vs score / long-tail owners. Live-service idler vs ship-and-forget.

Report gets a dedicated **"Building an Idler: What the Data Says"** section.

## Site (GitHub Pages)

Single self-contained static site in `/docs`:
- Landing report: written narrative covering both audiences.
- Interactive Plotly charts: theme treemap, gap scatter, quality correlations,
  genre-growth timeline, monetization/art/update breakdowns.
- Methodology + confidence-caveats page — report stays honest about thin data.
- No server. Charts embed n + confidence inline.

## Errors / testing / honesty

- Scrapers: rate-limit + retry + disk cache. One source fails → pipeline
  continues, logs the gap.
- Tests: master-table schema validation; taxonomy classifier spot-checks;
  scraper parse tests against saved HTML fixtures.
- Every chart carries n + confidence flag.

## Known limitations (stated up front in report)

- **Mobile revenue = weakest leg.** No paid tools (Sensor Tower/data.ai), so
  mobile download/revenue is estimate-only, clearly flagged.
- **Scrapers are brittle** — break if portal HTML changes.
- **Owner counts are estimates**, not ground truth (SteamSpy modeling).
- **SteamDB patch history deliberately NOT scraped** (Cloudflare / ToS).
  Update cadence uses the official Steam News API instead.
- Art-style and theme classification are tag-derived heuristics, medium
  confidence.

## Out of scope (YAGNI)

- Paid data sources / API keys.
- Live/auto-refreshing dashboard server (static snapshot only).
- Per-game deep dives beyond the aggregate analysis.
