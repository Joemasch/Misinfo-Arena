"""Tools page — combines Annotate, Exports, and Prompts sub-tabs."""

import json
import pandas as pd
import streamlit as st

from arena.presentation.streamlit.pages.prompts_page import render_prompts_page
from arena.presentation.streamlit.pages.annotation_page import render_annotation_page


# ---------------------------------------------------------------------------
# Citation extraction helpers
# ---------------------------------------------------------------------------

_NAMED_SOURCES = [
    "CDC", "WHO", "FDA", "EPA", "NASA", "NIH", "IPCC",
    "Harvard", "Stanford", "MIT", "Oxford", "Yale", "Cambridge",
    "Nature", "Lancet", "Science", "JAMA", "BMJ", "NEJM",
    "Pew Research", "Gallup", "Reuters", "AP News", "BBC",
    "Amnesty International", "Human Rights Watch",
    "United Nations", "World Bank", "IMF",
]

_VAGUE_KEYWORDS = [
    "research shows", "studies show", "experts say", "scientists say",
    "according to studies", "evidence suggests", "research suggests",
    "some researchers", "many experts", "studies have shown",
]


def _extract_citation_data(ep: dict) -> dict:
    """Extract citation signals from an episode's transcript."""
    turns = ep.get("turns", [])
    result = {
        "spr_named_sources": 0, "spr_vague_sources": 0, "spr_urls": 0,
        "deb_named_sources": 0, "deb_vague_sources": 0, "deb_urls": 0,
    }
    for t in turns:
        for side, prefix in [("spreader_message", "spr"), ("debunker_message", "deb")]:
            msg = t.get(side, {})
            text = msg.get("content", "") if isinstance(msg, dict) else str(msg or "")
            text_lower = text.lower()

            if "http" in text_lower:
                result[f"{prefix}_urls"] += 1
            for src in _NAMED_SOURCES:
                if src.lower() in text_lower:
                    result[f"{prefix}_named_sources"] += 1
                    break
            for kw in _VAGUE_KEYWORDS:
                if kw in text_lower:
                    result[f"{prefix}_vague_sources"] += 1
                    break
    return result


# ---------------------------------------------------------------------------
# Strategy extraction helpers
# ---------------------------------------------------------------------------

def _extract_strategy_data(ep: dict) -> dict:
    """Extract strategy fields from an episode."""
    sa = ep.get("strategy_analysis") or {}
    return {
        "strategy_status": sa.get("status", "missing"),
        "spr_primary_strategy": sa.get("spreader_primary", ""),
        "deb_primary_strategy": sa.get("debunker_primary", ""),
        "spr_strategies": "|".join(sa.get("spreader_strategies", [])),
        "deb_strategies": "|".join(sa.get("debunker_strategies", [])),
        "spr_strategy_count": len(sa.get("spreader_strategies", [])),
        "deb_strategy_count": len(sa.get("debunker_strategies", [])),
    }


# ---------------------------------------------------------------------------
# Exports tab
# ---------------------------------------------------------------------------

def _render_exports_tab():
    """Render per-finding CSV exports with hypotheses and Minitab steps."""
    from arena.analysis.episode_dataset import build_episode_df
    from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
    from arena.io.run_store_v2_read import load_episodes
    from pathlib import Path

    RUNS_DIR = "runs"

    _TIER_MAP = {
        "gpt-4o-mini": "budget", "gpt-4o": "premium",
        "claude-sonnet-4-20250514": "premium", "claude-sonnet-4": "premium",
        "gemini-2.5-flash": "mid",
    }

    def _get_tier(model: str) -> str:
        return _TIER_MAP.get(model or "", "unknown")

    st.markdown(
        '<p style="font-family:Playfair Display,Georgia,serif;font-size:2rem;font-weight:400;'
        'color:var(--color-accent-red,#C9363E);margin-top:1rem;margin-bottom:0.2rem;'
        'padding-bottom:0.3rem;border-bottom:1px solid var(--color-border,#2A2A2A);'
        'text-align:left">Statistical Exports</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.95rem;color:var(--color-text-muted,#888);margin-bottom:1.5rem;line-height:1.5">'
        'Per-test CSVs organized by research finding. Each export contains exactly the columns '
        'needed for that statistical test — download, open in Minitab, run the test.'
        '</p>',
        unsafe_allow_html=True,
    )

    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed debates. Run experiments first.")
        return

    # ── Load episodes with strategy + citation data ──────────────────────
    # We need raw episode data for citation extraction, not just the DataFrame
    all_rows = []
    runs_path = Path(RUNS_DIR)
    for run_id in run_ids:
        eps, _ = load_episodes(run_id, RUNS_DIR, token)
        for ep in eps:
            if ep.get("study_id") != "experiment":
                continue
            if ep.get("results", {}).get("winner") == "error":
                continue
            # Skip pre-fix episodes
            if (ep.get("created_at") or "") < "2026-04-13T21":
                continue

            config = ep.get("config_snapshot", {})
            agents = config.get("agents", {})
            results = ep.get("results", {})
            totals = results.get("totals", {})

            spr_model = (agents.get("spreader") or {}).get("model", "")
            deb_model = (agents.get("debunker") or {}).get("model", "")

            row = {
                "claim": ep.get("claim", ""),
                "claim_type": ep.get("claim_type", ""),
                "model_spreader": spr_model,
                "model_debunker": deb_model,
                "model_matchup": f"{spr_model} vs {deb_model}",
                "spreader_tier": _get_tier(spr_model),
                "debunker_tier": _get_tier(deb_model),
                "max_turns": config.get("planned_max_turns", 0),
                "winner": results.get("winner", ""),
                "fc_win": 1 if results.get("winner") == "debunker" else 0,
                "spr_win": 1 if results.get("winner") == "spreader" else 0,
                "margin": round((totals.get("debunker", 0) or 0) - (totals.get("spreader", 0) or 0), 2),
                "confidence": results.get("judge_confidence", 0),
            }

            # Scorecard
            for s in results.get("scorecard", []):
                m = s.get("metric", "")
                row[f"{m}_spr"] = s.get("spreader", 0)
                row[f"{m}_deb"] = s.get("debunker", 0)

            # Strategy
            row.update(_extract_strategy_data(ep))

            # Citations
            row.update(_extract_citation_data(ep))

            all_rows.append(row)

    if not all_rows:
        st.info("No experiment episodes found.")
        return

    df = pd.DataFrame(all_rows)

    st.markdown(
        f'<div class="ds-callout"><strong>{len(df)} experiment episodes</strong> available for export.</div>',
        unsafe_allow_html=True,
    )

    # ── Helpers ───────────────────────────────────────────────────────────
    def _finding_header(title: str):
        st.markdown(
            f'<div style="margin-top:2rem;margin-bottom:0.3rem;padding:1rem 1.2rem;'
            f'background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
            f'border-radius:8px;border-left:4px solid var(--color-accent-red,#C9363E)">'
            f'<div style="font-size:1.15rem;font-weight:700;color:var(--color-text-primary,#E8E4D9)">'
            f'{title}</div></div>',
            unsafe_allow_html=True,
        )

    def _test_block(
        test_name: str,
        h0: str,
        ha: str,
        minitab_steps: str,
        export_df: pd.DataFrame,
        filename: str,
    ):
        st.markdown(f"**{test_name}**")
        st.markdown(
            f'<div style="font-size:0.88rem;color:var(--color-text-muted,#888);line-height:1.7;'
            f'margin:0.3rem 0 0.5rem 0">'
            f'<b>H₀:</b> {h0}<br>'
            f'<b>Hₐ:</b> {ha}<br>'
            f'<b>Minitab:</b> {minitab_steps}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            f"Download {filename}",
            data=export_df.to_csv(index=False).encode(),
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )
        with st.expander(f"Preview ({len(export_df)} rows × {len(export_df.columns)} cols)", expanded=False):
            st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)
        st.markdown("")

    # ══════════════════════════════════════════════════════════════════════
    # FULL EXPORT
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Full Export")
    _test_block(
        "Complete dataset — all columns",
        "N/A", "N/A",
        "Use for custom analyses not covered by per-test exports below.",
        df,
        "full_experiment_data.csv",
    )

    # ══════════════════════════════════════════════════════════════════════
    # FINDING 1: MODEL STRATEGY FINGERPRINTS
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Finding 1: Model Strategy Fingerprints")
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted,#888);margin-bottom:1rem">'
        'Does each model have a distinct set of tactics it defaults to as spreader and debunker?</p>',
        unsafe_allow_html=True,
    )

    # Build long-format strategy table (one row per episode × strategy)
    strat_rows = []
    for _, row in df.iterrows():
        for side, col in [("spreader", "spr_strategies"), ("debunker", "deb_strategies")]:
            strategies = str(row.get(col, "")).split("|") if row.get(col) else []
            model = row["model_spreader"] if side == "spreader" else row["model_debunker"]
            for s in strategies:
                s = s.strip()
                if s:
                    strat_rows.append({
                        "model": model,
                        "side": side,
                        "strategy": s,
                        "claim_type": row["claim_type"],
                        "max_turns": row["max_turns"],
                    })
    strat_df = pd.DataFrame(strat_rows) if strat_rows else pd.DataFrame()

    if not strat_df.empty:
        _test_block(
            "1.1 — Chi-Squared: Strategy frequency differs by model",
            "Strategy frequency distribution is the same across all models (as spreader).",
            "At least one model uses strategies at significantly different frequencies.",
            "Stat > Tables > Cross Tabulation and Chi-Square. Rows: model, Columns: strategy. "
            "Run separately for side=spreader and side=debunker.",
            strat_df,
            "f1_strategy_by_model.csv",
        )

    # ══════════════════════════════════════════════════════════════════════
    # FINDING 2: STRATEGY × CLAIM TYPE
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Finding 2: Models Argue Differently by Claim Type")
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted,#888);margin-bottom:1rem">'
        'Do models adapt their strategy based on the claim domain?</p>',
        unsafe_allow_html=True,
    )

    if not strat_df.empty:
        _test_block(
            "2.1 — Chi-Squared: Strategy distribution differs by claim type (within model)",
            "A given model uses the same strategy distribution regardless of claim type.",
            "The model's strategy distribution differs significantly across claim types.",
            "Filter to one model + one side. Stat > Tables > Cross Tabulation. "
            "Rows: claim_type, Columns: strategy. Repeat for each model.",
            strat_df,
            "f2_strategy_by_claim_type.csv",
        )

    _test_block(
        "2.2 — Two-Way ANOVA: Model × Claim Type on Margin",
        "Neither model nor claim type affects score margin, and there is no interaction.",
        "Model, claim type, or their interaction significantly affects margin.",
        "Stat > ANOVA > General Linear Model. Response: margin. "
        "Factors: model_matchup + claim_type. Include interaction term.",
        df[["model_matchup", "claim_type", "margin"]].copy(),
        "f2_model_x_claimtype_margin.csv",
    )

    # ══════════════════════════════════════════════════════════════════════
    # FINDING 3: GAME THEORY
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Finding 3: Strategic Adaptation (Game Theory)")
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted,#888);margin-bottom:1rem">'
        'When the debunker names a manipulation tactic, does the spreader abandon it?</p>',
        unsafe_allow_html=True,
    )

    _test_block(
        "3.1 — Chi-Squared: Tactic-naming frequency differs by debunker model",
        "All debunker models name manipulation tactics at the same rate.",
        "At least one debunker model names tactics significantly more or less often.",
        "Stat > Tables > Cross Tabulation. Rows: model (debunker), "
        "Columns: uses_tactic_naming (1/0). Check Chi-Square.",
        df[["model_debunker", "deb_strategies"]].assign(
            uses_tactic_naming=df["deb_strategies"].str.contains("logical_refutation", na=False).astype(int)
        )[["model_debunker", "uses_tactic_naming"]].copy(),
        "f3_tactic_naming_by_model.csv",
    )

    _test_block(
        "3.2 — Descriptive: Strategy diversity as proxy for adaptation",
        "N/A (descriptive)",
        "N/A (descriptive)",
        "Compute mean spr_strategy_count and deb_strategy_count grouped by model and max_turns. "
        "Higher counts in longer debates suggest ongoing adaptation.",
        df[["model_spreader", "model_debunker", "max_turns",
            "spr_strategy_count", "deb_strategy_count"]].copy(),
        "f3_strategy_diversity.csv",
    )

    # ══════════════════════════════════════════════════════════════════════
    # FINDING 4: CITATION QUALITY
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Finding 4: Citation Quality by Model and Claim Type")
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted,#888);margin-bottom:1rem">'
        'Which model produces the most credible citations as debunker?</p>',
        unsafe_allow_html=True,
    )

    citation_cols = ["model_debunker", "claim_type", "max_turns",
                     "deb_named_sources", "deb_vague_sources", "deb_urls",
                     "spr_named_sources", "spr_vague_sources", "spr_urls"]
    cite_df = df[[c for c in citation_cols if c in df.columns]].copy()

    _test_block(
        "4.1 — One-Way ANOVA: Named source count differs by debunker model",
        "All debunker models cite named sources at the same rate.",
        "At least one model cites named sources significantly more or less often.",
        "Stat > ANOVA > One-Way. Response: deb_named_sources. Factor: model_debunker. "
        "Post-hoc: Tukey's pairwise comparison.",
        cite_df,
        "f4_citations_by_model.csv",
    )

    _test_block(
        "4.2 — Two-Way ANOVA: Model × Claim Type on Citation Quality",
        "Neither model nor claim type affects citation count, and there is no interaction.",
        "Model, claim type, or their interaction significantly affects citation count.",
        "Stat > ANOVA > General Linear Model. Response: deb_named_sources. "
        "Factors: model_debunker + claim_type. Include interaction.",
        cite_df,
        "f4_citations_model_x_type.csv",
    )

    _test_block(
        "4.3 — Chi-Squared: Citation type distribution differs by model",
        "All models use the same mix of citation types (named vs vague vs URL).",
        "At least one model's citation type distribution differs significantly.",
        "Create a column for dominant citation type per episode, then "
        "Stat > Tables > Cross Tabulation. Rows: model_debunker, Columns: citation_type.",
        cite_df,
        "f4_citation_types.csv",
    )

    # ══════════════════════════════════════════════════════════════════════
    # FINDING 5: STRATEGY DEPTH PLATEAU
    # ══════════════════════════════════════════════════════════════════════
    _finding_header("Finding 5: Strategy Depth Plateaus with Debate Length")
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted,#888);margin-bottom:1rem">'
        'Do longer debates produce more unique tactics, or do agents just recycle?</p>',
        unsafe_allow_html=True,
    )

    depth_cols = ["model_spreader", "model_debunker", "max_turns",
                  "spr_strategy_count", "deb_strategy_count"]
    depth_df = df[[c for c in depth_cols if c in df.columns]].copy()

    _test_block(
        "5.1 — One-Way ANOVA: Strategy diversity differs by turn length",
        "The number of unique strategies per episode is the same at 2, 6, and 10 turns.",
        "Strategy diversity differs significantly across turn lengths.",
        "Stat > ANOVA > One-Way. Response: spr_strategy_count (or deb_strategy_count). "
        "Factor: max_turns.",
        depth_df,
        "f5_diversity_by_turns.csv",
    )

    _test_block(
        "5.2 — Two-Way ANOVA: Model × Turn Length on Strategy Diversity",
        "Neither model nor turn length affects strategy diversity, and there is no interaction.",
        "The diversity plateau differs by model (interaction is significant).",
        "Stat > ANOVA > General Linear Model. Response: spr_strategy_count. "
        "Factors: model_spreader + max_turns. Include interaction.",
        depth_df,
        "f5_diversity_model_x_turns.csv",
    )

    _test_block(
        "5.3 — Paired T-Test: Diversity jump from 2→6 vs 6→10",
        "The increase in strategy diversity from 2→6 turns equals the increase from 6→10.",
        "The 2→6 increase is significantly larger than the 6→10 increase (plateau effect).",
        "Compute mean diversity at each turn length. Stat > Basic Statistics > Paired t. "
        "Compare the 2→6 difference against the 6→10 difference.",
        depth_df,
        "f5_diversity_paired.csv",
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
