"""
src/site/build.py
Static site builder for the idle-game-market analysis report.

Public API
----------
make_figures(analysis: dict) -> dict[str, str]
    Build Plotly figures from the analysis dict (keyed by module stem).
    Each figure is guarded: if its source data is missing or empty, the
    figure is silently skipped (no crash).
    Returns {figure_name: html_div_string}.

build_site(analysis_dir="data/analysis", out="docs") -> None
    Load all *.json files from analysis_dir, call make_figures, render two
    Jinja2 templates into out/:
      index.html       – interactive report with charts + narrative
      methodology.html – data sources, caveats, known limitations

HONESTY POLICY
--------------
- Owner counts are SteamSpy estimates (noted in captions).
- Kongregate ratings are star-derived, low confidence, not comparable to
  Steam review %.
- Mobile not covered.
- Reddit sentiment unavailable if supplementary.reddit.available is False.
- Narrative prose pulls numbers from JSON; no hardcoded statistics.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_list(data: dict, *keys: str) -> list:
    """Return nested list at data[keys[0]][keys[1]]... or [] if missing/empty."""
    obj: Any = data
    for k in keys:
        if not isinstance(obj, dict):
            return []
        obj = obj.get(k)
    if not isinstance(obj, list) or len(obj) == 0:
        return []
    return obj


def _fig_to_div(fig: go.Figure) -> str:
    """Serialise a Plotly figure to an HTML div string (no inline Plotly JS).

    The Plotly library is loaded once in the <head> of the template via a
    single <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"> tag.
    """
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ---------------------------------------------------------------------------
# Individual figure builders (each guarded)
# ---------------------------------------------------------------------------


def _fig_theme_bar(analysis: dict) -> str | None:
    """Bar chart: theme vs total_owners (SteamSpy estimate), coloured by weighted_score.

    Bars are sorted descending by total_owners.  Text labels are removed from the
    bars (the colorbar already encodes weighted_score).  A rich hovertemplate
    shows count, owners, and weighted_score on hover.
    """
    rows = _safe_list(analysis.get("topics", {}), "themes")
    if not rows:
        return None

    # Sort descending by total_owners
    rows_sorted = sorted(rows, key=lambda r: r.get("total_owners", 0) or 0, reverse=True)
    themes = [r.get("theme", "") for r in rows_sorted]
    owners = [r.get("total_owners", 0) or 0 for r in rows_sorted]
    counts = [r.get("count", 0) or 0 for r in rows_sorted]
    scores = [r.get("weighted_score") for r in rows_sorted]

    fig = go.Figure(
        go.Bar(
            x=themes,
            y=owners,
            marker=dict(
                color=scores,
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Weighted score"),
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Games: %{customdata[0]}<br>"
                "Est. owners: %{y:,}<br>"
                "Weighted score: %{customdata[1]}<extra></extra>"
            ),
            customdata=list(zip(counts, [f"{s:.1f}" if s is not None else "n/a" for s in scores])),
        )
    )
    n_themes = len(themes)
    fig.update_layout(
        title="Themes by estimated reach (SteamSpy owner counts — modeled estimates)",
        xaxis_title="Theme",
        yaxis_title="Total estimated owners",
        height=max(420, 300 + n_themes * 12),
        margin=dict(t=60, b=120),
    )
    return _fig_to_div(fig)


def _fig_gap_scatter(analysis: dict) -> str | None:
    """Scatter: supply (log) vs demand (weighted_score); underserved highlighted.

    Only themes with non-None demand are plotted.  Themes with demand=None
    (from gaps["insufficient_data"]) are listed in a chart annotation instead
    of being plotted as fake points.

    Quadrant reference lines at median supply and median demand divide the plot
    into four quadrants; the top-left is annotated "Underserved".
    """
    gaps_data = analysis.get("gaps", {})
    rows = _safe_list(gaps_data, "themes")
    if not rows:
        return None

    insufficient = gaps_data.get("insufficient_data", [])

    # Only plot themes with valid demand
    plotted = [r for r in rows if r.get("demand") is not None]
    if not plotted:
        return None

    x_supply = [r.get("supply", 0) or 0 for r in plotted]
    y_demand = [r.get("demand", 0) or 0 for r in plotted]
    labels = [r.get("theme", "") for r in plotted]
    underserved = [r.get("underserved", False) for r in plotted]
    colors = ["red" if u else "steelblue" for u in underserved]

    import statistics

    supply_median = statistics.median(x_supply) if x_supply else None
    demand_median = statistics.median(y_demand) if y_demand else None

    fig = go.Figure(
        go.Scatter(
            x=x_supply,
            y=y_demand,
            mode="markers+text",
            text=labels,
            textfont=dict(size=9),
            textposition="top center",
            marker=dict(color=colors, size=12, opacity=0.85),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Supply (games): %{x}<br>"
                "Demand (weighted score): %{y:.1f}<br>"
                "Underserved: %{customdata}<extra></extra>"
            ),
            customdata=["Yes" if u else "No" for u in underserved],
        )
    )

    # Quadrant reference lines
    if supply_median is not None:
        fig.add_vline(
            x=supply_median,
            line_dash="dot",
            line_color="grey",
            line_width=1,
            annotation_text=f"median supply={supply_median:.0f}",
            annotation_position="top right",
        )
    if demand_median is not None:
        fig.add_hline(
            y=demand_median,
            line_dash="dot",
            line_color="grey",
            line_width=1,
            annotation_text=f"median demand={demand_median:.1f}",
            annotation_position="right",
        )

    # Underserved quadrant annotation
    if supply_median is not None and demand_median is not None:
        fig.add_annotation(
            x=0,
            y=1,
            xref="paper",
            yref="paper",
            text="<b>Underserved</b><br>(low supply · high demand)",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=10, color="red"),
            bgcolor="rgba(255,255,255,0.7)",
        )

    # Annotation for themes with insufficient data
    if insufficient:
        fig.add_annotation(
            x=0,
            y=0,
            xref="paper",
            yref="paper",
            text="Insufficient review data (not plotted): " + ", ".join(insufficient),
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=9, color="#666"),
            bgcolor="rgba(255,255,255,0.7)",
        )

    fig.update_xaxes(type="log")
    fig.update_layout(
        title="Supply vs Demand by Theme (log supply axis; red = underserved: low supply, high demand)",
        xaxis_title="Supply — number of games (log scale)",
        yaxis_title="Demand — weighted quality score",
        height=520,
    )
    return _fig_to_div(fig)


def _fig_performance_bar(analysis: dict) -> str | None:
    """Horizontal bar: weighted_score per theme (performance ranking).

    Only themes with a valid (non-None) weighted_score are shown.
    Bars are ordered so the highest score appears at the TOP of the chart
    (Plotly horizontal bars put the first category at the bottom, so we
    sort ascending and then reverse the y-axis).
    """
    rows = _safe_list(analysis.get("performance", {}), "by_theme")
    if not rows:
        return None

    # Only include themes with a valid score; sort ascending for reversed axis
    valid = [(r.get("theme", ""), r.get("weighted_score")) for r in rows
             if r.get("weighted_score") is not None]
    if not valid:
        return None
    valid_sorted = sorted(valid, key=lambda t: t[1])  # ascending → reversed axis gives top=highest

    themes = [t[0] for t in valid_sorted]
    scores = [t[1] for t in valid_sorted]

    fig = go.Figure(
        go.Bar(
            y=themes,
            x=scores,
            orientation="h",
            marker_color="mediumseagreen",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        title="Theme Performance (weighted score = review% × log(owners); owners are SteamSpy estimates)",
        xaxis_title="Weighted score",
        yaxis_title="Theme",
        height=max(300, len(themes) * 28 + 80),
        margin=dict(l=160, t=60),
    )
    return _fig_to_div(fig)


def _fig_feature_delta(analysis: dict) -> str | None:
    """Bar: feature quality delta (mean_with - mean_without review %)."""
    rows = _safe_list(analysis.get("quality", {}), "features")
    if not rows:
        return None

    features = []
    deltas = []
    for r in rows:
        d = r.get("delta")
        if d is not None:
            features.append(r.get("feature", ""))
            deltas.append(d)

    if not features:
        return None

    colors = ["seagreen" if d >= 0 else "tomato" for d in deltas]

    fig = go.Figure(
        go.Bar(
            x=features,
            y=deltas,
            marker_color=colors,
            text=[f"{d:+.1f}%" for d in deltas],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Feature Impact on Review Score (delta = mean_with − mean_without review %)",
        xaxis_title="Feature",
        yaxis_title="Delta (percentage points)",
        height=380,
        shapes=[dict(type="line", x0=-0.5, x1=len(features) - 0.5,
                     y0=0, y1=0, line=dict(color="black", width=1))],
    )
    return _fig_to_div(fig)


def _fig_monetization_bar(analysis: dict) -> str | None:
    """Bar: business model distribution by count and weighted_score.

    Bars are sorted descending by count (no inherent order for business models).
    Secondary y-axis (weighted_score) is left auto-scaled with axis title.
    """
    rows = _safe_list(analysis.get("monetization", {}), "by_business_model")
    if not rows:
        return None

    # Sort by count descending
    rows_sorted = sorted(rows, key=lambda r: r.get("count", 0) or 0, reverse=True)
    models = [r.get("business_model", "") for r in rows_sorted]
    counts = [r.get("count", 0) or 0 for r in rows_sorted]
    scores = [r.get("weighted_score") for r in rows_sorted]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Count",
        x=models,
        y=counts,
        marker_color="cornflowerblue",
        yaxis="y",
    ))
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Weighted score",
            x=models,
            y=scores,
            mode="lines+markers",
            marker=dict(color="darkorange", size=8),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Business Model Distribution (owner counts are SteamSpy estimates)",
        xaxis_title="Business model",
        yaxis=dict(title="Number of games"),
        yaxis2=dict(title="Weighted score", overlaying="y", side="right"),
        height=420,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


def _fig_price_buckets(analysis: dict) -> str | None:
    """Bar: price bucket distribution."""
    rows = _safe_list(analysis.get("monetization", {}), "price_buckets")
    if not rows:
        return None

    buckets = [r.get("bucket", "") for r in rows]
    counts = [r.get("count", 0) or 0 for r in rows]
    scores = [r.get("mean_positive") for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Count",
        x=buckets,
        y=counts,
        marker_color="mediumpurple",
        yaxis="y",
    ))
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Mean review %",
            x=buckets,
            y=scores,
            mode="lines+markers",
            marker=dict(color="tomato", size=8),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Price Bucket Distribution and Review Score",
        xaxis_title="Price bucket (USD)",
        yaxis=dict(title="Number of games"),
        yaxis2=dict(title="Mean review %", overlaying="y", side="right", range=[0, 100]),
        height=400,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


def _fig_art_bar(analysis: dict) -> str | None:
    """Bar: art style distribution and quality.

    Bars are sorted descending by count (no inherent order for art styles).
    Secondary y-axis (weighted_score) is auto-scaled with axis title.
    """
    rows = _safe_list(analysis.get("art", {}), "by_art_style")
    if not rows:
        return None

    # Sort by count descending
    rows_sorted = sorted(rows, key=lambda r: r.get("count", 0) or 0, reverse=True)
    styles = [r.get("art_style", "") for r in rows_sorted]
    counts = [r.get("count", 0) or 0 for r in rows_sorted]
    scores = [r.get("weighted_score") for r in rows_sorted]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Count",
        x=styles,
        y=counts,
        marker_color="darkcyan",
        yaxis="y",
    ))
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Weighted score",
            x=styles,
            y=scores,
            mode="lines+markers",
            marker=dict(color="coral", size=8),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Art Style Distribution (owner counts are SteamSpy estimates)",
        xaxis_title="Art style",
        yaxis=dict(title="Number of games"),
        yaxis2=dict(title="Weighted score", overlaying="y", side="right"),
        height=420,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


def _fig_update_cadence(analysis: dict) -> str | None:
    """Bar: update cadence bucket distribution."""
    rows = _safe_list(analysis.get("updates", {}), "by_cadence")
    if not rows:
        return None

    cadences = [r.get("cadence", "") for r in rows]
    counts = [r.get("count", 0) or 0 for r in rows]
    scores = [r.get("mean_positive") for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Count",
        x=cadences,
        y=counts,
        marker_color=["seagreen", "goldenrod", "firebrick"],
        yaxis="y",
    ))
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Mean review %",
            x=cadences,
            y=scores,
            mode="lines+markers",
            marker=dict(color="navy", size=8),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Update Cadence: active (≤30d), occasional (31-120d), abandoned (>120d or none)",
        xaxis_title="Cadence bucket",
        yaxis=dict(title="Number of games"),
        yaxis2=dict(title="Mean review %", overlaying="y", side="right", range=[0, 100]),
        height=400,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


def _fig_naming_bar(analysis: dict) -> str | None:
    """Bar chart: naming pattern count and mean review % per pattern.

    Bars are sorted descending by count (no inherent order).
    Secondary y-axis (mean review %) is fixed to [0, 100] to avoid misleading auto-scaling.
    """
    rows = _safe_list(analysis.get("naming", {}), "by_pattern")
    if not rows:
        return None

    # Sort by count descending
    rows_sorted = sorted(rows, key=lambda r: r.get("count", 0) or 0, reverse=True)
    patterns = [r.get("pattern", "") for r in rows_sorted]
    counts = [r.get("count", 0) or 0 for r in rows_sorted]
    scores = [r.get("mean_positive") for r in rows_sorted]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Count",
        x=patterns,
        y=counts,
        marker_color="slateblue",
        yaxis="y",
    ))
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Mean review %",
            x=patterns,
            y=scores,
            mode="lines+markers",
            marker=dict(color="darkorange", size=8),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Naming Patterns: title keyword match (idle_x / x_clicker / creative)",
        xaxis_title="Pattern",
        yaxis=dict(title="Number of games"),
        yaxis2=dict(title="Mean review %", overlaying="y", side="right", range=[0, 100]),
        height=400,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


def _fig_releases_per_year(analysis: dict) -> str | None:
    """Line chart: releases per year."""
    rows = _safe_list(analysis.get("trends", {}), "by_year")
    if not rows:
        return None

    years = [r.get("year") for r in rows]
    releases = [r.get("releases", 0) or 0 for r in rows]
    median_scores = [r.get("median_positive") for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        name="Releases",
        x=years,
        y=releases,
        mode="lines+markers",
        marker=dict(color="steelblue", size=8),
        yaxis="y",
    ))
    valid_scores = [s for s in median_scores if s is not None]
    if valid_scores:
        fig.add_trace(go.Scatter(
            name="Median review %",
            x=years,
            y=median_scores,
            mode="lines+markers",
            marker=dict(color="darkorange", size=6),
            yaxis="y2",
        ))
    fig.update_layout(
        title="Idle/Incremental Game Releases per Year (Steam catalogue)",
        xaxis_title="Year",
        yaxis=dict(title="Number of releases"),
        yaxis2=dict(title="Median review %", overlaying="y", side="right", range=[0, 100]),
        height=420,
        legend=dict(x=0.01, y=0.99),
    )
    return _fig_to_div(fig)


# ---------------------------------------------------------------------------
# Public API: make_figures
# ---------------------------------------------------------------------------


def make_figures(analysis: dict) -> dict[str, str]:
    """Build Plotly figures from the analysis dict.

    Each figure builder is called in a try/except guard so that a missing or
    malformed source key never crashes the entire render.

    Args:
        analysis: dict keyed by analysis module stem (topics, gaps, performance,
                  quality, monetization, art, updates, trends, supplementary).

    Returns:
        {figure_name: html_div_string}  — only figures that could be built.
    """
    builders = [
        ("theme_bar", _fig_theme_bar),
        ("gap_scatter", _fig_gap_scatter),
        ("performance_bar", _fig_performance_bar),
        ("feature_delta", _fig_feature_delta),
        ("monetization_bar", _fig_monetization_bar),
        ("price_buckets", _fig_price_buckets),
        ("art_bar", _fig_art_bar),
        ("update_cadence", _fig_update_cadence),
        ("releases_per_year", _fig_releases_per_year),
        ("naming_bar", _fig_naming_bar),
    ]

    figures: dict[str, str] = {}
    for name, builder in builders:
        try:
            html = builder(analysis)
            if html is not None:
                figures[name] = html
        except Exception:  # noqa: BLE001
            # Guard: skip figure on any error; never crash the whole render.
            pass

    return figures


# ---------------------------------------------------------------------------
# Public API: build_site
# ---------------------------------------------------------------------------


def build_site(analysis_dir: str = "data/analysis", out: str = "docs") -> None:
    """Load analysis JSONs and render the static site into out/.

    Args:
        analysis_dir: Directory containing *.json analysis outputs.
        out:          Output directory for HTML files (GitHub Pages root).
    """
    # -- Load analysis JSONs --
    analysis: dict[str, Any] = {}
    analysis_path = pathlib.Path(analysis_dir)
    if analysis_path.exists():
        for json_file in sorted(analysis_path.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                analysis[json_file.stem] = data
            except Exception:  # noqa: BLE001
                pass  # Skip unparseable files silently

    # -- Build figures --
    figures = make_figures(analysis)

    # -- Extract supplementary section (with defaults if missing) --
    supp = analysis.get("supplementary", {})
    supp_itch = supp.get("itch", {})
    supp_kong = supp.get("kongregate", {})
    supp_reddit = supp.get("reddit", {"available": False, "note": "", "sentiment": {}})
    supp_caveats = supp.get("caveats", [])

    # -- Collect overall caveats (supplementary + static methodology notes) --
    static_caveats = [
        "Steam is the quantitative spine. Owner counts are SteamSpy modeled estimates"
        " — not verified sales figures. Treat as order-of-magnitude only.",
        "Mobile (iOS/Android) is not covered — no free/reliable data source was available.",
        "Reddit r/incremental_games top.json returns 403 without OAuth;"
        " qualitative sentiment not collected unless cached.",
        "Kongregate ratings are 1–5 stars mapped to a percentage; they are NOT"
        " comparable to Steam review percentages (low confidence).",
        "itch.io provides no owner/revenue data — coverage counts only.",
        "Scrapers parse static HTML/JSON-LD; counts reflect one page of results,"
        " not the full catalogue.",
        "SteamDB was excluded from this pipeline (Cloudflare / ToS barriers)."
        " The Steam News API IS used for update cadence detection (~2,169 games).",
        "Theme, mechanic, and art style classifications are derived from each game's real"
        " Steam user tags (fetched via the SteamSpy appdetails endpoint) plus short"
        " description keyword matching (word-boundary regex). Tags are crowd-sourced"
        " (community-applied, can be noisy or popularity-biased) — medium confidence;"
        " treat as directional signals, not authoritative genre data.",
        "Art style is classified from Steam user tags (e.g. 'Pixel Graphics', 'Anime')."
        " 3,206 of 3,479 games have an art style assigned. Tags are crowd-sourced"
        " (medium confidence — see above).",
        "Weighted score = review_pct_positive × log(1 + total_owners);"
        " biases toward popular games with high approval.",
    ]
    all_caveats = static_caveats + list(supp_caveats)

    # -- Compute summary stats for narrative (pulled from analysis JSON) --
    topics_themes = _safe_list(analysis.get("topics", {}), "themes")
    n_themes = len(topics_themes)
    top_theme = topics_themes[0].get("theme", "—") if topics_themes else "—"

    gaps_themes = _safe_list(analysis.get("gaps", {}), "themes")
    underserved_themes = [t.get("theme") for t in gaps_themes if t.get("underserved")]

    perf_themes = _safe_list(analysis.get("performance", {}), "by_theme")
    top_perf = perf_themes[0].get("theme", "—") if perf_themes else "—"

    quality_features = _safe_list(analysis.get("quality", {}), "features")
    positive_features = [
        f for f in quality_features
        if f.get("delta") is not None and f["delta"] > 0
    ]

    trends_years = _safe_list(analysis.get("trends", {}), "by_year")
    rising_themes = (analysis.get("trends") or {}).get("rising_themes", [])

    # -- Dataset summary (guards for absence in older runs) --
    ctx_dataset = analysis.get("dataset", {})

    # -- Jinja2 context --
    ctx: dict[str, Any] = {
        "figures": figures,
        "dataset": ctx_dataset,
        # supplementary
        "supp_itch": supp_itch,
        "supp_kong": supp_kong,
        "supp_reddit": supp_reddit,
        "supp_caveats": supp_caveats,
        # methodology
        "all_caveats": all_caveats,
        # narrative stats (pulled from JSON, not hardcoded)
        "n_themes": n_themes,
        "top_theme": top_theme,
        "underserved_themes": underserved_themes,
        "top_perf_theme": top_perf,
        "positive_features": [f.get("feature") for f in positive_features],
        "rising_themes": rising_themes,
        "n_trends_years": len(trends_years),
    }

    # -- Render templates --
    out_path = pathlib.Path(out)
    out_path.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    for template_name, out_file in [
        ("report.html.j2", "index.html"),
        ("methodology.html.j2", "methodology.html"),
    ]:
        template = env.get_template(template_name)
        rendered = template.render(**ctx)
        (out_path / out_file).write_text(rendered, encoding="utf-8")
