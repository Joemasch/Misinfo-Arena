"""
Study-baseline panels that anchor a user's debate against the
960-episode experiment_v2 baseline.

  - render_predicted_outcome_panel(claim): pre-debate, on the Arena tab
  - render_result_vs_baseline(claim, winner, margin): post-verdict, used
    by judge_report so it appears in both Arena live verdict and Replay
    → Verdict tab
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from arena.study_baselines import (
    compare_outcome,
    get_baseline_for_claim,
    judge_model,
)


_PANEL_CSS_KEY = "_baseline_panel_css_injected"


def _inject_css() -> None:
    if st.session_state.get(_PANEL_CSS_KEY):
        return
    st.session_state[_PANEL_CSS_KEY] = True
    st.markdown(
        """
        <style>
        .bp-panel {
            margin: 0.8rem 0 0.4rem 0;
            padding: 0.85rem 1.1rem;
            background: rgba(74,127,165,0.06);
            border-left: 3px solid #4A7FA5;
            border-radius: 4px;
            font-family: 'IBM Plex Sans', sans-serif;
        }
        .bp-panel.match { border-left-color: #4CAF7D; background: rgba(76,175,125,0.07); }
        .bp-panel.diverge { border-left-color: #D4A843; background: rgba(212,168,67,0.07); }
        .bp-head {
            font-size: 0.72rem; font-weight: 700; letter-spacing: 1.5px;
            text-transform: uppercase; color: #4A7FA5; margin-bottom: 0.4rem;
        }
        .bp-panel.match .bp-head { color: #4CAF7D; }
        .bp-panel.diverge .bp-head { color: #D4A843; }
        .bp-row { display: flex; gap: 1.6rem; flex-wrap: wrap; align-items: baseline; }
        .bp-stat { display: flex; flex-direction: column; gap: 0.05rem; }
        .bp-stat-num {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 1.15rem; font-weight: 700; color: #E8E4D9; line-height: 1.05;
        }
        .bp-stat-label {
            font-size: 0.7rem; color: #888; text-transform: uppercase;
            letter-spacing: 0.5px; line-height: 1.2;
        }
        .bp-interp {
            margin-top: 0.55rem; font-size: 0.88rem; color: #C8C4B9;
            line-height: 1.5;
        }
        .bp-interp em { color: #888; font-style: normal; font-size: 0.78rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _pct(x: float) -> str:
    return f"{round(float(x) * 100)}%"


def _interpretation(baseline: dict) -> str:
    domain = baseline["domain"]
    fals = baseline["falsifiability"]
    fc = float(baseline.get("fc_win_rate", 0) or 0)
    sp = float(baseline.get("sp_win_rate", 0) or 0)
    if fc >= 0.70:
        return (
            f"Fact-checker tends to dominate <strong>{domain}</strong> {fals} claims. "
            "Expect a decisive fact-checker win."
        )
    if fc >= 0.55:
        return (
            f"Fact-checker has a moderate edge on <strong>{domain}</strong> {fals} claims, "
            "but the spreader still wins a meaningful share."
        )
    if sp >= 0.55:
        return (
            f"Spreader has a moderate-to-strong edge on <strong>{domain}</strong> {fals} claims — "
            "fact-checkers struggle here."
        )
    return (
        f"<strong>{domain}</strong> {fals} claims are roughly even in our study — "
        "expect a contested debate."
    )


def render_predicted_outcome_panel(claim: str) -> None:
    """Pre-debate banner. Hidden when the claim's cell isn't classifiable."""
    if not claim or not claim.strip():
        return
    baseline = get_baseline_for_claim(claim)
    if baseline is None:
        return

    _inject_css()
    fc = baseline["fc_win_rate"]
    conf = baseline["avg_confidence"]
    margin = baseline["avg_margin"]
    n = baseline["n"]
    domain = baseline["domain"]
    fals = baseline["falsifiability"].title()

    st.markdown(
        f"""
        <div class="bp-panel">
            <div class="bp-head">Predicted outcome &middot; from our 960-debate study</div>
            <div class="bp-row">
                <div class="bp-stat">
                    <div class="bp-stat-num">{_pct(fc)}</div>
                    <div class="bp-stat-label">Fact-checker win rate</div>
                </div>
                <div class="bp-stat">
                    <div class="bp-stat-num">{conf:.2f}</div>
                    <div class="bp-stat-label">Avg judge confidence</div>
                </div>
                <div class="bp-stat">
                    <div class="bp-stat-num">{margin:.2f}</div>
                    <div class="bp-stat-label">Avg score margin</div>
                </div>
                <div class="bp-stat">
                    <div class="bp-stat-num">{n}</div>
                    <div class="bp-stat-label">Similar episodes ({domain} &middot; {fals})</div>
                </div>
            </div>
            <div class="bp-interp">
                {_interpretation(baseline)}
                <br><em>Baselines judged by {judge_model()}.</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result_vs_baseline(
    claim: str,
    actual_winner: str,
    actual_margin: Optional[float] = None,
) -> None:
    """Post-verdict comparison card. Used inside judge_report.

    actual_winner: "spreader" | "debunker" | "draw"
    actual_margin: |debunker - spreader| total
    """
    if not claim or actual_winner not in ("spreader", "debunker", "draw"):
        return
    baseline = get_baseline_for_claim(claim)
    if baseline is None:
        return

    cmp = compare_outcome(actual_winner, float(actual_margin or 0.0), baseline)
    klass = "match" if cmp["outcome_match"] else "diverge"
    domain = baseline["domain"]
    fals = baseline["falsifiability"]
    actual_side_display = {"debunker": "Fact-checker", "spreader": "Spreader", "draw": "Draw"}[actual_winner]

    if cmp["outcome_match"]:
        headline = (
            f"<strong>{actual_side_display} won</strong> — matches the baseline "
            f"({_pct(cmp['majority_rate'])} of {domain} {fals} claims tip this way)."
        )
    else:
        headline = (
            f"<strong>{actual_side_display} won</strong> — diverges from the baseline. "
            f"Only {_pct(cmp['actual_rate'])} of {domain} {fals} claims tip this way; "
            f"the {cmp['majority_side']} usually wins ({_pct(cmp['majority_rate'])})."
        )

    margin_line = ""
    if actual_margin is not None:
        margin_line = (
            f"Margin <strong>{float(actual_margin):.2f}</strong> &middot; "
            f"baseline <strong>{cmp['baseline_avg_margin']:.2f}</strong> &middot; "
            f"<em>{cmp['margin_descriptor']} the baseline.</em>"
        )

    _inject_css()
    st.markdown(
        f"""
        <div class="bp-panel {klass}">
            <div class="bp-head">How this compares to the study</div>
            <div class="bp-interp" style="margin-top:0;">{headline}</div>
            {f'<div class="bp-interp">{margin_line}</div>' if margin_line else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
