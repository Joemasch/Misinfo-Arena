"""
Judge Report Component for Misinformation Arena v2

Displays the winner, confidence, reasoning, and detailed scorecard
from the completed debate evaluation. Styled to match the app-wide
dashboard design system.
"""

import pandas as pd
import streamlit as st


SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"

_METRIC_EXPLANATIONS = {
    "Factuality": (
        "How internally consistent and credible each side's argument appears. "
        "The spreader is scored on narrative plausibility; the debunker on "
        "grounding in verifiable, specific facts. (D2D, EMNLP 2025)"
    ),
    "Source Credibility": (
        "Quality and specificity of cited sources. Named institutions, specific "
        "statistics, and checkable claims score higher than vague appeals to "
        "authority like 'studies show.' (D2D, EMNLP 2025)"
    ),
    "Reasoning Quality": (
        "Logical structure and coherence. Does the argument follow from its "
        "premises? Both sides are judged on how well they construct and "
        "deconstruct logical chains. (Wachsmuth et al., 2017 — Cogency)"
    ),
    "Responsiveness": (
        "How directly each side engaged the strongest point in the opponent's "
        "previous message. Ignoring and pivoting scores low; reframing while "
        "acknowledging is valid. (Wachsmuth et al., 2017 — Reasonableness)"
    ),
    "Persuasion": (
        "Overall convincingness to an uncommitted reader scrolling past. Captures "
        "tone, narrative coherence, emotional resonance, and readability. "
        "This is the key dimension for the spreader. (Wachsmuth et al., 2017 — Effectiveness)"
    ),
    "Manipulation Awareness": (
        "For the spreader: penalizes reliance on manipulation tactics (fear, conspiracy "
        "framing, fake authority, identity pressure). For the debunker: rewards explicitly "
        "naming and exposing these techniques — inoculation. (Roozenbeek & van der Linden, 2022)"
    ),
}


def _confidence_label(conf: float) -> str:
    if conf >= 0.85: return "decisive"
    if conf >= 0.70: return "clear"
    if conf >= 0.55: return "moderate"
    if conf >= 0.40: return "narrow"
    return "coin-flip"


def _inject_report_css():
    st.markdown("""
    <style>
    .jr-section {
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.09em; color: #9ca3af;
        border-bottom: 1px solid rgba(0,0,0,0.08);
        padding-bottom: 0.3rem; margin: 1.4rem 0 0.75rem 0;
    }
    .jr-verdict-card {
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 12px; padding: 1.2rem 1.5rem;
        margin: 0.5rem 0 1.2rem 0; background: #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .jr-verdict-winner { border-left: 5px solid #888; }
    .jr-verdict-debunker { border-left-color: #3A7EC7; }
    .jr-verdict-spreader { border-left-color: #E8524A; }
    .jr-verdict-draw { border-left-color: #F0A500; }
    .jr-winner-text {
        font-size: 1.6rem; font-weight: 800; line-height: 1.2; margin-bottom: 0.3rem;
    }
    .jr-conf-text {
        font-size: 0.9rem; color: #555; margin-bottom: 0.6rem;
    }
    .jr-reason-box {
        background: rgba(0,0,0,0.025); border-radius: 8px;
        border: 1px solid rgba(0,0,0,0.06);
        padding: 0.8rem 1rem; font-size: 0.93rem;
        line-height: 1.6; color: #374151; margin-top: 0.6rem;
    }
    .jr-metric-grid {
        display: flex; gap: 0.8rem; margin: 0.8rem 0; flex-wrap: wrap;
    }
    .jr-metric-card {
        flex: 1; min-width: 100px;
        background: #fff; border: 1px solid #e5e7eb;
        border-radius: 8px; padding: 0.7rem 0.9rem;
        text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .jr-metric-label {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.06em; color: #9ca3af; margin-bottom: 0.15rem;
    }
    .jr-metric-value {
        font-size: 1.4rem; font-weight: 700; line-height: 1.1;
    }
    .jr-metric-sub { font-size: 0.72rem; color: #9ca3af; margin-top: 0.1rem; }
    </style>
    """, unsafe_allow_html=True)


def render_judge_report():
    """Render the judge report with styled verdict card and scorecard."""
    if not st.session_state.get("judge_report_visible", False):
        return
    if not st.session_state.get("match_completed", False):
        return

    _inject_report_css()

    decision = st.session_state.get("judge_decision")
    if decision is None:
        st.warning("Judge decision not available.")
        return

    judge_status = st.session_state.get("judge_status")
    if judge_status == "error":
        st.warning(
            "The AI judge encountered an error. Scores below are heuristic estimates."
        )

    # ── Verdict card ─────────────────────────────────────────────────────────
    winner = decision.winner
    conf = float(decision.confidence)
    conf_label = _confidence_label(conf)
    spreader_total = float(decision.totals.get("spreader", 0.0))
    debunker_total = float(decision.totals.get("debunker", 0.0))
    margin = abs(spreader_total - debunker_total)

    if winner == "debunker":
        winner_display = "Fact-checker wins"
        winner_color = DEBUNKER_COLOR
        verdict_class = "jr-verdict-debunker"
    elif winner == "spreader":
        winner_display = "Spreader wins"
        winner_color = SPREADER_COLOR
        verdict_class = "jr-verdict-spreader"
    else:
        winner_display = "Draw"
        winner_color = DRAW_COLOR
        verdict_class = "jr-verdict-draw"

    st.markdown(
        f'<div class="jr-verdict-card jr-verdict-winner {verdict_class}">'
        f'<div class="jr-winner-text" style="color:{winner_color}">{winner_display}</div>'
        f'<div class="jr-conf-text">'
        f'Confidence: <b>{conf:.0%}</b> ({conf_label}) · '
        f'Margin: <b>{margin:.1f} pts</b> · '
        f'Spreader {spreader_total:.1f} – Fact-checker {debunker_total:.1f}'
        f'</div>'
        f'<div class="jr-reason-box">{decision.reason}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Scorecard as metric cards ────────────────────────────────────────────
    st.markdown('<div class="jr-section">Scorecard</div>', unsafe_allow_html=True)

    cards_html = '<div class="jr-metric-grid">'
    for metric in decision.scorecard:
        category = metric.metric.replace("_", " ").title()
        s = float(metric.spreader)
        d = float(metric.debunker)
        delta = d - s
        if delta > 0.5:
            delta_color = "#16a34a"
            delta_label = f"FC +{delta:.1f}"
        elif delta < -0.5:
            delta_color = SPREADER_COLOR
            delta_label = f"Spr +{abs(delta):.1f}"
        else:
            delta_color = "#9ca3af"
            delta_label = "Even"

        cards_html += (
            f'<div class="jr-metric-card">'
            f'<div class="jr-metric-label">{category}</div>'
            f'<div class="jr-metric-value" style="color:{delta_color}">{delta_label}</div>'
            f'<div class="jr-metric-sub">Spr {s:.1f} · FC {d:.1f}</div>'
            f'</div>'
        )
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

    st.caption(
        "Scores are 0–10 per metric, role-relative. "
        "The spreader is scored on persuasive execution, not factual accuracy."
    )

    # ── Detailed table (expandable) ──────────────────────────────────────────
    with st.expander("Detailed scorecard table"):
        scorecard_data = []
        for metric in decision.scorecard:
            category = metric.metric.replace("_", " ").title()
            s_score = float(metric.spreader)
            d_score = float(metric.debunker)
            weight = float(metric.weight)
            scorecard_data.append({
                "Category":     category,
                "Weight":       f"{weight:.0%}",
                "Spreader":     f"{s_score:.1f}",
                "Fact-checker": f"{d_score:.1f}",
                "Delta":        f"{d_score - s_score:+.1f}",
            })
        df = pd.DataFrame(scorecard_data)

        def _color_delta(val):
            try:
                v = float(val)
            except (ValueError, TypeError):
                return ""
            if v > 0.5:
                return "color: #16a34a; font-weight: 600;"
            if v < -0.5:
                return "color: #dc2626; font-weight: 600;"
            return "color: #6b7280;"

        styled = df.style.map(_color_delta, subset=["Delta"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Metric explanations ──────────────────────────────────────────────────
    with st.expander("What do these metrics mean?"):
        for name, explanation in _METRIC_EXPLANATIONS.items():
            st.markdown(f"**{name}** — {explanation}")
        st.caption(
            "Scores are role-relative. The spreader is not penalised for promoting a "
            "contested claim — it is scored on how effectively it executes that role."
        )

    # ── Raw data ─────────────────────────────────────────────────────────────
    with st.expander("Raw evaluation data"):
        st.json({
            "winner":     decision.winner,
            "confidence": decision.confidence,
            "reason":     decision.reason,
            "totals":     decision.totals,
            "scorecard": [
                {"metric": s.metric, "spreader": s.spreader,
                 "debunker": s.debunker, "weight": s.weight}
                for s in decision.scorecard
            ],
        })
