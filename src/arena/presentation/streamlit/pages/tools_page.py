"""Tools page — combines Prompts, Experiment, Annotate, and Exports sub-tabs."""

import pandas as pd
import streamlit as st

from arena.presentation.streamlit.pages.prompts_page import render_prompts_page
from arena.presentation.streamlit.pages.experiment_page import render_experiment_page
from arena.presentation.streamlit.pages.annotation_page import render_annotation_page


def _render_exports_tab():
    """Render analysis-ready CSV exports for Minitab / SPSS / R."""
    from arena.analysis.episode_dataset import build_episode_df
    from arena.io.run_store_v2_read import list_runs
    from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

    RUNS_DIR = "runs"

    st.markdown(
        '<p style="font-size:2rem;font-weight:800;color:#111;margin-bottom:0.1rem">Statistical Exports</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.95rem;color:#555;margin-bottom:1.5rem;line-height:1.5">'
        'Pre-formatted CSVs for statistical significance testing in Minitab, SPSS, or R. '
        'Each export contains only the columns needed for that specific analysis. '
        'See <code>docs/statistical_analysis_guide.md</code> for step-by-step Minitab instructions.'
        '</p>',
        unsafe_allow_html=True,
    )

    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed debates. Run experiments first to generate export data.")
        return

    df, _ = build_episode_df(list(run_ids), runs_dir=RUNS_DIR, refresh_token=token)
    if df.empty:
        st.info("No episode data found.")
        return

    st.success(f"**{len(df)} episodes** from {df['run_id'].nunique()} runs available for export.")

    # ── Helper to build and offer download ────────────────────────────────
    def _export_button(label: str, export_df: pd.DataFrame, filename: str, description: str):
        st.markdown(f"**{label}**")
        st.caption(description)
        st.download_button(
            f"Download {filename}",
            data=export_df.to_csv(index=False).encode(),
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )
        with st.expander(f"Preview ({len(export_df)} rows × {len(export_df.columns)} columns)", expanded=False):
            st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)
        st.markdown("---")

    # ── 1. Turn Count Analysis ────────────────────────────────────────────
    tc_cols = ["claim", "claim_type", "planned_max_turns", "winner", "margin", "abs_margin",
               "judge_confidence", "model_spreader", "model_debunker", "judge_model"]
    # Add metric columns if present
    for m in ["persuasion", "manipulation_awareness"]:
        for side in ["spreader", "debunker"]:
            col = f"metric_{m}_{side}"
            if col in df.columns:
                tc_cols.append(col)

    tc_df = df[[c for c in tc_cols if c in df.columns]].copy()
    tc_df.rename(columns={
        "planned_max_turns": "max_turns",
        "judge_confidence": "confidence",
        "model_spreader": "spreader_model",
        "model_debunker": "debunker_model",
    }, inplace=True)
    # Add binary fc_win column for regression
    tc_df["fc_win"] = (tc_df["winner"].str.lower() == "debunker").astype(int)
    # Rename metric columns for clarity
    for m in ["persuasion", "manipulation_awareness"]:
        for side, abbr in [("spreader", "spr"), ("debunker", "deb")]:
            old = f"metric_{m}_{side}"
            new = f"{m}_{abbr}"
            if old in tc_df.columns:
                tc_df.rename(columns={old: new}, inplace=True)

    _export_button(
        "1. Turn Count Analysis",
        tc_df,
        "turn_count_analysis.csv",
        "ANOVA: does turn count affect margin? Chi-squared: does turn count affect win rate? Regression: does persuasion change with debate length?",
    )

    # ── 2. Domain Analysis ────────────────────────────────────────────────
    dom_cols = ["claim", "claim_type", "winner", "margin", "abs_margin",
                "judge_confidence", "model_spreader", "model_debunker", "judge_model"]
    dom_df = df[[c for c in dom_cols if c in df.columns]].copy()
    dom_df.rename(columns={
        "judge_confidence": "confidence",
        "model_spreader": "spreader_model",
        "model_debunker": "debunker_model",
    }, inplace=True)
    dom_df["fc_win"] = (dom_df["winner"].str.lower() == "debunker").astype(int)

    _export_button(
        "2. Domain Analysis",
        dom_df,
        "domain_analysis.csv",
        "Chi-squared: does domain affect win rate? ANOVA: does domain affect score margin?",
    )

    # ── 3. Model Comparison ───────────────────────────────────────────────
    mod_cols = ["model_spreader", "model_debunker", "judge_model", "winner",
                "margin", "abs_margin", "judge_confidence", "claim_type"]
    for m in ["persuasion"]:
        col = f"metric_{m}_spreader"
        if col in df.columns:
            mod_cols.append(col)

    mod_df = df[[c for c in mod_cols if c in df.columns]].copy()
    mod_df.rename(columns={
        "model_spreader": "spreader_model",
        "model_debunker": "debunker_model",
        "judge_confidence": "confidence",
    }, inplace=True)
    if "metric_persuasion_spreader" in mod_df.columns:
        mod_df.rename(columns={"metric_persuasion_spreader": "persuasion_spr"}, inplace=True)
    mod_df["fc_win"] = (mod_df["winner"].str.lower() == "debunker").astype(int)
    mod_df["model_matchup"] = mod_df["spreader_model"] + " vs " + mod_df["debunker_model"]

    _export_button(
        "3. Model Comparison",
        mod_df,
        "model_comparison.csv",
        "Chi-squared: does model matchup affect win rate? Two-way ANOVA: model × domain interaction. One-way ANOVA: which model is the best spreader?",
    )

    # ── 4. Judge Consistency ──────────────────────────────────────────────
    jud_cols = ["run_id", "episode_id", "claim", "judge_model", "winner",
                "judge_confidence", "margin"]
    for m in ["factuality", "source_credibility", "reasoning_quality",
              "responsiveness", "persuasion", "manipulation_awareness"]:
        for side in ["spreader", "debunker"]:
            col = f"metric_{m}_{side}"
            if col in df.columns:
                jud_cols.append(col)

    jud_df = df[[c for c in jud_cols if c in df.columns]].copy()
    jud_df.rename(columns={"judge_confidence": "confidence"}, inplace=True)
    # Rename metric columns for clarity
    for m in ["factuality", "source_credibility", "reasoning_quality",
              "responsiveness", "persuasion", "manipulation_awareness"]:
        for side, abbr in [("spreader", "spr"), ("debunker", "deb")]:
            old = f"metric_{m}_{side}"
            new = f"{m}_{abbr}"
            if old in jud_df.columns:
                jud_df.rename(columns={old: new}, inplace=True)

    _export_button(
        "4. Judge Consistency",
        jud_df,
        "judge_consistency.csv",
        "Chi-squared: do judge models produce different winners? ANOVA: do they produce different scores? Correlation: do they agree on individual metrics?",
    )

    # ── 5. Concession Analysis ────────────────────────────────────────────
    conc_cols = ["claim", "claim_type", "early_stop", "conceded_by", "concession_turn",
                 "planned_max_turns", "model_spreader", "model_debunker", "judge_model",
                 "winner", "margin", "judge_confidence"]
    for m in ["persuasion"]:
        for side in ["spreader", "debunker"]:
            col = f"metric_{m}_{side}"
            if col in df.columns:
                conc_cols.append(col)

    conc_df = df[[c for c in conc_cols if c in df.columns]].copy()
    conc_df.rename(columns={
        "planned_max_turns": "max_turns",
        "model_spreader": "spreader_model",
        "model_debunker": "debunker_model",
        "judge_confidence": "confidence",
    }, inplace=True)
    if "metric_persuasion_spreader" in conc_df.columns:
        conc_df.rename(columns={"metric_persuasion_spreader": "persuasion_spr"}, inplace=True)
    if "metric_persuasion_debunker" in conc_df.columns:
        conc_df.rename(columns={"metric_persuasion_debunker": "persuasion_deb"}, inplace=True)
    # Binary conceded column
    conc_df["conceded"] = conc_df["early_stop"].fillna(False).astype(int)

    _export_button(
        "5. Concession Analysis",
        conc_df,
        "concession_analysis.csv",
        "Logistic regression: what predicts concession? Chi-squared: does model choice affect concession rate?",
    )


def render_tools_page():
    st.markdown(
        '<p style="font-size:2.4rem;font-weight:800;letter-spacing:-0.02em;color:#111;margin-bottom:0.15rem">Tools</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:1rem;color:#555;margin-bottom:1.5rem;line-height:1.5">'
        'Prompt reference, model comparison experiments, human annotation, and statistical exports.'
        '</p>',
        unsafe_allow_html=True,
    )

    tab_prompts, tab_experiment, tab_annotate, tab_exports = st.tabs([
        "Prompts", "Experiment", "Annotate", "Exports"
    ])

    with tab_prompts:
        render_prompts_page()
    with tab_experiment:
        render_experiment_page()
    with tab_annotate:
        render_annotation_page()
    with tab_exports:
        _render_exports_tab()
