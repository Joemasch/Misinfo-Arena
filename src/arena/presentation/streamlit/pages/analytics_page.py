"""
Analytics Page for Misinformation Arena v2.

Editorial, narrative-driven analytics from JSON v2 (runs/<run_id>/episodes.jsonl).
Read-only; no agent/judge calls.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

RUNS_DIR = "runs"

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------
SPREADER_COLOR  = "#E8524A"   # Coral red  — misinformation spreader
DEBUNKER_COLOR  = "#3A7EC7"   # Steel blue — fact-checker / debunker
DRAW_COLOR      = "#F0A500"   # Amber      — draw

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
    /* ── Global typography ── */
    [data-testid="stAppViewContainer"] {
        font-family: "Source Sans Pro", "Segoe UI", sans-serif;
    }

    /* ── Page title ── */
    .ma-page-title {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #111;
        margin-bottom: 0.15rem;
    }
    .ma-page-subtitle {
        font-size: 1rem;
        color: #555;
        margin-bottom: 1.5rem;
        line-height: 1.5;
    }

    /* ── Section headers (Part I / Part II style) ── */
    .ma-section-header {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111;
        margin-top: 2.5rem;
        margin-bottom: 0.2rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #e8e8e8;
    }
    .ma-section-question {
        font-size: 1rem;
        font-weight: 700;
        color: #222;
        margin-bottom: 0.4rem;
    }
    .ma-section-prose {
        font-size: 0.95rem;
        color: #444;
        line-height: 1.65;
        margin-bottom: 1.2rem;
        max-width: 760px;
    }

    /* ── Metric cards ── */
    .ma-metric-grid {
        display: flex;
        gap: 1rem;
        margin: 1.2rem 0 1.8rem 0;
        flex-wrap: wrap;
    }
    .ma-metric-card {
        flex: 1;
        min-width: 130px;
        background: #fff;
        border: 1px solid #e4e4e4;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .ma-metric-label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #888;
        margin-bottom: 0.25rem;
    }
    .ma-metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #111;
        line-height: 1.1;
    }
    .ma-metric-value.highlight-debunker { color: #3A7EC7; }
    .ma-metric-value.highlight-spreader  { color: #E8524A; }
    .ma-metric-value.highlight-neutral   { color: #F0A500; }
    .ma-metric-sub {
        font-size: 0.78rem;
        color: #777;
        margin-top: 0.2rem;
    }

    /* ── Summary callout ── */
    .ma-callout {
        background: #f0f6ff;
        border-left: 4px solid #3A7EC7;
        border-radius: 0 6px 6px 0;
        padding: 0.85rem 1.1rem;
        margin-bottom: 1.5rem;
        font-size: 0.95rem;
        color: #1a2e4a;
        line-height: 1.6;
    }
    .ma-callout.warning {
        background: #fff8f0;
        border-left-color: #F0A500;
        color: #4a3000;
    }

    /* ── Chart caption ── */
    .ma-chart-caption {
        font-size: 0.82rem;
        color: #666;
        line-height: 1.5;
        margin-top: 0.3rem;
        margin-bottom: 1rem;
        max-width: 760px;
    }

    /* ── Dimension definition grid ── */
    .ma-dim-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 0.75rem;
        margin: 0.5rem 0 1.5rem 0;
    }
    .ma-dim-card {
        background: #fafafa;
        border: 1px solid #e8e8e8;
        border-radius: 6px;
        padding: 0.75rem 1rem;
    }
    .ma-dim-name {
        font-size: 0.85rem;
        font-weight: 700;
        color: #222;
        margin-bottom: 0.2rem;
    }
    .ma-dim-desc {
        font-size: 0.8rem;
        color: #666;
        line-height: 1.45;
    }

    /* ── Divider ── */
    .ma-divider {
        border: none;
        border-top: 1px solid #e8e8e8;
        margin: 2rem 0;
    }

    /* ── Filter row ── */
    .ma-filter-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }

    /* Fix Streamlit expander border color (override red/orange) */
    [data-testid="stExpander"] {
        border: 1px solid #e4e4e4 !important;
        border-radius: 6px !important;
    }

    /* Tighten default Streamlit metric spacing */
    [data-testid="metric-container"] {
        background: #fff;
        border: 1px solid #e4e4e4;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
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
                   gridcolor="rgba(200,200,200,0.3)"),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=30, b=80, l=55, r=15), height=390,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _score_dist(long_df: pd.DataFrame) -> go.Figure:
    """Grouped box+strip chart: score distribution per metric per side across all debates."""
    canon = [m for m in CANONICAL_METRICS if m in long_df["metric_name"].unique()]
    fig = go.Figure()
    for side, color, fill, name in [
        ("spreader", SPREADER_COLOR, "rgba(232,82,74,0.08)",   "Spreader"),
        ("debunker", DEBUNKER_COLOR, "rgba(58,126,199,0.08)",  "Fact-checker"),
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
                   gridcolor="rgba(200,200,200,0.3)"),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=80, l=55, r=15), height=420,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
        yaxis=dict(title=label, tickfont=dict(size=11), gridcolor="rgba(200,200,200,0.3)"),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=60, l=55, r=15), height=300,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
                   tickfont=dict(size=11), gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(title="Judge Confidence  (0% = uncertain, 100% = certain)",
                   tickformat=".0%", tickfont=dict(size=11),
                   gridcolor="rgba(200,200,200,0.3)", range=[0, 1.05]),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=80, l=70, r=15), height=380,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
                   gridcolor="rgba(200,200,200,0.3)"),
        margin=dict(t=10, b=60, l=60, r=15),
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    fig.update_yaxes(showgrid=True)
    return fig


# ---------------------------------------------------------------------------
# Strategy × outcome helpers
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_strategy_outcomes(run_ids: tuple, runs_dir: str, token: float) -> pd.DataFrame:
    """Return long DataFrame: (strategy_label, role, winner) for every tagged episode."""
    from arena.io.run_store_v2_read import load_episodes
    rows: list[dict] = []
    for rid in run_ids:
        eps, _ = load_episodes(rid, runs_dir, token)
        for ep in eps:
            winner = (ep.get("results") or {}).get("winner", "").strip().lower()
            sa     = ep.get("strategy_analysis") or {}
            for lbl in (sa.get("spreader_strategies") or []):
                if lbl and isinstance(lbl, str):
                    rows.append({"strategy": lbl.strip(), "role": "spreader", "winner": winner})
            for lbl in (sa.get("debunker_strategies") or []):
                if lbl and isinstance(lbl, str):
                    rows.append({"strategy": lbl.strip(), "role": "debunker", "winner": winner})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["strategy", "role", "winner"])


def _strategy_label(s: str) -> str:
    return s.replace("_", " ").title()


def _strategy_outcome_chart(so_df: pd.DataFrame, role: str, min_n: int = 2) -> "go.Figure | None":
    """Horizontal stacked bar: for each strategy label, FC% vs Spr% vs Draw% of debates it appeared in."""
    sub = so_df[so_df["role"] == role].copy()
    if sub.empty:
        return None

    # Count outcome per strategy label
    counts = sub.groupby(["strategy", "winner"]).size().unstack(fill_value=0).reset_index()
    counts["n_total"] = counts.drop(columns="strategy").sum(axis=1)
    counts = counts[counts["n_total"] >= min_n].copy()
    if counts.empty:
        return None

    for col in ["debunker", "spreader", "draw"]:
        if col not in counts.columns:
            counts[col] = 0
    counts["fc_pct"]  = counts["debunker"] / counts["n_total"] * 100
    counts["spr_pct"] = counts["spreader"] / counts["n_total"] * 100
    counts["draw_pct"]= counts.get("draw", 0) / counts["n_total"] * 100

    # Sort: for spreader strategies sort by spr_pct desc; for debunker by fc_pct desc
    sort_col = "spr_pct" if role == "spreader" else "fc_pct"
    counts = counts.sort_values(sort_col, ascending=True)  # ascending=True because horizontal bars read bottom→top

    labels = [_strategy_label(s) for s in counts["strategy"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Fact-checker wins", y=labels, x=counts["fc_pct"], orientation="h",
        marker_color=DEBUNKER_COLOR, opacity=0.85,
        text=[f"{v:.0f}%" if v >= 8 else "" for v in counts["fc_pct"]],
        textposition="inside", textfont=dict(size=10, color="white"),
        hovertemplate="%{y}<br>FC wins: <b>%{x:.0f}%</b><extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Spreader wins", y=labels, x=counts["spr_pct"], orientation="h",
        marker_color=SPREADER_COLOR, opacity=0.85,
        text=[f"{v:.0f}%" if v >= 8 else "" for v in counts["spr_pct"]],
        textposition="inside", textfont=dict(size=10, color="white"),
        hovertemplate="%{y}<br>Spr wins: <b>%{x:.0f}%</b><extra></extra>",
    ))
    if counts["draw_pct"].sum() > 0:
        fig.add_trace(go.Bar(
            name="Draw", y=labels, x=counts["draw_pct"], orientation="h",
            marker_color=DRAW_COLOR, opacity=0.75,
            hovertemplate="%{y}<br>Draw: <b>%{x:.0f}%</b><extra></extra>",
        ))

    # Annotate sample sizes on the right
    for i, (_, row) in enumerate(counts.iterrows()):
        fig.add_annotation(
            x=101, y=labels[i], text=f"n={int(row['n_total'])}",
            xanchor="left", showarrow=False,
            font=dict(size=9, color="#9ca3af"),
        )

    fig.update_layout(
        barmode="stack",
        xaxis=dict(range=[0, 115], ticksuffix="%", showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=11)),
        margin=dict(t=10, b=55, l=10, r=55),
        height=max(200, len(labels) * 36 + 80),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Claim difficulty helpers
# ---------------------------------------------------------------------------

def _compute_claim_difficulty(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-claim difficulty metrics, sorted hardest→easiest."""
    if "claim" not in df.columns or df["claim"].isna().all():
        return pd.DataFrame()

    grp = df.groupby("claim").agg(
        n_episodes        =("winner",          "count"),
        fc_wins           =("winner",          lambda x: (x.str.lower() == "debunker").sum()),
        spr_wins          =("winner",          lambda x: (x.str.lower() == "spreader").sum()),
        avg_confidence    =("judge_confidence", "mean"),
        avg_margin        =("abs_margin",       "mean"),
        margin_std        =("abs_margin",       "std"),
    ).reset_index()

    grp["fc_win_rate"]  = grp["fc_wins"]  / grp["n_episodes"]
    grp["spr_win_rate"] = grp["spr_wins"] / grp["n_episodes"]

    max_std = grp["margin_std"].max()
    grp["margin_std_norm"] = (grp["margin_std"] / max_std).fillna(0) if max_std > 0 else 0.0

    # Difficulty = hard to debunk: high Spr win rate + low confidence + high result variance
    grp["difficulty_index"] = (
        grp["spr_win_rate"].fillna(0)           * 0.45 +
        (1 - grp["avg_confidence"].fillna(0.5)) * 0.35 +
        grp["margin_std_norm"]                  * 0.20
    )
    grp["avg_confidence"] = grp["avg_confidence"].fillna(0)
    grp["margin_std"]     = grp["margin_std"].fillna(0)
    return grp.sort_values("difficulty_index", ascending=False).reset_index(drop=True)


def _claim_difficulty_chart(diff_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: difficulty index per claim, top 12."""
    top = diff_df.head(12).copy()
    claims = [c[:55] + "…" if len(c) > 55 else c for c in top["claim"]]
    idx    = top["difficulty_index"].tolist()

    # Color by how often spreader wins: red = spreader wins, blue = FC wins
    colors = [
        SPREADER_COLOR if row["spr_win_rate"] >= 0.5 else DEBUNKER_COLOR
        for _, row in top.iterrows()
    ]

    fig = go.Figure(go.Bar(
        y=claims[::-1], x=idx[::-1], orientation="h",
        marker_color=colors[::-1], opacity=0.85,
        text=[f"{v:.2f}" for v in idx[::-1]],
        textposition="outside",
        hovertemplate=(
            "%{y}<br>Difficulty: <b>%{x:.2f}</b><br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        xaxis=dict(title="Difficulty index (0 = easy, 1 = very hard)",
                   range=[0, 1.15], tickfont=dict(size=10),
                   gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=10, b=40, l=10, r=55),
        height=max(200, len(top) * 38 + 60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
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
    # PART I — WIN RATES
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Part I: Who is winning?</p>', unsafe_allow_html=True)

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

    with st.expander("Browse all episode data", expanded=False):
        preview_cols = [c for c in PREVIEW_COLUMNS if c in df.columns]
        if preview_cols:
            disp = df[preview_cols].copy()
            disp = disp.rename(columns={k: v for k, v in EPISODE_TABLE_RENAME.items() if k in disp.columns})
            if "How It Ended" in disp.columns:
                disp["How It Ended"] = disp["How It Ended"].apply(_fmt_trigger)
            if "Winner" in disp.columns:
                disp["Winner"] = disp["Winner"].str.capitalize()
            if "Confidence" in disp.columns:
                disp["Confidence"] = pd.to_numeric(disp["Confidence"], errors="coerce").map(
                    lambda v: f"{v:.0%}" if pd.notna(v) else "—"
                )
            st.dataframe(disp.head(50), use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download CSV", df.to_csv(index=False).encode(), "episodes.csv", "text/csv")
        with c2:
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

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART II — PERFORMANCE BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Part II: How did each side argue?</p>', unsafe_allow_html=True)
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

    long_df = _load_long(tuple(run_ids), RUNS_DIR, token)

    if long_df.empty:
        st.warning("No scored episodes found. The judge needs to have run successfully on at least one debate.")
    else:
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

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            sel_arena    = st.multiselect("Arena type", arena_opts, default=[], key="ra_arena")
        with fc2:
            sel_spreader = st.multiselect("Spreader model", spreader_opts, default=[], key="ra_spreader")
        with fc3:
            sel_debunker = st.multiselect("Debunker model", debunker_opts, default=[], key="ra_debunker")

        excl_err = st.checkbox("Exclude debates with judge errors", value=True, key="ra_exclude_err")

        with st.expander("Advanced filters", expanded=False):
            DEFAULT_JUDGE_MODES = ["agent"]
            sel_judge = st.multiselect(
                "Judge type", judge_opts,
                default=DEFAULT_JUDGE_MODES if "agent" in judge_opts else (judge_opts[:1] if judge_opts else []),
                key="ra_judge",
            )
            jm_disabled = "agent" not in (sel_judge or DEFAULT_JUDGE_MODES)
            sel_jmodel  = st.multiselect("Judge model", jmodel_opts, default=[], key="ra_judge_model", disabled=jm_disabled)
            fp_agg  = st.selectbox("Fingerprint aggregation", ["mean", "sum", "median"], index=0, key="ra_fp_agg")
            traj_view = st.selectbox("Trajectory view", ["raw", "normalized"], index=0, key="ra_traj_view")

        eff_judge  = (sel_judge or None) or DEFAULT_JUDGE_MODES
        eff_jmodel = sel_jmodel or None
        eff_fp_agg = fp_agg if "fp_agg" in dir() else "mean"
        eff_traj   = traj_view if "traj_view" in dir() else "raw"

        filtered = apply_research_filters(
            long_df,
            arena_types=sel_arena or None,
            judge_modes=eff_judge,
            spreader_models=sel_spreader or None,
            debunker_models=sel_debunker or None,
            judge_models=eff_jmodel,
            exclude_error_episodes=excl_err,
        )

        if filtered.empty:
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
                    '(<span style="color:#3A7EC7"><b>blue = fact-checker leads</b></span>, '
                    '<span style="color:#E8524A"><b>red = spreader leads</b></span>). '
                    'Bars above 7 are a clear strength; below 4 is a weakness.</p>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(_bar(fp_df), use_container_width=True)

            # Score distribution
            st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)
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

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART III — UNUSUAL DEBATES
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Part III: Unusual debates worth a closer look</p>', unsafe_allow_html=True)
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

            # Scatter
            st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)
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
                else:
                    st.caption("Not enough data points yet.")
            else:
                st.warning("Score margin or confidence columns not found in episode data.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART IV — CLAIM DIFFICULTY INDEX
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Part IV: Which claims are hardest to debunk?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ma-section-prose">'
        'The <b>Difficulty Index</b> is a composite score (0–1) that measures how resistant a claim '
        'is to fact-checking across all debates involving it. A high index means the spreader wins '
        'more often, the judge is less confident, and results are inconsistent across runs — '
        'all signs of a genuinely hard claim to counter. '
        '<b>Red bars</b> = spreader won the majority; '
        '<b>Blue bars</b> = fact-checker won the majority.'
        '</p>',
        unsafe_allow_html=True,
    )

    diff_df = _compute_claim_difficulty(df)
    if diff_df.empty or len(diff_df) < 1:
        st.info(
            "Not enough claim data yet. Run more debates — ideally multiple episodes per claim — "
            "to see difficulty rankings."
        )
    else:
        if len(diff_df) == 1:
            st.info(
                "Only one unique claim in the data. Run debates across multiple claims "
                "to compare difficulty."
            )
        else:
            st.plotly_chart(_claim_difficulty_chart(diff_df), use_container_width=True)

        # Ranked table
        st.markdown(
            '<p class="ma-section-question" style="margin-top:0.5rem;">Claim difficulty breakdown</p>',
            unsafe_allow_html=True,
        )
        disp_diff = diff_df[[
            "claim", "n_episodes", "fc_win_rate", "spr_win_rate",
            "avg_confidence", "difficulty_index"
        ]].copy()
        disp_diff.columns = [
            "Claim", "Episodes", "FC Win %", "Spr Win %", "Avg Confidence", "Difficulty"
        ]
        disp_diff["FC Win %"]       = disp_diff["FC Win %"].map(lambda v: f"{v:.0%}")
        disp_diff["Spr Win %"]      = disp_diff["Spr Win %"].map(lambda v: f"{v:.0%}")
        disp_diff["Avg Confidence"] = disp_diff["Avg Confidence"].map(lambda v: f"{v:.0%}")
        disp_diff["Difficulty"]     = disp_diff["Difficulty"].map(lambda v: f"{v:.2f}")
        st.dataframe(disp_diff, use_container_width=True, hide_index=True)
        st.markdown(
            '<p class="ma-chart-caption">'
            'Difficulty = 0.45 × Spreader win rate + 0.35 × (1 − Avg confidence) + 0.20 × Score variance. '
            'Requires multiple episodes per claim for reliable estimates.'
            '</p>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART V — STRATEGY × OUTCOME CORRELATION
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="ma-section-header">Part V: Which argument tactics predict winning?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ma-section-prose">'
        'For every debate where strategy tagging ran, the AI labeled which rhetorical tactics '
        'each side used. The charts below show, for each tactic, how often the debate ended '
        'in a fact-checker win vs. a spreader win. '
        'A bar that is mostly blue means debates where that tactic was used tended to go to the '
        'fact-checker; a mostly red bar means the spreader benefited. '
        'Only tactics appearing in at least 2 debates are shown. '
        '<em>n</em> = number of debates where that tactic was detected.'
        '</p>',
        unsafe_allow_html=True,
    )

    so_df = _load_strategy_outcomes(tuple(run_ids), RUNS_DIR, token)

    if so_df.empty:
        st.info(
            "No strategy analysis data found. Strategy tagging runs automatically after each debate — "
            "complete a few more debates to see results here."
        )
    else:
        strat_tabs = st.tabs(["Spreader tactics", "Debunker tactics"])

        with strat_tabs[0]:
            st.markdown(
                '<p class="ma-section-prose" style="margin-bottom:0.5rem;">'
                'When the <b>spreader</b> used each tactic, how did the debate end?</p>',
                unsafe_allow_html=True,
            )
            fig_spr = _strategy_outcome_chart(so_df, role="spreader", min_n=2)
            if fig_spr is None:
                st.info("Not enough spreader strategy data yet (need ≥2 debates per tactic).")
            else:
                st.plotly_chart(fig_spr, use_container_width=True)

        with strat_tabs[1]:
            st.markdown(
                '<p class="ma-section-prose" style="margin-bottom:0.5rem;">'
                'When the <b>fact-checker</b> used each tactic, how did the debate end?</p>',
                unsafe_allow_html=True,
            )
            fig_deb = _strategy_outcome_chart(so_df, role="debunker", min_n=2)
            if fig_deb is None:
                st.info("Not enough debunker strategy data yet (need ≥2 debates per tactic).")
            else:
                st.plotly_chart(fig_deb, use_container_width=True)

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART VI — MODEL VS MODEL COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part VI: How do different models perform against each other?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'When you run debates with different LLM models (e.g., GPT-4o spreader vs Claude debunker), '
        'this section shows how each model performs by role. '
        '<b>Cross-provider matchups</b> (OpenAI vs Anthropic) are highlighted.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty and "model_spreader" in df.columns and "model_debunker" in df.columns:
        _model_df = df.dropna(subset=["model_spreader", "model_debunker", "winner"]).copy()
        if len(_model_df) >= 2:
            matchup = _model_df.groupby(["model_spreader", "model_debunker"]).apply(
                lambda g: pd.Series({
                    "n": len(g),
                    "fc_win_rate": (g["winner"].str.lower() == "debunker").mean(),
                    "avg_confidence": pd.to_numeric(g["judge_confidence"], errors="coerce").mean(),
                    "avg_margin": pd.to_numeric(g["abs_margin"], errors="coerce").mean(),
                })
            ).reset_index()

            if not matchup.empty:
                matchup_disp = matchup.copy()
                matchup_disp.columns = ["Spreader Model", "FC Model", "Debates", "FC Win %", "Avg Confidence", "Avg Margin"]
                matchup_disp["Debates"] = matchup_disp["Debates"].astype(int)
                matchup_disp["FC Win %"] = matchup_disp["FC Win %"].map(lambda v: f"{v:.0%}")
                matchup_disp["Avg Confidence"] = matchup_disp["Avg Confidence"].map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
                matchup_disp["Avg Margin"] = matchup_disp["Avg Margin"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
                st.dataframe(matchup_disp, use_container_width=True, hide_index=True)

                if "cross_provider" in _model_df.columns and _model_df["cross_provider"].any():
                    n_cross = int(_model_df["cross_provider"].sum())
                    st.caption(f"{n_cross} cross-provider debate(s) detected (OpenAI vs Anthropic).")

                st.markdown("**Model effectiveness as fact-checker**")
                deb_perf = _model_df.groupby("model_debunker").apply(
                    lambda g: pd.Series({
                        "n": len(g),
                        "fc_win_rate": (g["winner"].str.lower() == "debunker").mean(),
                    })
                ).reset_index().sort_values("fc_win_rate", ascending=False)
                if len(deb_perf) > 1:
                    fig_model = go.Figure()
                    fig_model.add_trace(go.Bar(
                        y=deb_perf["model_debunker"],
                        x=deb_perf["fc_win_rate"],
                        orientation="h",
                        marker_color=DEBUNKER_COLOR,
                        text=[f"{v:.0%} (n={int(n)})" for v, n in zip(deb_perf["fc_win_rate"], deb_perf["n"])],
                        textposition="outside",
                    ))
                    fig_model.update_layout(
                        xaxis=dict(title="Fact-checker Win Rate", tickformat=".0%", range=[0, 1.1]),
                        yaxis=dict(title=""),
                        margin=dict(t=10, b=40, l=150, r=60), height=max(200, len(deb_perf) * 45),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    )
                    fig_model.update_xaxes(showgrid=True, gridcolor="rgba(200,200,200,0.3)")
                    st.plotly_chart(fig_model, use_container_width=True)
                else:
                    st.caption("Only one model used — run debates with different models to see comparison.")
        else:
            st.info("Need at least 2 episodes with model data to show comparisons.")
    else:
        st.info("No model information found in episode data.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART VII — PROMPT VARIANT A/B COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part VII: Which prompt variants perform best?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'Every episode records which prompt library variant was active for each agent. '
        'This section compares win rates across prompt variants so you can see which '
        'prompt strategies are most effective. Only variants with ≥2 episodes are shown.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty and "prompt_id_spreader" in df.columns:
        _has_spr = df["prompt_id_spreader"].notna() & (df["prompt_id_spreader"] != "")
        _has_deb = df["prompt_id_debunker"].notna() & (df["prompt_id_debunker"] != "") if "prompt_id_debunker" in df.columns else pd.Series(False, index=df.index)

        if _has_spr.any() or _has_deb.any():
            prompt_tabs = st.tabs(["Spreader prompts", "Fact-checker prompts"])

            for tab_idx, (ptab, role, pid_col) in enumerate(zip(
                prompt_tabs,
                ["spreader", "debunker"],
                ["prompt_id_spreader", "prompt_id_debunker"],
            )):
                with ptab:
                    if pid_col not in df.columns:
                        st.info(f"No {role} prompt variant data found.")
                        continue
                    valid = df[df[pid_col].notna() & (df[pid_col] != "") & df["winner"].notna()].copy()
                    if valid.empty:
                        st.info(f"No {role} prompt variant data found.")
                        continue
                    grp = valid.groupby(pid_col).apply(
                        lambda g: pd.Series({
                            "n": len(g),
                            "fc_win_rate": (g["winner"].str.lower() == "debunker").mean(),
                            "avg_confidence": pd.to_numeric(g["judge_confidence"], errors="coerce").mean(),
                        })
                    ).reset_index()
                    grp = grp[grp["n"] >= 2].sort_values("fc_win_rate", ascending=False)
                    if grp.empty:
                        st.info(f"Need ≥2 episodes per variant to compare. Run more debates with different {role} prompts.")
                        continue
                    disp = grp.copy()
                    disp.columns = ["Prompt ID", "Debates", "FC Win %", "Avg Confidence"]
                    disp["Debates"] = disp["Debates"].astype(int)
                    disp["FC Win %"] = disp["FC Win %"].map(lambda v: f"{v:.0%}")
                    disp["Avg Confidence"] = disp["Avg Confidence"].map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
                    st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.info(
                "No prompt variant IDs found in episode data. "
                "Apply a prompt from the Prompt Library before running debates to enable A/B tracking."
            )
    else:
        st.info("No prompt variant data available yet.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART VIII — CONCESSION ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part VIII: When and how do debates end early?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'Some debates end before the maximum turns because one side concedes. '
        'This section shows concession patterns: who concedes more often, at what turn, '
        'and whether certain claim types trigger earlier concessions.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty and "end_trigger" in df.columns:
        trigger_counts = df["end_trigger"].fillna("max_turns").value_counts()
        total_eps = len(df)
        early_stop_n = int(df["early_stop"].sum()) if "early_stop" in df.columns and df["early_stop"].dtype == bool else 0

        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.metric("Total debates", total_eps)
        with col_c2:
            st.metric("Early stops", early_stop_n, delta=f"{early_stop_n/max(total_eps,1):.0%} of debates")
        with col_c3:
            if "conceded_by" in df.columns:
                concessions = df["conceded_by"].dropna()
                if len(concessions):
                    most_common = concessions.value_counts().index[0]
                    st.metric("Most likely to concede", most_common.title())
                else:
                    st.metric("Concessions detected", 0)
            else:
                st.metric("Concession data", "Not available")

        st.markdown("**How debates end**")
        trigger_disp = pd.DataFrame({
            "Trigger": trigger_counts.index.map(lambda x: _fmt_trigger(x)),
            "Count": trigger_counts.values,
            "%": (trigger_counts.values / total_eps * 100).round(1),
        })
        st.dataframe(trigger_disp, use_container_width=True, hide_index=True)

        if "concession_turn" in df.columns:
            conc_turns = pd.to_numeric(df["concession_turn"], errors="coerce").dropna()
            if len(conc_turns) >= 2:
                st.markdown("**When do concessions happen?**")
                fig_ct = go.Figure()
                fig_ct.add_trace(go.Histogram(x=conc_turns, nbinsx=10, marker_color=DRAW_COLOR, opacity=0.8))
                fig_ct.update_layout(
                    xaxis=dict(title="Turn number"), yaxis=dict(title="Count"),
                    margin=dict(t=10, b=40, l=50, r=15), height=250,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_ct, use_container_width=True)

        if "conceded_by" in df.columns and "claim_type" in df.columns:
            conc_by_type = df[df["conceded_by"].notna() & df["claim_type"].notna()].copy()
            if len(conc_by_type) >= 2:
                st.markdown("**Concession rates by claim type**")
                ct_grp = conc_by_type.groupby("claim_type")["conceded_by"].value_counts().unstack(fill_value=0)
                if not ct_grp.empty:
                    st.dataframe(ct_grp, use_container_width=True)
    else:
        st.info("No end-trigger data found yet.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART IX — RESPONSE LENGTH ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part IX: Does message length predict winning?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'Each debate\'s transcript is stored in full. This section measures whether longer '
        'responses correlate with better outcomes — a strong correlation would suggest that '
        'verbosity (or depth) is a factor in the judge\'s evaluation.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty and "avg_spreader_chars" in df.columns and "avg_debunker_chars" in df.columns:
        len_df = df[["avg_spreader_chars", "avg_debunker_chars", "winner", "judge_confidence", "abs_margin"]].dropna(
            subset=["avg_spreader_chars", "avg_debunker_chars", "winner"]
        ).copy()
        len_df["avg_spreader_chars"] = pd.to_numeric(len_df["avg_spreader_chars"], errors="coerce")
        len_df["avg_debunker_chars"] = pd.to_numeric(len_df["avg_debunker_chars"], errors="coerce")
        len_df = len_df.dropna(subset=["avg_spreader_chars", "avg_debunker_chars"])
        len_df = len_df[(len_df["avg_spreader_chars"] > 0) | (len_df["avg_debunker_chars"] > 0)]

        if len(len_df) >= 3:
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                st.metric("Avg spreader message", f"{len_df['avg_spreader_chars'].mean():.0f} chars")
            with col_l2:
                st.metric("Avg fact-checker message", f"{len_df['avg_debunker_chars'].mean():.0f} chars")

            len_df["abs_margin"] = pd.to_numeric(len_df["abs_margin"], errors="coerce")
            valid_scatter = len_df.dropna(subset=["abs_margin"])
            if len(valid_scatter) >= 3:
                cmap = {"debunker": DEBUNKER_COLOR, "spreader": SPREADER_COLOR, "draw": DRAW_COLOR}
                fig_len = go.Figure()
                for w in valid_scatter["winner"].unique():
                    sub = valid_scatter[valid_scatter["winner"] == w]
                    fig_len.add_trace(go.Scatter(
                        x=sub["avg_debunker_chars"], y=sub["abs_margin"],
                        mode="markers",
                        name=w.title().replace("Debunker", "FC wins").replace("Spreader", "Spr wins"),
                        marker=dict(color=cmap.get(w.lower(), "#888"), size=8, opacity=0.7),
                    ))
                fig_len.update_layout(
                    xaxis=dict(title="Avg fact-checker message length (chars)"),
                    yaxis=dict(title="Score margin"),
                    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                    margin=dict(t=10, b=70, l=60, r=15), height=320,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                fig_len.update_xaxes(showgrid=True, gridcolor="rgba(200,200,200,0.3)")
                fig_len.update_yaxes(showgrid=True, gridcolor="rgba(200,200,200,0.3)")
                st.plotly_chart(fig_len, use_container_width=True)
                st.markdown(
                    '<p class="ma-chart-caption">'
                    'Each point is one debate. If longer fact-checker messages cluster with larger margins, '
                    'message depth may be helping the judge differentiate quality.'
                    '</p>',
                    unsafe_allow_html=True,
                )

            st.markdown("**Average message length by outcome**")
            by_winner = len_df.groupby("winner")[["avg_spreader_chars", "avg_debunker_chars"]].mean().round(0)
            by_winner.columns = ["Avg Spreader (chars)", "Avg FC (chars)"]
            st.dataframe(by_winner, use_container_width=True)
        else:
            st.info("Need at least 3 episodes with transcript data.")
    else:
        st.info("No response length data available yet.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART X — LONGITUDINAL TRENDS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part X: How has performance changed over time?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'Each episode records when it was created. This timeline shows how key metrics '
        'evolve across your research — useful for spotting improvements from prompt changes, '
        'model upgrades, or judge tuning.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty and "created_at" in df.columns:
        time_df = df.copy()
        time_df["created_at"] = pd.to_datetime(time_df["created_at"], errors="coerce")
        time_df = time_df.dropna(subset=["created_at"]).sort_values("created_at")

        if len(time_df) >= 3:
            time_df["judge_confidence"] = pd.to_numeric(time_df["judge_confidence"], errors="coerce")
            time_df["abs_margin"] = pd.to_numeric(time_df["abs_margin"], errors="coerce")
            time_df["fc_win"] = (time_df["winner"].str.lower() == "debunker").astype(float)

            window = min(5, max(2, len(time_df) // 3))
            time_df["rolling_confidence"] = time_df["judge_confidence"].rolling(window, min_periods=1).mean()
            time_df["rolling_margin"] = time_df["abs_margin"].rolling(window, min_periods=1).mean()
            time_df["rolling_fc_win"] = time_df["fc_win"].rolling(window, min_periods=1).mean()

            metric_choice = st.selectbox(
                "Trend metric",
                options=["FC win rate", "Judge confidence", "Score margin"],
                key="trend_metric_select",
            )
            col_map = {
                "FC win rate": ("rolling_fc_win", "FC Win Rate (rolling avg)", ".0%"),
                "Judge confidence": ("rolling_confidence", "Judge Confidence (rolling avg)", ".0%"),
                "Score margin": ("rolling_margin", "Score Margin (rolling avg)", ".2f"),
            }
            y_col, y_title, y_fmt = col_map[metric_choice]

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=time_df["created_at"], y=time_df[y_col],
                mode="lines+markers",
                line=dict(color=DEBUNKER_COLOR, width=2),
                marker=dict(size=5),
                hovertemplate="<b>%{x|%b %d, %H:%M}</b><br>" + y_title + ": %{y:" + y_fmt + "}<extra></extra>",
            ))
            fig_trend.update_layout(
                xaxis=dict(title=""), yaxis=dict(title=y_title, tickformat=y_fmt, gridcolor="rgba(200,200,200,0.3)"),
                margin=dict(t=10, b=40, l=60, r=15), height=300,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
            )
            fig_trend.update_xaxes(showgrid=True, gridcolor="rgba(200,200,200,0.3)")
            fig_trend.update_yaxes(showgrid=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            st.markdown(
                f'<p class="ma-chart-caption">'
                f'Rolling average (window={window}) smooths noise. '
                f'An upward trend in FC win rate or confidence suggests prompt/judge improvements are working.'
                f'</p>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Need at least 3 episodes with timestamps.")
    else:
        st.info("No timestamp data found in episodes.")

    st.markdown('<hr class="ma-divider">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PART XI — JUDGE CALIBRATION
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="ma-section-header">Part XI: Is the judge well-calibrated?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="ma-section-prose">'
        'A well-calibrated judge should express <b>high confidence only when the score margin is large</b> '
        '— i.e., when one side clearly dominated. If the bars below are flat or random, the judge\'s '
        'confidence numbers are not tracking debate decisiveness and should be interpreted with caution. '
        'An upward-sloping pattern (low-confidence episodes have low margins, high-confidence episodes '
        'have large margins) indicates good calibration. '
        'Each bar shows the mean score gap across all debates in that confidence bucket; '
        '<em>n</em> = number of debates.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not df.empty:
        fig_cal = _calibration_plot(df)
        if fig_cal is not None:
            st.plotly_chart(fig_cal, use_container_width=True)
            st.markdown(
                '<p class="ma-chart-caption">'
                'How to read: taller bars at the right side = confidence tracks decisiveness. '
                'Flat bars = confidence is not predictive of outcome clarity — consider using Judge Consistency Mode (≥3 runs) to improve reliability.'
                '</p>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Not enough data for calibration analysis (need ≥4 episodes with both confidence and margin values).")
    else:
        st.info("Run some debates to see calibration data here.")
