"""
Research Analysis Page for Misinformation Arena v2.

Experiment-specific analyses that answer the core research questions:
- RQ1: How does conversation length affect strategy?
- RQ2: How do agents perform across domains? (covered by Claim Analysis)
- RQ3: Does the judge model affect verdicts?
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.analysis.episode_dataset import (
    build_episode_df,
    build_strategy_long_df,
)
from arena.io.run_store_v2_read import list_runs
from arena.presentation.streamlit.pages.citation_page import render_citation_page
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.styles import PLOTLY_LAYOUT

RUNS_DIR = "runs"

SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"
DRAW_COLOR     = "#D4A843"


def _inject_styles():
    st.markdown("""
    <style>
    .rs-page-title {
        font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9); margin-bottom: 0.15rem;
    }
    .rs-page-subtitle {
        font-size: 1rem; color: var(--color-text-muted, #888); margin-bottom: 1.5rem; line-height: 1.5;
    }
    .rs-section {
        font-size: 1.35rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin-top: 2rem; margin-bottom: 0.3rem;
        padding-bottom: 0.3rem; border-bottom: 2px solid var(--color-border, #2A2A2A);
    }
    .rs-prose {
        font-size: 0.95rem; color: var(--color-text-muted, #888); line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .rs-caption {
        font-size: 0.82rem; color: var(--color-text-muted, #888); line-height: 1.5;
        margin-top: 0.3rem; margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load_data(run_ids: tuple, runs_dir: str, token: float):
    df, _ = build_episode_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)
    return df


@st.cache_data(show_spinner=False)
def _load_strategy(run_ids: tuple, runs_dir: str, token: float):
    return build_strategy_long_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)


def render_research_page():
    _inject_styles()

    st.markdown('<p class="rs-page-title">Research Analysis</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rs-page-subtitle">'
        'Experiment-specific analyses answering the core research questions. '
        'These views are most useful after running structured experiments with varied '
        'turn counts, models, and claim domains.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed debates yet. Run experiments to see research analysis here.")
        return

    df = _load_data(tuple(run_ids), RUNS_DIR, token)
    if df.empty:
        st.info("No episode data found.")
        return

    strategy_df = _load_strategy(tuple(run_ids), RUNS_DIR, token)

    # ── Filters ──────────────────────────────────────────────────────────
    st.markdown('<p class="rs-section">Filters</p>', unsafe_allow_html=True)

    _spr_models = sorted(df["model_spreader"].dropna().unique().tolist()) if "model_spreader" in df.columns else []
    _deb_models = sorted(df["model_debunker"].dropna().unique().tolist()) if "model_debunker" in df.columns else []
    _judge_models = sorted(df["judge_model"].dropna().unique().tolist()) if "judge_model" in df.columns else []

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel_spr = st.multiselect("Spreader model", _spr_models, default=[], key="rs_spr_model")
    with fc2:
        sel_deb = st.multiselect("Debunker model", _deb_models, default=[], key="rs_deb_model")
    with fc3:
        sel_judge = st.multiselect("Judge model", _judge_models, default=[], key="rs_judge_model")

    # Apply model filters
    if sel_spr:
        df = df[df["model_spreader"].isin(sel_spr)]
    if sel_deb:
        df = df[df["model_debunker"].isin(sel_deb)]
    if sel_judge and "judge_model" in df.columns:
        df = df[df["judge_model"].isin(sel_judge)]

    # Filter strategy_df by matching run_id + episode_id
    if sel_spr or sel_deb or sel_judge:
        valid_keys = set(zip(df["run_id"], df["episode_id"])) if not df.empty else set()
        if not strategy_df.empty and "run_id" in strategy_df.columns and "episode_id" in strategy_df.columns:
            strategy_df = strategy_df[
                strategy_df.apply(lambda r: (r["run_id"], r["episode_id"]) in valid_keys, axis=1)
            ]

    _total = len(df)
    _filtered = " (filtered)" if (sel_spr or sel_deb or sel_judge) else ""
    st.caption(f"{_total} episode{'s' if _total != 1 else ''} matched{_filtered}")

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab_strat_turn, tab_judge, tab_citations = st.tabs([
        "Strategy × Turn Count", "Judge Model Comparison", "Citations",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — STRATEGY × TURN COUNT
    # ══════════════════════════════════════════════════════════════════════
    with tab_strat_turn:
        st.markdown(
            '<p class="rs-section">How does conversation length affect strategy?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="rs-prose">'
            'As debates get longer, do agents shift their tactics? This analysis breaks down '
            'strategy frequency by turn count to reveal whether the spreader adapts its approach '
            'over longer conversations and whether the fact-checker\'s correction strategies change.'
            '</p>',
            unsafe_allow_html=True,
        )

        if strategy_df.empty:
            st.info("No strategy analysis data. Run debates with strategy labeling enabled to populate this view.")
        elif "planned_max_turns" not in df.columns:
            st.info("No turn count variation found. Run single-claim experiments with different max_turns values.")
        else:
            # Join turn count into strategy data
            turn_map = df[["run_id", "episode_id", "planned_max_turns"]].drop_duplicates()
            strat_with_turns = strategy_df.merge(
                turn_map, on=["run_id", "episode_id"], how="left"
            )
            strat_with_turns = strat_with_turns.dropna(subset=["planned_max_turns"])
            strat_with_turns["planned_max_turns"] = strat_with_turns["planned_max_turns"].astype(int)

            if strat_with_turns.empty or strat_with_turns["planned_max_turns"].nunique() < 2:
                st.info("Need at least 2 different turn counts to show strategy evolution. Run debates at different max_turns values.")
            else:
                turn_counts = sorted(strat_with_turns["planned_max_turns"].unique())

                for side, color, label in [
                    ("spreader", SPREADER_COLOR, "Spreader"),
                    ("debunker", DEBUNKER_COLOR, "Fact-checker"),
                ]:
                    st.markdown(f'**{label} strategy distribution by turn count**')

                    side_data = strat_with_turns[strat_with_turns["side"] == side]
                    if side_data.empty:
                        st.caption(f"No {label.lower()} strategy data.")
                        continue

                    # Compute frequency per strategy per turn count
                    freq = (
                        side_data.groupby(["planned_max_turns", "strategy_label"])
                        .size()
                        .reset_index(name="count")
                    )
                    # Normalize within each turn count
                    totals = freq.groupby("planned_max_turns")["count"].transform("sum")
                    freq["pct"] = (freq["count"] / totals * 100).round(1)

                    # Get top 6 strategies by overall frequency
                    top_strategies = (
                        side_data["strategy_label"]
                        .value_counts()
                        .head(6)
                        .index.tolist()
                    )

                    fig = go.Figure()
                    for strat in top_strategies:
                        strat_freq = freq[freq["strategy_label"] == strat]
                        strat_freq = strat_freq.set_index("planned_max_turns").reindex(turn_counts, fill_value=0)
                        fig.add_trace(go.Scatter(
                            x=turn_counts,
                            y=strat_freq["pct"].values,
                            mode="lines+markers",
                            name=strat.replace("_", " ").title(),
                            marker=dict(size=6),
                            hovertemplate="%{y:.1f}% of debates<extra>%{fullData.name}</extra>",
                        ))

                    fig.update_layout(
                        xaxis=dict(title="Max Turns", tickvals=turn_counts, tickfont=dict(size=11)),
                        yaxis=dict(title="% of debates using this strategy", tickfont=dict(size=11),
                                   gridcolor="#2A2A2A"),
                        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center", font=dict(size=11)),
                        margin=dict(t=10, b=80, l=60, r=15), height=350,
                        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                    )
                    fig.update_xaxes(showgrid=True, gridcolor="#2A2A2A")
                    fig.update_yaxes(showgrid=True)
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown(
                    '<p class="rs-caption">'
                    'Each line shows how frequently a strategy was detected as debates get longer. '
                    'A rising line means the tactic becomes more common in longer debates; '
                    'a falling line means it fades. Top 6 strategies per side are shown.'
                    '</p>',
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — JUDGE MODEL COMPARISON
    # ══════════════════════════════════════════════════════════════════════
    with tab_judge:
        st.markdown(
            '<p class="rs-section">Does the judge model affect the verdict?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="rs-prose">'
            'If different judge models score the same debate differently, the evaluation '
            'is model-dependent — a validity concern. This section compares judge behavior '
            'across models. High agreement means the scoring is robust; low agreement '
            'means results should be interpreted with caution.'
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

            disp = judge_wr.copy()
            disp.columns = ["Judge Model", "Debates", "FC Win %", "Avg Confidence", "Avg Margin"]
            disp["Debates"] = disp["Debates"].astype(int)
            disp["FC Win %"] = disp["FC Win %"].map(lambda v: f"{v:.0%}")
            disp["Avg Confidence"] = disp["Avg Confidence"].map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
            disp["Avg Margin"] = disp["Avg Margin"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Confidence distribution by judge model
            st.markdown("**Confidence distribution by judge model**")
            fig_conf = go.Figure()
            colors = [DEBUNKER_COLOR, SPREADER_COLOR, DRAW_COLOR] + ["#888"] * 10
            for i, jm in enumerate(judge_models):
                jm_data = pd.to_numeric(df[df[judge_col] == jm]["judge_confidence"], errors="coerce").dropna()
                if len(jm_data) > 0:
                    fig_conf.add_trace(go.Box(
                        y=jm_data, name=str(jm),
                        marker_color=colors[i % len(colors)],
                        boxmean=True,
                    ))
            fig_conf.update_layout(
                yaxis=dict(title="Judge Confidence", tickformat=".0%", range=[0, 1.05],
                           gridcolor="#2A2A2A"),
                margin=dict(t=10, b=40, l=60, r=15), height=300,
                **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
                showlegend=False,
            )
            fig_conf.update_yaxes(showgrid=True)
            st.plotly_chart(fig_conf, use_container_width=True)

            # Average metric scores by judge model
            metric_cols_spr = [c for c in df.columns if c.startswith("metric_") and c.endswith("_spreader")]
            metric_cols_deb = [c for c in df.columns if c.startswith("metric_") and c.endswith("_debunker")]

            if metric_cols_spr:
                st.markdown("**Average metric scores by judge model**")
                rows = []
                for jm in judge_models:
                    jm_df = df[df[judge_col] == jm]
                    row = {"Judge Model": jm}
                    for mc in metric_cols_spr:
                        metric_name = mc.replace("metric_", "").replace("_spreader", "")
                        s_mean = pd.to_numeric(jm_df[mc], errors="coerce").mean()
                        d_col = mc.replace("_spreader", "_debunker")
                        d_mean = pd.to_numeric(jm_df[d_col], errors="coerce").mean() if d_col in jm_df.columns else None
                        row[f"{metric_name} (Spr)"] = round(s_mean, 1) if pd.notna(s_mean) else "—"
                        row[f"{metric_name} (FC)"] = round(d_mean, 1) if pd.notna(d_mean) else "—"
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.markdown(
                '<p class="rs-caption">'
                'If FC Win % varies significantly across judge models, the scoring is model-dependent. '
                'Consider using judge consistency runs (N>1) or fixing the judge model for all experiments.'
                '</p>',
                unsafe_allow_html=True,
            )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — CITATIONS
    # ══════════════════════════════════════════════════════════════════════
    with tab_citations:
        render_citation_page()
