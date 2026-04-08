"""
Analytics Page for Misinformation Arena v2.

Editorial, narrative-driven analytics from JSON v2 (runs/<run_id>/episodes.jsonl).
Read-only; no agent/judge calls.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.presentation.streamlit.styles import PLOTLY_LAYOUT

from arena.analysis.anomaly_detection import compute_iqr_outliers, compute_mad_outliers
from arena.analysis.episode_dataset import (
    CANONICAL_METRICS,
    build_episode_df,
    build_episode_long_df,
    compute_aggregates,
)
from arena.analysis.research_analytics import (
    apply_research_filters,
    compute_transparency_summary,
    compute_strength_fingerprint,
)
from arena.io.run_store_v2_read import list_runs
from arena.presentation.streamlit.pages.strategy_leaderboard_page import render_strategy_leaderboard_page
from arena.presentation.streamlit.pages.citation_page import render_citation_page
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

RUNS_DIR = "runs"

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------
SPREADER_COLOR  = "#D4A843"   # Amber  — misinformation spreader
DEBUNKER_COLOR  = "#4A7FA5"   # Steel blue — fact-checker / debunker
DRAW_COLOR      = "#888888"   # Grey       — draw / other

METRIC_LABELS = {
    "factuality":              "Factuality",
    "source_credibility":      "Source Credibility",
    "reasoning_quality":       "Reasoning",
    "responsiveness":          "Responsiveness",
    "persuasion":              "Persuasion",
    "manipulation_awareness":  "Manipulation Awareness",
    # Backward compat for old episodes
    "truthfulness_proxy":      "Factuality",
    "evidence_quality":        "Source Credibility",
    "civility":                "Manipulation Awareness",
}

METRIC_DESCRIPTIONS = {
    "factuality":              "How internally consistent and credible the argument appears. For the spreader, narrative plausibility; for the debunker, grounding in verifiable facts. (D2D, EMNLP 2025)",
    "source_credibility":      "Quality and specificity of cited sources. Named institutions and checkable claims score higher than vague appeals to authority. (D2D, EMNLP 2025)",
    "reasoning_quality":       "Logical structure and coherence — does the argument follow from its premises? Identifies fallacies? (Wachsmuth et al., 2017 — Cogency)",
    "responsiveness":          "How directly each side engages the strongest point in the opponent's previous argument. Ignoring and pivoting scores low. (Wachsmuth et al., 2017 — Reasonableness)",
    "persuasion":              "Overall convincingness to an uncommitted reader — tone, narrative coherence, emotional resonance, and readability. (Wachsmuth et al., 2017 — Effectiveness)",
    "manipulation_awareness":  "For spreader: penalizes reliance on manipulation tactics (fear, conspiracy framing, fake authority). For debunker: rewards explicitly naming and exposing manipulation techniques. (Inoculation theory — Roozenbeek & van der Linden, 2022)",
    # Backward compat
    "truthfulness_proxy":      "How internally consistent and credible the argument appears.",
    "evidence_quality":        "Quality and specificity of cited sources.",
    "civility":                "Manipulation awareness (legacy label).",
}

EPISODE_TABLE_RENAME = {
    "run_label":            "Run",
    "run_id":               "Run ID",
    "episode_id":           "Episode",
    "winner":               "Winner",
    "judge_confidence":     "Confidence",
    "abs_margin":           "Score Margin",
    "planned_max_turns":    "Max Turns",
    "completed_turn_pairs": "Turns Completed",
    "end_trigger":          "How It Ended",
    "error_flag":           "Error",
}

END_TRIGGER_LABELS = {
    "max_turns":          "Reached max turns",
    "concession_keyword": "Concession",
    "concession":         "Concession",
    "error":              "Error",
}

PREVIEW_COLUMNS = [
    "run_label", "episode_id", "winner", "judge_confidence", "abs_margin",
    "planned_max_turns", "completed_turn_pairs", "end_trigger", "error_flag",
]


def _label_metric(name: str) -> str:
    return METRIC_LABELS.get(name, name.replace("_", " ").title())


def _fmt_trigger(val) -> str:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return "—"
    return END_TRIGGER_LABELS.get(str(val).strip().lower(), str(val).replace("_", " ").title())


# ---------------------------------------------------------------------------
# Page-level CSS
# ---------------------------------------------------------------------------

def _inject_styles():
    st.markdown("""
    <style>
    /* ── Page title ── */
    .ma-page-title {
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 2.6rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: var(--color-text-primary, #E8E4D9) !important;
        margin-bottom: 0.15rem !important;
        text-align: center !important;
        line-height: 1.15 !important;
    }
    .ma-page-subtitle {
        font-size: 1rem;
        color: var(--color-text-muted, #888);
        margin-bottom: 1.5rem;
        line-height: 1.5;
        text-align: center;
    }

    /* ── Section headers ── */
    .ma-section-header {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2rem;
        font-weight: 400;
        color: var(--color-accent-red, #C9363E);
        margin-top: 2.5rem;
        margin-bottom: 0.2rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid var(--color-border, #2A2A2A);
        text-align: left;
    }
    .ma-section-question {
        font-size: 1rem;
        font-weight: 700;
        color: var(--color-text-primary, #E8E4D9);
        margin-bottom: 0.4rem;
        text-align: left;
    }
    .ma-section-prose {
        font-size: 0.95rem;
        color: var(--color-text-muted, #888);
        line-height: 1.65;
        margin-bottom: 1.2rem;
        max-width: 760px;
        text-align: left;
    }

    /* ── Metric cards (red left-border style) ── */
    .ma-metric-grid {
        display: flex;
        gap: 1rem;
        margin: 1.2rem 0 1.8rem 0;
        flex-wrap: wrap;
    }
    .ma-metric-card {
        flex: 1;
        min-width: 130px;
        background: var(--color-surface, #111);
        border-left: 3px solid var(--color-accent-red, #C9363E);
        border-radius: 4px;
        padding: 1rem 1.2rem;
    }
    .ma-metric-label {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--color-text-muted, #888);
        margin-bottom: 0.25rem;
    }
    .ma-metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2rem;
        font-weight: 700;
        color: var(--color-accent-red, #C9363E);
        line-height: 1.1;
    }
    .ma-metric-value.highlight-debunker { color: var(--color-accent-blue, #4A7FA5); }
    .ma-metric-value.highlight-spreader  { color: var(--color-accent-amber, #D4A843); }
    .ma-metric-value.highlight-neutral   { color: var(--color-accent-amber, #D4A843); }
    .ma-metric-sub {
        font-size: 0.78rem;
        color: var(--color-text-muted, #888);
        margin-top: 0.2rem;
    }

    /* ── Summary callout ── */
    .ma-callout {
        background: rgba(74, 127, 165, 0.08);
        border-left: 4px solid var(--color-accent-blue, #4A7FA5);
        border-radius: 0 4px 4px 0;
        padding: 0.85rem 1.1rem;
        margin-bottom: 1.5rem;
        font-size: 0.95rem;
        color: var(--color-text-primary, #E8E4D9);
        line-height: 1.6;
    }
    .ma-callout.warning {
        background: rgba(212, 168, 67, 0.08);
        border-left-color: var(--color-accent-amber, #D4A843);
    }

    /* ── Chart caption ── */
    .ma-chart-caption {
        font-size: 0.82rem;
        color: var(--color-text-muted, #888);
        line-height: 1.5;
        margin-top: 0.3rem;
        margin-bottom: 1rem;
        max-width: 760px;
        text-align: left;
    }

    /* ── Dimension definition grid ── */
    .ma-dim-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 0.75rem;
        margin: 0.5rem 0 1.5rem 0;
    }
    .ma-dim-card {
        background: var(--color-surface, #111);
        border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 4px;
        padding: 0.75rem 1rem;
    }
    .ma-dim-name {
        font-size: 0.85rem;
        font-weight: 700;
        color: var(--color-text-primary, #E8E4D9);
        margin-bottom: 0.2rem;
    }
    .ma-dim-desc {
        font-size: 0.8rem;
        color: var(--color-text-muted, #888);
        line-height: 1.45;
    }

    /* ── Divider ── */
    .ma-divider {
        border: none;
        border-top: 1px solid var(--color-border, #2A2A2A);
        margin: 2rem 0;
    }

    /* ── Filter row ── */
    .ma-filter-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--color-text-muted, #888);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_wide(run_ids: tuple, runs_dir: str, token: float):
    return build_episode_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)


@st.cache_data(show_spinner=False)
def _load_long(run_ids: tuple, runs_dir: str, token: float):
    return build_episode_long_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _bar(fp_df: pd.DataFrame) -> go.Figure:
    labels    = [_label_metric(m) for m in fp_df["metric_name"]]
    spr_vals  = fp_df["spreader_value"].fillna(0).tolist()
    deb_vals  = fp_df["debunker_value"].fillna(0).tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Spreader", x=labels, y=spr_vals,
        marker_color=SPREADER_COLOR, opacity=0.85,
        hovertemplate="%{x}<br>Spreader: <b>%{y:.2f}</b> / 10<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Fact-checker", x=labels, y=deb_vals,
        marker_color=DEBUNKER_COLOR, opacity=0.85,
        hovertemplate="%{x}<br>Fact-checker: <b>%{y:.2f}</b> / 10<extra></extra>",
    ))
    # Delta annotations above each bar pair
    for lbl, sv, dv in zip(labels, spr_vals, deb_vals):
        delta = dv - sv
        sign  = "+" if delta >= 0 else ""
        color = DEBUNKER_COLOR if delta >= 0 else SPREADER_COLOR
        fig.add_annotation(
            x=lbl, y=max(sv, dv) + 0.55,
            text=f"<b>{sign}{delta:.1f}</b>",
            showarrow=False, font=dict(size=11, color=color), xanchor="center",
        )
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Average score (0–10)", range=[0, 11.5], tickfont=dict(size=11),
                   gridcolor="#2A2A2A"),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=30, b=80, l=55, r=15), height=390,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    fig.add_hline(y=5, line_dash="dot", line_color="rgba(150,150,150,0.5)",
                  annotation_text="midpoint (5)", annotation_font_size=10,
                  annotation_font_color="#999")
    return fig


def _win_dist_bar(win_dist_df: pd.DataFrame) -> go.Figure:
    """Horizontal stacked bar showing win distribution."""
    d = win_dist_df.copy()
    d["winner_norm"] = d["winner"].str.strip().str.lower()

    deb_pct = float(d.loc[d["winner_norm"] == "debunker", "percent"].sum())
    spr_pct = float(d.loc[d["winner_norm"] == "spreader", "percent"].sum())
    oth_pct = float(d.loc[~d["winner_norm"].isin(["spreader", "debunker"]), "percent"].sum())
    deb_n   = int(d.loc[d["winner_norm"] == "debunker", "count"].sum())
    spr_n   = int(d.loc[d["winner_norm"] == "spreader", "count"].sum())
    oth_n   = int(d.loc[~d["winner_norm"].isin(["spreader", "debunker"]), "count"].sum())

    fig = go.Figure()
    if deb_pct > 0:
        fig.add_trace(go.Bar(
            name="Fact-checker wins", x=[deb_pct], y=[""], orientation="h",
            marker_color=DEBUNKER_COLOR,
            text=f"Fact-checker  {deb_pct:.0f}%  ({deb_n})",
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=12, color="white"),
            hovertemplate=f"Fact-checker: <b>{deb_pct:.1f}%</b> ({deb_n} debates)<extra></extra>",
        ))
    if spr_pct > 0:
        fig.add_trace(go.Bar(
            name="Spreader wins", x=[spr_pct], y=[""], orientation="h",
            marker_color=SPREADER_COLOR,
            text=f"Spreader  {spr_pct:.0f}%  ({spr_n})",
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=12, color="white"),
            hovertemplate=f"Spreader: <b>{spr_pct:.1f}%</b> ({spr_n} debates)<extra></extra>",
        ))
    if oth_pct > 0:
        fig.add_trace(go.Bar(
            name="Draw / Other", x=[oth_pct], y=[""], orientation="h",
            marker_color=DRAW_COLOR,
            text=f"Other  {oth_pct:.0f}%  ({oth_n})",
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=12, color="white"),
            hovertemplate=f"Other: <b>{oth_pct:.1f}%</b> ({oth_n} debates)<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack",
        xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", y=-0.55, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=5, b=55, l=10, r=10), height=100,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _score_dist(long_df: pd.DataFrame) -> go.Figure:
    """Grouped box+strip chart: score distribution per metric per side across all debates."""
    canon = [m for m in CANONICAL_METRICS if m in long_df["metric_name"].unique()]
    fig = go.Figure()
    for side, color, fill, name in [
        ("spreader", SPREADER_COLOR, "rgba(212,168,67,0.1)",   "Spreader"),
        ("debunker", DEBUNKER_COLOR, "rgba(74,127,165,0.1)",  "Fact-checker"),
    ]:
        x_cats, y_vals = [], []
        for metric in canon:
            sub  = long_df[(long_df["metric_name"] == metric) & (long_df["side"] == side)]
            vals = pd.to_numeric(sub["metric_value"], errors="coerce").dropna()
            lbl  = _label_metric(metric)
            x_cats.extend([lbl] * len(vals))
            y_vals.extend(vals.tolist())
        if x_cats:
            fig.add_trace(go.Box(
                x=x_cats, y=y_vals,
                name=name,
                boxpoints="all", jitter=0.35, pointpos=0,
                marker=dict(color=color, size=7, opacity=0.65, line=dict(width=0.5, color="white")),
                line=dict(color=color, width=1.5),
                fillcolor=fill,
                hovertemplate="%{x}: <b>%{y:.1f}</b> / 10<extra>" + name + "</extra>",
            ))
    fig.add_hline(y=5, line_dash="dot", line_color="rgba(150,150,150,0.5)",
                  annotation_text="midpoint (5)", annotation_font_size=10,
                  annotation_font_color="#999")
    fig.update_layout(
        boxmode="group",
        yaxis=dict(title="Score (0–10)", range=[0, 10.5], tickfont=dict(size=11),
                   gridcolor="#2A2A2A"),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=80, l=55, r=15), height=420,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig



def _strip(values: pd.Series, flagged: pd.Series, label: str,
           customdata: "pd.Series | None" = None) -> go.Figure:
    """Strip chart: one dot per debate, flagged outliers shown as red ×.

    customdata: optional Series (same index as values) of strings to embed per dot,
                used for click-to-navigate. Format: "run_id|||episode_id|||claim".
    """
    inliers  = values[~flagged].dropna()
    outliers = values[flagged].dropna()

    def _jitter(n, width=0.22):
        if n == 0: return []
        if n == 1: return [0.0]
        step = width * 2 / (n - 1)
        return [-width + i * step for i in range(n)]

    def _custom(subset: pd.Series) -> list:
        if customdata is None:
            return [None] * len(subset)
        return customdata.reindex(subset.index).fillna("").tolist()

    fig = go.Figure()
    if len(inliers):
        cd = _custom(inliers)
        fig.add_trace(go.Scatter(
            x=_jitter(len(inliers)), y=inliers.tolist(),
            mode="markers", name="Normal",
            marker=dict(color=DEBUNKER_COLOR, size=10, opacity=0.7,
                        line=dict(width=0.5, color="white")),
            customdata=cd,
            hovertemplate=(
                f"<b>%{{customdata}}</b><br>{label}: <b>%{{y:.3f}}</b>"
                "<br><i>Click to select</i><extra>Normal</extra>"
            ) if customdata is not None else f"{label}: <b>%{{y:.3f}}</b><extra>Normal</extra>",
        ))
    if len(outliers):
        cd2 = _custom(outliers)
        fig.add_trace(go.Scatter(
            x=_jitter(len(outliers), width=0.12), y=outliers.tolist(),
            mode="markers", name="Flagged outlier",
            marker=dict(color=SPREADER_COLOR, size=13, symbol="x-thin-open",
                        line=dict(width=2.5)),
            customdata=cd2,
            hovertemplate=(
                f"<b>%{{customdata}}</b><br>{label}: <b>%{{y:.3f}}</b>"
                "<br><i>Click to select</i><extra>Flagged</extra>"
            ) if customdata is not None else f"{label}: <b>%{{y:.3f}}</b><extra>Flagged</extra>",
        ))
    fig.update_layout(
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.7, 0.7]),
        yaxis=dict(title=label, tickfont=dict(size=11), gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=60, l=55, r=15), height=300,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _scatter(scatter_df: pd.DataFrame) -> go.Figure:
    cmap = {"debunker": DEBUNKER_COLOR, "spreader": SPREADER_COLOR, "draw": DRAW_COLOR}
    name_map = {"debunker": "Fact-checker wins", "spreader": "Spreader wins", "draw": "Draw"}
    fig = go.Figure()
    for wval in scatter_df["winner"].dropna().unique():
        sub = scatter_df[scatter_df["winner"] == wval]
        fig.add_trace(go.Scatter(
            x=sub["abs_margin"], y=sub["judge_confidence"],
            mode="markers", name=name_map.get(wval.lower(), wval.title()),
            marker=dict(color=cmap.get(wval.lower(), "#888"), size=9, opacity=0.75,
                        line=dict(width=0.5, color="white")),
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                "Score margin: %{x:.2f}<br>"
                "Judge confidence: %{y:.0%}<extra></extra>"
            ),
            customdata=sub.get("claim", pd.Series([""] * len(sub))).fillna("").str[:60].tolist(),
        ))
    fig.update_layout(
        xaxis=dict(title="Score Margin  (how decisive was the result?)",
                   tickfont=dict(size=11), gridcolor="#2A2A2A"),
        yaxis=dict(title="Judge Confidence  (0% = uncertain, 100% = certain)",
                   tickformat=".0%", tickfont=dict(size=11),
                   gridcolor="#2A2A2A", range=[0, 1.05]),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=80, l=70, r=15), height=380,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
        hovermode="closest",
    )
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    return fig


# ---------------------------------------------------------------------------
# Judge calibration plot
# ---------------------------------------------------------------------------

def _calibration_plot(df: pd.DataFrame) -> go.Figure | None:
    """Bar chart: confidence buckets vs mean score margin.

    A well-calibrated judge shows higher margin when confidence is high.
    Returns None when there is insufficient data.
    """
    needed = {"judge_confidence", "abs_margin"}
    if not needed.issubset(df.columns):
        return None
    cal = df[["judge_confidence", "abs_margin"]].dropna().copy()
    cal["judge_confidence"] = pd.to_numeric(cal["judge_confidence"], errors="coerce")
    cal["abs_margin"]       = pd.to_numeric(cal["abs_margin"],       errors="coerce")
    cal = cal.dropna()
    if len(cal) < 4:
        return None

    bins   = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    labels = ["0–20 %", "20–40 %", "40–60 %", "60–80 %", "80–100 %"]
    cal["bucket"] = pd.cut(cal["judge_confidence"], bins=bins, labels=labels, right=False)
    grouped = (
        cal.groupby("bucket", observed=True)["abs_margin"]
        .agg(mean="mean", n="count")
        .reset_index()
    )
    grouped = grouped[grouped["n"] > 0]
    if grouped.empty:
        return None

    bucket_colors = [
        "#c7d2fe" if i < 2 else DEBUNKER_COLOR if i > 3 else "#93c5fd"
        for i in range(len(grouped))
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grouped["bucket"].astype(str),
        y=grouped["mean"],
        marker_color=bucket_colors,
        text=[f"n = {int(n)}" for n in grouped["n"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Mean margin: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Judge Confidence Bucket", tickfont=dict(size=11)),
        yaxis=dict(title="Mean Score Margin", tickfont=dict(size=11),
                   gridcolor="#2A2A2A"),
        margin=dict(t=10, b=60, l=60, r=15),
        height=340,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
        showlegend=False,
    )
    fig.update_yaxes(showgrid=True)
    return fig


# ---------------------------------------------------------------------------
# Legacy expander
# ---------------------------------------------------------------------------

def _legacy_expander():
    from arena.app_config import DEFAULT_MATCHES_PATH
    from arena.analytics import normalize_analytics_df
    from arena.io.run_store import load_matches_jsonl
    with st.expander("Legacy data (old format)", expanded=False):
        try:
            matches = load_matches_jsonl(str(DEFAULT_MATCHES_PATH))
            df = pd.DataFrame(matches) if matches else pd.DataFrame()
        except Exception:
            df = pd.DataFrame()
        if df.empty:
            st.info("No legacy data found.")
            return
        df = normalize_analytics_df(df)
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_analytics_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    # ── Load runs ──────────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.markdown('<p class="ma-page-title">Debate Analytics</p>', unsafe_allow_html=True)
        st.info("No completed debates yet. Run a debate in the Arena tab to see results here.")
        _legacy_expander()
        return

    list_runs(RUNS_DIR, refresh_token=token)

    df, warnings = _load_wide(tuple(run_ids), RUNS_DIR, token)
    if df.empty:
        st.info("No episodes found. Complete some debates first.")
        _legacy_expander()
        return

    if warnings:
        with st.expander("⚠️ Data warnings", expanded=False):
            for w in warnings:
                st.caption(w)

    agg = compute_aggregates(df)
    wr   = agg["debunker_win_rate"]
    n_ep = agg["n_episodes"]
    n_runs = agg["n_runs"]
    ac   = agg["avg_confidence"]
    fr   = agg["fallback_rate"]

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE HEADER
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-page-title">Debate Analytics</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ma-page-subtitle">'
        'A record of every AI debate run in this arena — who won, how confident '
        'the judge was, and where each side was strongest or weakest.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TOP SECTION — KPI CARDS + WIN DISTRIBUTION + FILTERS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Who is winning?</p>', unsafe_allow_html=True)

    if wr is not None and n_ep > 0:
        deb_wins = int(round(wr * n_ep))
        spr_wins = n_ep - deb_wins
        if wr >= 0.75:
            interp = (f"The fact-checker is dominating — winning <b>{deb_wins} of {n_ep} debates ({wr:.0%})</b>. "
                      "This suggests the debunking strategy is highly effective against the current spreader prompts.")
        elif wr >= 0.55:
            interp = (f"The fact-checker has a clear edge, winning <b>{deb_wins} of {n_ep} debates ({wr:.0%})</b>. "
                      "The spreader is putting up a fight but losing more often than not.")
        elif wr >= 0.45:
            interp = (f"Results are mixed — the fact-checker won <b>{deb_wins}</b> debates and the spreader won "
                      f"<b>{spr_wins}</b>. Neither side has a decisive advantage.")
        else:
            interp = (f"The spreader is winning more often — the fact-checker only won "
                      f"<b>{deb_wins} of {n_ep} debates ({wr:.0%})</b>. "
                      "Consider reviewing the debunker's prompts and strategy.")
        st.markdown(f'<div class="ma-callout">{interp}</div>', unsafe_allow_html=True)

    # Metric cards
    def _card(label, value, sub="", cls=""):
        return (
            f'<div class="ma-metric-card">'
            f'<div class="ma-metric-label">{label}</div>'
            f'<div class="ma-metric-value {cls}">{value}</div>'
            f'<div class="ma-metric-sub">{sub}</div>'
            f'</div>'
        )

    wr_cls = "highlight-debunker" if (wr or 0) >= 0.5 else "highlight-spreader"
    ac_pct = f"{ac:.0%}" if ac is not None else "—"
    fr_pct = f"{fr:.1%}" if fr is not None else "—"
    fr_cls = "highlight-spreader" if (fr or 0) > 0.1 else ""

    cards_html = (
        '<div class="ma-metric-grid">'
        + _card("Total Debates", n_ep, f"across {n_runs} run{'s' if n_runs != 1 else ''}")
        + _card("Fact-checker Win Rate", f"{wr:.0%}" if wr is not None else "—",
                f"{int(round(wr*n_ep)) if wr else 0} wins of {n_ep}", wr_cls)
        + _card("Avg Judge Confidence", ac_pct,
                "How certain the judge was in its calls")
        + _card("Error Rate", fr_pct,
                "Debates where judge used fallback", fr_cls)
        + '</div>'
    )
    st.markdown(cards_html, unsafe_allow_html=True)

    # Win distribution bar
    win_dist_df = agg.get("win_distribution", pd.DataFrame())
    if not win_dist_df.empty:
        st.markdown(
            '<p class="ma-chart-caption" style="margin-top:1.2rem;">'
            'How wins are distributed across all debates</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(_win_dist_bar(win_dist_df), use_container_width=True)

    st.markdown(
        '<p class="ma-section-prose">'
        '<b>Judge Confidence</b> reflects how certain the AI judge was in its decision — '
        '100% means it was fully confident in the winner, 50% means it was essentially a coin flip. '
        '<b>Error Rate</b> shows the percentage of debates where the primary AI judge failed and '
        'a simpler fallback was used instead. Debates with errors are excluded from the charts below by default.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load long_df and build filters (needed by multiple tabs) ──────────
    long_df = _load_long(tuple(run_ids), RUNS_DIR, token)
    filtered = pd.DataFrame()

    if not long_df.empty:
        # Compact filter row
        st.markdown('<p class="ma-filter-label">Filter results</p>', unsafe_allow_html=True)
        arena_opts    = [x for x in long_df["arena_type"].dropna().unique().astype(str) if x != "nan"]
        spreader_opts = [x for x in long_df["model_spreader"].dropna().unique().astype(str) if x != "nan"]
        debunker_opts = [x for x in long_df["model_debunker"].dropna().unique().astype(str) if x != "nan"]
        judge_opts    = [x for x in long_df["judge_mode"].dropna().unique().astype(str) if x != "nan"]
        metric_opts   = sorted([x for x in long_df["metric_name"].dropna().unique().astype(str) if x != "nan"])
        _excl = {"heuristic", "n/a", "na", "none", ""}
        jmodel_opts   = [x for x in long_df["model_judge"].dropna().unique().astype(str)
                         if x != "nan" and x.strip().lower() not in _excl]

        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            sel_arena    = st.multiselect("Arena type", arena_opts, default=[], key="ra_arena")
        with fc2:
            sel_spreader = st.multiselect("Spreader model", spreader_opts, default=[], key="ra_spreader")
        with fc3:
            sel_debunker = st.multiselect("Debunker model", debunker_opts, default=[], key="ra_debunker")
        with fc4:
            sel_jmodel   = st.multiselect("Judge model", jmodel_opts, default=[], key="ra_judge_model")

        excl_err = st.checkbox("Exclude debates with judge errors", value=True, key="ra_exclude_err")

        DEFAULT_JUDGE_MODES = ["agent"]
        eff_fp_agg = "mean"
        eff_traj   = "raw"

        filtered = apply_research_filters(
            long_df,
            arena_types=sel_arena or None,
            judge_modes=DEFAULT_JUDGE_MODES,
            spreader_models=sel_spreader or None,
            debunker_models=sel_debunker or None,
            judge_models=sel_jmodel or None,
            exclude_error_episodes=excl_err,
        )

    # ── Download buttons ──────────────────────────────────────────────────
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button("Download episodes CSV", df.to_csv(index=False).encode(), "episodes.csv", "text/csv")
    with dl2:
        import json
        agg_exp = {k: v for k, v in agg.items()
                   if k not in ("win_distribution","confidence_bins","metric_means_by_role",
                                "metric_delta_means","by_turn_plan","by_run")}
        for k in ("win_distribution","confidence_bins","metric_means_by_role",
                  "metric_delta_means","by_turn_plan","by_run"):
            agg_exp[k] = agg[k].to_dict(orient="records") if not agg[k].empty else []
        st.download_button("Download aggregated JSON",
                           json.dumps(agg_exp, indent=2, default=str),
                           "aggregates.json", "application/json")

    # ══════════════════════════════════════════════════════════════════════════
    # TABS
    # ══════════════════════════════════════════════════════════════════════════
    tab_perf, tab_models, tab_strategy, tab_citations, tab_concessions, tab_anomalies = st.tabs([
        "Performance", "Models", "Strategy", "Citations", "Concessions", "Anomalies"
    ])

    # ── Strategy tab ─────────────────────────────────────────────────────
    with tab_strategy:
        render_strategy_leaderboard_page()

    # ── Citations tab ────────────────────────────────────────────────────
    with tab_citations:
        render_citation_page()

    # ── Performance tab ───────────────────────────────────────────────────
    with tab_perf:
        st.markdown('<p class="ma-section-header">How did each side argue?</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="ma-section-prose">'
            'The judge scores every debate across <b>six dimensions</b>, each on a scale of <b>0 to 10</b>. '
            'A score above 7 indicates strong performance; below 4 is weak. '
            'The charts below show average scores across all debates, so you can see at a glance '
            'which dimensions each side consistently wins or loses.'
            '</p>',
            unsafe_allow_html=True,
        )

        # Dimension definition cards — inline, not hidden
        dim_cards = "".join(
            f'<div class="ma-dim-card">'
            f'<div class="ma-dim-name">{_label_metric(k)}</div>'
            f'<div class="ma-dim-desc">{v}</div>'
            f'</div>'
            for k, v in METRIC_DESCRIPTIONS.items()
        )
        st.markdown(f'<div class="ma-dim-grid">{dim_cards}</div>', unsafe_allow_html=True)

        if long_df.empty:
            st.warning("No scored episodes found. The judge needs to have run successfully on at least one debate.")
        elif filtered.empty:
            st.warning("No debates match the current filters. Try removing some filters.")
        else:
            summary = compute_transparency_summary(filtered)
            ep_key = [c for c in ["run_id", "episode_index"] if c in long_df.columns]
            n_total  = long_df.drop_duplicates(subset=ep_key).shape[0] if ep_key else 0
            n_after_err = apply_research_filters(long_df, exclude_error_episodes=excl_err,
                judge_modes=None, arena_types=None, spreader_models=None,
                debunker_models=None, judge_models=None
            ).drop_duplicates(subset=ep_key).shape[0] if ep_key else 0
            n_excl_err   = n_total - n_after_err
            n_excl_other = n_after_err - summary["n_episodes"]

            excl_parts = []
            if excl_err and n_excl_err:   excl_parts.append(f"{n_excl_err} error debate{'s' if n_excl_err>1 else ''} excluded")
            if n_excl_other:              excl_parts.append(f"{n_excl_other} filtered out")
            caption = f"Showing **{summary['n_episodes']} debates** from {summary['n_runs']} run{'s' if summary['n_runs']!=1 else ''}"
            if excl_parts: caption += " · " + " · ".join(excl_parts)
            st.caption(caption)

            # Strength fingerprint
            fp_df = compute_strength_fingerprint(filtered, agg=eff_fp_agg, view="raw")

            if not fp_df.empty and len(fp_df) >= 3:
                st.markdown(
                    '<p class="ma-section-question">Side-by-side scores — with advantage delta</p>'
                    '<p class="ma-chart-caption">Average score per dimension, out of 10. '
                    'The number above each pair shows the fact-checker\'s advantage '
                    '(<span style="color:#4A7FA5"><b>steel blue = fact-checker leads</b></span>, '
                    '<span style="color:#D4A843"><b>amber = spreader leads</b></span>). '
                    'Bars above 7 are a clear strength; below 4 is a weakness.</p>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(_bar(fp_df), use_container_width=True)

            # Score distribution
            st.markdown(
                '<p class="ma-section-question">How do scores spread across all debates?</p>'
                '<p class="ma-chart-caption">'
                'Each dot is one debate. The box shows the middle 50% of scores; the line is the median. '
                'A tight cluster means the judge scores consistently; a wide spread means results vary a lot. '
                'Hover over any dot to see its exact score.'
                '</p>',
                unsafe_allow_html=True,
            )
            if not filtered.empty:
                sd_fig = _score_dist(filtered)
                st.plotly_chart(sd_fig, use_container_width=True)
            else:
                st.caption("No data available for score distribution.")

    # ── Models tab ────────────────────────────────────────────────────────
    with tab_models:
        st.markdown(
            '<p class="ma-section-header">Model Performance Comparison</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="ma-section-prose">'
            'How do different AI models perform when assigned to each role? '
            'The matchup matrix below shows every model pairing that has been tested, '
            'while the bar charts reveal which models are strongest as spreaders vs. fact-checkers.'
            '</p>',
            unsafe_allow_html=True,
        )

        has_model_cols = "model_spreader" in df.columns and "model_debunker" in df.columns
        model_df = df.dropna(subset=["model_spreader", "model_debunker"]) if has_model_cols else pd.DataFrame()

        if model_df.empty:
            st.info("No model data available. Complete some debates to see model comparisons.")
        else:
            # ── 1. Model matchup matrix ──────────────────────────────────
            st.markdown(
                '<p class="ma-section-question">Model Matchup Matrix</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="ma-chart-caption">'
                'Each row is a unique spreader-model vs. debunker-model pairing. '
                'FC Win % shows how often the fact-checker won that matchup.'
                '</p>',
                unsafe_allow_html=True,
            )

            matchup = model_df.groupby(["model_spreader", "model_debunker"]).agg(
                Debates=("winner", "size"),
                FC_Wins=("winner", lambda x: (x == "debunker").sum()),
                Avg_Confidence=("judge_confidence", "mean"),
                Avg_Margin=("abs_margin", "mean"),
            ).reset_index()
            matchup["FC Win %"] = (matchup["FC_Wins"] / matchup["Debates"] * 100).round(1)
            matchup["Avg Confidence"] = matchup["Avg_Confidence"].round(2)
            matchup["Avg Margin"] = matchup["Avg_Margin"].round(2)

            display_matchup = matchup.rename(columns={
                "model_spreader": "Spreader Model",
                "model_debunker": "Debunker Model",
            })[["Spreader Model", "Debunker Model", "Debates", "FC Win %", "Avg Confidence", "Avg Margin"]]

            # Heatmap view of FC Win % by model matchup
            spr_models = sorted(matchup["model_spreader"].unique())
            deb_models = sorted(matchup["model_debunker"].unique())
            if len(spr_models) >= 2 or len(deb_models) >= 2:
                pivot = matchup.pivot_table(
                    index="model_spreader", columns="model_debunker",
                    values="FC Win %", aggfunc="first",
                )
                n_pivot = matchup.pivot_table(
                    index="model_spreader", columns="model_debunker",
                    values="Debates", aggfunc="first",
                )
                text_vals = [
                    [f"{v:.0f}%<br>n={int(n_pivot.iloc[r, c])}" if pd.notna(v) else "—"
                     for c, v in enumerate(row)]
                    for r, row in enumerate(pivot.values)
                ]
                fig_hm = go.Figure(go.Heatmap(
                    z=pivot.values,
                    x=[str(c) for c in pivot.columns],
                    y=[str(r) for r in pivot.index],
                    text=text_vals,
                    texttemplate="%{text}",
                    textfont=dict(size=12),
                    colorscale=[[0, "#C9363E"], [0.5, "#D4A843"], [1, "#4A7FA5"]],
                    zmin=0, zmax=100,
                    colorbar=dict(title="FC Win %", ticksuffix="%"),
                    hovertemplate="Spreader: %{y}<br>Debunker: %{x}<br>FC Win: %{z:.0f}%<extra></extra>",
                ))
                fig_hm.update_layout(
                    xaxis=dict(title="Debunker Model", tickfont=dict(size=11)),
                    yaxis=dict(title="Spreader Model", tickfont=dict(size=11), autorange="reversed"),
                    height=max(250, len(spr_models) * 60 + 100),
                    margin=dict(l=10, r=10, t=10, b=40),
                    **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                )
                st.plotly_chart(fig_hm, use_container_width=True)
                with st.expander("Full matchup table"):
                    st.dataframe(display_matchup, use_container_width=True, hide_index=True)
            else:
                st.dataframe(display_matchup, use_container_width=True, hide_index=True)

            # ── 2. Model effectiveness by role ───────────────────────────
            st.markdown(
                '<p class="ma-section-question">Model Effectiveness by Role</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="ma-chart-caption">'
                'Left: average persuasion score when a model plays the spreader role (higher = more persuasive spreader). '
                'Right: fact-checker win rate when a model plays the debunker role (higher = more effective debunker).'
                '</p>',
                unsafe_allow_html=True,
            )

            col_spr, col_deb = st.columns(2)

            # Left chart: Model as Spreader — avg persuasion score
            with col_spr:
                persuasion_col = None
                for candidate in ["metric_persuasion_spreader", "metric_persuasion_delta"]:
                    if candidate in model_df.columns:
                        persuasion_col = candidate
                        break

                if persuasion_col and model_df[persuasion_col].notna().any():
                    spr_perf = (
                        model_df.groupby("model_spreader")[persuasion_col]
                        .mean()
                        .sort_values(ascending=True)
                        .reset_index()
                    )
                    spr_perf.columns = ["Model", "Avg Persuasion"]
                    spr_perf["Avg Persuasion"] = spr_perf["Avg Persuasion"].round(2)

                    fig_spr = go.Figure(go.Bar(
                        x=spr_perf["Avg Persuasion"],
                        y=spr_perf["Model"],
                        orientation="h",
                        marker_color=SPREADER_COLOR,
                        text=spr_perf["Avg Persuasion"].apply(lambda v: f"{v:.1f}"),
                        textposition="outside",
                    ))
                    fig_spr.update_layout(
                        title=dict(text="Model as Spreader", font=dict(size=14)),
                        xaxis_title="Avg Persuasion Score",
                        yaxis_title="",
                        margin=dict(l=10, r=40, t=40, b=40),
                        height=max(250, len(spr_perf) * 45 + 80),
                        plot_bgcolor="#111111",
                    )
                    fig_spr.update_xaxes(range=[0, 10], gridcolor="#e8e8e8")
                    fig_spr.update_yaxes(gridcolor="#e8e8e8")
                    st.plotly_chart(fig_spr, use_container_width=True)
                else:
                    st.info("No persuasion scores available for spreader models yet.")

            # Right chart: Model as Fact-checker — FC win rate
            with col_deb:
                deb_perf = model_df.groupby("model_debunker").agg(
                    total=("winner", "size"),
                    wins=("winner", lambda x: (x == "debunker").sum()),
                ).reset_index()
                deb_perf["FC Win %"] = (deb_perf["wins"] / deb_perf["total"] * 100).round(1)
                deb_perf = deb_perf.sort_values("FC Win %", ascending=True).reset_index(drop=True)

                fig_deb = go.Figure(go.Bar(
                    x=deb_perf["FC Win %"],
                    y=deb_perf["model_debunker"],
                    orientation="h",
                    marker_color=DEBUNKER_COLOR,
                    text=deb_perf["FC Win %"].apply(lambda v: f"{v:.0f}%"),
                    textposition="outside",
                ))
                fig_deb.update_layout(
                    title=dict(text="Model as Fact-Checker", font=dict(size=14)),
                    xaxis_title="FC Win Rate (%)",
                    yaxis_title="",
                    margin=dict(l=10, r=40, t=40, b=40),
                    height=max(250, len(deb_perf) * 45 + 80),
                    plot_bgcolor="#111111",
                )
                fig_deb.update_xaxes(range=[0, 105], gridcolor="#e8e8e8")
                fig_deb.update_yaxes(gridcolor="#e8e8e8")
                st.plotly_chart(fig_deb, use_container_width=True)

            # ── 3. Cross-provider detection ──────────────────────────────
            if "cross_provider" in model_df.columns and model_df["cross_provider"].any():
                cp_count = int(model_df["cross_provider"].sum())
                st.caption(
                    f"{cp_count} of {len(model_df)} debate(s) used models from different providers "
                    f"(cross-provider matchup)."
                )

        # ── 4. Judge model comparison ────────────────────────────────
        st.markdown("---")
        st.markdown(
            '<p class="ma-section-question">Judge Model Comparison</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="ma-chart-caption">'
            'If different judge models score the same debate differently, the evaluation '
            'is model-dependent — a validity concern. High agreement means the scoring is robust; '
            'low agreement means results should be interpreted with caution.'
            '</p>',
            unsafe_allow_html=True,
        )

        judge_col = "judge_model"
        if judge_col not in df.columns or df[judge_col].nunique() < 2:
            st.info(
                "Only one judge model used across all episodes. "
                "Run experiments with different judge models (select in the sidebar) to enable this comparison."
            )
        else:
            judge_models = sorted(df[judge_col].dropna().unique())

            # FC win rate by judge model
            st.markdown("**FC win rate by judge model**")
            judge_wr = df.groupby(judge_col).apply(
                lambda g: pd.Series({
                    "n": len(g),
                    "fc_win_rate": (g["winner"].str.lower() == "debunker").mean(),
                    "avg_confidence": pd.to_numeric(g["judge_confidence"], errors="coerce").mean(),
                    "avg_margin": pd.to_numeric(g["abs_margin"], errors="coerce").mean(),
                })
            ).reset_index()

            disp_judge = judge_wr.copy()
            disp_judge.columns = ["Judge Model", "Debates", "FC Win %", "Avg Confidence", "Avg Margin"]
            disp_judge["Debates"] = disp_judge["Debates"].astype(int)
            disp_judge["FC Win %"] = disp_judge["FC Win %"].map(lambda v: f"{v:.0%}")
            disp_judge["Avg Confidence"] = disp_judge["Avg Confidence"].map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
            disp_judge["Avg Margin"] = disp_judge["Avg Margin"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
            st.dataframe(disp_judge, use_container_width=True, hide_index=True)

            # Confidence distribution by judge model
            st.markdown("**Confidence distribution by judge model**")
            fig_jconf = go.Figure()
            jcolors = [DEBUNKER_COLOR, SPREADER_COLOR, DRAW_COLOR] + ["#888"] * 10
            for i, jm in enumerate(judge_models):
                jm_data = pd.to_numeric(df[df[judge_col] == jm]["judge_confidence"], errors="coerce").dropna()
                if len(jm_data) > 0:
                    fig_jconf.add_trace(go.Box(
                        y=jm_data, name=str(jm),
                        marker_color=jcolors[i % len(jcolors)],
                        boxmean=True,
                    ))
            fig_jconf.update_layout(
                yaxis=dict(title="Judge Confidence", tickformat=".0%", range=[0, 1.05],
                           gridcolor="#2A2A2A"),
                margin=dict(t=10, b=40, l=60, r=15), height=300,
                **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                showlegend=False,
            )
            fig_jconf.update_yaxes(showgrid=True)
            st.plotly_chart(fig_jconf, use_container_width=True)

            # Average metric scores by judge model
            metric_cols_spr = [c for c in df.columns if c.startswith("metric_") and c.endswith("_spreader")]

            if metric_cols_spr:
                st.markdown("**Average metric scores by judge model**")
                # Build data for grouped bar chart
                jm_bar_data = []
                for jm in judge_models:
                    jm_df = df[df[judge_col] == jm]
                    for mc in metric_cols_spr:
                        metric_name = mc.replace("metric_", "").replace("_spreader", "").replace("_", " ").title()
                        s_mean = pd.to_numeric(jm_df[mc], errors="coerce").mean()
                        d_col = mc.replace("_spreader", "_debunker")
                        d_mean = pd.to_numeric(jm_df[d_col], errors="coerce").mean() if d_col in jm_df.columns else None
                        if pd.notna(s_mean):
                            jm_bar_data.append({"Judge": jm, "Metric": metric_name, "Side": "Spreader", "Score": round(s_mean, 1)})
                        if d_mean is not None and pd.notna(d_mean):
                            jm_bar_data.append({"Judge": jm, "Metric": metric_name, "Side": "Fact-checker", "Score": round(d_mean, 1)})

                if jm_bar_data:
                    jm_bar_df = pd.DataFrame(jm_bar_data)
                    fig_jm = go.Figure()
                    side_colors = {"Spreader": SPREADER_COLOR, "Fact-checker": DEBUNKER_COLOR}
                    for side in ["Spreader", "Fact-checker"]:
                        sub = jm_bar_df[jm_bar_df["Side"] == side]
                        if sub.empty:
                            continue
                        # x-axis labels combine judge + metric
                        x_labels = [f"{r['Metric']}<br><span style='font-size:10px'>{r['Judge']}</span>" for _, r in sub.iterrows()]
                        fig_jm.add_trace(go.Bar(
                            name=side, x=sub["Metric"], y=sub["Score"],
                            marker_color=side_colors[side], opacity=0.85,
                            text=sub["Score"].map(lambda v: f"{v:.1f}"),
                            textposition="outside", textfont=dict(size=10),
                            hovertemplate="%{x}: <b>%{y:.1f}</b> / 10<extra>" + side + "</extra>",
                        ))
                    fig_jm.update_layout(
                        barmode="group",
                        yaxis=dict(title="Score (0-10)", range=[0, 10.5], gridcolor="#2A2A2A"),
                        xaxis=dict(tickfont=dict(size=10)),
                        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"),
                        margin=dict(l=40, r=10, t=40, b=40), height=350,
                        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                    )
                    st.plotly_chart(fig_jm, use_container_width=True)

            st.markdown(
                '<p class="ma-chart-caption">'
                'If FC Win % varies significantly across judge models, the scoring is model-dependent. '
                'Consider using judge consistency runs (N>1) or fixing the judge model for all experiments.'
                '</p>',
                unsafe_allow_html=True,
            )

    # ── Concessions tab ──────────────────────────────────────────────────
    with tab_concessions:
        st.markdown(
            '<p class="ma-section-header">How do agents convince each other?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="ma-section-prose">'
            'When a debate ends early, one side conceded — meaning the other side\'s argument '
            'was convincing enough to trigger agreement. This section analyzes concession patterns: '
            'who concedes, when, for which claim types, and most importantly — what argument '
            'actually caused it.'
            '</p>',
            unsafe_allow_html=True,
        )

        if not df.empty and "end_trigger" in df.columns:
            trigger_counts = df["end_trigger"].fillna("max_turns").value_counts()
            total_eps = len(df)
            early_stop_n = int(df["early_stop"].sum()) if "early_stop" in df.columns and df["early_stop"].dtype == bool else 0

            # ── KPI cards ──
            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            with col_c1:
                st.metric("Total debates", total_eps)
            with col_c2:
                st.metric("Concessions", early_stop_n, delta=f"{early_stop_n/max(total_eps,1):.0%} of debates")
            with col_c3:
                if "conceded_by" in df.columns:
                    _spr_conc = (df["conceded_by"] == "spreader").sum()
                    _deb_conc = (df["conceded_by"] == "debunker").sum()
                    st.metric("Spreader conceded", int(_spr_conc))
                else:
                    st.metric("Spreader conceded", "—")
            with col_c4:
                if "conceded_by" in df.columns:
                    st.metric("FC conceded", int(_deb_conc))
                else:
                    st.metric("FC conceded", "—")

            # ── When do concessions happen? ──
            if "concession_turn" in df.columns:
                conc_turns = pd.to_numeric(df["concession_turn"], errors="coerce").dropna()
                if len(conc_turns) >= 2:
                    st.markdown(
                        '<p class="ma-section-header">When do concessions happen?</p>',
                        unsafe_allow_html=True,
                    )
                    fig_ct = go.Figure()
                    fig_ct.add_trace(go.Histogram(x=conc_turns, nbinsx=10, marker_color=DRAW_COLOR, opacity=0.85))
                    fig_ct.update_layout(
                        xaxis=dict(title="Turn number when concession occurred"),
                        yaxis=dict(title="Count"),
                        margin=dict(t=10, b=40, l=50, r=15), height=250,
                        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                    )
                    st.plotly_chart(fig_ct, use_container_width=True)
                    st.markdown(
                        '<p class="ma-chart-caption">'
                        'Early concessions (turn 1-2) suggest the opponent\'s opening was immediately '
                        'convincing. Late concessions suggest gradual persuasion over multiple exchanges.'
                        '</p>',
                        unsafe_allow_html=True,
                    )

            # ── Concession rates by claim type ──
            if "conceded_by" in df.columns and "claim_type" in df.columns:
                conc_by_type = df[df["conceded_by"].notna() & df["claim_type"].notna()].copy()
                if len(conc_by_type) >= 2:
                    st.markdown(
                        '<p class="ma-section-header">Which claim types trigger more concessions?</p>',
                        unsafe_allow_html=True,
                    )
                    ct_grp = conc_by_type.groupby("claim_type")["conceded_by"].value_counts().unstack(fill_value=0)
                    if not ct_grp.empty:
                        ct_grp.columns = [c.title() for c in ct_grp.columns]
                        fig_ctc = go.Figure()
                        conc_colors = {"Spreader": SPREADER_COLOR, "Debunker": DEBUNKER_COLOR}
                        for col_name in ct_grp.columns:
                            fig_ctc.add_trace(go.Bar(
                                name=col_name if col_name != "Debunker" else "Fact-checker",
                                x=ct_grp.index.tolist(),
                                y=ct_grp[col_name].tolist(),
                                marker_color=conc_colors.get(col_name, "#888"),
                                text=ct_grp[col_name].tolist(),
                                textposition="inside",
                                hovertemplate="%{x}<br>" + col_name + ": <b>%{y}</b><extra></extra>",
                            ))
                        fig_ctc.update_layout(
                            barmode="stack",
                            yaxis=dict(title="Concessions", gridcolor="#2A2A2A"),
                            xaxis=dict(tickangle=-25, tickfont=dict(size=11)),
                            legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"),
                            margin=dict(l=40, r=10, t=30, b=60), height=300,
                            **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                        )
                        st.plotly_chart(fig_ctc, use_container_width=True)

            # ── Concession rates by model ──
            if "conceded_by" in df.columns and "model_spreader" in df.columns:
                conc_by_model = df[df["conceded_by"].notna()].copy()
                if len(conc_by_model) >= 2:
                    st.markdown(
                        '<p class="ma-section-header">Which models concede more?</p>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        '<p class="ma-section-prose">'
                        'Do certain models give up more easily as the spreader? '
                        'Or are some models more resistant to conceding as the fact-checker?'
                        '</p>',
                        unsafe_allow_html=True,
                    )
                    _conc_model = conc_by_model.groupby(["model_spreader", "model_debunker", "conceded_by"]).size().reset_index(name="count")
                    _conc_model.columns = ["Spreader Model", "FC Model", "Conceded By", "Count"]
                    _conc_model["Conceded By"] = _conc_model["Conceded By"].str.title()
                    st.dataframe(_conc_model.sort_values("Count", ascending=False), use_container_width=True, hide_index=True)

            # ── The convincing arguments ──
            st.markdown(
                '<p class="ma-section-header">What arguments triggered concessions?</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="ma-section-prose">'
                'The most important question: what did the winning side actually say that convinced '
                'the other side to concede? Below are the final exchanges — the winning argument '
                'and the concession response — so you can study what makes an argument convincing.'
                '</p>',
                unsafe_allow_html=True,
            )

            conc_eps = df[df["early_stop"] == True].copy() if "early_stop" in df.columns else pd.DataFrame()
            if not conc_eps.empty and "run_id" in conc_eps.columns:
                from arena.io.run_store_v2_read import load_episodes as _load_eps

                _conc_count = 0
                for _, row in conc_eps.iterrows():
                    _rid = str(row.get("run_id", ""))
                    _eid = row.get("episode_id", 0)
                    _claim = str(row.get("claim", ""))[:70]
                    _conceded_by = str(row.get("conceded_by", "unknown"))
                    _conc_turn = row.get("concession_turn")
                    _winner = str(row.get("winner", "")).title()
                    _run_label = str(row.get("run_label", _rid))
                    _spr_model = str(row.get("model_spreader", ""))
                    _deb_model = str(row.get("model_debunker", ""))

                    try:
                        _eps_list, _ = _load_eps(_rid, RUNS_DIR)
                        _ep = next((e for e in _eps_list if e.get("episode_id") == _eid), None)
                    except Exception:
                        _ep = None

                    if not _ep:
                        continue

                    _turns = _ep.get("turns", [])
                    if not _turns:
                        continue

                    _last_msgs = _turns[-2:] if len(_turns) >= 2 else _turns
                    _conceder_label = "Spreader" if _conceded_by == "spreader" else "Fact-checker"
                    _convincer_label = "Fact-checker" if _conceded_by == "spreader" else "Spreader"
                    _border_color = DEBUNKER_COLOR if _conceded_by == "spreader" else SPREADER_COLOR

                    _model_info = ""
                    if _spr_model or _deb_model:
                        _model_info = f" · {_spr_model} vs {_deb_model}"

                    with st.expander(
                        f"{_conceder_label} conceded to {_convincer_label} — \"{_claim}\""
                        f" (Turn {_conc_turn or '?'}){_model_info}"
                    ):
                        for msg in _last_msgs:
                            _name = msg.get("name", msg.get("speaker", "?"))
                            _content = msg.get("content", "")
                            _is_conceder = _name.lower() == _conceded_by.lower()

                            if _is_conceder:
                                _label = f"{_name.upper()} — CONCEDED"
                                _bg = "rgba(240,165,0,0.06)"
                                _border = DRAW_COLOR
                            else:
                                _label = f"{_name.upper()} — WINNING ARGUMENT"
                                _bg = "rgba(58,126,199,0.05)" if _name.lower() == "debunker" else "rgba(232,82,74,0.05)"
                                _border = _border_color

                            st.markdown(
                                f'<div style="border-left:3px solid {_border};background:{_bg};'
                                f'border-radius:0 8px 8px 0;padding:0.7rem 1rem;margin-bottom:0.5rem">'
                                f'<span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
                                f'letter-spacing:0.07em;color:{_border}">{_label}</span><br>'
                                f'{_content[:800]}{"..." if len(_content) > 800 else ""}</div>',
                                unsafe_allow_html=True,
                            )

                        if st.button("Open in Replay", key=f"conc_replay_{_rid}_{_eid}"):
                            st.session_state["replay_target_run_id"] = _rid
                            st.session_state["replay_target_episode_id"] = str(_eid)
                            st.session_state["replay_target_source"] = "analytics_concession"
                            st.info("Switch to the **Replay** tab to view the full transcript.")

                    _conc_count += 1
                    if _conc_count >= 20:
                        st.caption(f"Showing first 20 of {len(conc_eps)} concessions.")
                        break
            else:
                st.info(
                    "No concessions detected yet. Concessions happen when an agent uses phrases "
                    "like 'I agree,' 'you're right,' or 'I concede.' Run more debates to see concession analysis here."
                )
        else:
            st.info("No debate data found yet.")

    # ── Anomalies tab ─────────────────────────────────────────────────────
    with tab_anomalies:
        st.markdown('<p class="ma-section-header">Unusual debates worth a closer look</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="ma-section-prose">'
            'Most debates follow a predictable pattern, but some stand out — the judge was unusually uncertain, '
            'the score was surprisingly close, or one side dramatically outperformed its typical level. '
            'These outliers are often the most interesting to replay. '
            'Select a metric below to find debates that deviate from the norm, then open any flagged debate '
            'directly in the <b>Run Replay</b> tab.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="ma-section-prose">'
            '<b>Score Margin</b> is the difference between the fact-checker\'s total score and the spreader\'s '
            'total score. A margin near 0 means the debate was very close; a margin of 2 or more means it was '
            'decisive. <b>Judge Confidence</b> is how certain the AI judge was in its verdict — a low-confidence '
            'debate might be worth reviewing manually.'
            '</p>',
            unsafe_allow_html=True,
        )

        ANOMALY_OPTIONS = [
            ("Judge Confidence",      "judge_confidence"),
            ("Score Margin",          "abs_margin"),
            ("Turns Completed",       "completed_turn_pairs"),
            ("Evidence Quality Gap",  "metric_evidence_quality_delta"),
            ("Reasoning Gap",         "metric_reasoning_quality_delta"),
            ("Persuasion Gap",        "metric_persuasion_delta"),
            ("Responsiveness Gap",    "metric_responsiveness_delta"),
            ("Factual Grounding Gap", "metric_truthfulness_proxy_delta"),
            ("Civility Gap",          "metric_civility_delta"),
        ]
        avail = [(lbl, col) for lbl, col in ANOMALY_OPTIONS if col in df.columns]

        if not avail:
            st.info("Not enough data for anomaly analysis yet.")
        else:
            lbl_to_col = {l: c for l, c in avail}
            opts = [l for l, _ in avail]

            if st.session_state.get("analytics_anomaly_metric") not in opts:
                st.session_state["analytics_anomaly_metric"] = opts[0]
            st.session_state.setdefault("analytics_anomaly_method", "IQR")
            st.session_state.setdefault("analytics_anomaly_flagged_only", False)

            ac1, ac2, ac3 = st.columns([2, 2, 1])
            with ac1:
                sel_lbl = st.selectbox("Measure", opts, key="analytics_anomaly_metric")
            with ac2:
                sel_method = st.selectbox("Detection method", ["IQR", "Robust Z-score (MAD)"],
                                          key="analytics_anomaly_method",
                                          help="IQR flags values outside the typical middle 50%. MAD is more robust to extreme outliers.")
            with ac3:
                flagged_only = st.checkbox("Flagged only", key="analytics_anomaly_flagged_only")

            col_name = lbl_to_col[sel_lbl]
            series = pd.to_numeric(df[col_name], errors="coerce").dropna()

            if len(series) < 2:
                st.info("Not enough data points for outlier detection yet.")
            else:
                if sel_method == "IQR":
                    is_outlier, lower, upper, _, _ = compute_iqr_outliers(df[col_name])
                    adf = df.copy()
                    adf["_val"]    = pd.to_numeric(adf[col_name], errors="coerce")
                    adf["_flag"]   = is_outlier.reindex(adf.index, fill_value=False)
                    adf["_reason"] = adf["_flag"].map(
                        lambda x: f"Outside normal range ({lower:.2f} – {upper:.2f})" if x else ""
                    )
                    adf["_lo"] = lower; adf["_hi"] = upper
                    adf["_score"] = adf["_val"].apply(
                        lambda v: (v - upper) if pd.notna(v) and v > upper
                                  else ((lower - v) if pd.notna(v) and v < lower else 0)
                    )
                else:
                    is_outlier, rz, med, mad = compute_mad_outliers(df[col_name])
                    adf = df.copy()
                    adf["_val"]    = pd.to_numeric(adf[col_name], errors="coerce")
                    adf["_flag"]   = is_outlier.reindex(adf.index, fill_value=False)
                    adf["_reason"] = adf["_flag"].map(
                        lambda x: "Statistically unusual (robust Z-score > 3.5)" if x else ""
                    )
                    lo = med - 3.5 * mad / 0.6745 if mad else med
                    hi = med + 3.5 * mad / 0.6745 if mad else med
                    adf["_lo"] = lo; adf["_hi"] = hi
                    adf["_score"] = rz.reindex(adf.index).fillna(0).abs()

                n_flagged = int(adf["_flag"].sum())
                vals = adf["_val"].dropna()

                if len(vals):
                    # Build customdata: "run_id|||episode_id|||claim (truncated)"
                    custom_series = (
                        adf.reindex(vals.index)["run_id"].fillna("").astype(str)
                        + "|||"
                        + adf.reindex(vals.index)["episode_id"].fillna("").astype(str)
                        + "|||"
                        + adf.reindex(vals.index)["claim"].fillna("").astype(str).str[:55]
                    )
                    flagged_for_vals = adf["_flag"].reindex(vals.index, fill_value=False)

                    strip_event = st.plotly_chart(
                        _strip(vals, flagged_for_vals, sel_lbl, customdata=custom_series),
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode=["points"],
                        key="anomaly_strip_chart",
                    )
                    st.markdown(
                        f'<p class="ma-chart-caption">'
                        f'Each dot is one debate. '
                        f'<b>{n_flagged} debate{"s" if n_flagged != 1 else ""} flagged</b> out of {len(vals)} — '
                        f'normal range: {adf["_lo"].iloc[0]:.2f} – {adf["_hi"].iloc[0]:.2f}. '
                        f'Red × markers are outliers. <b>Click any dot to select it</b>, then open it in Replay.'
                        f'</p>',
                        unsafe_allow_html=True,
                    )

                    # Handle click selection
                    selected_pts = []
                    try:
                        selected_pts = strip_event.selection.points or []
                    except Exception:
                        pass

                    sel_rid = sel_eid = sel_claim = None
                    if selected_pts:
                        raw = selected_pts[0].get("customdata", "") or ""
                        parts = str(raw).split("|||")
                        if len(parts) >= 2:
                            sel_rid   = parts[0] or None
                            sel_eid   = parts[1] or None
                            sel_claim = parts[2] if len(parts) > 2 else ""

                    if sel_rid and sel_eid is not None:
                        st.markdown(
                            f'<div class="ma-callout" style="margin-top:0.5rem;">'
                            f'<b>Selected:</b> Run <code>{sel_rid}</code> · Episode {sel_eid}'
                            f'{(" — " + sel_claim) if sel_claim else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button("Open in Replay →", key="analytics_open_replay", type="primary"):
                            st.session_state["replay_target_run_id"]     = str(sel_rid)
                            st.session_state["replay_target_episode_id"] = sel_eid
                            st.session_state["replay_target_source"]     = "analytics"
                            st.success("Debate queued. Switch to the **Run Replay** tab to view it.")
                    else:
                        st.caption("Click any dot on the chart above to select a debate, then open it in Replay.")

                    # Selectbox for flagged outliers
                    flagged_rows = adf[adf["_flag"] & adf["_val"].notna()].copy()
                    if len(flagged_rows) > 0 and "run_id" in flagged_rows.columns and "episode_id" in flagged_rows.columns:
                        outlier_options = []
                        for _, row in flagged_rows.iterrows():
                            rid = str(row.get("run_id", ""))
                            eid = str(row.get("episode_id", ""))
                            val = row.get("_val", "")
                            claim = str(row.get("claim", ""))[:45]
                            label = f"Run {rid} / Ep {eid} — {sel_lbl}: {val:.3f} — {claim}"
                            outlier_options.append((label, rid, eid))
                        if outlier_options:
                            st.markdown("**Flagged outlier episodes**")
                            out_idx = st.selectbox(
                                "Select a flagged episode",
                                range(len(outlier_options)),
                                format_func=lambda i: outlier_options[i][0],
                                key="anomaly_outlier_select",
                            )
                            if st.button("Open in Run Replay", key="anomaly_outlier_replay_btn"):
                                _, o_rid, o_eid = outlier_options[out_idx]
                                st.session_state["replay_target_run_id"] = o_rid
                                st.session_state["replay_target_episode_id"] = o_eid
                                st.session_state["replay_target_source"] = "analytics"
                                st.info("Switch to the **Run Replay** tab to view this episode.")

                # Scatter
                st.markdown(
                    '<p class="ma-section-question">Confidence vs. Score Margin</p>'
                    '<p class="ma-chart-caption">'
                    'Each point is one debate. The further right, the more decisive the result was '
                    '(larger score gap between the two sides). The higher up, the more confident the judge was. '
                    'Debates in the bottom-left corner — low margin <em>and</em> low confidence — are the most '
                    'ambiguous and worth reviewing. Hover over any point to see the claim.'
                    '</p>',
                    unsafe_allow_html=True,
                )

                if "abs_margin" in df.columns and "judge_confidence" in df.columns:
                    valid = df["abs_margin"].notna() & df["judge_confidence"].notna()
                    if valid.sum() > 1:
                        sc_df = df.loc[valid].copy()
                        sc_df["abs_margin"]       = pd.to_numeric(sc_df["abs_margin"], errors="coerce")
                        sc_df["judge_confidence"] = pd.to_numeric(sc_df["judge_confidence"], errors="coerce")
                        sc_df = sc_df.dropna(subset=["abs_margin","judge_confidence"])
                        if "winner" not in sc_df.columns: sc_df["winner"] = "unknown"
                        if len(sc_df):
                            st.plotly_chart(_scatter(sc_df), use_container_width=True)

                            # Jump to replay from scatter
                            if "run_id" in sc_df.columns and "episode_id" in sc_df.columns:
                                scatter_options = []
                                for _, row in sc_df.iterrows():
                                    rid = str(row.get("run_id", ""))
                                    eid = str(row.get("episode_id", ""))
                                    winner = str(row.get("winner", "")).capitalize()
                                    margin = row.get("abs_margin", 0)
                                    conf = row.get("judge_confidence", 0)
                                    claim = str(row.get("claim", ""))[:40]
                                    label = f"Run {rid} / Ep {eid} — {winner} — margin {margin:.2f}, conf {conf:.0%} — {claim}"
                                    scatter_options.append((label, rid, eid))
                                if scatter_options:
                                    sc_idx = st.selectbox(
                                        "Select an episode from the scatter plot",
                                        range(len(scatter_options)),
                                        format_func=lambda i: scatter_options[i][0],
                                        key="anomaly_scatter_select",
                                    )
                                    if st.button("Open in Run Replay", key="anomaly_scatter_replay_btn"):
                                        _, s_rid, s_eid = scatter_options[sc_idx]
                                        st.session_state["replay_target_run_id"] = s_rid
                                        st.session_state["replay_target_episode_id"] = s_eid
                                        st.session_state["replay_target_source"] = "analytics"
                                        st.info("Switch to the **Run Replay** tab to view this episode.")
                    else:
                        st.caption("Not enough data points yet.")
                else:
                    st.warning("Score margin or confidence columns not found in episode data.")
