"""
Judge Report Component for Misinformation Arena v2

Displays the winner, confidence, reasoning, and detailed scorecard
from the completed debate evaluation. Styled to match the app-wide
dashboard design system.
"""

import pandas as pd
import streamlit as st


SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"
DRAW_COLOR     = "#D4A843"

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


_HEDGE_PATTERN = None


def _count_hedges(text: str) -> int:
    """Count hedge markers in a message. Lazy-compiled regex."""
    global _HEDGE_PATTERN
    if _HEDGE_PATTERN is None:
        import re
        _HEDGE_PATTERN = re.compile(
            r'\b(some|may|could|might|suggests?|potentially|arguably|questionable|'
            r'concerns?|likely|possibly|appears? to|seems? to)\b',
            re.IGNORECASE,
        )
    if not text:
        return 0
    return len(_HEDGE_PATTERN.findall(text))


def _build_verdict_explainer(decision, winner: str) -> str:
    """
    Plain-English explanation of WHY this verdict happened, anchored in the
    research findings:
      F1 — Falsifiability of the claim (95% vs 53% debunker win rate)
      F4 — Hedge ratio between sides (spreaders hedge 2.4× more)
      F5 — Tactic diversity (deepening one argument beats pivoting)

    Returns an HTML block. Empty string if nothing useful can be said.
    """
    bullets = []

    # F1: Falsifiability of the claim
    claim_text = (st.session_state.get("claim_text") or "").strip()
    if claim_text:
        try:
            from arena.claim_metadata import classify_falsifiability
            fals, _src = classify_falsifiability(claim_text)
            if fals == "falsifiable":
                bullets.append(
                    '<li><b>The claim is falsifiable.</b> Empirical evidence can settle it. '
                    'Across 960 prior debates in our research, the fact-checker won '
                    '<b>95% of falsifiable claims</b> — the side with evidence usually prevails.</li>'
                )
            elif fals == "unfalsifiable":
                bullets.append(
                    '<li><b>The claim is unfalsifiable.</b> No evidence can fully settle it — '
                    'it appeals to hidden intent, secret control, or unobservable agents. '
                    'These debates split closer to <b>53% / 47%</b>, and the spreader has '
                    'much more room to maneuver than on factual claims.</li>'
                )
        except Exception:
            pass

    # F4: Hedge ratio between sides
    transcript = (
        st.session_state.get("episode_transcript")
        or st.session_state.get("debate_messages")
        or st.session_state.get("messages")
        or []
    )
    s_hedges, d_hedges = 0, 0
    s_words, d_words = 0, 0
    for msg in transcript:
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or msg.get("name") or "").lower()
        content = msg.get("content") or ""
        if "spread" in role:
            s_hedges += _count_hedges(content)
            s_words += len(content.split())
        elif "debunk" in role or "fact" in role:
            d_hedges += _count_hedges(content)
            d_words += len(content.split())

    if s_hedges + d_hedges >= 4 and s_words > 0 and d_words > 0:
        s_rate = s_hedges / max(s_words, 1) * 1000
        d_rate = d_hedges / max(d_words, 1) * 1000
        if s_rate > d_rate * 1.5:
            ratio = s_rate / max(d_rate, 0.1)
            bullets.append(
                f'<li><b>The spreader hedged {ratio:.1f}× more than the fact-checker.</b> '
                f'({s_hedges} vs {d_hedges} hedge markers like "some," "may," "suggests.") '
                f'Hedging weakens citations — in our research it predicts losing more '
                f'reliably than how many sources are cited.</li>'
            )
        elif d_rate > s_rate * 1.5:
            ratio = d_rate / max(s_rate, 0.1)
            bullets.append(
                f'<li><b>The fact-checker hedged {ratio:.1f}× more than the spreader.</b> '
                f'({d_hedges} vs {s_hedges} hedge markers.) Unusual — the spreader '
                f'projected more certainty than the debunker, which often signals overreach '
                f'but can also indicate a confident misinformation play.</li>'
            )

    # F5: Tactic diversity (proxy for deepening vs pivoting)
    sa = st.session_state.get("strategy_analysis") or {}
    if isinstance(sa, dict):
        s_strats = sa.get("spreader_strategies") or []
        d_strats = sa.get("debunker_strategies") or []
        s_uniq = len({str(x).lower() for x in s_strats if x})
        d_uniq = len({str(x).lower() for x in d_strats if x})
        if s_uniq >= 2 or d_uniq >= 2:
            if winner == "debunker" and d_uniq < s_uniq:
                bullets.append(
                    f'<li><b>The fact-checker deepened one line of reasoning ({d_uniq} '
                    f'distinct tactics) while the spreader cycled through {s_uniq}.</b> '
                    f'The winning side is usually the one that commits to a single coherent '
                    f'argument and reinforces it across challenges '
                    f'(adaptability r = 0.753 in our study).</li>'
                )
            elif winner == "spreader" and s_uniq < d_uniq:
                bullets.append(
                    f'<li><b>The spreader stayed with {s_uniq} core tactic(s) while the '
                    f'fact-checker cycled through {d_uniq}.</b> The spreader won by '
                    f'deepening one argument rather than scattering responses '
                    f'(adaptability r = 0.753 in our study).</li>'
                )

    if not bullets:
        return ""

    return (
        '<div style="background:var(--color-surface-alt,#1A1A1A);'
        'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
        'padding:0.9rem 1.1rem;margin:0.4rem 0 1.2rem 0;">'
        '<ul style="margin:0;padding-left:1.2rem;color:var(--color-text-primary,#E8E4D9);'
        'font-size:0.92rem;line-height:1.55;">'
        + "".join(bullets) +
        '</ul>'
        '<div style="font-size:0.72rem;color:#6b7280;margin-top:0.5rem;font-style:italic;">'
        'Explanations draw on findings from our 960-episode research study. '
        'See the Findings tab for the full results.</div>'
        '</div>'
    )


def _inject_report_css():
    st.markdown("""
    <style>
    .jr-section {
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.09em; color: var(--color-text-muted, #888);
        border-bottom: 1px solid var(--color-border, #2A2A2A);
        padding-bottom: 0.3rem; margin: 1.4rem 0 0.75rem 0;
    }
    .jr-verdict-card {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 10px; padding: 1.2rem 1.5rem;
        margin: 0.5rem 0 1.2rem 0; background: var(--color-surface, #111);
    }
    .jr-verdict-winner { border-left: 5px solid #888; }
    .jr-verdict-debunker { border-left-color: var(--color-accent-blue, #4A7FA5); }
    .jr-verdict-spreader { border-left-color: var(--color-accent-amber, #D4A843); }
    .jr-verdict-draw { border-left-color: var(--color-accent-amber, #D4A843); }
    .jr-winner-text {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.6rem; font-weight: 700; line-height: 1.2; margin-bottom: 0.3rem;
        color: var(--color-text-primary, #E8E4D9);
    }
    .jr-conf-text {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem; color: var(--color-text-muted, #888); margin-bottom: 0.6rem;
    }
    .jr-reason-box {
        background: var(--color-surface-alt, #1A1A1A); border-radius: 4px;
        border: 1px solid var(--color-border, #2A2A2A);
        padding: 0.8rem 1rem; font-size: 0.93rem;
        line-height: 1.6; color: var(--color-text-primary, #E8E4D9);
        font-style: italic; margin-top: 0.6rem;
    }
    .jr-metric-grid {
        display: flex; gap: 0.8rem; margin: 0.8rem 0; flex-wrap: wrap;
    }
    .jr-metric-card {
        flex: 1; min-width: 100px;
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 4px; padding: 0.7rem 0.9rem;
        text-align: center;
    }
    .jr-metric-label {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--color-text-muted, #888); margin-bottom: 0.15rem;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .jr-metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.4rem; font-weight: 700; line-height: 1.1;
    }
    .jr-metric-sub { font-size: 0.72rem; color: var(--color-text-muted, #888); margin-top: 0.1rem; }
    </style>
    """, unsafe_allow_html=True)


def _count_episodes_for_claim(claim_text: str) -> int:
    """Count existing stored episodes that share this claim text. Best-effort."""
    if not claim_text:
        return 0
    try:
        from pathlib import Path
        import json
        count = 0
        runs_dir = Path("runs")
        if not runs_dir.exists():
            return 0
        target = claim_text.strip().lower()
        for d in runs_dir.iterdir():
            if not d.is_dir():
                continue
            ep_path = d / "episodes.jsonl"
            if not ep_path.exists():
                continue
            try:
                with open(ep_path) as f:
                    for line in f:
                        try:
                            ep = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if (ep.get("claim") or "").strip().lower() == target:
                            count += 1
            except OSError:
                continue
        return count
    except Exception:
        return 0


def _render_smart_nudges():
    """
    Show 1–2 context-aware suggestions for what to try next.

    Rules:
      - After a falsifiable claim: suggest trying an unfalsifiable claim
        (lets the user feel F1 firsthand).
      - After an unfalsifiable claim: suggest trying a falsifiable claim.
      - If ≥2 prior runs exist on this claim: suggest the Compare tab.
    """
    claim_text = (st.session_state.get("claim_text") or "").strip()
    if not claim_text:
        return

    # Falsifiability for this claim
    try:
        from arena.claim_metadata import classify_falsifiability, SUGGESTED_CLAIMS
        fals, _src = classify_falsifiability(claim_text)
    except Exception:
        fals, _src = ("unknown", "unknown")
        SUGGESTED_CLAIMS = []

    nudges = []

    # 1) Compare nudge (if user has stacked up multiple runs)
    ep_count = _count_episodes_for_claim(claim_text)
    if ep_count >= 2:
        nudges.append({
            "headline": "You have multiple runs on this claim",
            "body": f"Compare them side-by-side to see how different model pairs argued it.",
            "cta_label": f"Compare {ep_count} runs in Explore tab",
            "action": "explore_compare",
        })

    # 2) Try a different falsifiability class
    if fals == "falsifiable":
        alt = next((c for c in SUGGESTED_CLAIMS if c.get("kind") == "unfalsifiable"), None)
        if alt:
            nudges.append({
                "headline": "Try an unfalsifiable claim",
                "body": (
                    "On falsifiable claims, evidence usually wins. "
                    "Unfalsifiable claims are much more contested (~53% / 47%). "
                    f"Try: \"{alt['text']}\""
                ),
                "cta_label": f"Load: {alt['text'][:40]}",
                "action": "load_claim",
                "payload": alt["text"],
            })
    elif fals == "unfalsifiable":
        alt = next((c for c in SUGGESTED_CLAIMS if c.get("kind") == "falsifiable"), None)
        if alt:
            nudges.append({
                "headline": "Try a falsifiable claim",
                "body": (
                    "Unfalsifiable claims are contested. Falsifiable ones tilt much "
                    "harder toward the fact-checker (~95%). "
                    f"Try: \"{alt['text']}\""
                ),
                "cta_label": f"Load: {alt['text'][:40]}",
                "action": "load_claim",
                "payload": alt["text"],
            })

    nudges = nudges[:2]
    if not nudges:
        return

    st.markdown('<div class="jr-section">What to try next</div>', unsafe_allow_html=True)
    cols = st.columns(len(nudges))
    for col, n in zip(cols, nudges):
        with col:
            st.markdown(
                f'<div style="background:var(--color-surface-alt,#1A1A1A);'
                f'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
                f'padding:0.7rem 0.9rem;margin-bottom:0.4rem;height:100%;">'
                f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;'
                f'color:#9ca3af;font-weight:700;margin-bottom:0.3rem;">{n["headline"]}</div>'
                f'<div style="font-size:0.86rem;color:var(--color-text-primary,#E8E4D9);'
                f'line-height:1.5;margin-bottom:0.6rem;">{n["body"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Action button
            btn_key = f"nudge_{n['action']}_{hash(n['cta_label']) & 0xFFFF}"
            if st.button(n["cta_label"], key=btn_key, use_container_width=True):
                if n["action"] == "load_claim":
                    st.session_state["claim_text"] = n["payload"]
                    # Reset debate state so the new claim starts fresh
                    for k in (
                        "judge_report_visible", "match_completed", "judge_decision",
                        "episode_transcript", "debate_messages", "strategy_analysis",
                    ):
                        st.session_state.pop(k, None)
                    st.rerun()
                elif n["action"] == "explore_compare":
                    st.session_state["nav_to_explore"] = True
                    st.rerun()


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

    # ── How this compares to the study (result vs. baseline) ─────────────────
    try:
        from arena.presentation.streamlit.components.arena.baseline_panels import (
            render_result_vs_baseline,
        )
        _claim_for_baseline = (st.session_state.get("claim_text") or "").strip()
        render_result_vs_baseline(_claim_for_baseline, winner, margin)
    except Exception:
        pass

    # ── "Why this verdict?" — research-anchored explainer (F1/F4/F5) ─────────
    _why_html = _build_verdict_explainer(decision, winner)
    if _why_html:
        st.markdown('<div class="jr-section">Why this verdict?</div>', unsafe_allow_html=True)
        st.markdown(_why_html, unsafe_allow_html=True)

    # ── "What to try next" — context-aware nudges ────────────────────────────
    _render_smart_nudges()

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
