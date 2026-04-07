"""
Batch Experiment Page for Misinformation Arena v2.

Runs an N × M × C grid (spreader variants × debunker variants × claims)
and shows a results matrix. No live debate state is required.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
from arena.batch_runner import BatchConfig, PromptVariant, run_batch_experiment
from arena.config import AVAILABLE_MODELS


EXPERIMENTS_DIR = Path("runs/experiments")

SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"


def _inject_styles():
    st.markdown("""
    <style>
    .ex-page-title {
        font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em;
        color: #111; margin-bottom: 0.15rem;
    }
    .ex-page-subtitle {
        font-size: 1rem; color: #555; margin-bottom: 1.5rem; line-height: 1.5;
    }
    .ex-section {
        font-size: 1.35rem; font-weight: 700; color: #111;
        margin-top: 2rem; margin-bottom: 0.3rem;
        padding-bottom: 0.3rem; border-bottom: 2px solid #e8e8e8;
    }
    .ex-prose {
        font-size: 0.95rem; color: #444; line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .ex-metric-grid {
        display: flex; gap: 1rem; margin: 1.2rem 0 1.5rem 0; flex-wrap: wrap;
    }
    .ex-metric-card {
        flex: 1; min-width: 140px;
        background: #fff; border: 1px solid #e4e4e4;
        border-radius: 8px; padding: 0.9rem 1.1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .ex-metric-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.07em; color: #888; margin-bottom: 0.2rem;
    }
    .ex-metric-value {
        font-size: 1.8rem; font-weight: 700; color: #111; line-height: 1.1;
    }
    .ex-metric-sub { font-size: 0.78rem; color: #777; margin-top: 0.15rem; }
    .ex-divider { border: none; border-top: 1px solid #e5e7eb; margin: 1.8rem 0; }
    .ex-callout {
        background: #f0f6ff; border-left: 4px solid #3A7EC7;
        border-radius: 0 6px 6px 0; padding: 0.8rem 1.1rem;
        margin-bottom: 1.2rem; font-size: 0.95rem; color: #1a2e4a; line-height: 1.6;
    }
    .ex-variant-label {
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.07em; color: #9ca3af; margin: 0.5rem 0 0.3rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _winner_badge(winner: str) -> str:
    if winner == "debunker":
        return f'<span style="color:{DEBUNKER_COLOR};font-weight:700">FC</span>'
    if winner == "spreader":
        return f'<span style="color:{SPREADER_COLOR};font-weight:700">SPR</span>'
    if winner == "error":
        return '<span style="color:#888">ERR</span>'
    return '<span style="color:#F0A500;font-weight:700">DRAW</span>'


def _build_matrix(outcomes: list) -> pd.DataFrame:
    """Pivot outcomes into a spreader × debunker × claim results grid."""
    rows = []
    for ep in outcomes:
        rows.append({
            "Spreader Prompt": ep.spreader_prompt_name,
            "Debunker Prompt": ep.debunker_prompt_name,
            "Claim": (ep.claim[:60] + "…") if len(ep.claim) > 60 else ep.claim,
            "Winner": ep.winner.title().replace("Debunker", "Fact-checker"),
            "Confidence": f"{ep.judge_confidence:.0%}",
            "FC Score": f"{ep.debunker_total:.2f}",
            "Spr Score": f"{ep.spreader_total:.2f}",
            "Error": ep.error or "",
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def render_experiment_page():
    _inject_styles()

    st.markdown('<p class="ex-page-title">Model Comparison Experiment</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ex-page-subtitle">'
        'Compare how different LLM models perform as spreader and fact-checker across a set of claims. '
        'Set different models per side (e.g., GPT-4o spreader vs Claude debunker) to test whether '
        'model capability affects debate outcomes. Prompts are fixed to the literature-grounded '
        'IME507 defaults — the independent variable is the model, not the prompt.'
        '</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)

    # ── Prompt Variants ──────────────────────────────────────────────────────
    st.markdown('<p class="ex-section">Agent Prompts</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ex-prose">'
        'The research-grounded IME507 prompts are pre-loaded for both sides. '
        'These are the canonical prompts used across all experiments for consistency. '
        'You can upload custom variants via CSV if needed for exploratory analysis.'
        '</p>',
        unsafe_allow_html=True,
    )

    prompt_input_method = st.radio(
        "Prompt input method",
        options=["manual", "csv"],
        format_func=lambda x: "Manual entry" if x == "manual" else "Upload CSV",
        horizontal=True,
        key="exp_prompt_input_method",
    )

    spreader_variants: list[PromptVariant] = []
    debunker_variants: list[PromptVariant] = []

    if prompt_input_method == "csv":
        st.markdown(
            '<p class="ex-prose">'
            'Upload a CSV with columns: <code>name</code>, <code>role</code> (spreader or debunker), '
            'and <code>prompt_text</code>. Each row becomes one variant.'
            '</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:0.7rem 1rem;margin-bottom:0.8rem;font-family:monospace;font-size:0.8rem;'
            'line-height:1.6;color:#374151">'
            '<span style="color:#9ca3af">CSV format:</span><br>'
            'name,role,prompt_text<br>'
            'IME507 Spreader,spreader,"You are a misinformation spreader agent..."<br>'
            'Naive Debunker,debunker,"You are a fact-checker in a debate..."'
            '</div>',
            unsafe_allow_html=True,
        )
        prompt_file = st.file_uploader(
            "Upload prompt variants CSV",
            type=["csv"],
            key="exp_prompt_csv",
            help="CSV with columns: name, role, prompt_text",
        )
        if prompt_file is not None:
            try:
                pdf = pd.read_csv(prompt_file)
                # Normalize column names
                pdf.columns = [c.strip().lower().replace(" ", "_") for c in pdf.columns]
                if "prompt_text" not in pdf.columns or "role" not in pdf.columns:
                    st.error("CSV must have `role` and `prompt_text` columns. Found: " + ", ".join(pdf.columns))
                else:
                    if "name" not in pdf.columns:
                        pdf["name"] = [f"Variant {i+1}" for i in range(len(pdf))]
                    for _, row in pdf.iterrows():
                        role = str(row["role"]).strip().lower()
                        name = str(row.get("name", "")).strip() or "Unnamed"
                        text = str(row["prompt_text"]).strip()
                        if not text:
                            continue
                        if role in ("spreader", "spr"):
                            spreader_variants.append(PromptVariant(name=name, text=text))
                        elif role in ("debunker", "deb", "fact-checker", "factchecker", "fc"):
                            debunker_variants.append(PromptVariant(name=name, text=text))
                    st.success(f"Loaded {len(spreader_variants)} spreader + {len(debunker_variants)} fact-checker variants")
            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")

        # Show what was loaded
        if spreader_variants or debunker_variants:
            with st.expander(f"Loaded variants ({len(spreader_variants)} spr, {len(debunker_variants)} fc)", expanded=False):
                for v in spreader_variants:
                    st.caption(f"**Spreader:** {v.name} — {len(v.text)} chars")
                for v in debunker_variants:
                    st.caption(f"**FC:** {v.name} — {len(v.text)} chars")
    else:
        sp_col, dp_col = st.columns(2)

        with sp_col:
            st.markdown("**Spreader prompts**")
            n_spr = st.number_input("Number of spreader variants", min_value=1, max_value=5, value=1, key="exp_n_spr")
            for i in range(int(n_spr)):
                st.markdown(f'<div class="ex-variant-label">Variant {i+1}</div>', unsafe_allow_html=True)
                name = st.text_input(f"Name", value=f"Spreader {i+1}", key=f"exp_spr_name_{i}", label_visibility="collapsed")
                text = st.text_area(
                    f"Prompt text",
                    value=SPREADER_SYSTEM_PROMPT if i == 0 else "",
                    height=140,
                    key=f"exp_spr_text_{i}",
                    label_visibility="collapsed",
                    placeholder="Spreader system prompt (use {claim} placeholder)",
                )
                spreader_variants.append(PromptVariant(name=name or f"Spreader {i+1}", text=text or ""))

        with dp_col:
            st.markdown("**Fact-checker prompts**")
            n_deb = st.number_input("Number of fact-checker variants", min_value=1, max_value=5, value=1, key="exp_n_deb")
            for i in range(int(n_deb)):
                st.markdown(f'<div class="ex-variant-label">Variant {i+1}</div>', unsafe_allow_html=True)
                name = st.text_input(f"Name", value=f"Fact-checker {i+1}", key=f"exp_deb_name_{i}", label_visibility="collapsed")
                text = st.text_area(
                    f"Prompt text",
                    value=DEBUNKER_SYSTEM_PROMPT if i == 0 else "",
                    height=140,
                    key=f"exp_deb_text_{i}",
                    label_visibility="collapsed",
                    placeholder="Fact-checker system prompt (use {claim} placeholder)",
                )
                debunker_variants.append(PromptVariant(name=name or f"Fact-checker {i+1}", text=text or ""))

    # ── Claims ───────────────────────────────────────────────────────────────
    st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ex-section">Claims</p>', unsafe_allow_html=True)

    claim_input_method = st.radio(
        "Claim input method",
        options=["manual", "csv"],
        format_func=lambda x: "Manual entry" if x == "manual" else "Upload CSV",
        horizontal=True,
        key="exp_claim_input_method",
    )

    claims: list[str] = []

    if claim_input_method == "csv":
        st.markdown(
            '<p class="ex-prose">'
            'Upload a CSV with a <code>claim</code> column. Optional: '
            '<code>claim_type</code>.'
            '</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:0.7rem 1rem;margin-bottom:0.8rem;font-family:monospace;font-size:0.8rem;'
            'line-height:1.6;color:#374151">'
            '<span style="color:#9ca3af">CSV format:</span><br>'
            'claim,claim_type<br>'
            'Vaccines cause autism,Health / Vaccine<br>'
            '5G towers spread COVID,Health / Vaccine<br>'
            'Climate change is a hoax,Environmental<br>'
            'The 2020 election was stolen,Political / Election<br>'
            'AI will replace all human jobs,Economic'
            '</div>',
            unsafe_allow_html=True,
        )
        claim_file = st.file_uploader(
            "Upload claims CSV",
            type=["csv", "xlsx"],
            key="exp_claim_csv",
            help="CSV/XLSX with a 'claim' column. One claim per row.",
        )
        if claim_file is not None:
            try:
                if claim_file.name.endswith(".xlsx"):
                    cdf = pd.read_excel(claim_file)
                else:
                    cdf = pd.read_csv(claim_file)
                cdf.columns = [c.strip().lower().replace(" ", "_") for c in cdf.columns]
                if "claim" not in cdf.columns:
                    st.error("File must have a `claim` column. Found: " + ", ".join(cdf.columns))
                else:
                    # Auto-classify claims missing claim_type
                    from arena.claim_metadata import classify_claim
                    if "claim_type" not in cdf.columns:
                        cdf["claim_type"] = ""
                    for idx, row in cdf.iterrows():
                        ct = str(row.get("claim_type", "") or "").strip()
                        if not ct or ct.lower() in ("", "unknown", "nan", "none"):
                            classified, _ = classify_claim(str(row["claim"]).strip(), use_llm_fallback=False)
                            if classified and classified != "unknown":
                                cdf.at[idx, "claim_type"] = classified

                    claims = [str(c).strip() for c in cdf["claim"].dropna() if str(c).strip()]
                    st.success(f"Loaded {len(claims)} claims (auto-classified)")
                    with st.expander(f"Preview ({len(claims)} claims)", expanded=False):
                        for i, c in enumerate(claims[:20]):
                            st.caption(f"{i+1}. {c[:100]}{'...' if len(c) > 100 else ''}")
                        if len(claims) > 20:
                            st.caption(f"... and {len(claims) - 20} more")
            except Exception as e:
                st.error(f"Failed to parse file: {e}")
    else:
        n_claims = st.number_input("Number of claims", min_value=1, max_value=50, value=2, key="exp_n_claims")
        for i in range(int(n_claims)):
            val = st.text_input(
                f"Claim {i+1}",
                key=f"exp_claim_{i}",
                placeholder="Enter a misinformation claim to debate",
            )
            if val and val.strip():
                claims.append(val.strip())

    # ── Run Settings ─────────────────────────────────────────────────────────
    st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ex-section">Run Settings</p>', unsafe_allow_html=True)
    cfg_col1, cfg_col2, cfg_col3, cfg_col4 = st.columns(4)
    with cfg_col1:
        turns = st.number_input("Turns per episode", min_value=2, max_value=10, value=4, key="exp_turns")
    with cfg_col2:
        default_idx = AVAILABLE_MODELS.index("gpt-4o-mini") if "gpt-4o-mini" in AVAILABLE_MODELS else 0
        model_spr = st.selectbox("Spreader model", options=AVAILABLE_MODELS, index=default_idx, key="exp_model_spr")
    with cfg_col3:
        model_deb = st.selectbox("Fact-checker model", options=AVAILABLE_MODELS, index=default_idx, key="exp_model_deb")
    with cfg_col4:
        consistency = st.selectbox("Judge consistency runs", options=[1, 3, 5], index=0, key="exp_consistency")

    cross_provider = (
        any(p in str(model_spr).lower() for p in ("claude", "gemini", "grok"))
        != any(p in str(model_deb).lower() for p in ("claude", "gemini", "grok"))
    ) or (
        any(p in str(model_spr).lower() for p in ("claude",))
        != any(p in str(model_deb).lower() for p in ("claude",))
    )
    _spr_provider = "Anthropic" if "claude" in str(model_spr) else "Google" if "gemini" in str(model_spr) else "xAI" if "grok" in str(model_spr) else "OpenAI"
    _deb_provider = "Anthropic" if "claude" in str(model_deb) else "Google" if "gemini" in str(model_deb) else "xAI" if "grok" in str(model_deb) else "OpenAI"
    if _spr_provider != _deb_provider:
        st.success(
            f"**Cross-provider matchup:** {model_spr} ({_spr_provider}) vs {model_deb} ({_deb_provider}). "
            "Make sure both API keys are set."
        )

    # ── Cost estimate ─────────────────────────────────────────────────────────
    total_episodes = max(len(spreader_variants), 1) * max(len(debunker_variants), 1) * max(len(claims), 1)
    _cost_per_turn = 0.0085 if ("mini" not in str(model_spr) and "haiku" not in str(model_spr)) else 0.0006
    _est_low  = total_episodes * int(turns) * _cost_per_turn * 0.6
    _est_high = total_episodes * int(turns) * _cost_per_turn * 1.4
    st.info(
        f"**Grid size:** {total_episodes} episode(s)  ·  "
        f"**Est. cost:** ~${_est_low:.2f}–${_est_high:.2f}  "
        f"(spreader: {model_spr}, fact-checker: {model_deb}, {turns} turns × {int(consistency)} judge run(s))"
    )

    # ── CSV Templates ─────────────────────────────────────────────────────────
    with st.expander("CSV format reference & templates", expanded=False):
        st.caption("Use these formats to prepare your experiment data. Download the templates to get started.")

        st.markdown("**Claims CSV**")
        st.markdown(
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:0.7rem 1rem;margin-bottom:0.6rem;font-family:monospace;font-size:0.8rem;'
            'line-height:1.6;color:#374151">'
            'claim,claim_type<br>'
            'Vaccines cause autism,Health / Vaccine<br>'
            '5G towers spread COVID,Health / Vaccine<br>'
            'Big Pharma hides cancer cures,Institutional Conspiracy<br>'
            'Climate change is a hoax,Environmental<br>'
            'The 2020 election was stolen,Political / Election<br>'
            'AI will replace all human jobs,Economic'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown("**Prompt Variants CSV**")
        st.markdown(
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:0.7rem 1rem;margin-bottom:0.6rem;font-family:monospace;font-size:0.8rem;'
            'line-height:1.6;color:#374151">'
            'name,role,prompt_text<br>'
            'IME507 Spreader,spreader,"You are a misinformation spreader agent..."<br>'
            'Naive Spreader,spreader,"You are a misinformation spreader in a debate..."<br>'
            'IME507 Debunker,debunker,"You are a fact-checking debunker agent..."'
            '</div>',
            unsafe_allow_html=True,
        )

        t_col1, t_col2 = st.columns(2)
        with t_col1:
            _claims_template = "claim,claim_type\nVaccines cause autism,Health / Vaccine\n5G towers spread COVID,Health / Vaccine\nBig Pharma hides cancer cures,Institutional Conspiracy\nClimate change is a hoax,Environmental\nThe 2020 election was stolen,Political / Election\nAI will replace all human jobs,Economic\nFluoride in water is mind control,Institutional Conspiracy\n"
            st.download_button(
                "Download claims template",
                data=_claims_template,
                file_name="claims_template.csv",
                mime="text/csv",
            )
        with t_col2:
            _prompts_template = 'name,role,prompt_text\nIME507 Spreader,spreader,"You are a misinformation spreader agent in a structured research simulation..."\nNaive Spreader,spreader,"You are a misinformation spreader in a debate. Argue passionately for your position..."\nIME507 Debunker,debunker,"You are a fact-checking debunker agent in a structured research simulation..."\nNaive Debunker,debunker,"You are a fact-checker. Provide evidence and correct false claims..."\n'
            st.download_button(
                "Download prompts template",
                data=_prompts_template,
                file_name="prompt_variants_template.csv",
                mime="text/csv",
            )

    # ── Run Button ────────────────────────────────────────────────────────────
    st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)
    _can_run = bool(spreader_variants and debunker_variants and claims)
    if not _can_run:
        st.warning("Add at least one spreader prompt, one fact-checker prompt, and one claim to run.")
    else:
        if st.button("▶ Run Batch Experiment", type="primary", use_container_width=True, key="exp_run_btn"):
            st.session_state["exp_outcomes"] = []
            st.session_state["exp_running"] = True
            st.session_state["exp_config_summary"] = {
                "spreader_variants": [v.name for v in spreader_variants],
                "debunker_variants": [v.name for v in debunker_variants],
                "claims": claims,
                "turns": turns,
                "model": model,
                "consistency": consistency,
            }

            config = BatchConfig(
                spreader_prompts=spreader_variants,
                debunker_prompts=debunker_variants,
                claims=claims,
                turns_per_episode=int(turns),
                model_spreader=str(model_spr),
                model_debunker=str(model_deb),
                judge_model="gpt-4o-mini",
                temperature_spreader=0.7,
                temperature_debunker=0.7,
                judge_consistency_runs=int(consistency),
            )

            progress_bar = st.progress(0, text="Starting batch experiment…")
            status_text = st.empty()
            outcomes_collected = []

            try:
                gen = run_batch_experiment(config, save_dir=EXPERIMENTS_DIR)
                while True:
                    try:
                        (done, total_c), outcome = next(gen)
                        outcomes_collected.append(outcome)
                        pct = done / total_c
                        progress_bar.progress(pct, text=f"Episode {done}/{total_c}")
                        status_text.caption(
                            f"Last: {outcome.spreader_prompt_name} vs {outcome.debunker_prompt_name} — "
                            f"*{outcome.claim[:50]}* → **{outcome.winner.title()}**"
                        )
                    except StopIteration as si:
                        outcomes_collected = [asdict(ep) for ep in (si.value.outcomes if si.value else outcomes_collected)]
                        break
            except Exception as e:
                st.error(f"Experiment failed: {e}")
                st.session_state["exp_running"] = False
                return

            progress_bar.progress(1.0, text="Done!")
            status_text.empty()
            st.session_state["exp_outcomes"] = outcomes_collected
            st.session_state["exp_running"] = False
            st.success(f"Completed {len(outcomes_collected)} episode(s).")
            st.rerun()

    # ── Results Matrix ────────────────────────────────────────────────────────
    outcomes = st.session_state.get("exp_outcomes", [])
    if outcomes:
        st.markdown('<hr class="ex-divider">', unsafe_allow_html=True)
        st.markdown('<p class="ex-section">Results</p>', unsafe_allow_html=True)

        # Summary KPI cards
        n_total = len(outcomes)
        n_fc = sum(1 for ep in outcomes if (ep.get("winner") or "").lower() == "debunker")
        n_spr = sum(1 for ep in outcomes if (ep.get("winner") or "").lower() == "spreader")
        n_err = sum(1 for ep in outcomes if ep.get("error"))
        fc_pct = n_fc / max(n_total, 1)
        st.markdown(
            f'<div class="ex-metric-grid">'
            f'<div class="ex-metric-card"><div class="ex-metric-label">Episodes</div>'
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

        st.markdown(
            '<p class="ex-prose">'
            'Each row is one debate cell from the grid. '
            'Winner = FC (fact-checker), Spreader, or Draw.'
            '</p>',
            unsafe_allow_html=True,
        )

        rows = []
        for ep in outcomes:
            if isinstance(ep, dict):
                rows.append({
                    "Spreader": ep.get("spreader_prompt_name", ""),
                    "Fact-checker": ep.get("debunker_prompt_name", ""),
                    "Claim": (ep.get("claim", "")[:60] + "…") if len(ep.get("claim", "")) > 60 else ep.get("claim", ""),
                    "Winner": ep.get("winner", "").title().replace("Debunker", "Fact-checker"),
                    "Confidence": f"{ep.get('judge_confidence', 0):.0%}",
                    "FC Score": f"{ep.get('debunker_total', 0):.2f}",
                    "Spr Score": f"{ep.get('spreader_total', 0):.2f}",
                    "Error": ep.get("error") or "",
                })

        result_df = pd.DataFrame(rows)
        if not result_df.empty:
            st.dataframe(result_df, use_container_width=True, hide_index=True)

            # Win-rate summary
            st.markdown("**Win Rate Summary**")
            win_summary = (
                result_df.groupby(["Spreader", "Fact-checker"])["Winner"]
                .value_counts(normalize=True)
                .mul(100)
                .round(1)
                .rename("Win %")
                .reset_index()
            )
            if not win_summary.empty:
                st.dataframe(win_summary, use_container_width=True, hide_index=True)

            # Download
            st.download_button(
                "⬇ Download results as JSON",
                data=json.dumps(outcomes, indent=2),
                file_name="batch_experiment_results.json",
                mime="application/json",
            )
