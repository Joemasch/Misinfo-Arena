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

    # ── Helpers ────────────────────────────────────────────────────────────
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

    def _pick(cols_list):
        """Select columns that exist in df."""
        return df[[c for c in cols_list if c in df.columns]].copy()

    def _rename_common(d):
        """Apply standard column renames."""
        renames = {"planned_max_turns": "max_turns", "judge_confidence": "confidence",
                   "completed_turn_pairs": "turns_completed"}
        d.rename(columns={k: v for k, v in renames.items() if k in d.columns}, inplace=True)
        return d

    # ══════════════════════════════════════════════════════════════════════
    # FULL EXPORT
    # ══════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p style="font-size:1.2rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);'
        'margin-top:1.5rem;margin-bottom:0.2rem;padding-bottom:0.3rem;'
        'border-bottom:2px solid var(--color-border,#2A2A2A)">Full Export</p>',
        unsafe_allow_html=True,
    )

    full_cols = [
        "study_id", "condition", "run_id", "episode_id",
        "claim", "claim_type",
        "model_spreader", "model_debunker", "judge_model",
        "model_matchup", "spreader_tier", "debunker_tier",
        "same_model", "cross_provider",
        "planned_max_turns", "completed_turn_pairs",
        "winner", "fc_win", "margin", "abs_margin", "judge_confidence",
    ] + metric_cols
    _export_button(
        "Full Episode Export",
        _rename_common(_pick(full_cols)),
        "full_episodes.csv",
        "Every episode with all columns. Use for custom analyses or when per-test exports don't cover your need.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # STUDY 1 — JUDGE VALIDATION
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        '<p style="font-size:1.2rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);'
        'margin-top:1rem;margin-bottom:0.5rem;padding-bottom:0.3rem;'
        'border-bottom:2px solid var(--color-border,#2A2A2A)">Study 1: Judge Validation</p>',
        unsafe_allow_html=True,
    )

    _export_button(
        "Judge Validation",
        _rename_common(_pick([
            "study_id", "run_id", "episode_id", "claim", "claim_type",
            "judge_model", "judge_consistency_n", "judge_consistency_std",
            "winner", "fc_win", "judge_confidence", "margin",
        ] + metric_cols)),
        "judge_validation.csv",
        "Spearman correlation (judge vs human per dimension), consistency CV, confidence discrimination. "
        "Cohen's kappa is computed in the Annotate tab.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # STUDY 2 — CONVERSATION LENGTH
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        '<p style="font-size:1.2rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);'
        'margin-top:1rem;margin-bottom:0.5rem;padding-bottom:0.3rem;'
        'border-bottom:2px solid var(--color-border,#2A2A2A)">Study 2: Conversation Length</p>',
        unsafe_allow_html=True,
    )

    # 2.1 ANOVA: turns → margin
    _export_button(
        "2.1 — One-Way ANOVA: Turn Count → Margin",
        _rename_common(_pick(["planned_max_turns", "margin", "claim", "claim_type"])),
        "study2_anova_turns_margin.csv",
        "Minitab: Stat > ANOVA > One-Way. Response: margin, Factor: max_turns. "
        "Tests whether debate length affects score gap.",
    )

    # 2.2 Chi-squared: turns → winner
    _export_button(
        "2.2 — Chi-Squared: Turn Count → Winner",
        _rename_common(_pick(["planned_max_turns", "winner", "fc_win"])),
        "study2_chi2_turns_winner.csv",
        "Minitab: Stat > Tables > Cross Tabulation. Rows: max_turns, Columns: winner. "
        "Tests whether debate length affects who wins.",
    )

    # 2.3 Two-way ANOVA: model × turns
    _export_button(
        "2.3 — Two-Way ANOVA: Model × Turn Count",
        _rename_common(_pick(["model_matchup", "planned_max_turns", "margin"])),
        "study2_anova_model_turns.csv",
        "Minitab: Stat > ANOVA > General Linear Model. Response: margin, "
        "Factors: model_matchup + max_turns + interaction. "
        "Tests whether some models improve more with debate length.",
    )

    # 2.4 T-test: same-model vs cross-model
    _export_button(
        "2.4 — T-Test: Same-Model vs Cross-Model Pairs",
        _rename_common(_pick(["same_model", "margin", "abs_margin", "model_matchup"])),
        "study2_ttest_same_model.csv",
        "Minitab: Stat > Basic Statistics > 2-Sample t. "
        "Samples: margin grouped by same_model. "
        "Tests whether mirror matchups produce different outcomes.",
    )

    # 2.5 Two-way ANOVA: tier × turns
    _export_button(
        "2.5 — Two-Way ANOVA: Tier × Turn Count",
        _rename_common(_pick(["debunker_tier", "planned_max_turns", "margin"])),
        "study2_anova_tier_turns.csv",
        "Minitab: Stat > ANOVA > General Linear Model. Response: margin, "
        "Factors: debunker_tier + max_turns + interaction. "
        "Tests whether budget models respond differently to length than premium.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # STUDY 3 — CLAIM TYPE
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        '<p style="font-size:1.2rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);'
        'margin-top:1rem;margin-bottom:0.5rem;padding-bottom:0.3rem;'
        'border-bottom:2px solid var(--color-border,#2A2A2A)">Study 3: Claim Type</p>',
        unsafe_allow_html=True,
    )

    # 3.1 ANOVA: type → margin
    _export_button(
        "3.1 — One-Way ANOVA: Claim Type → Margin",
        _rename_common(_pick(["claim_type", "margin", "claim"])),
        "study3_anova_type_margin.csv",
        "Minitab: Stat > ANOVA > One-Way. Response: margin, Factor: claim_type. "
        "Tests whether some claim domains are harder to debunk.",
    )

    # 3.2 Chi-squared: type → winner
    _export_button(
        "3.2 — Chi-Squared: Claim Type → Winner",
        _rename_common(_pick(["claim_type", "winner", "fc_win"])),
        "study3_chi2_type_winner.csv",
        "Minitab: Stat > Tables > Cross Tabulation. Rows: claim_type, Columns: winner. "
        "Tests whether claim type affects who wins.",
    )

    # 3.3 Two-way ANOVA: model × type
    _export_button(
        "3.3 — Two-Way ANOVA: Model × Claim Type",
        _rename_common(_pick(["model_matchup", "claim_type", "margin"] + metric_cols)),
        "study3_anova_model_type.csv",
        "Minitab: Stat > ANOVA > General Linear Model. Response: margin, "
        "Factors: model_matchup + claim_type + interaction. "
        "Tests whether the best model depends on claim domain.",
    )

    # 3.4 Two-way ANOVA: tier × type
    _export_button(
        "3.4 — Two-Way ANOVA: Tier × Claim Type",
        _rename_common(_pick(["debunker_tier", "claim_type", "margin"])),
        "study3_anova_tier_type.csv",
        "Minitab: Stat > ANOVA > General Linear Model. Response: margin, "
        "Factors: debunker_tier + claim_type + interaction. "
        "Tests whether budget models struggle more on certain claim types.",
    )

    # ══════════════════════════════════════════════════════════════════════
    # MODEL COMPARISON (cross-study)
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        '<p style="font-size:1.2rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);'
        'margin-top:1rem;margin-bottom:0.5rem;padding-bottom:0.3rem;'
        'border-bottom:2px solid var(--color-border,#2A2A2A)">Model Comparison (Cross-Study)</p>',
        unsafe_allow_html=True,
    )

    # 4.1 Best spreader
    _export_button(
        "4.1 — One-Way ANOVA: Best Spreader Model",
        _rename_common(_pick(["model_spreader", "margin", "abs_margin"])),
        "model_best_spreader.csv",
        "Minitab: Stat > ANOVA > One-Way. Response: margin, Factor: model_spreader. "
        "Lower margin = better spreader. Post-hoc Tukey's for pairwise comparison.",
    )

    # 4.2 Best debunker
    _export_button(
        "4.2 — One-Way ANOVA: Best Debunker Model",
        _rename_common(_pick(["model_debunker", "margin", "abs_margin"])),
        "model_best_debunker.csv",
        "Minitab: Stat > ANOVA > One-Way. Response: margin, Factor: model_debunker. "
        "Higher margin = better debunker. Post-hoc Tukey's for pairwise comparison.",
    )

    # 4.3 Spreader × debunker interaction
    _export_button(
        "4.3 — Two-Way ANOVA: Spreader × Debunker",
        _rename_common(_pick(["model_spreader", "model_debunker", "model_matchup", "margin"] + metric_cols)),
        "model_interaction.csv",
        "Minitab: Stat > ANOVA > General Linear Model. Response: margin, "
        "Factors: model_spreader + model_debunker + interaction. "
        "Tests whether certain pairings produce unexpected results.",
    )

    # 4.4 Cross-provider vs within
    _export_button(
        "4.4 — T-Test: Cross-Provider vs Within-Provider",
        _rename_common(_pick(["cross_provider", "margin", "abs_margin", "model_matchup"])),
        "model_cross_provider.csv",
        "Minitab: Stat > Basic Statistics > 2-Sample t. "
        "Samples: margin grouped by cross_provider. "
        "Tests whether debates across providers differ from same-provider debates.",
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
