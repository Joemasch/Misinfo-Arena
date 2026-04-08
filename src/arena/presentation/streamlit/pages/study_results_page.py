"""
Study Results Page for Misinformation Arena v2.

Hypothesis-driven analytics organized by study. Reads episodes with
study_id metadata and presents results grouped by experimental conditions
with side-by-side comparisons.

Phase 7 will build out the full implementation. This is the placeholder.
"""

import pandas as pd
import streamlit as st

from arena.analysis.episode_dataset import build_episode_df
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids


RUNS_DIR = "runs"


def _inject_styles():
    st.markdown("""
    <style>
    .sr-page-title {
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 2.6rem !important; font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: var(--color-text-primary, #E8E4D9) !important;
        margin-bottom: 0.15rem !important; text-align: center !important;
    }
    .sr-page-subtitle {
        font-size: 1rem !important; color: var(--color-text-muted, #888) !important;
        margin-bottom: 1.5rem !important; line-height: 1.5 !important;
        text-align: center !important;
    }
    .sr-empty-state {
        text-align: center; padding: 4rem 2rem;
        color: var(--color-text-muted, #888);
    }
    .sr-empty-icon {
        font-size: 3rem; margin-bottom: 1rem; opacity: 0.4;
    }
    .sr-empty-title {
        font-size: 1.3rem; font-weight: 600;
        color: var(--color-text-primary, #E8E4D9);
        margin-bottom: 0.5rem;
    }
    .sr-empty-body {
        font-size: 0.95rem; line-height: 1.6; max-width: 500px;
        margin: 0 auto;
    }
    .sr-study-card {
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem;
    }
    .sr-study-name {
        font-size: 1.1rem; font-weight: 700;
        color: var(--color-text-primary, #E8E4D9); margin-bottom: 0.3rem;
    }
    .sr-study-meta {
        font-size: 0.85rem; color: var(--color-text-muted, #888); line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)


def render_study_results_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    st.markdown('<p class="sr-page-title">Study Results</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-page-subtitle">'
        'Hypothesis-driven analysis of experiment data, organized by study. '
        'Run experiments with a spec CSV to populate this page.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Load data and check for study-tagged episodes
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    has_study_data = False
    studies_found: dict[str, dict] = {}

    if run_ids:
        df, _ = build_episode_df(list(run_ids), runs_dir=RUNS_DIR, refresh_token=token)
        if not df.empty and "study_id" in df.columns:
            study_df = df[df["study_id"].notna() & (df["study_id"] != "")]
            if not study_df.empty:
                has_study_data = True
                for study_id in study_df["study_id"].unique():
                    sdf = study_df[study_df["study_id"] == study_id]
                    n_eps = len(sdf)
                    conditions = sdf["condition"].nunique() if "condition" in sdf.columns else 0
                    models = set()
                    if "model_spreader" in sdf.columns:
                        models.update(sdf["model_spreader"].dropna().unique())
                    if "model_debunker" in sdf.columns:
                        models.update(sdf["model_debunker"].dropna().unique())
                    claims = sdf["claim"].nunique() if "claim" in sdf.columns else 0
                    wr = (sdf["winner"].str.lower() == "debunker").mean() if "winner" in sdf.columns else None

                    studies_found[study_id] = {
                        "episodes": n_eps,
                        "conditions": conditions,
                        "models": len(models),
                        "claims": claims,
                        "win_rate": wr,
                    }

    if not has_study_data:
        st.markdown(
            '<div class="sr-empty-state">'
            '<div class="sr-empty-icon">&#x1F50D;</div>'
            '<div class="sr-empty-title">No study data yet</div>'
            '<div class="sr-empty-body">'
            'Run an experiment using a spec CSV (Arena > Experiment mode) '
            'with <code>study_id</code> and <code>condition</code> columns. '
            'Results will appear here organized by study with hypothesis-driven '
            'visualizations and side-by-side comparisons.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Study picker ─────────────────────────────────────────────────────────
    study_ids = sorted(studies_found.keys())

    for sid in study_ids:
        info = studies_found[sid]
        wr_str = f"{info['win_rate']:.0%}" if info["win_rate"] is not None else "—"
        st.markdown(
            f'<div class="sr-study-card">'
            f'<div class="sr-study-name">{sid}</div>'
            f'<div class="sr-study-meta">'
            f'{info["episodes"]} episodes &middot; '
            f'{info["conditions"]} conditions &middot; '
            f'{info["claims"]} claims &middot; '
            f'{info["models"]} models &middot; '
            f'FC win rate: {wr_str}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    selected_study = st.selectbox(
        "Select study",
        options=study_ids,
        key="sr_study_picker",
    )

    if selected_study:
        st.markdown("---")
        st.info(
            f"**{selected_study}** — {studies_found[selected_study]['episodes']} episodes loaded. "
            "Full study-specific visualizations (condition comparisons, side-by-side charts, "
            "statistical summaries) will be built in Phase 7."
        )

        # Preview the data for this study
        study_episodes = df[df["study_id"] == selected_study]
        preview_cols = [c for c in [
            "condition", "claim", "model_spreader", "model_debunker",
            "planned_max_turns", "winner", "judge_confidence", "margin",
        ] if c in study_episodes.columns]

        if preview_cols:
            st.dataframe(
                study_episodes[preview_cols].head(50),
                use_container_width=True,
                hide_index=True,
            )
            if len(study_episodes) > 50:
                st.caption(f"Showing first 50 of {len(study_episodes)} episodes.")
