"""
Prompts Page for Misinformation Arena v2

Read-only view of the literature-grounded IME507 prompts used by each agent.
Prompts are held constant across all experiments per advisor guidance.
"""

from __future__ import annotations

import streamlit as st

from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
from arena.prompts.judge_static_prompt import (
    get_judge_static_prompt,
    get_judge_static_prompt_version,
)


def render_prompts_page():
    """Render the Prompts page as a read-only reference."""
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    st.markdown(
        '<p style="font-family:Playfair Display,Georgia,serif;font-size:2rem;font-weight:400;'
        'color:var(--color-accent-red, #C9363E);margin-top:1rem;margin-bottom:0.2rem;'
        'padding-bottom:0.3rem;border-bottom:1px solid var(--color-border, #2A2A2A);'
        'text-align:left">Active Prompts</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.95rem;color:var(--color-text-muted, #888);margin-bottom:1.5rem;line-height:1.5">'
        'These are the literature-grounded IME507 prompts used by each agent. '
        'Prompts are held constant across all experiments to isolate the effect of '
        'model selection, claim type, and debate length.'
        '</p>',
        unsafe_allow_html=True,
    )

    st.success(
        "Research configuration active — prompts are fixed for experimental consistency."
    )

    # ── Spreader ──────────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:1.35rem;font-weight:700;color:var(--color-text-primary, #E8E4D9);margin-top:2rem;'
        'margin-bottom:0.3rem;padding-bottom:0.3rem;border-bottom:2px solid var(--color-border, #2A2A2A)">'
        'Spreader Agent</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted, #888);margin-bottom:0.5rem">'
        'Argues in favor of the misinformation claim using persuasion tactics derived from '
        'IME507 course research. Strategies include emotional appeals, selective evidence, '
        'conspiratorial framing, and inoculation against corrections.</p>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Spreader system prompt",
        value=SPREADER_SYSTEM_PROMPT,
        height=250,
        disabled=True,
        key="prompts_view_spreader",
        label_visibility="collapsed",
    )
    st.caption(f"Length: {len(SPREADER_SYSTEM_PROMPT):,} characters")

    # ── Debunker ──────────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:1.35rem;font-weight:700;color:var(--color-text-primary, #E8E4D9);margin-top:2rem;'
        'margin-bottom:0.3rem;padding-bottom:0.3rem;border-bottom:2px solid var(--color-border, #2A2A2A)">'
        'Fact-Checker Agent</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted, #888);margin-bottom:0.5rem">'
        'Counters the claim using evidence-based reasoning and inoculation techniques. '
        '6-step response architecture: lead with truth, name the manipulation tactic, '
        'structured evidence, address cognitive bias, alternative narrative, calibrated confidence.</p>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Debunker system prompt",
        value=DEBUNKER_SYSTEM_PROMPT,
        height=250,
        disabled=True,
        key="prompts_view_debunker",
        label_visibility="collapsed",
    )
    st.caption(f"Length: {len(DEBUNKER_SYSTEM_PROMPT):,} characters")

    # ── Judge ─────────────────────────────────────────────────────────────
    judge_prompt = get_judge_static_prompt()
    st.markdown(
        '<p style="font-size:1.35rem;font-weight:700;color:var(--color-text-primary, #E8E4D9);margin-top:2rem;'
        'margin-bottom:0.3rem;padding-bottom:0.3rem;border-bottom:2px solid var(--color-border, #2A2A2A)">'
        'Judge Rubric</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--color-text-muted, #888);margin-bottom:0.5rem">'
        f'Version: <code>{get_judge_static_prompt_version()}</code> — '
        'Scores 6 dimensions with equal weights, grounded in Wachsmuth et al. (2017), '
        'D2D (EMNLP 2025), and inoculation theory. Role-relative scoring: the spreader '
        'is evaluated on persuasive effectiveness, not factual accuracy.</p>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Judge prompt",
        value=judge_prompt,
        height=350,
        disabled=True,
        key="prompts_view_judge",
        label_visibility="collapsed",
    )
    st.caption(f"Length: {len(judge_prompt):,} characters")

    # ── Literature references ─────────────────────────────────────────────
    st.divider()
    st.markdown(
        '<p style="font-size:1.35rem;font-weight:700;color:var(--color-text-primary, #E8E4D9);'
        'margin-bottom:0.3rem;padding-bottom:0.3rem;border-bottom:2px solid var(--color-border, #2A2A2A)">'
        'Literature Grounding</p>',
        unsafe_allow_html=True,
    )
    st.markdown("""
**Scoring dimensions:**
- **Factuality, Source Credibility** — D2D: Debate-to-Detect (EMNLP 2025)
- **Reasoning Quality** — Wachsmuth et al. (2017) "Argumentation Quality Assessment" — Cogency
- **Responsiveness** — Wachsmuth et al. (2017) — Reasonableness
- **Persuasion** — Wachsmuth et al. (2017) — Effectiveness
- **Manipulation Awareness** — Roozenbeek & van der Linden (2022), Cook et al. (2017) — Inoculation theory

**Strategy taxonomy:**
- Spreader tactics: FLICC (Cook & Lewandowsky, 2020), SemEval-2023 Task 3
- Debunker tactics: Cook et al. (2017), Lewandowsky (2020) Debunking Handbook
    """)
