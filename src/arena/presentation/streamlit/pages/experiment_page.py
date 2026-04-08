"""
Experiment Page for Misinformation Arena v2.

Upload a spec CSV (one row per episode) with per-episode model configs,
study metadata, and run grouping. Replaces the old N × M × C prompt grid.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
from arena.batch_runner import parse_spec_csv, run_experiment_from_spec
from arena.config import AVAILABLE_MODELS


SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"


def _inject_styles():
    st.markdown("""
    <style>
    .ex-page-title {
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 2rem !important; font-weight: 400 !important;
        color: var(--color-accent-red, #C9363E) !important; margin-top: 1rem !important; margin-bottom: 0.2rem !important;
        padding-bottom: 0.3rem !important; border-bottom: 1px solid var(--color-border, #2A2A2A) !important;
        text-align: left !important;
    }
    .ex-page-subtitle {
        font-size: 0.95rem !important; color: var(--color-text-muted, #888) !important; margin-bottom: 1.5rem !important; line-height: 1.5 !important;
        text-align: left !important;
    }
    .ex-section {
        font-size: 1.35rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin-top: 2rem; margin-bottom: 0.3rem;
        padding-bottom: 0.3rem; border-bottom: 2px solid var(--color-border, #2A2A2A);
    }
    .ex-prose {
        font-size: 0.95rem; color: var(--color-text-muted, #888); line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .ex-metric-grid {
        display: flex; gap: 1rem; margin: 1.2rem 0 1.5rem 0; flex-wrap: wrap;
    }
    .ex-metric-card {
        flex: 1; min-width: 140px;
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.9rem 1.1rem;
    }
    .ex-metric-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.07em; color: var(--color-text-muted, #888); margin-bottom: 0.2rem;
    }
    .ex-metric-value {
        font-size: 1.8rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9); line-height: 1.1;
    }
    .ex-metric-sub { font-size: 0.78rem; color: var(--color-text-muted, #888); margin-top: 0.15rem; }
    .ex-divider { border: none; border-top: 1px solid var(--color-border, #2A2A2A); margin: 1.8rem 0; }
    .ex-callout {
        background: rgba(74,127,165,0.08); border-left: 4px solid #4A7FA5;
        border-radius: 0 6px 6px 0; padding: 0.8rem 1.1rem;
        margin-bottom: 1.2rem; font-size: 0.95rem; color: var(--color-text-primary, #E8E4D9); line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Template CSV
# ---------------------------------------------------------------------------

_TEMPLATE_CSV = """study_id,condition,run_group,claim,claim_type,spreader_model,debunker_model,judge_model,max_turns,consistency_runs
study1_corpus,combo_A_turns2,combo_A_vaccines_2t,Vaccines cause autism,Health,gpt-4o-mini,gpt-4o,,2,1
study1_corpus,combo_A_turns4,combo_A_vaccines_4t,Vaccines cause autism,Health,gpt-4o-mini,gpt-4o,,4,1
study2_length,pair1_turns2,pair1_vaccines,Vaccines cause autism,Health,gpt-4o-mini,gpt-4o-mini,gpt-4o,2,1
study2_length,pair1_turns4,pair1_vaccines,Vaccines cause autism,Health,gpt-4o-mini,gpt-4o-mini,gpt-4o,4,1
""".strip()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def render_experiment_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    st.markdown('<p class="ex-page-title">Run Experiment</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ex-page-subtitle">'
        'Upload a spec CSV where each row defines one episode. '
        'Specify spreader model, debunker model, judge model, claim, and turn count per episode. '
        'Episodes are grouped into runs by the <code>run_group</code> column and tagged with '
        '<code>study_id</code> and <code>condition</code> for analysis in Study Results.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Spec CSV Upload ──────────────────────────────────────────────────────
    st.markdown('<p class="ex-section">Experiment Spec</p>', unsafe_allow_html=True)

    st.markdown(
        '<div class="ex-callout">'
        '<b>Required column:</b> <code>claim</code><br>'
        '<b>Optional columns:</b> <code>study_id</code>, <code>condition</code>, '
        '<code>run_group</code>, <code>claim_type</code>, '
        '<code>spreader_model</code>, <code>debunker_model</code>, <code>judge_model</code>, '
        '<code>max_turns</code>, <code>consistency_runs</code><br>'
        'Missing optional columns get defaults (gpt-4o-mini, 5 turns, 1 consistency run). '
        'Use <code>scripts/generate_study_specs.py</code> to auto-generate spec CSVs for Studies 1–3.'
        '</div>',
        unsafe_allow_html=True,
    )

    col_upload, col_template = st.columns([3, 1])
    with col_upload:
        spec_file = st.file_uploader(
            "Upload spec CSV",
            type=["csv"],
            key="exp_spec_csv",
            help="One row per episode. See template for column format.",
        )
    with col_template:
        st.download_button(
            "Download template",
            data=_TEMPLATE_CSV,
            file_name="experiment_spec_template.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Parse and preview
    spec_rows = None
    if spec_file is not None:
        try:
            spec_rows = parse_spec_csv(spec_file)
            if not spec_rows:
                st.warning("No valid rows found in spec CSV.")
                spec_rows = None
        except Exception as e:
            st.error(f"Failed to parse spec CSV: {e}")

    if spec_rows:
        # Preview table
        preview_data = []
        for r in spec_rows[:50]:
            preview_data.append({
                "Study": r.study_id or "—",
                "Condition": (r.condition[:30] + "…") if len(r.condition) > 30 else (r.condition or "—"),
                "Run Group": (r.run_group[:25] + "…") if len(r.run_group) > 25 else (r.run_group or "auto"),
                "Claim": (r.claim[:40] + "…") if len(r.claim) > 40 else r.claim,
                "Type": r.claim_type or "—",
                "Spreader": r.spreader_model,
                "Debunker": r.debunker_model,
                "Judge": r.judge_model or "—",
                "Turns": r.max_turns,
            })
        preview_df = pd.DataFrame(preview_data)

        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        if len(spec_rows) > 50:
            st.caption(f"Showing first 50 of {len(spec_rows)} episodes.")

        # Summary stats
        studies = set(r.study_id for r in spec_rows if r.study_id)
        run_groups = set(r.run_group for r in spec_rows if r.run_group)
        models_used = set()
        for r in spec_rows:
            models_used.update([r.spreader_model, r.debunker_model])
            if r.judge_model:
                models_used.add(r.judge_model)

        st.markdown(
            f'<div class="ex-metric-grid">'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Episodes</div>'
            f'<div class="ex-metric-value">{len(spec_rows)}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Studies</div>'
            f'<div class="ex-metric-value">{len(studies) or "—"}</div>'
            f'<div class="ex-metric-sub">{", ".join(sorted(studies)) if studies else "No study_id set"}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Runs</div>'
            f'<div class="ex-metric-value">{len(run_groups)}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Models</div>'
            f'<div class="ex-metric-value">{len(models_used)}</div>'
            f'<div class="ex-metric-sub">{", ".join(sorted(models_used))}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Run Button ────────────────────────────────────────────────────────
        st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)

        if st.button("Run Experiment", type="primary", use_container_width=True, key="exp_run_spec_btn"):
            st.session_state["exp_spec_outcomes"] = []
            st.session_state["exp_spec_running"] = True

            progress_bar = st.progress(0, text="Starting experiment…")
            status_text = st.empty()
            outcomes_collected = []

            try:
                gen = run_experiment_from_spec(
                    spec_rows=spec_rows,
                    spreader_prompt=SPREADER_SYSTEM_PROMPT,
                    debunker_prompt=DEBUNKER_SYSTEM_PROMPT,
                    judge_prompt_template=st.session_state.get("judge_static_prompt"),
                )
                for (done, total), summary in gen:
                    outcomes_collected.append(summary)
                    pct = done / total
                    progress_bar.progress(pct, text=f"Episode {done}/{total}")
                    winner_display = summary.get("winner", "").title().replace("Debunker", "FC")
                    claim_short = (summary.get("claim", ""))[:40]
                    status_text.caption(
                        f"Last: {summary.get('spreader_model', '')} vs {summary.get('debunker_model', '')} — "
                        f"*{claim_short}* → **{winner_display}** ({summary.get('confidence', 0):.0%})"
                    )
            except Exception as e:
                st.error(f"Experiment failed: {e}")
                st.session_state["exp_spec_running"] = False
                return

            progress_bar.progress(1.0, text="Done!")
            status_text.empty()
            st.session_state["exp_spec_outcomes"] = outcomes_collected
            st.session_state["exp_spec_running"] = False

            # Increment refresh token so Analytics/Replay pick up new runs
            st.session_state["runs_refresh_token"] = st.session_state.get("runs_refresh_token", 0.0) + 1.0

            st.success(f"Completed {len(outcomes_collected)} episode(s). Results saved to runs/.")
            st.rerun()

    # ── Results Display ──────────────────────────────────────────────────────
    outcomes = st.session_state.get("exp_spec_outcomes", [])
    if outcomes:
        st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)
        st.markdown('<p class="ex-section">Results</p>', unsafe_allow_html=True)

        n_total = len(outcomes)
        n_fc = sum(1 for ep in outcomes if (ep.get("winner") or "").lower() == "debunker")
        n_spr = sum(1 for ep in outcomes if (ep.get("winner") or "").lower() == "spreader")
        n_err = sum(1 for ep in outcomes if ep.get("error"))
        fc_pct = n_fc / max(n_total, 1)

        st.markdown(
            f'<div class="ex-metric-grid">'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Completed</div>'
            f'<div class="ex-metric-value">{n_total}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">FC Win Rate</div>'
            f'<div class="ex-metric-value" style="color:{DEBUNKER_COLOR}">{fc_pct:.0%}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Spreader Wins</div>'
            f'<div class="ex-metric-value" style="color:{SPREADER_COLOR}">{n_spr}</div></div>'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Errors</div>'
            f'<div class="ex-metric-value">{n_err}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Results table
        result_rows = []
        for ep in outcomes:
            result_rows.append({
                "Run": ep.get("run_group", "")[:20],
                "Claim": (ep.get("claim", "")[:40] + "…") if len(ep.get("claim", "")) > 40 else ep.get("claim", ""),
                "Spreader": ep.get("spreader_model", ""),
                "Debunker": ep.get("debunker_model", ""),
                "Judge": ep.get("judge_model", ""),
                "Turns": ep.get("max_turns", ""),
                "Winner": ep.get("winner", "").title().replace("Debunker", "Fact-checker"),
                "Confidence": f"{ep.get('confidence', 0):.0%}",
                "Error": ep.get("error") or "",
            })

        result_df = pd.DataFrame(result_rows)
        if not result_df.empty:
            st.dataframe(result_df, use_container_width=True, hide_index=True)

        # Download
        st.download_button(
            "Download results as JSON",
            data=json.dumps(outcomes, indent=2, default=str),
            file_name="experiment_results.json",
            mime="application/json",
        )
