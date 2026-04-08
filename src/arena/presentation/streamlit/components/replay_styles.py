"""
CSS for Episode Replay page — clean editorial style matching Analytics page.
"""

import streamlit as st

REPLAY_CSS = """
<style>
/* ── Page header ── */
.rp-page-title {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-size: 2.6rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: var(--color-text-primary, #E8E4D9) !important;
    margin: 0 0 0.25rem 0 !important;
    line-height: 1.15 !important;
    text-align: center !important;
}
.rp-page-subtitle {
    font-size: 1rem;
    color: var(--color-text-muted, #888);
    margin: 0 0 1.5rem 0;
    text-align: center;
}

/* ── Claim banner ── */
.rp-claim-banner {
    border-left: 4px solid var(--color-accent-blue, #4A7FA5);
    background: rgba(74, 127, 165, 0.08);
    border-radius: 0 4px 4px 0;
    padding: 0.75rem 1.1rem;
    margin: 0.75rem 0 0.5rem 0;
}
.rp-claim-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-accent-blue, #4A7FA5);
    margin-bottom: 0.2rem;
}
.rp-claim-text {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--color-text-primary, #E8E4D9);
    line-height: 1.4;
}

/* ── Verdict card ── */
.rp-verdict-card {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin: 0.5rem 0 1rem 0;
    background: var(--color-surface, #111);
}
.rp-verdict-winner-debunker {
    border-left: 5px solid var(--color-accent-blue, #4A7FA5);
}
.rp-verdict-winner-spreader {
    border-left: 5px solid var(--color-accent-amber, #D4A843);
}
.rp-verdict-winner-draw {
    border-left: 5px solid var(--color-accent-amber, #D4A843);
}

/* ── Badges ── */
.ma-badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 4px;
    font-size: 0.88rem;
    font-weight: 600;
    font-family: 'IBM Plex Sans', sans-serif;
    margin-right: 0.4rem;
    margin-bottom: 0.3rem;
}
.ma-badge-winner {
    border: 1px solid rgba(76, 175, 125, 0.5);
    color: var(--color-accent-green, #4CAF7D);
}
.ma-badge-spreader {
    border: 1px solid rgba(212, 168, 67, 0.5);
    color: var(--color-accent-amber, #D4A843);
    background: rgba(212, 168, 67, 0.1);
}
.ma-badge-debunker {
    border: 1px solid rgba(74, 127, 165, 0.5);
    color: var(--color-accent-blue, #4A7FA5);
    background: rgba(74, 127, 165, 0.1);
}
.ma-badge-draw {
    border: 1px solid rgba(212, 168, 67, 0.5);
    color: var(--color-accent-amber, #D4A843);
    background: rgba(212, 168, 67, 0.1);
}
.ma-badge-confidence {
    border: 1px solid rgba(74, 127, 165, 0.4);
    color: var(--color-accent-blue, #4A7FA5);
}
.ma-badge-trigger {
    border: 1px solid var(--color-border, #2A2A2A);
    color: var(--color-text-muted, #888);
}

/* ── Reason box ── */
.rp-reason-box {
    background: var(--color-surface-alt, #1A1A1A);
    border-radius: 4px;
    border: 1px solid var(--color-border, #2A2A2A);
    padding: 0.7rem 1rem;
    font-size: 0.97rem;
    line-height: 1.55;
    margin: 0.5rem 0 1rem 0;
    color: var(--color-text-primary, #E8E4D9);
    font-style: italic;
}

/* ── Debate brief card (Summary tab) ── */
.rp-brief-card {
    background: var(--color-surface, #111);
    border: 1px solid var(--color-border, #2A2A2A);
    border-radius: 4px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1.2rem;
}
.rp-brief-section-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--color-text-muted, #888);
    margin: 0.9rem 0 0.3rem 0;
}
.rp-brief-section-label:first-child {
    margin-top: 0;
}
.rp-brief-value {
    font-size: 0.97rem;
    color: var(--color-text-primary, #E8E4D9);
    line-height: 1.5;
}
.rp-brief-bullet {
    font-size: 0.95rem;
    color: var(--color-text-primary, #E8E4D9);
    line-height: 1.6;
    padding-left: 0.2rem;
}

/* ── Summary prose container ── */
.rp-summary-prose {
    font-size: 0.97rem;
    line-height: 1.72;
    color: var(--color-text-primary, #E8E4D9);
    margin-top: 0.5rem;
}
.rp-summary-meta {
    font-size: 0.78rem;
    color: var(--color-text-muted, #888);
    margin-top: 0.75rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border, #2A2A2A);
}

/* ── Transcript chat bubbles ── */
.rp-turn-header {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted, #888);
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
    background: rgba(212, 168, 67, 0.08);
    border-left: 3px solid var(--color-accent-amber, #D4A843);
}
.rp-bubble-spreader .rp-bubble-role {
    color: var(--color-accent-amber, #D4A843);
}
.rp-bubble-debunker {
    background: rgba(74, 127, 165, 0.08);
    border-left: 3px solid var(--color-accent-blue, #4A7FA5);
}
.rp-bubble-debunker .rp-bubble-role {
    color: var(--color-accent-blue, #4A7FA5);
}
.rp-bubble-body {
    color: var(--color-text-primary, #E8E4D9);
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* ── Run overview / dividers ── */
.ma-replay-divider {
    height: 1px;
    background: var(--color-border, #2A2A2A);
    margin: 1rem 0;
}
.ma-replay-note {
    font-size: 0.82rem;
    color: var(--color-text-muted, #888);
    margin-top: 0.4rem;
}

/* ── Section subheadings within tabs ── */
.rp-tab-section {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted, #888);
    border-bottom: 1px solid var(--color-border, #2A2A2A);
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
        color = "#4A7FA5" if "debunker" in direction else "#D4A843"
        arrow = "▲" if "debunker" in direction else "▼"
        drivers_html += (
            f'<li style="margin-bottom:0.2rem;color:#E8E4D9;">'
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
        <p style="margin:0.35rem 0;font-size:0.97rem;color:#E8E4D9;">
            <strong>Score margin:</strong> {margin_str}
            &nbsp;&nbsp;<span style="font-size:0.88rem;color:#888;">(fact-checker total - spreader total)</span>
        </p>
        <p style="margin:0.5rem 0 0.25rem 0;font-size:0.9rem;font-weight:600;color:#E8E4D9;">Top decision drivers</p>
        <ul style="margin:0.2rem 0 0 1.1rem;padding:0;font-size:0.94rem;">{drivers_html or '<li style="color:#888;">---</li>'}</ul>
    </div>
    """
