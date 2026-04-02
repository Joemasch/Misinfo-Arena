"""
CSS for Episode Replay page — clean editorial style matching Analytics page.
"""

import streamlit as st

REPLAY_CSS = """
<style>
/* ── Page header ── */
.rp-page-title {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 0.25rem 0;
    line-height: 1.2;
}
.rp-page-subtitle {
    font-size: 1rem;
    color: #6b7280;
    margin: 0 0 1.5rem 0;
}

/* ── Claim banner ── */
.rp-claim-banner {
    border-left: 4px solid #3A7EC7;
    background: rgba(58, 126, 199, 0.06);
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1.1rem;
    margin: 0.75rem 0 0.5rem 0;
}
.rp-claim-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #3A7EC7;
    margin-bottom: 0.2rem;
}
.rp-claim-text {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.4;
}

/* ── Verdict card ── */
.rp-verdict-card {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin: 0.5rem 0 1rem 0;
    background: transparent;
}
.rp-verdict-winner-debunker {
    border-left: 5px solid #3A7EC7;
}
.rp-verdict-winner-spreader {
    border-left: 5px solid #E8524A;
}
.rp-verdict-winner-draw {
    border-left: 5px solid #F0A500;
}

/* ── Badges ── */
.ma-badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 6px;
    font-size: 0.88rem;
    font-weight: 600;
    margin-right: 0.4rem;
    margin-bottom: 0.3rem;
}
.ma-badge-winner {
    border: 1px solid rgba(34,139,34,0.6);
    color: #166534;
}
.ma-badge-spreader {
    border: 1px solid rgba(232,82,74,0.5);
    color: #c0392b;
    background: rgba(232,82,74,0.07);
}
.ma-badge-debunker {
    border: 1px solid rgba(58,126,199,0.5);
    color: #1a5fa8;
    background: rgba(58,126,199,0.07);
}
.ma-badge-draw {
    border: 1px solid rgba(240,165,0,0.5);
    color: #92650a;
    background: rgba(240,165,0,0.07);
}
.ma-badge-confidence {
    border: 1px solid rgba(59,130,246,0.4);
    color: #1d4ed8;
}
.ma-badge-trigger {
    border: 1px solid rgba(107,114,128,0.5);
    color: #374151;
}

/* ── Reason box ── */
.rp-reason-box {
    background: rgba(0,0,0,0.03);
    border-radius: 6px;
    border: 1px solid rgba(0,0,0,0.07);
    padding: 0.7rem 1rem;
    font-size: 0.97rem;
    line-height: 1.55;
    margin: 0.5rem 0 1rem 0;
    color: #374151;
}

/* ── Debate brief card (Summary tab) ── */
.rp-brief-card {
    background: rgba(0,0,0,0.02);
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1.2rem;
}
.rp-brief-section-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #9ca3af;
    margin: 0.9rem 0 0.3rem 0;
}
.rp-brief-section-label:first-child {
    margin-top: 0;
}
.rp-brief-value {
    font-size: 0.97rem;
    color: #1f2937;
    line-height: 1.5;
}
.rp-brief-bullet {
    font-size: 0.95rem;
    color: #374151;
    line-height: 1.6;
    padding-left: 0.2rem;
}

/* ── Summary prose container ── */
.rp-summary-prose {
    font-size: 0.97rem;
    line-height: 1.72;
    color: #374151;
    margin-top: 0.5rem;
}
.rp-summary-meta {
    font-size: 0.78rem;
    color: #9ca3af;
    margin-top: 0.75rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(0,0,0,0.08);
}

/* ── Transcript chat bubbles ── */
.rp-turn-header {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9ca3af;
    margin: 1.6rem 0 0.75rem 0;
}
.rp-turn-header:first-child {
    margin-top: 0;
}
.rp-bubble {
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.75rem;
    line-height: 1.65;
    font-size: 0.95rem;
    position: relative;
}
.rp-bubble-role {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.4rem;
}
.rp-bubble-spreader {
    background: rgba(232, 82, 74, 0.06);
    border-left: 3px solid #E8524A;
}
.rp-bubble-spreader .rp-bubble-role {
    color: #c0392b;
}
.rp-bubble-debunker {
    background: rgba(58, 126, 199, 0.06);
    border-left: 3px solid #3A7EC7;
}
.rp-bubble-debunker .rp-bubble-role {
    color: #1a5fa8;
}
.rp-bubble-body {
    color: #1f2937;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* ── Run overview / dividers ── */
.ma-replay-divider {
    height: 1px;
    background: rgba(128,128,128,0.2);
    margin: 1rem 0;
}
.ma-replay-note {
    font-size: 0.82rem;
    color: #9ca3af;
    margin-top: 0.4rem;
}

/* ── Section subheadings within tabs ── */
.rp-tab-section {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9ca3af;
    border-bottom: 1px solid rgba(0,0,0,0.08);
    padding-bottom: 0.3rem;
    margin: 1.4rem 0 0.75rem 0;
}
.rp-tab-section:first-child {
    margin-top: 0;
}
</style>
"""


def inject_replay_css() -> None:
    st.markdown(REPLAY_CSS, unsafe_allow_html=True)


def verdict_card_html(
    winner: str,
    confidence: "str | float | None",
    margin: "float | None",
    end_trigger: str,
    turns_str: str,
    top_drivers: "list[tuple[str, str]]",
) -> str:
    w = (winner or "").lower()
    if w == "debunker":
        badge_cls   = "ma-badge-debunker"
        card_cls    = "rp-verdict-winner-debunker"
        winner_disp = "Fact-checker"
    elif w == "spreader":
        badge_cls   = "ma-badge-spreader"
        card_cls    = "rp-verdict-winner-spreader"
        winner_disp = "Spreader"
    else:
        badge_cls   = "ma-badge-draw"
        card_cls    = "rp-verdict-winner-draw"
        winner_disp = "Draw"

    conf_pct = f"{float(confidence):.0%}" if isinstance(confidence, (int, float)) else (confidence or "—")
    margin_str = f"{margin:+.2f}" if margin is not None else "—"
    trigger_label = {
        "max_turns": "Reached max turns",
        "concession": "Concession",
        "concession_keyword": "Concession",
        "error": "Error",
    }.get((end_trigger or "").lower(), (end_trigger or "—").replace("_", " ").title())

    drivers_html = ""
    for metric, direction in top_drivers:
        color = "#1a5fa8" if "debunker" in direction else "#c0392b"
        arrow = "▲" if "debunker" in direction else "▼"
        drivers_html += (
            f'<li style="margin-bottom:0.2rem;">'
            f'<strong>{metric}</strong> '
            f'<span style="color:{color};font-size:0.88rem;">{arrow} {direction}</span>'
            f'</li>'
        )

    return f"""
    <div class="rp-verdict-card {card_cls}">
        <div style="margin-bottom:0.7rem;">
            <span class="ma-badge {badge_cls}">Winner: {winner_disp}</span>
            <span class="ma-badge ma-badge-confidence">Confidence: {conf_pct}</span>
            <span class="ma-badge ma-badge-trigger">{trigger_label} · {turns_str} turns</span>
        </div>
        <p style="margin:0.35rem 0;font-size:0.97rem;">
            <strong>Score margin:</strong> {margin_str}
            &nbsp;&nbsp;<span style="font-size:0.88rem;color:#6b7280;">(fact-checker total − spreader total)</span>
        </p>
        <p style="margin:0.5rem 0 0.25rem 0;font-size:0.9rem;font-weight:600;color:#374151;">Top decision drivers</p>
        <ul style="margin:0.2rem 0 0 1.1rem;padding:0;font-size:0.94rem;">{drivers_html or '<li>—</li>'}</ul>
    </div>
    """
