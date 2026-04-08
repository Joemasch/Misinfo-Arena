"""
Debate Insights Component for Misinformation Arena v2

AI-generated strategic analysis of the debate, styled as a readable
brief with clear sections and visual hierarchy.
"""

import json
import streamlit as st

DEBUNKER_COLOR = "#4A7FA5"
SPREADER_COLOR = "#D4A843"


def _inject_insights_css():
    st.markdown("""
    <style>
    .di-card {
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 4px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    }
    .di-section-label {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.09em; color: var(--color-text-muted, #888); margin: 0.9rem 0 0.3rem 0;
    }
    .di-section-label:first-child { margin-top: 0; }
    .di-body {
        font-size: 0.95rem; color: var(--color-text-primary, #E8E4D9); line-height: 1.65;
    }
    .di-tldr {
        background: rgba(74, 127, 165, 0.08); border-left: 4px solid var(--color-accent-blue, #4A7FA5);
        border-radius: 0 4px 4px 0; padding: 0.7rem 1rem;
        font-size: 0.95rem; font-weight: 500; color: var(--color-text-primary, #E8E4D9); line-height: 1.5;
        margin-bottom: 0.8rem;
    }
    .di-key-turns {
        display: inline-block; font-size: 0.78rem; font-weight: 600;
        padding: 0.2rem 0.55rem; border-radius: 4px;
        border: 1px solid rgba(74, 127, 165, 0.4); color: var(--color-accent-blue, #4A7FA5);
        background: rgba(74, 127, 165, 0.1); margin-right: 0.3rem;
    }
    .di-meta {
        font-size: 0.78rem; color: var(--color-text-muted, #888); margin-top: 0.6rem;
        padding-top: 0.5rem; border-top: 1px solid var(--color-border, #2A2A2A);
    }
    </style>
    """, unsafe_allow_html=True)


def render_debate_insights():
    """Render AI-generated debate insights as a styled brief."""
    debug_enabled = st.session_state.get("debug") or st.session_state.get("debug_insights", False)

    _inject_insights_css()

    # ── Read match result ────────────────────────────────────────────────────
    match_result = (
        st.session_state.get("current_match_result")
        or st.session_state.get("match_result")
    )

    if match_result is None:
        if st.session_state.get("debate_in_progress", False):
            st.info("Insights will appear after the debate finishes.")
        return

    # ── Extract insights safely ──────────────────────────────────────────────
    if isinstance(match_result, dict):
        insights = match_result.get("insights")
        insights_error = match_result.get("insights_error")
    else:
        insights = getattr(match_result, "insights", None)
        insights_error = getattr(match_result, "insights_error", None)

    if insights_error:
        st.warning(f"Insights unavailable: {insights_error}")
        return

    if not insights:
        if st.session_state.get("debate_in_progress", False):
            st.info("Insights will appear after the debate finishes...")
        return

    # ── Helper ───────────────────────────────────────────────────────────────
    def _get(key: str, default=""):
        if isinstance(insights, dict):
            return insights.get(key, default)
        return getattr(insights, key, default)

    tldr              = _get("tldr")
    conflict          = _get("core_conflict")
    dynamics          = _get("strategic_dynamics")
    outcome           = _get("outcome_driver")
    counterfactual    = _get("counterfactual")
    pattern_note      = _get("pattern_note")
    key_turns         = _get("key_turns", [])
    turning_explained = _get("turning_points_explained")
    model_name        = _get("model", "AI")
    generated_at      = _get("generated_at", "")

    quality_warnings = []
    if isinstance(insights, dict):
        quality_warnings = insights.get("quality_warnings") or []
    elif insights is not None:
        quality_warnings = getattr(insights, "quality_warnings", None) or []

    # ── Render as styled brief ───────────────────────────────────────────────
    if tldr:
        st.markdown(f'<div class="di-tldr"><b>TL;DR:</b> {tldr}</div>', unsafe_allow_html=True)

    # Build brief card
    sections = []
    if conflict:
        sections.append(
            '<div class="di-section-label">Core Conflict</div>'
            f'<div class="di-body">{conflict}</div>'
        )
    if dynamics:
        sections.append(
            '<div class="di-section-label">Strategic Dynamics</div>'
            f'<div class="di-body">{dynamics}</div>'
        )
    if outcome:
        sections.append(
            '<div class="di-section-label">Why This Outcome</div>'
            f'<div class="di-body">{outcome}</div>'
        )
    if counterfactual:
        sections.append(
            '<div class="di-section-label">What Could Have Changed</div>'
            f'<div class="di-body">{counterfactual}</div>'
        )
    if pattern_note:
        sections.append(
            '<div class="di-section-label">Pattern Note</div>'
            f'<div class="di-body">{pattern_note}</div>'
        )

    if key_turns:
        turn_badges = "".join(f'<span class="di-key-turns">Turn {t}</span>' for t in key_turns)
        turns_section = f'<div class="di-section-label">Key Turning Points</div>{turn_badges}'
        if turning_explained:
            turns_section += f'<div class="di-body" style="margin-top:0.4rem">{turning_explained}</div>'
        sections.append(turns_section)

    if sections:
        meta = f'<div class="di-meta">Generated by {model_name}' + (f' at {generated_at}' if generated_at else '') + '</div>'
        card_body = "".join(sections) + meta
        st.markdown(f'<div class="di-card">{card_body}</div>', unsafe_allow_html=True)

    if quality_warnings:
        with st.expander("Quality notices", expanded=False):
            for w in quality_warnings:
                st.caption(f"• {w}")

    # ── Export ───────────────────────────────────────────────────────────────
    full_parts = []
    if tldr:           full_parts.append(f"TL;DR: {tldr}")
    if conflict:       full_parts.append(f"\nCORE CONFLICT:\n{conflict}")
    if dynamics:       full_parts.append(f"\nSTRATEGIC DYNAMICS:\n{dynamics}")
    if outcome:        full_parts.append(f"\nWHY THIS OUTCOME:\n{outcome}")
    if counterfactual: full_parts.append(f"\nWHAT COULD HAVE CHANGED:\n{counterfactual}")
    if pattern_note:   full_parts.append(f"\nPATTERN NOTE: {pattern_note}")
    if key_turns:
        full_parts.append(f"\nKEY TURNS: {', '.join(f'Turn {t}' for t in key_turns)}")
        if turning_explained:
            full_parts.append(f"WHY: {turning_explained}")
    full_text = "\n".join(full_parts)

    if full_text.strip():
        with st.expander("Export insights"):
            st.download_button(
                "Download as .txt",
                data=full_text,
                file_name="debate_insights.txt",
                mime="text/plain",
                use_container_width=True,
            )
