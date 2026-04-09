"""Tools page — combines Annotate, Exports, and Prompts sub-tabs."""

import pandas as pd
import streamlit as st

from arena.presentation.streamlit.pages.prompts_page import render_prompts_page
from arena.presentation.streamlit.pages.annotation_page import render_annotation_page


def _render_exports_tab():
    """Render analysis-ready CSV exports aligned to experimental design."""
    from arena.analysis.episode_dataset import build_episode_df
    from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

    RUNS_DIR = "runs"

    # Tier mapping for model grouping
    _TIER_MAP = {
        "gpt-4o-mini": "budget", "gpt-4o": "premium",
        "claude-sonnet-4-20250514": "premium", "claude-sonnet-4": "premium",
        "gemini-2.5-flash": "mid",
        "grok-3-mini": "budget", "grok-3": "premium",
        "gemini-2.0-flash": "budget", "gemini-2.5-pro": "premium",
        "claude-haiku-4-5-20251001": "budget",
    }

    def _get_tier(model: str) -> str:
        if not model:
            return "unknown"
        return _TIER_MAP.get(model, "unknown")

    st.markdown(
        '<p style="font-family:Playfair Display,Georgia,serif;font-size:2rem;font-weight:400;'
        'color:var(--color-accent-red,#C9363E);margin-top:1rem;margin-bottom:0.2rem;'
        'padding-bottom:0.3rem;border-bottom:1px solid var(--color-border,#2A2A2A);'
        'text-align:left">Statistical Exports</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.95rem;color:var(--color-text-muted,#888);margin-bottom:1.5rem;line-height:1.5">'
        'Pre-formatted CSVs for statistical significance testing in Minitab, SPSS, or R. '
        'Each export is aligned to a specific study or analysis type.'
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

    st.markdown(
        f'<div class="ds-callout"><strong>{len(df)} episodes</strong> from '
        f'{df["run_id"].nunique()} runs available for export.</div>',
        unsafe_allow_html=True,
    )

    # ── Derive computed columns ──────────────────────────────────────────
    df["fc_win"] = (df["winner"].fillna("").str.lower() == "debunker").astype(int)
    df["model_matchup"] = df["model_spreader"].fillna("") + " vs " + df["model_debunker"].fillna("")
    df["spreader_tier"] = df["model_spreader"].apply(_get_tier)
    df["debunker_tier"] = df["model_debunker"].apply(_get_tier)
    df["same_model"] = (df["model_spreader"] == df["model_debunker"]).astype(int)
    if "cross_provider" not in df.columns:
        df["cross_provider"] = (df.get("provider_spreader", "") != df.get("provider_debunker", "")).astype(int)
    else:
        df["cross_provider"] = df["cross_provider"].astype(int)

    # Collect all metric columns
    _METRICS = ["factuality", "source_credibility", "reasoning_quality",
                "responsiveness", "persuasion", "manipulation_awareness"]
    metric_cols = []
    for m in _METRICS:
        for side, abbr in [("spreader", "spr"), ("debunker", "deb")]:
            src = f"metric_{m}_{side}"
            dst = f"{m}_{abbr}"
            if src in df.columns:
                df[dst] = df[src]
                metric_cols.append(dst)

    # ── Helper ───────────────────────────────────────────────────────────
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

    # ══════════════════════════════════════════════════════════════════════
    # 1. FULL EPISODE EXPORT — everything in one CSV
    # ══════════════════════════════════════════════════════════════════════
    full_cols = [
        "study_id", "condition", "run_id", "episode_id",
        "claim", "claim_type",
        "model_spreader", "model_debunker", "judge_model",
        "model_matchup", "spreader_tier", "debunker_tier",
        "same_model", "cross_provider",
        "planned_max_turns", "completed_turn_pairs",
        "winner", "fc_win", "margin", "abs_margin", "judge_confidence",
    ] + metric_cols

    full_df = df[[c for c in full_cols if c in df.columns]].copy()
    full_df.rename(columns={
        "planned_max_turns": "max_turns",
        "judge_confidence": "confidence",
        "completed_turn_pairs": "turns_completed",
    }, inplace=True)

    _export_button(
        "1. Full Episode Export",
        full_df,
        "full_episodes.csv",
        "Every episode with all columns — study tags, models, tiers, matchup flags, "
        "outcomes, and all 12 dimension scores. Use this for custom analyses or when "
        "other exports don't cover your specific test.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # 2. TURN COUNT ANALYSIS — Study 2
    # ══════════════════════════════════════════════════════════════════════
    tc_cols_list = [
        "study_id", "claim", "claim_type",
        "model_spreader", "model_debunker", "model_matchup",
        "spreader_tier", "debunker_tier", "same_model",
        "planned_max_turns", "winner", "fc_win",
        "margin", "abs_margin", "judge_confidence",
    ] + metric_cols

    tc_df = df[[c for c in tc_cols_list if c in df.columns]].copy()
    tc_df.rename(columns={
        "planned_max_turns": "max_turns",
        "judge_confidence": "confidence",
    }, inplace=True)

    _export_button(
        "2. Turn Count Analysis (Study 2)",
        tc_df,
        "turn_count_analysis.csv",
        "ANOVA: does turn count affect margin? Chi-squared: does turn count affect win rate? "
        "Interaction: model × turn count on margin. Tier comparison: budget vs premium slopes.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # 3. CLAIM TYPE ANALYSIS — Study 3
    # ══════════════════════════════════════════════════════════════════════
    ct_cols_list = [
        "study_id", "claim", "claim_type",
        "model_spreader", "model_debunker", "model_matchup",
        "spreader_tier", "debunker_tier",
        "winner", "fc_win", "margin", "abs_margin", "judge_confidence",
    ] + metric_cols

    ct_df = df[[c for c in ct_cols_list if c in df.columns]].copy()
    ct_df.rename(columns={"judge_confidence": "confidence"}, inplace=True)

    _export_button(
        "3. Claim Type Analysis (Study 3)",
        ct_df,
        "claim_type_analysis.csv",
        "ANOVA: does claim type affect margin? Chi-squared: does type affect win rate? "
        "Two-way ANOVA: model × claim type interaction. Per-dimension scores by type.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # 4. MODEL COMPARISON — Cross-study
    # ══════════════════════════════════════════════════════════════════════
    mod_cols_list = [
        "study_id", "claim_type",
        "model_spreader", "model_debunker", "model_matchup",
        "spreader_tier", "debunker_tier",
        "same_model", "cross_provider",
        "planned_max_turns",
        "winner", "fc_win", "margin", "abs_margin", "judge_confidence",
    ] + metric_cols

    mod_df = df[[c for c in mod_cols_list if c in df.columns]].copy()
    mod_df.rename(columns={
        "planned_max_turns": "max_turns",
        "judge_confidence": "confidence",
    }, inplace=True)

    _export_button(
        "4. Model Comparison",
        mod_df,
        "model_comparison.csv",
        "One-way ANOVA: best spreader / best debunker. Two-way ANOVA: spreader × debunker model. "
        "T-test: same-model vs cross-model pairs. T-test: cross-provider vs within-provider. "
        "Two-way ANOVA: spreader tier × debunker tier.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # 5. JUDGE VALIDATION — Study 1
    # ══════════════════════════════════════════════════════════════════════
    jud_cols_list = [
        "study_id", "run_id", "episode_id", "claim", "claim_type",
        "judge_model", "judge_consistency_n", "judge_consistency_std",
        "winner", "fc_win", "judge_confidence", "margin",
    ] + metric_cols

    jud_df = df[[c for c in jud_cols_list if c in df.columns]].copy()
    jud_df.rename(columns={"judge_confidence": "confidence"}, inplace=True)

    _export_button(
        "5. Judge Validation (Study 1)",
        jud_df,
        "judge_validation.csv",
        "Cohen's kappa: judge vs human winner agreement. Spearman correlation: per-dimension "
        "judge vs human scores. Consistency CV: score variance across repeated runs. "
        "Confidence discrimination: variance of confidence scores per judge model.",
    )


def render_tools_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    st.markdown(
        '<p style="font-size:2.6rem;font-weight:700;letter-spacing:-0.02em;'
        'color:var(--color-text-primary);margin-bottom:0.15rem;'
        'font-family:Playfair Display,Georgia,serif;text-align:center">Tools</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:1rem;color:var(--color-text-muted);margin-bottom:1.5rem;'
        'line-height:1.5;text-align:center">'
        'Human annotation, statistical exports, and prompt reference.'
        '</p>',
        unsafe_allow_html=True,
    )

    tab_annotate, tab_exports, tab_prompts = st.tabs([
        "Annotate", "Exports", "Prompts"
    ])

    with tab_annotate:
        render_annotation_page()
    with tab_exports:
        _render_exports_tab()
    with tab_prompts:
        render_prompts_page()
