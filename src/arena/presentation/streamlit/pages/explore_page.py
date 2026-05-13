"""
Replay Page — per-episode viewer with verdict, transcript download,
strategy analysis, citation analysis, and episode comparison.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

import pandas as pd
import streamlit as st

from arena.io.run_store_v2_read import load_episodes
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.components.replay_styles import inject_replay_css, verdict_card_html
from arena.presentation.streamlit.data.definitions import (
    get_institution_info,
    resolve_strategy_description,
)

RUNS_DIR = "runs"
SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"

_MODEL_SHORT = {
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4-20250514": "Claude Sonnet",
    "claude-sonnet-4": "Claude Sonnet",
    "gemini-2.5-flash": "Gemini Flash",
    "gemini-2.5-flash-lite-preview-06-17": "Gemini Flash",
}

_NAMED_SOURCES = [
    "CDC", "WHO", "FDA", "EPA", "NASA", "NIH", "IPCC",
    "Harvard", "Stanford", "MIT", "Oxford", "Yale", "Cambridge",
    "Nature", "Lancet", "Science", "JAMA", "BMJ", "NEJM",
    "Pew Research", "Gallup", "Reuters", "AP News", "BBC",
    "Federal Reserve", "World Bank", "IMF", "Congressional Budget Office",
    "Amnesty International", "Human Rights Watch", "United Nations",
    "World Health Organization",
]

# Per-source compiled patterns — word-bounded, case-sensitive so we don't
# match "mit" inside "limit", "who" inside "who said", or "nature" inside
# "human nature." Institution names are conventionally capitalized in text.
_SOURCE_PATTERNS = {
    src: re.compile(r'\b' + re.escape(src) + r'\b')
    for src in _NAMED_SOURCES
}

# Aliases that point at the same institution under a different name. The raw
# regex list keeps both forms so we can still detect a sentence using either,
# but everywhere downstream we funnel matches through _canonical_source() so
# they aggregate into a single entry rather than appearing as two.
_SOURCE_ALIASES = {
    "World Health Organization": "WHO",
    "Associated Press":           "AP News",
}


def _canonical_source(src: str) -> str:
    """Map a citation alias to its canonical name (no-op if already canonical)."""
    return _SOURCE_ALIASES.get(src, src)


def _patterns_for_canonical(canonical: str) -> list:
    """Return the compiled patterns covering a canonical source + its aliases.

    Used when searching for a citation by its canonical name — we need to
    match both \"WHO\" and \"World Health Organization\" against text.
    """
    pats = []
    p = _SOURCE_PATTERNS.get(canonical)
    if p is not None:
        pats.append(p)
    for alias, can in _SOURCE_ALIASES.items():
        if can == canonical:
            pa = _SOURCE_PATTERNS.get(alias)
            if pa is not None and pa not in pats:
                pats.append(pa)
    return pats


def _source_appears_in(src: str, text: str) -> bool:
    """Word-bounded, case-sensitive check for a source mention."""
    pat = _SOURCE_PATTERNS.get(src)
    if pat is None:
        return False
    return bool(pat.search(text))

_HEDGING = re.compile(
    r'\b(some|may|could|might|suggests?|potentially|arguably|questionable|concerns?)\b',
    re.IGNORECASE,
)
_DEFINITIVE = re.compile(
    r'\b(clearly|conclusively|definitively|proven|established|confirms?|demonstrates?|shows that|evidence shows)\b',
    re.IGNORECASE,
)
_CONSPIRATORIAL = re.compile(
    r'\b(hidden|secret|cover.up|suppress|manipulat|exploit|scam|corrupt|rigged)\b',
    re.IGNORECASE,
)


def _short(model: str) -> str:
    return _MODEL_SHORT.get(model, model[:20])


# Plain-English translations for opaque strategy labels.
# The original (academic) labels are kept as tooltips so power users can
# still see them, but casual users see human-readable versions.
_LABEL_PLAIN = {
    "appeal to (dis)trust":    "Attacks Credibility",
    "appeal to distrust":      "Attacks Credibility",
    "appeal to emotion":       "Emotional Appeal",
    "anecdotal evidence":      "Personal Stories",
    "pseudo-scientific claim": "Pseudo-Science",
    "source weaponization":    "Misused Sources",
    "conspiracy theory":       "Conspiracy Framing",
    "historical revisionism":  "Rewrites History",
    "cherry picking":          "Selective Evidence",
    "impossible expectations": "Impossible Standards",
    "evidence citation":       "Cites Research",
    "scientific consensus":    "Cites Consensus",
    "logical refutation":      "Logical Counter",
    "contextual analysis":     "Adds Nuance",
    "mechanism explanation":   "Explains How It Works",
    "technical correction":    "Corrects Data",
    "verification":            "Demands Verification",
    "public safety":           "Safety Appeal",
}


def _label(s: str) -> str:
    """Pretty-print a raw strategy label. Title-case fallback."""
    return (s or "").replace("_", " ").title()


def _label_plain(s: str) -> str:
    """Translate a raw strategy label to a casual-friendly phrase.

    Falls back to the title-case version if no translation exists.
    """
    if not s:
        return ""
    key = s.lower().replace("_", " ").strip()
    return _LABEL_PLAIN.get(key, _label(s))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_all_episodes(run_ids: tuple, runs_dir: str, token: float) -> list[dict]:
    episodes = []
    for run_id in run_ids:
        eps, _ = load_episodes(run_id, runs_dir, token)
        for ep in eps:
            if ep.get("results", {}).get("winner") == "error":
                continue
            episodes.append(ep)
    return episodes


def _normalize_turn_pairs(ep: dict) -> list[dict]:
    """Convert episode turns to normalized pair format."""
    turns = ep.get("turns") or []
    pairs = []
    for i, t in enumerate(turns):
        if "spreader_message" in t or "debunker_message" in t:
            sm = t.get("spreader_message") or {}
            dm = t.get("debunker_message") or {}
            pairs.append({
                "pair_idx": t.get("turn_index", i) + 1,
                "spreader_text": sm.get("content", "") if isinstance(sm, dict) else "",
                "debunker_text": dm.get("content", "") if isinstance(dm, dict) else "",
            })
        elif isinstance(t, dict) and "content" in t:
            role = t.get("role") or t.get("name", "")
            idx = t.get("turn_index", i // 2) + 1
            if "spread" in role.lower():
                pairs.append({"pair_idx": idx, "spreader_text": t["content"], "debunker_text": ""})
            elif "debunk" in role.lower() or "fact" in role.lower():
                if not pairs:
                    pairs.append({"pair_idx": idx, "spreader_text": "", "debunker_text": ""})
                pairs[-1]["debunker_text"] = t["content"]
    return pairs


def _get_all_text(ep: dict, role: str) -> list[str]:
    """Extract all text segments for a given role from the episode."""
    pairs = _normalize_turn_pairs(ep)
    key = "spreader_text" if role == "spreader" else "debunker_text"
    return [p[key] for p in pairs if p.get(key, "").strip()]


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _inject_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;800&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500;700&display=swap');

    .rp-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.2rem; font-weight: 700; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0;
    }
    .rp-subtitle {
        font-size: 0.95rem; color: var(--color-text-muted, #888);
        margin: 0 0 1.5rem 0; line-height: 1.5;
    }
    .rp-detail-header {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.3rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin: 1.5rem 0 0.5rem 0; padding-bottom: 0.3rem;
        border-bottom: 3px solid var(--color-accent-red, #C9363E);
    }
    .rp-claim-box {
        background: var(--color-surface, #111);
        border-left: 4px solid var(--color-accent-red, #C9363E);
        border-radius: 0 8px 8px 0;
        padding: 0.6rem 1rem; margin-bottom: 1rem;
        font-size: 0.95rem; color: var(--color-text-primary, #E8E4D9);
    }
    .rp-section-label {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em;
        color: #9ca3af; margin: 1.5rem 0 0.4rem 0;
    }
    .rp-stat-row {
        display: flex; gap: 0.8rem; flex-wrap: wrap; margin: 0.5rem 0 1rem 0;
    }
    .rp-stat {
        background: var(--color-surface, #111);
        border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.6rem 1rem; flex: 1; min-width: 120px;
    }
    .rp-stat-label {
        font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.07em; color: #9ca3af;
    }
    .rp-stat-val {
        font-size: 1.1rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
    }
    .rp-strat-card {
        background: var(--color-surface, #111);
        border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    }
    .rp-strat-name {
        font-size: 1rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
    }
    .rp-strat-raw {
        font-size: 0.72rem; color: #6b7280; font-family: 'IBM Plex Mono', monospace;
        margin-top: 0.05rem;
    }
    .rp-strat-desc {
        font-size: 0.85rem; color: #9ca3af; line-height: 1.5; margin-top: 0.2rem;
    }
    .rp-cite-bar {
        display: flex; height: 12px; border-radius: 6px; overflow: hidden; margin: 0.3rem 0;
    }
    .rp-framing-row {
        display: flex; gap: 0.5rem; margin: 0.3rem 0;
    }
    .rp-framing-tag {
        font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 12px;
        font-weight: 600;
    }
    .rp-compare-vs {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.1rem; font-weight: 700;
        text-align: center; color: var(--color-text-muted, #888);
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Verdict renderer
# ---------------------------------------------------------------------------

def _render_verdict(ep):
    results = ep.get("results") or {}
    config = ep.get("config_snapshot") or {}
    totals = results.get("totals") or {}
    scorecard = results.get("scorecard") or []

    winner = results.get("winner", "?")
    confidence = results.get("judge_confidence")
    margin = (totals.get("debunker", 0) or 0) - (totals.get("spreader", 0) or 0)
    turns_completed = results.get("completed_turn_pairs")
    planned = config.get("planned_max_turns")
    turns_str = f"{turns_completed}/{planned}" if turns_completed and planned else "—"

    top_drivers = []
    if scorecard:
        sorted_sc = sorted(scorecard, key=lambda s: abs(s.get("debunker", 0) - s.get("spreader", 0)), reverse=True)
        for s in sorted_sc[:3]:
            delta = s.get("debunker", 0) - s.get("spreader", 0)
            direction = "benefits fact-checker" if delta > 0 else "benefits spreader"
            top_drivers.append((_label(s.get("metric", "")), direction))

    card_html = verdict_card_html(
        winner=winner.title(),
        confidence=confidence,
        margin=margin,
        end_trigger="Max turns",
        turns_str=turns_str,
        top_drivers=top_drivers,
    )
    st.markdown(card_html, unsafe_allow_html=True)

    reason = results.get("reason", "")
    if reason:
        st.markdown(
            f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
            f'border-radius:8px;padding:0.8rem 1rem;margin:0.8rem 0;font-size:0.9rem;'
            f'color:var(--color-text-muted,#888);line-height:1.6;font-style:italic">'
            f'<b>Judge\'s reasoning:</b> {reason}</div>',
            unsafe_allow_html=True,
        )

    # ── How this compares to the study (result vs. baseline) ─────────────────
    try:
        from arena.presentation.streamlit.components.arena.baseline_panels import (
            render_result_vs_baseline,
        )
        render_result_vs_baseline(
            ep.get("claim", ""),
            (winner or "").lower(),
            abs(margin),
        )
    except Exception:
        pass

    if scorecard:
        st.markdown('<div class="rp-section-label">Score breakdown</div>', unsafe_allow_html=True)
        sorted_sc = sorted(scorecard, key=lambda x: abs(x.get("debunker", 0) - x.get("spreader", 0)), reverse=True)
        rows_html = ""
        for s in sorted_sc:
            dim = _label(s.get("metric", ""))
            spr_score = s.get("spreader", 0)
            deb_score = s.get("debunker", 0)
            delta = deb_score - spr_score
            adv_color = DEBUNKER_COLOR if delta > 0 else SPREADER_COLOR if delta < 0 else "#888"
            adv_label = f"{'FC' if delta > 0 else 'Spr'} +{abs(delta):.1f}" if delta != 0 else "Even"
            # Bar visualization
            spr_pct = spr_score / 10 * 100
            deb_pct = deb_score / 10 * 100
            rows_html += (
                f'<tr>'
                f'<td style="padding:0.5rem 0.8rem;font-weight:600;color:#E8E4D9;border-bottom:1px solid #2A2A4A">{dim}</td>'
                f'<td style="padding:0.5rem 0.8rem;border-bottom:1px solid #2A2A4A">'
                f'<div style="display:flex;align-items:center;gap:0.5rem">'
                f'<div style="flex:1;height:6px;background:#1A1A2E;border-radius:3px;overflow:hidden">'
                f'<div style="width:{spr_pct}%;height:100%;background:{SPREADER_COLOR};border-radius:3px"></div></div>'
                f'<span style="color:{SPREADER_COLOR};font-weight:700;min-width:2rem;text-align:right">{spr_score:.1f}</span></div></td>'
                f'<td style="padding:0.5rem 0.8rem;border-bottom:1px solid #2A2A4A">'
                f'<div style="display:flex;align-items:center;gap:0.5rem">'
                f'<div style="flex:1;height:6px;background:#1A1A2E;border-radius:3px;overflow:hidden">'
                f'<div style="width:{deb_pct}%;height:100%;background:{DEBUNKER_COLOR};border-radius:3px"></div></div>'
                f'<span style="color:{DEBUNKER_COLOR};font-weight:700;min-width:2rem;text-align:right">{deb_score:.1f}</span></div></td>'
                f'<td style="padding:0.5rem 0.8rem;color:{adv_color};font-weight:700;border-bottom:1px solid #2A2A4A;text-align:center">{adv_label}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);border-radius:8px;overflow:hidden">'
            f'<thead><tr style="background:#16213E">'
            f'<th style="padding:0.5rem 0.8rem;text-align:left;color:#9ca3af;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Dimension</th>'
            f'<th style="padding:0.5rem 0.8rem;text-align:left;color:{SPREADER_COLOR};font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Spreader</th>'
            f'<th style="padding:0.5rem 0.8rem;text-align:left;color:{DEBUNKER_COLOR};font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Fact-checker</th>'
            f'<th style="padding:0.5rem 0.8rem;text-align:center;color:#9ca3af;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Advantage</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Transcript renderer (download only)
# ---------------------------------------------------------------------------

def _render_transcript(ep):
    pairs = _normalize_turn_pairs(ep)
    planned = (ep.get("config_snapshot") or {}).get("planned_max_turns") or len(pairs)
    pts = ep.get("per_turn_strategies") or []

    if not pairs:
        st.info("No transcript data for this episode.")
        return

    claim = ep.get("claim", "Unknown")
    cfg = ep.get("config_snapshot", {})
    agents = cfg.get("agents", {})
    spr_model = agents.get("spreader", {}).get("model", "unknown")
    deb_model = agents.get("debunker", {}).get("model", "unknown")
    winner = ep.get("results", {}).get("winner", "unknown")
    reason = ep.get("results", {}).get("reason", "")

    # Build annotated transcript with strategy labels
    lines = [
        "MISINFORMATION ARENA — ANNOTATED DEBATE TRANSCRIPT",
        "=" * 55,
        f"Claim: {claim}",
        f"Spreader: {spr_model}",
        f"Fact-checker: {deb_model}",
        f"Winner: {winner.title()}",
        f"Reason: {reason}",
        f"Turns: {len(pairs)}/{planned}",
        "=" * 55, "",
    ]
    for i, p in enumerate(pairs):
        turn_num = p.get("pair_idx", "?")
        lines.append(f"--- Turn {turn_num} of {planned} ---\n")

        # Get strategy labels for this turn if available
        spr_strats_str = ""
        deb_strats_str = ""
        if i < len(pts):
            spr_strats = pts[i].get("spreader_strategies", [])
            deb_strats = pts[i].get("debunker_strategies", [])
            if spr_strats:
                spr_strats_str = f"  [Strategy: {', '.join(spr_strats)}]"
            if deb_strats:
                deb_strats_str = f"  [Strategy: {', '.join(deb_strats)}]"

        if p.get("spreader_text", "").strip():
            lines.append(f"[SPREADER]{spr_strats_str}\n{p['spreader_text'].strip()}\n")
        if p.get("debunker_text", "").strip():
            lines.append(f"[FACT-CHECKER]{deb_strats_str}\n{p['debunker_text'].strip()}\n")

    transcript_text = "\n".join(lines)

    st.download_button(
        label=f"Download Annotated Transcript ({len(pairs)} turns)",
        data=transcript_text,
        file_name=f"transcript_{ep.get('run_id', 'unknown')}_{ep.get('episode_id', 0)}.txt",
        mime="text/plain",
    )

    st.caption(f"{len(pairs)} turn pairs between {_short(spr_model)} and {_short(deb_model)}. "
               f"Strategy labels are embedded in the download.")


# ---------------------------------------------------------------------------
# Strategy renderer (enhanced)
# ---------------------------------------------------------------------------

_STRATEGY_CONTEXT = {
    "appeal to (dis)trust": (
        "Undermines the credibility of institutions, experts, or sources rather than "
        "engaging with the claims they make. The implicit logic is \"you can't trust "
        "the messenger, so you can ignore the message.\" Claude's signature spreader "
        "tactic on unfalsifiable claims."
    ),
    "anecdotal evidence": (
        "Uses individual stories or single examples as evidence for a general claim, "
        "in place of systematic data or population-level statistics. The vividness "
        "substitutes for representativeness. GPT-4o-mini's default tactic on Health claims."
    ),
    "pseudo-scientific claim": (
        "Presents non-scientific or unsupported claims using scientific-sounding "
        "terminology, technical formatting, or surface markers of expertise — without "
        "the underlying methodology or peer review. Gemini's signature spreader tactic."
    ),
    "source weaponization": (
        "Cites real, credible institutions but misrepresents what they actually said — "
        "selective excerpting, authority transfer, or scope manipulation. Rises sharply "
        "on unfalsifiable claims."
    ),
    "conspiracy theory": (
        "Frames a pattern as the deliberate, coordinated action of a hidden powerful "
        "group. Self-sealing: counter-evidence becomes proof of the cover-up. Triggers "
        "when debunkers demand verification."
    ),
    "historical revisionism": (
        "Reinterprets, downplays, or denies established historical events to support a "
        "present-day claim. Dominant Environmental spreader tactic."
    ),
    "appeal to emotion": (
        "Uses fear, alarm, outrage, sympathy, or moral urgency to drive belief — "
        "displacing reason and evidence with affect. Dominant on Political and Technology claims."
    ),
    "cherry picking": (
        "Presents only the data or sources that support a position while ignoring "
        "contradicting evidence that is equally available."
    ),
    "impossible expectations": (
        "Sets a standard of proof that no realistic evidence could meet, then dismisses "
        "existing evidence for failing it. \"You can't prove X with 100% certainty.\""
    ),
    "evidence citation": (
        "Supports a claim by referring to specific, named studies, datasets, or "
        "peer-reviewed publications the audience could verify. The universal debunker "
        "tactic on falsifiable claims."
    ),
    "scientific consensus": (
        "Appeals to established agreement among qualified experts or major scientific "
        "bodies. Drops to ~0% on unfalsifiable claims, where no formal consensus exists."
    ),
    "logical refutation": (
        "Exposes flaws in the opponent's reasoning — invalid inferences, contradictions, "
        "or unstated assumptions — without necessarily disputing the underlying facts."
    ),
    "contextual analysis": (
        "Argues the opponent's claim oversimplifies a more complex situation, "
        "introducing factors or qualifiers that change the bottom line. The fallback "
        "when direct evidence fails — wins only 35% of the time."
    ),
    "mechanism explanation": (
        "Explains the underlying causal process so the audience can evaluate the claim "
        "against how things actually work. Claude's unique tactic on unfalsifiable "
        "claims; 95% win rate."
    ),
    "technical correction": (
        "Identifies and corrects specific factual errors — wrong numbers, misattributed "
        "quotes, mistaken dates — with precise verifiable values."
    ),
    "verification": (
        "Asks the opponent to provide checkable sources or methodology rather than "
        "accepting unsupported assertions. Triggers conspiracy pivots from spreaders."
    ),
    "public safety": (
        "Frames the dispute in terms of harm — health risk, institutional erosion, "
        "social trust — arguing the stakes, not just the facts."
    ),
}


def _render_strategy(ep):
    sa = ep.get("strategy_analysis") or {}
    pts = ep.get("per_turn_strategies") or []

    spr_primary = sa.get("spreader_primary", "")
    deb_primary = sa.get("debunker_primary", "")

    # Compute tactic counters early — used by both Top 5 panel and effectiveness inference
    from collections import Counter as _Ctr
    spr_freq = _Ctr()
    deb_freq = _Ctr()
    for t in pts:
        for s in (t.get("spreader_strategies") or []):
            spr_freq[_label_plain(s)] += 1
        for s in (t.get("debunker_strategies") or []):
            deb_freq[_label_plain(s)] += 1

    # Map plain label -> raw label for context lookup
    _spr_raw_for_plain = {}
    _deb_raw_for_plain = {}
    for t in pts:
        for s in (t.get("spreader_strategies") or []):
            _spr_raw_for_plain.setdefault(_label_plain(s), s)
        for s in (t.get("debunker_strategies") or []):
            _deb_raw_for_plain.setdefault(_label_plain(s), s)

    # ──────────────────────────────────────────────────────────────────
    # 1) Top 5 tactics per side (replaces single-primary card)
    # ──────────────────────────────────────────────────────────────────
    if spr_freq or deb_freq or spr_primary or deb_primary:
        st.markdown('<div class="rp-section-label">Top tactics</div>', unsafe_allow_html=True)
        _t5_cols = st.columns(2)
        with _t5_cols[0]:
            _render_top5_panel("Spreader", SPREADER_COLOR, spr_freq, spr_primary,
                              _spr_raw_for_plain, len(pts))
        with _t5_cols[1]:
            _render_top5_panel("Fact-checker", DEBUNKER_COLOR, deb_freq, deb_primary,
                              _deb_raw_for_plain, len(pts))

    if not pts:
        if not spr_primary and not deb_primary:
            st.info("No strategy data available for this episode.")
        return

    pairs = _normalize_turn_pairs(ep)

    # ──────────────────────────────────────────────────────────────────
    # 2) Horizontal swimlane — sides as rows, turns as columns
    # ──────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Strategy evolution</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Sides as rows, turns as columns. Each cell shows the tactics used that turn; "
        "the ↗ arrow marks a shift from the previous turn. Read across to see the rhythm. "
        "The inflection row at top flags moments where both sides adapted simultaneously — "
        "the pivotal turns in the debate."
    )

    _n_turns = len(pts)
    # CSS grid: side-label column + N turn columns, sized equally
    _grid_template = f'grid-template-columns: 110px repeat({_n_turns}, minmax(0, 1fr));'

    def _build_pills_cell(strats, color, adapted):
        """Build pill HTML for one cell of the swimlane."""
        if not strats:
            return f'<span style="color:#6b7280;font-size:0.74rem;font-style:italic">—</span>'
        pills = ""
        for j, s in enumerate(strats[:3]):
            is_primary = j == 0
            bg = f"rgba({_hex_to_rgb_str(color)},{'0.18' if is_primary else '0.08'})"
            border = f"1px solid rgba({_hex_to_rgb_str(color)},{'0.55' if is_primary else '0.25'})"
            weight = "600" if is_primary else "400"
            pills += (
                f'<div style="display:inline-block;margin:0.1rem 0.15rem 0.1rem 0;'
                f'padding:0.12rem 0.45rem;border-radius:10px;background:{bg};'
                f'border:{border};color:{color};font-size:0.74rem;font-weight:{weight};'
                f'line-height:1.3">{s}</div>'
            )
        if adapted:
            pills += (
                f'<div style="margin-top:0.2rem;color:#4CAF7D;font-size:0.7rem;font-weight:600">↗ adapted</div>'
            )
        return pills

    # Header row: turn numbers — clickable, jump to that turn's transcript below
    _hdr_cells = '<div style="font-size:0.66rem;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:0.07em"></div>'
    for t in pts:
        turn_num = t.get("turn", "?")
        _hdr_cells += (
            f'<div style="text-align:center;padding:0.3rem 0;'
            f'border-bottom:2px solid var(--color-border,#2A2A2A)">'
            f'<a href="#strat-turn-{turn_num}" '
            f'style="font-family:\'IBM Plex Mono\',monospace;font-size:0.72rem;'
            f'color:#9ca3af;font-weight:700;letter-spacing:0.07em;'
            f'text-decoration:none;border-bottom:1px dotted #6b7280;padding-bottom:1px;cursor:pointer" '
            f'title="Jump to turn {turn_num} transcript">TURN {turn_num} ↓</a>'
            f'</div>'
        )

    # Inflection row: turns where both sides adapted
    _infl_cells = (
        '<div style="font-size:0.66rem;color:#9ca3af;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;padding:0.5rem 0;align-self:center">Inflection</div>'
    )
    _has_inflection = False
    for t in pts:
        spr_adapted = bool(t.get("spreader_adapted"))
        deb_adapted = bool(t.get("debunker_adapted"))
        if spr_adapted and deb_adapted:
            _has_inflection = True
            _infl_cells += (
                '<div style="text-align:center;padding:0.4rem 0;'
                'background:rgba(76,175,125,0.10);border-left:1px solid var(--color-border,#2A2A2A);'
                'border-right:1px solid var(--color-border,#2A2A2A)">'
                '<span style="font-size:0.95rem;color:#4CAF7D">⚡</span>'
                '<div style="font-size:0.66rem;color:#4CAF7D;font-weight:600;margin-top:0.1rem;'
                'text-transform:uppercase;letter-spacing:0.04em">both adapted</div>'
                '</div>'
            )
        elif spr_adapted or deb_adapted:
            who = "Spr" if spr_adapted else "FC"
            who_color = SPREADER_COLOR if spr_adapted else DEBUNKER_COLOR
            _infl_cells += (
                f'<div style="text-align:center;padding:0.4rem 0;color:{who_color};'
                f'font-size:0.7rem;font-weight:600">↗ {who}</div>'
            )
        else:
            _infl_cells += '<div style="text-align:center;padding:0.4rem 0;color:#3a3a3a">·</div>'

    # Spreader row
    _spr_cells = (
        f'<div style="color:{SPREADER_COLOR};font-size:0.74rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.07em;padding-top:0.4rem">Spreader</div>'
    )
    for t in pts:
        spr_strats = [_label_plain(s) for s in (t.get("spreader_strategies") or [])]
        _spr_cells += (
            f'<div style="padding:0.4rem 0.3rem;border-top:1px solid var(--color-border,#2A2A2A);'
            f'border-bottom:1px solid var(--color-border,#2A2A2A)">'
            f'{_build_pills_cell(spr_strats, SPREADER_COLOR, bool(t.get("spreader_adapted")))}'
            f'</div>'
        )

    # Debunker row
    _deb_cells = (
        f'<div style="color:{DEBUNKER_COLOR};font-size:0.74rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.07em;padding-top:0.4rem">Fact-checker</div>'
    )
    for t in pts:
        deb_strats = [_label_plain(s) for s in (t.get("debunker_strategies") or [])]
        _deb_cells += (
            f'<div style="padding:0.4rem 0.3rem">'
            f'{_build_pills_cell(deb_strats, DEBUNKER_COLOR, bool(t.get("debunker_adapted")))}'
            f'</div>'
        )

    st.markdown(
        f'<div style="display:grid;{_grid_template}gap:0.4rem;align-items:start">'
        f'{_hdr_cells}'
        f'{_infl_cells}'
        f'{_spr_cells}'
        f'{_deb_cells}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not _has_inflection:
        st.caption(
            "No simultaneous-adaptation inflection points in this debate "
            "(no turn where both sides shifted their tactics at once)."
        )

    # Adaptation summary
    spr_adapt_count = sum(1 for t in pts if t.get("spreader_adapted"))
    deb_adapt_count = sum(1 for t in pts if t.get("debunker_adapted"))
    _adapt_denom = max(len(pts) - 1, 1)
    st.markdown(
        f'<div class="rp-stat-row" style="margin-top:0.8rem">'
        f'<div class="rp-stat" style="border-left:3px solid {SPREADER_COLOR}">'
        f'<div class="rp-stat-label">Spreader adaptation</div>'
        f'<div class="rp-stat-val">{spr_adapt_count}/{_adapt_denom} turns '
        f'({spr_adapt_count/_adapt_denom*100:.0f}%)</div></div>'
        f'<div class="rp-stat" style="border-left:3px solid {DEBUNKER_COLOR}">'
        f'<div class="rp-stat-label">Fact-checker adaptation</div>'
        f'<div class="rp-stat-val">{deb_adapt_count}/{_adapt_denom} turns '
        f'({deb_adapt_count/_adapt_denom*100:.0f}%)</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # 3) Click-to-drill — see actual sentences for each unique tactic
    # ──────────────────────────────────────────────────────────────────
    _render_tactic_drilldown(pts, pairs)

    # ──────────────────────────────────────────────────────────────────
    # 4) Reaction patterns — when X happened, Y followed
    # ──────────────────────────────────────────────────────────────────
    if len(pts) >= 2:
        st.markdown(
            '<div class="rp-section-label" style="margin-top:1.4rem">Reaction patterns in this debate</div>',
            unsafe_allow_html=True,
        )
        st.caption("Each row shows a within-turn back-and-forth — spreader speaks, fact-checker responds.")
        _react_rows = []
        for i, t in enumerate(pts):
            spr_strats = [_label_plain(s) for s in (t.get("spreader_strategies") or [])[:1]]
            deb_strats = [_label_plain(s) for s in (t.get("debunker_strategies") or [])[:1]]
            if not spr_strats or not deb_strats:
                continue
            _react_rows.append(
                f'<div style="display:grid;grid-template-columns:1fr 30px 1fr;gap:0.5rem;'
                f'align-items:center;padding:0.4rem 0;font-size:0.88rem;">'
                f'<div style="text-align:right;color:{SPREADER_COLOR};font-weight:600;">{spr_strats[0]}</div>'
                f'<div style="text-align:center;color:#9ca3af;font-size:1.1rem">→</div>'
                f'<div style="color:{DEBUNKER_COLOR};font-weight:600;">{deb_strats[0]}</div>'
                f'</div>'
            )
        if _react_rows:
            st.markdown("".join(_react_rows), unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────
    # 5) Tactic → outcome attribution
    # ──────────────────────────────────────────────────────────────────
    _render_outcome_attribution(ep, pts)

    # ──────────────────────────────────────────────────────────────────
    # 6) Per-turn transcript — always visible so anchor links from the
    #    swimlane TURN N headers can scroll-to here.
    # ──────────────────────────────────────────────────────────────────
    _render_per_turn_transcript(
        ep, pts, pairs,
        anchor_prefix="strat-turn",
        caption=("Click any TURN N header in the swimlane above to jump down to that "
                 "turn's transcript here."),
    )


def _render_per_turn_transcript(ep, pts, pairs, anchor_prefix, caption=None):
    """Shared renderer: per-turn transcript section with anchor ids.

    Used by both the Strategy tab (anchor_prefix='strat-turn') and the
    Citations tab (anchor_prefix='cite-turn'). Each tab needs its own copy
    because Streamlit hides inactive tabs via display:none, which breaks
    cross-tab anchor scrolling.
    """
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Transcript by turn</div>',
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)

    # If pts isn't provided, derive a stub per pair so anchors still work
    if not pts:
        pts = [{"turn": i + 1} for i in range(len(pairs))]

    for i, t in enumerate(pts):
        turn_num = t.get("turn", i + 1)
        spr_strats = [_label_plain(s) for s in (t.get("spreader_strategies") or [])]
        deb_strats = [_label_plain(s) for s in (t.get("debunker_strategies") or [])]
        spr_text = (pairs[i].get("spreader_text") or "").strip() if i < len(pairs) else ""
        deb_text = (pairs[i].get("debunker_text") or "").strip() if i < len(pairs) else ""

        st.markdown(
            f'<div id="{anchor_prefix}-{turn_num}" '
            f'style="scroll-margin-top:80px;margin-top:1.2rem;'
            f'font-size:0.74rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'color:#9ca3af;font-weight:700;border-bottom:1px solid var(--color-border,#2A2A2A);'
            f'padding-bottom:0.3rem">TURN {turn_num}</div>',
            unsafe_allow_html=True,
        )
        _tc1, _tc2 = st.columns(2)
        with _tc1:
            _label_html = ", ".join(spr_strats) if spr_strats else "—"
            st.markdown(
                f'<div style="font-size:0.78rem;color:{SPREADER_COLOR};font-weight:600;'
                f'margin:0.3rem 0 0.2rem 0">Spreader{(" — " + _label_html) if spr_strats else ""}</div>',
                unsafe_allow_html=True,
            )
            if spr_text:
                st.markdown(
                    f'<div style="font-size:0.85rem;line-height:1.55;'
                    f'background:rgba(212,168,67,0.05);border-radius:6px;padding:0.6rem;'
                    f'white-space:pre-wrap;'
                    f'color:var(--color-text-primary,#E8E4D9)">{spr_text}</div>',
                    unsafe_allow_html=True,
                )
        with _tc2:
            _label_html = ", ".join(deb_strats) if deb_strats else "—"
            st.markdown(
                f'<div style="font-size:0.78rem;color:{DEBUNKER_COLOR};font-weight:600;'
                f'margin:0.3rem 0 0.2rem 0">Fact-checker{(" — " + _label_html) if deb_strats else ""}</div>',
                unsafe_allow_html=True,
            )
            if deb_text:
                st.markdown(
                    f'<div style="font-size:0.85rem;line-height:1.55;'
                    f'background:rgba(74,127,165,0.05);border-radius:6px;padding:0.6rem;'
                    f'white-space:pre-wrap;'
                    f'color:var(--color-text-primary,#E8E4D9)">{deb_text}</div>',
                    unsafe_allow_html=True,
                )


def _render_citation_drilldown(ep, _unused_spr_sents, _unused_deb_sents):
    """Per-source citation drill-down with inline framing tags.

    Two columns (Spreader / Fact-checker). Each unique source they cited is
    an expander showing every citation event with:
      - Turn link (↓ scrolls to the per-turn transcript section)
      - Framing tag chips (Hedging / Definitive / Conspiratorial)
      - The sentence with source name colored and framing words highlighted

    Same mental model as the Strategy tab's tactic drill-down, but for citations.
    """
    pairs = _normalize_turn_pairs(ep)
    if not pairs:
        return

    # Patterns for framing tags (defined as constants at module level: _HEDGING / _DEFINITIVE / _CONSPIRATORIAL)
    FRAMING_PATTERNS = [
        ("Hedging",        "#D4A843", _HEDGING),
        ("Definitive",     "#4CAF7D", _DEFINITIVE),
        ("Conspiratorial", "#C9363E", _CONSPIRATORIAL),
    ]

    def _per_side_citations(role_key):
        out = {}  # src -> [(turn, sentence, framing_tags)]
        for i, p in enumerate(pairs):
            turn_num = p.get("pair_idx", i + 1)
            text = (p.get(role_key) or "").strip()
            if not text:
                continue
            for sent in re.split(r'(?<=[.!?])\s+', text):
                s = sent.strip()
                if len(s) < 30:
                    continue
                # Canonicalize so a sentence mentioning both "WHO" and the
                # full "World Health Organization" doesn't double-count.
                raw_hits = [src for src, pat in _SOURCE_PATTERNS.items() if pat.search(s)]
                hits = sorted({_canonical_source(src) for src in raw_hits})
                if not hits:
                    continue
                tags = [name for name, _c, pat in FRAMING_PATTERNS if pat.search(s)]
                for src in hits:
                    out.setdefault(src, []).append((turn_num, s, tags))
        return out

    spr_cites = _per_side_citations("spreader_text")
    deb_cites = _per_side_citations("debunker_text")

    if not spr_cites and not deb_cites:
        return

    st.markdown(
        '<div class="rp-section-label" style="margin-top:1rem">Citation drill-down</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Each source expander shows every sentence where that side cited it, "
        "tagged with the framing pattern used. Click any Turn N ↓ to jump to the "
        "full transcript below."
    )

    def _framing_chip(name, color):
        return (
            f'<span style="display:inline-block;margin-right:0.35rem;'
            f'padding:0.08rem 0.45rem;border-radius:8px;'
            f'background:rgba({_hex_to_rgb_str(color)},0.18);'
            f'border:1px solid rgba({_hex_to_rgb_str(color)},0.55);'
            f'color:{color};font-size:0.7rem;font-weight:600;letter-spacing:0.04em;'
            f'text-transform:uppercase">{name}</span>'
        )

    def _highlight_sentence(s, source, side_color):
        # Highlight the canonical name AND any aliases that resolve to it
        # (so "WHO" highlighting also catches "World Health Organization").
        candidates = [source]
        for alias, canonical in _SOURCE_ALIASES.items():
            if canonical == source and alias not in candidates:
                candidates.append(alias)
        for cand in candidates:
            pat = _SOURCE_PATTERNS.get(cand)
            if pat is None:
                continue
            s = pat.sub(
                lambda m: f'<b style="color:{side_color}">{m.group(0)}</b>',
                s,
            )
        # Framing words highlighted
        for _name, fcolor, pat in FRAMING_PATTERNS:
            s = pat.sub(
                lambda m, c=fcolor: (
                    f'<mark style="background:rgba({_hex_to_rgb_str(c)},0.20);'
                    f'color:inherit;padding:0 2px;border-radius:2px">{m.group(0)}</mark>'
                ),
                s,
            )
        return s

    def _render_side_column(cites_map, role_label, side_color):
        side_rgb = _hex_to_rgb_str(side_color)
        st.markdown(
            f'<div style="font-size:0.72rem;color:{side_color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.4rem;'
            f'padding-bottom:0.3rem;border-bottom:2px solid rgba({side_rgb},0.25)">'
            f'{role_label} citations</div>',
            unsafe_allow_html=True,
        )
        if not cites_map:
            st.caption(f"— no named sources cited by {role_label.lower()} —")
            return

        sorted_sources = sorted(cites_map.items(), key=lambda x: -len(x[1]))
        for src, events in sorted_sources:
            tag_counts = {}
            for _t, _s, tags in events:
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            tag_breakdown = ", ".join(
                f"{n} {name.lower()}" for name, n in tag_counts.items()
            ) or "no framing words"
            header = f"{src} — {len(events)} use{'s' if len(events) != 1 else ''} · {tag_breakdown}"
            with st.expander(header):
                # "About this institution" — pulled from the shared
                # institution info table. Same definition surface as Atlas.
                info = get_institution_info(src)
                if info:
                    st.markdown(
                        f'<div style="background:var(--color-surface-alt,#1A1A1A);'
                        f'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
                        f'padding:0.55rem 0.75rem;margin:0.1rem 0 0.55rem 0">'
                        f'<div style="font-size:0.66rem;text-transform:uppercase;letter-spacing:0.08em;'
                        f'color:#9ca3af;font-weight:700;margin-bottom:0.25rem">About this institution</div>'
                        f'<div style="font-size:0.86rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">'
                        f'{info}</div></div>',
                        unsafe_allow_html=True,
                    )
                for turn_num, sent, tags in events:
                    chips = "".join(
                        _framing_chip(t, dict((n, c) for n, c, _ in FRAMING_PATTERNS)[t])
                        for t in tags
                    ) or '<span style="color:#6b7280;font-size:0.74rem;font-style:italic">— no framing words —</span>'
                    highlighted = _highlight_sentence(sent, src, side_color)
                    st.markdown(
                        f'<div style="margin:0.4rem 0">'
                        f'<div style="margin-bottom:0.25rem">'
                        f'<a href="#cite-turn-{turn_num}" '
                        f'style="color:{side_color};text-decoration:none;'
                        f'font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:0.06em;border-bottom:1px dotted {side_color};'
                        f'padding-bottom:1px;margin-right:0.6rem">Turn {turn_num} ↓</a>'
                        f'{chips}'
                        f'</div>'
                        f'<div style="font-size:0.85rem;line-height:1.55;'
                        f'background:rgba({side_rgb},0.05);border-left:3px solid {side_color};'
                        f'border-radius:0 4px 4px 0;padding:0.55rem 0.7rem;'
                        f'color:var(--color-text-primary,#E8E4D9)">{highlighted}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    cd_cols = st.columns(2)
    with cd_cols[0]:
        _render_side_column(spr_cites, "Spreader", SPREADER_COLOR)
    with cd_cols[1]:
        _render_side_column(deb_cites, "Fact-checker", DEBUNKER_COLOR)


def _render_top5_panel(role_label, color, freq_counter, primary_raw, raw_for_plain, n_turns):
    """Show top 5 tactics for one side, ranked by use count, each with a description."""
    if not freq_counter and not primary_raw:
        st.caption(f"No tactics recorded for {role_label}.")
        return

    items = freq_counter.most_common(5)
    # If we have a primary label but no per-turn data, fall back to a one-row entry
    if not items and primary_raw:
        items = [(_label_plain(primary_raw), 0)]

    rgb = _hex_to_rgb_str(color)
    rows = (
        f'<div style="background:var(--color-surface,#111);'
        f'border:1px solid var(--color-border,#2A2A2A);border-left:3px solid {color};'
        f'border-radius:6px;padding:0.7rem 0.9rem">'
        f'<div style="font-size:0.7rem;color:{color};font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.07em;margin-bottom:0.5rem">{role_label} — top tactics</div>'
    )
    for rank, (name, count) in enumerate(items, 1):
        # Find raw label so we can look up description through the shared resolver
        # (catalogue → per-episode → backfilled cache).
        raw = raw_for_plain.get(name, name.lower().replace(" ", "_"))
        desc = resolve_strategy_description(raw, primary_lookup=_STRATEGY_CONTEXT)
        pct = (count / n_turns * 100) if n_turns else 0
        is_primary = (rank == 1) or (primary_raw and _label_plain(primary_raw) == name)
        rows += (
            f'<div style="padding:0.4rem 0;border-bottom:1px solid var(--color-border,#2A2A2A)">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:0.9rem;color:var(--color-text-primary,#E8E4D9);font-weight:{"700" if is_primary else "500"}">'
            f'{"★ " if is_primary else ""}{name}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.74rem;color:#9ca3af">'
            f'{count} use{"s" if count != 1 else ""}{f" · {pct:.0f}% of turns" if n_turns and count else ""}</span>'
            f'</div>'
        )
        if desc:
            rows += (
                f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.2rem;line-height:1.45">{desc}</div>'
            )
        rows += '</div>'
    rows += '</div>'
    st.markdown(rows, unsafe_allow_html=True)


def _render_tactic_drilldown(pts, pairs):
    """List every unique tactic with the transcript sentences where it appeared.

    Split into two columns: Spreader tactics (left) and Fact-checker tactics
    (right). Lets the user click a tactic and immediately see the actual text
    that earned the label — closes the gap between an abstract label and the
    live message.
    """
    if not pts:
        return

    # Build per-side occurrence maps: tactic_plain → list of (turn, text, raw)
    spr_tactics = {}
    deb_tactics = {}
    for i, t in enumerate(pts):
        turn_num = t.get("turn", i + 1)
        spr_text = (pairs[i].get("spreader_text") or "").strip() if i < len(pairs) else ""
        deb_text = (pairs[i].get("debunker_text") or "").strip() if i < len(pairs) else ""
        for s in (t.get("spreader_strategies") or []):
            spr_tactics.setdefault(_label_plain(s), []).append((turn_num, spr_text, s))
        for s in (t.get("debunker_strategies") or []):
            deb_tactics.setdefault(_label_plain(s), []).append((turn_num, deb_text, s))

    if not spr_tactics and not deb_tactics:
        return

    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Tactic drill-down</div>',
        unsafe_allow_html=True,
    )
    st.caption("Click any tactic to see the transcript sentences where it appeared.")

    def _render_side(tactics_map, color, role_label):
        bg_rgb = _hex_to_rgb_str(color)
        st.markdown(
            f'<div style="font-size:0.72rem;color:{color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.4rem;'
            f'padding-bottom:0.3rem;border-bottom:2px solid rgba({bg_rgb},0.25)">'
            f'{role_label} tactics</div>',
            unsafe_allow_html=True,
        )
        if not tactics_map:
            st.caption(f"— no tactics recorded for {role_label.lower()} —")
            return
        sorted_tactics = sorted(tactics_map.items(), key=lambda x: -len(x[1]))
        for tactic, occurrences in sorted_tactics:
            with st.expander(f"{tactic} — {len(occurrences)} use{'s' if len(occurrences) != 1 else ''}"):
                raw = occurrences[0][2]
                desc = resolve_strategy_description(raw, primary_lookup=_STRATEGY_CONTEXT)
                if desc:
                    st.markdown(
                        f'<div style="font-size:0.84rem;color:#9ca3af;margin:0 0 0.5rem 0;'
                        f'font-style:italic">{desc}</div>',
                        unsafe_allow_html=True,
                    )
                for turn_num, text, _raw in occurrences:
                    preview = (text[:360] + ("…" if len(text) > 360 else "")) if text else "— no transcript text —"
                    st.markdown(
                        f'<div style="margin:0.4rem 0">'
                        f'<div style="font-size:0.7rem;color:{color};font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.2rem">'
                        f'<a href="#strat-turn-{turn_num}" '
                        f'style="color:{color};text-decoration:none;border-bottom:1px dotted {color};'
                        f'padding-bottom:1px">Turn {turn_num} ↓</a></div>'
                        f'<div style="font-size:0.85rem;line-height:1.5;'
                        f'background:rgba({bg_rgb},0.05);border-left:3px solid {color};'
                        f'border-radius:0 4px 4px 0;padding:0.5rem 0.7rem;'
                        f'color:var(--color-text-primary,#E8E4D9)">{preview}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    _dd_cols = st.columns(2)
    with _dd_cols[0]:
        _render_side(spr_tactics, SPREADER_COLOR, "Spreader")
    with _dd_cols[1]:
        _render_side(deb_tactics, DEBUNKER_COLOR, "Fact-checker")


def _hex_to_rgb_str(hex_color: str) -> str:
    """Convert '#RRGGBB' → 'r,g,b' string for CSS rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    try:
        r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
    except ValueError:
        return "128,128,128"
    return f"{r},{g},{b}"


def _render_freq_bars(freq, color, role_label):
    """Render a vertical list of tactic-frequency bars for one side."""
    if not freq:
        st.caption(f"No tactics recorded for {role_label}.")
        return
    total = sum(freq.values()) or 1
    items = sorted(freq.items(), key=lambda x: -x[1])
    rgb = _hex_to_rgb_str(color)
    rows = ""
    for name, count in items:
        pct = count / total * 100
        rows += (
            f'<div style="margin:0.25rem 0;font-size:0.84rem">'
            f'<div style="display:flex;justify-content:space-between;color:var(--color-text-primary,#E8E4D9);">'
            f'<span>{name}</span>'
            f'<span style="color:#9ca3af;font-family:\'IBM Plex Mono\',monospace;font-size:0.78rem">{count} ({pct:.0f}%)</span>'
            f'</div>'
            f'<div style="height:6px;background:rgba({rgb},0.10);border-radius:3px;overflow:hidden;margin-top:0.2rem">'
            f'<div style="height:100%;width:{pct:.0f}%;background:rgba({rgb},0.75);"></div>'
            f'</div>'
            f'</div>'
        )
    st.markdown(
        f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
        f'color:{color};font-weight:700;margin-bottom:0.3rem;">{role_label}</div>'
        + rows,
        unsafe_allow_html=True,
    )


def _render_outcome_attribution(ep, pts):
    """Connect tactic use to scorecard outcomes.

    Now produces per-tactic effectiveness lines: for each side's top tactic,
    identifies the scorecard dimension that swung in their favor (or against
    them, if they used it but still lost). Heuristic, not causal.
    """
    res = ep.get("results") or {}
    scorecard = res.get("scorecard") or []
    if not scorecard or not pts:
        return

    # Compute per-dimension deltas (debunker − spreader)
    deltas = []
    for s in scorecard:
        spr_s = float(s.get("spreader", 0) or 0)
        deb_s = float(s.get("debunker", 0) or 0)
        delta = deb_s - spr_s
        deltas.append((s.get("metric", ""), delta))
    deltas_sorted = sorted(deltas, key=lambda x: abs(x[1]), reverse=True)
    top_for_deb = [(m, d) for m, d in deltas_sorted if d > 0.5][:2]
    top_for_spr = [(m, d) for m, d in deltas_sorted if d < -0.5][:2]

    # Per-side frequency counters (uses across turns, top tactics)
    from collections import Counter as _Ctr
    spr_freq = _Ctr()
    deb_freq = _Ctr()
    for t in pts:
        for s in (t.get("spreader_strategies") or []):
            spr_freq[_label_plain(s)] += 1
        for s in (t.get("debunker_strategies") or []):
            deb_freq[_label_plain(s)] += 1

    spr_top3 = [name for name, _ in spr_freq.most_common(3)]
    deb_top3 = [name for name, _ in deb_freq.most_common(3)]
    winner = (res.get("winner") or "").lower()

    lines = []

    # Each side's top-3 tactics annotated as winning/losing alongside best dimension
    if deb_top3:
        outcome_tag = "(used by the winner)" if winner == "debunker" else "(used by the loser)"
        outcome_color = "#4CAF7D" if winner == "debunker" else "#9ca3af"
        if top_for_deb:
            metric_html = f"strongest aligned with <b>{_label(top_for_deb[0][0])}</b> (+{top_for_deb[0][1]:.1f} pts)"
        else:
            metric_html = "no dimension swung clearly in their favor"
        lines.append(
            f'<li><b>Fact-checker</b> leaned on <b>{", ".join(deb_top3)}</b> '
            f'<span style="color:{outcome_color};font-size:0.82rem;font-style:italic">{outcome_tag}</span> — '
            f'{metric_html}.</li>'
        )

    if spr_top3:
        outcome_tag = "(used by the winner)" if winner == "spreader" else "(used by the loser)"
        outcome_color = "#4CAF7D" if winner == "spreader" else "#9ca3af"
        if top_for_spr:
            metric_html = f"strongest aligned with <b>{_label(top_for_spr[0][0])}</b> ({top_for_spr[0][1]:+.1f} pts)"
        else:
            metric_html = "no dimension swung clearly in their favor"
        lines.append(
            f'<li><b>Spreader</b> leaned on <b>{", ".join(spr_top3)}</b> '
            f'<span style="color:{outcome_color};font-size:0.82rem;font-style:italic">{outcome_tag}</span> — '
            f'{metric_html}.</li>'
        )

    # Inflection-point note if any
    inflection_turns = [t.get("turn", i+1) for i, t in enumerate(pts)
                        if t.get("spreader_adapted") and t.get("debunker_adapted")]
    if inflection_turns:
        lines.append(
            f'<li>Both sides simultaneously adapted at <b>turn {", ".join(str(x) for x in inflection_turns)}</b> '
            f'— pivot points in the debate where neither was satisfied with their previous tactic.</li>'
        )

    if not lines:
        return

    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">What moved the needle</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:var(--color-surface-alt,#1A1A1A);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:6px;padding:0.8rem 1rem;">'
        f'<ul style="margin:0;padding-left:1.2rem;font-size:0.88rem;line-height:1.55;'
        f'color:var(--color-text-primary,#E8E4D9)">'
        + "".join(lines) +
        f'</ul>'
        f'<div style="font-size:0.72rem;color:#6b7280;margin-top:0.5rem;font-style:italic">'
        f'Heuristic correlation between primary tactics and scorecard gaps — not a causal claim.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Citation renderer (enhanced with framing analysis)
# ---------------------------------------------------------------------------

def _render_citations(ep):
    spr_texts = _get_all_text(ep, "spreader")
    deb_texts = _get_all_text(ep, "debunker")

    if not spr_texts and not deb_texts:
        st.info("No transcript data for citation analysis.")
        return

    # Source detection — word-bounded + alias-canonicalized so the same
    # institution under different names ("WHO" vs "World Health Organization")
    # aggregates into a single entry instead of two duplicates.
    spr_sources = []
    deb_sources = []
    for text in spr_texts:
        for src in _NAMED_SOURCES:
            if _source_appears_in(src, text):
                spr_sources.append(_canonical_source(src))
    for text in deb_texts:
        for src in _NAMED_SOURCES:
            if _source_appears_in(src, text):
                deb_sources.append(_canonical_source(src))

    spr_unique = sorted(set(spr_sources))
    deb_unique = sorted(set(deb_sources))
    shared = sorted(set(spr_unique) & set(deb_unique))

    # Framing analysis — keep matched sentences so we can show them as quotes.
    spr_all = " ".join(spr_texts)
    deb_all = " ".join(deb_texts)
    spr_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', spr_all) if len(s.strip()) > 30]
    deb_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', deb_all) if len(s.strip()) > 30]

    spr_hedge_sents = [s for s in spr_sents if _HEDGING.search(s)]
    deb_hedge_sents = [s for s in deb_sents if _HEDGING.search(s)]
    spr_defin_sents = [s for s in spr_sents if _DEFINITIVE.search(s)]
    deb_defin_sents = [s for s in deb_sents if _DEFINITIVE.search(s)]
    spr_consp_sents = [s for s in spr_sents if _CONSPIRATORIAL.search(s)]
    deb_consp_sents = [s for s in deb_sents if _CONSPIRATORIAL.search(s)]

    spr_hedge = len(spr_hedge_sents)
    deb_hedge = len(deb_hedge_sents)
    spr_defin = len(spr_defin_sents)
    deb_defin = len(deb_defin_sents)
    spr_consp = len(spr_consp_sents)
    deb_consp = len(deb_consp_sents)

    spr_n = max(len(spr_sents), 1)
    deb_n = max(len(deb_sents), 1)

    # Sources section
    st.markdown('<div class="rp-section-label">Institutions cited</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="rp-strat-card" style="border-left:3px solid {SPREADER_COLOR}">'
            f'<div style="font-size:0.7rem;color:{SPREADER_COLOR};font-weight:700;text-transform:uppercase">'
            f'Spreader — {len(spr_sources)} citations</div>'
            f'<div style="font-size:0.9rem;color:var(--color-text-primary,#E8E4D9);margin-top:0.3rem">'
            f'{", ".join(spr_unique) if spr_unique else "No named sources"}</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="rp-strat-card" style="border-left:3px solid {DEBUNKER_COLOR}">'
            f'<div style="font-size:0.7rem;color:{DEBUNKER_COLOR};font-weight:700;text-transform:uppercase">'
            f'Fact-checker — {len(deb_sources)} citations</div>'
            f'<div style="font-size:0.9rem;color:var(--color-text-primary,#E8E4D9);margin-top:0.3rem">'
            f'{", ".join(deb_unique) if deb_unique else "No named sources"}</div></div>',
            unsafe_allow_html=True,
        )

    if shared:
        st.markdown(
            f'<div style="background:rgba(201,54,62,0.1);border:1px solid rgba(201,54,62,0.3);'
            f'border-radius:8px;padding:0.6rem 1rem;margin:0.5rem 0;font-size:0.85rem;'
            f'color:var(--color-text-primary,#E8E4D9)">'
            f'<strong>Shared sources ({len(shared)}):</strong> {", ".join(shared)}'
            f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.2rem">'
            f'Both sides cite the same institutions — the difference is framing.</div></div>',
            unsafe_allow_html=True,
        )

    # ──────────────────────────────────────────────────────────────────
    # Citation drill-down — per-source detail with inline framing tags
    # ──────────────────────────────────────────────────────────────────
    _render_citation_drilldown(ep, spr_sents, deb_sents)

    # Framing section
    st.markdown('<div class="rp-section-label">Framing analysis</div>', unsafe_allow_html=True)
    st.caption(
        "How each side frames its references to institutions and evidence. "
        "Click any turn chip to jump to that turn in the transcript below."
    )

    # Per-turn framing-pattern presence — used for the click-to-jump chips.
    # The %/count numbers are still sentence-based for stable proportions.
    _framing_pairs = _normalize_turn_pairs(ep)

    def _framing_turns(role_key, pat):
        out = []
        for i, p in enumerate(_framing_pairs):
            turn_num = p.get("pair_idx", i + 1)
            text = (p.get(role_key) or "").strip()
            if text and pat.search(text):
                out.append(turn_num)
        return sorted(set(out))

    def _turn_chips(turns, color):
        if not turns:
            return '<span style="color:#3a3a3a;font-size:0.85rem">·</span>'
        return " ".join(
            f'<a href="#cite-turn-{t}" '
            f'style="display:inline-block;padding:0.08rem 0.42rem;margin:0.06rem 0.16rem 0.06rem 0;'
            f'background:{color}22;color:{color};border:1px solid {color}66;border-radius:3px;'
            f'font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;font-weight:700;'
            f'text-decoration:none;cursor:pointer">T{t}</a>'
            for t in turns
        )

    framing_data = [
        ("Hedging",        "some suggest · may · concerns",        spr_hedge, spr_n, deb_hedge, deb_n, _HEDGING),
        ("Definitive",     "conclusively · proven · demonstrates", spr_defin, spr_n, deb_defin, deb_n, _DEFINITIVE),
        ("Conspiratorial", "hidden · suppress · rigged",           spr_consp, spr_n, deb_consp, deb_n, _CONSPIRATORIAL),
    ]
    f_rows = ""
    for label, keywords, s_count, s_total, d_count, d_total, pat in framing_data:
        s_pct = s_count / s_total * 100
        d_pct = d_count / d_total * 100
        higher = SPREADER_COLOR if s_pct > d_pct else DEBUNKER_COLOR if d_pct > s_pct else "#888"
        s_turns = _framing_turns("spreader_text", pat)
        d_turns = _framing_turns("debunker_text", pat)
        f_rows += (
            f'<tr>'
            f'<td style="padding:0.6rem 0.8rem;border-bottom:1px solid #2A2A4A;vertical-align:top">'
            f'<div style="font-weight:600;color:#E8E4D9">{label}</div>'
            f'<div style="font-size:0.75rem;color:#666;font-style:italic">{keywords}</div></td>'
            f'<td style="padding:0.6rem 0.8rem;border-bottom:1px solid #2A2A4A;text-align:center;vertical-align:top">'
            f'<div style="margin-bottom:0.3rem">'
            f'<span style="font-size:1.1rem;font-weight:700;color:{SPREADER_COLOR}">{s_pct:.0f}%</span>'
            f'<span style="font-size:0.78rem;color:#666;margin-left:0.3rem">({s_count})</span></div>'
            f'<div>{_turn_chips(s_turns, SPREADER_COLOR)}</div></td>'
            f'<td style="padding:0.6rem 0.8rem;border-bottom:1px solid #2A2A4A;text-align:center;vertical-align:top">'
            f'<div style="margin-bottom:0.3rem">'
            f'<span style="font-size:1.1rem;font-weight:700;color:{DEBUNKER_COLOR}">{d_pct:.0f}%</span>'
            f'<span style="font-size:0.78rem;color:#666;margin-left:0.3rem">({d_count})</span></div>'
            f'<div>{_turn_chips(d_turns, DEBUNKER_COLOR)}</div></td>'
            f'<td style="padding:0.6rem 0.8rem;border-bottom:1px solid #2A2A4A;text-align:center;vertical-align:top">'
            f'<span style="font-size:0.85rem;font-weight:700;color:{higher}">'
            f'{"Spr" if s_pct > d_pct else "FC" if d_pct > s_pct else "—"} '
            f'{abs(s_pct - d_pct):.0f}pp</span></td>'
            f'</tr>'
        )
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);border-radius:8px;overflow:hidden">'
        f'<thead><tr style="background:#16213E">'
        f'<th style="padding:0.5rem 0.8rem;text-align:left;color:#9ca3af;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Framing</th>'
        f'<th style="padding:0.5rem 0.8rem;text-align:center;color:{SPREADER_COLOR};font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Spreader</th>'
        f'<th style="padding:0.5rem 0.8rem;text-align:center;color:{DEBUNKER_COLOR};font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Fact-checker</th>'
        f'<th style="padding:0.5rem 0.8rem;text-align:center;color:#9ca3af;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #2A2A4A">Gap</th>'
        f'</tr></thead><tbody>{f_rows}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── Per-framing-type quote drill-down ─────────────────────────────────
    def _hl(sent: str, pat: re.Pattern) -> str:
        return pat.sub(lambda m: f'<mark style="background:rgba(212,168,67,0.25);color:inherit;padding:0 2px;border-radius:2px">{m.group(0)}</mark>', sent)

    def _render_quotes(label, pat, spr_list, deb_list):
        if not (spr_list or deb_list):
            return
        with st.expander(f"See {label.lower()} sentences ({len(spr_list)} spreader · {len(deb_list)} fact-checker)"):
            cols = st.columns(2)
            with cols[0]:
                st.markdown(
                    f'<div style="font-size:0.74rem;color:{SPREADER_COLOR};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.3rem">Spreader · {len(spr_list)}</div>',
                    unsafe_allow_html=True,
                )
                if not spr_list:
                    st.caption("— none —")
                for s in spr_list[:6]:
                    st.markdown(
                        f'<div style="font-size:0.85rem;line-height:1.5;background:rgba(212,168,67,0.05);'
                        f'border-left:3px solid {SPREADER_COLOR};border-radius:0 4px 4px 0;'
                        f'padding:0.5rem 0.7rem;margin:0.3rem 0;color:var(--color-text-primary,#E8E4D9)">'
                        f'{_hl(s, pat)}</div>',
                        unsafe_allow_html=True,
                    )
                if len(spr_list) > 6:
                    st.caption(f"+ {len(spr_list) - 6} more")
            with cols[1]:
                st.markdown(
                    f'<div style="font-size:0.74rem;color:{DEBUNKER_COLOR};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.3rem">Fact-checker · {len(deb_list)}</div>',
                    unsafe_allow_html=True,
                )
                if not deb_list:
                    st.caption("— none —")
                for s in deb_list[:6]:
                    st.markdown(
                        f'<div style="font-size:0.85rem;line-height:1.5;background:rgba(74,127,165,0.05);'
                        f'border-left:3px solid {DEBUNKER_COLOR};border-radius:0 4px 4px 0;'
                        f'padding:0.5rem 0.7rem;margin:0.3rem 0;color:var(--color-text-primary,#E8E4D9)">'
                        f'{_hl(s, pat)}</div>',
                        unsafe_allow_html=True,
                    )
                if len(deb_list) > 6:
                    st.caption(f"+ {len(deb_list) - 6} more")

    _render_quotes("Hedging",        _HEDGING,        spr_hedge_sents, deb_hedge_sents)
    _render_quotes("Definitive",     _DEFINITIVE,     spr_defin_sents, deb_defin_sents)
    _render_quotes("Conspiratorial", _CONSPIRATORIAL, spr_consp_sents, deb_consp_sents)

    # ── Hedge-ratio sparkline — quick visual of who hedges more ─────────────
    _spr_words = sum(len(t.split()) for t in spr_texts) or 1
    _deb_words = sum(len(t.split()) for t in deb_texts) or 1
    _spr_per1k = spr_hedge / _spr_words * 1000
    _deb_per1k = deb_hedge / _deb_words * 1000
    _max_per1k = max(_spr_per1k, _deb_per1k, 1)

    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.2rem">Hedge intensity</div>',
        unsafe_allow_html=True,
    )
    st.caption("Hedge words per 1,000 words. Spreaders hedge ~2.4× more on average in our research.")
    _spr_bar_w = int(_spr_per1k / _max_per1k * 100) if _max_per1k > 0 else 0
    _deb_bar_w = int(_deb_per1k / _max_per1k * 100) if _max_per1k > 0 else 0
    st.markdown(
        f'<div style="display:grid;grid-template-columns:120px 1fr 70px;gap:0.6rem;'
        f'align-items:center;margin:0.3rem 0;font-size:0.86rem">'
        f'<div style="color:{SPREADER_COLOR};font-weight:600">Spreader</div>'
        f'<div style="height:14px;background:rgba(212,168,67,0.10);border-radius:7px;overflow:hidden">'
        f'<div style="height:100%;width:{_spr_bar_w}%;background:{SPREADER_COLOR}"></div></div>'
        f'<div style="text-align:right;font-family:\'IBM Plex Mono\',monospace;color:#9ca3af">{_spr_per1k:.1f}/1k</div>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:120px 1fr 70px;gap:0.6rem;'
        f'align-items:center;margin:0.3rem 0;font-size:0.86rem">'
        f'<div style="color:{DEBUNKER_COLOR};font-weight:600">Fact-checker</div>'
        f'<div style="height:14px;background:rgba(74,127,165,0.10);border-radius:7px;overflow:hidden">'
        f'<div style="height:100%;width:{_deb_bar_w}%;background:{DEBUNKER_COLOR}"></div></div>'
        f'<div style="text-align:right;font-family:\'IBM Plex Mono\',monospace;color:#9ca3af">{_deb_per1k:.1f}/1k</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Reframing detection — same institution, different framing ───────────
    if shared:
        st.markdown(
            '<div class="rp-section-label" style="margin-top:1.2rem">Reframing — same source, different framing</div>',
            unsafe_allow_html=True,
        )
        st.caption("The same institution cited by both sides. See how each side framed it.")
        for src in shared[:5]:
            patterns_for_src = _patterns_for_canonical(src)
            if not patterns_for_src:
                continue
            _spr_quotes = [s for s in spr_sents if any(p.search(s) for p in patterns_for_src)][:2]
            _deb_quotes = [s for s in deb_sents if any(p.search(s) for p in patterns_for_src)][:2]
            if not _spr_quotes and not _deb_quotes:
                continue
            with st.expander(f"How each side cited {src}"):
                cols = st.columns(2)
                with cols[0]:
                    st.markdown(
                        f'<div style="font-size:0.74rem;color:{SPREADER_COLOR};font-weight:700;'
                        f'text-transform:uppercase;margin-bottom:0.3rem">Spreader</div>',
                        unsafe_allow_html=True,
                    )
                    if not _spr_quotes:
                        st.caption("— didn't quote this source directly —")
                    for q in _spr_quotes:
                        _hi = q
                        for _p in patterns_for_src:
                            _hi = _p.sub(lambda m: f'<b style="color:{SPREADER_COLOR}">{m.group(0)}</b>', _hi)
                        st.markdown(
                            f'<div style="font-size:0.85rem;line-height:1.5;background:rgba(212,168,67,0.05);'
                            f'border-left:3px solid {SPREADER_COLOR};padding:0.5rem 0.7rem;margin:0.3rem 0;'
                            f'border-radius:0 4px 4px 0;color:var(--color-text-primary,#E8E4D9)">{_hi}</div>',
                            unsafe_allow_html=True,
                        )
                with cols[1]:
                    st.markdown(
                        f'<div style="font-size:0.74rem;color:{DEBUNKER_COLOR};font-weight:700;'
                        f'text-transform:uppercase;margin-bottom:0.3rem">Fact-checker</div>',
                        unsafe_allow_html=True,
                    )
                    if not _deb_quotes:
                        st.caption("— didn't quote this source directly —")
                    for q in _deb_quotes:
                        _hi = q
                        for _p in patterns_for_src:
                            _hi = _p.sub(lambda m: f'<b style="color:{DEBUNKER_COLOR}">{m.group(0)}</b>', _hi)
                        st.markdown(
                            f'<div style="font-size:0.85rem;line-height:1.5;background:rgba(74,127,165,0.05);'
                            f'border-left:3px solid {DEBUNKER_COLOR};padding:0.5rem 0.7rem;margin:0.3rem 0;'
                            f'border-radius:0 4px 4px 0;color:var(--color-text-primary,#E8E4D9)">{_hi}</div>',
                            unsafe_allow_html=True,
                        )

    # ── Plain-English interpretation (F4 — Source Weaponization) ──────────
    _interp_lines = []
    _s_hedge_rate = spr_hedge / spr_n if spr_n else 0
    _d_hedge_rate = deb_hedge / deb_n if deb_n else 0
    if _s_hedge_rate > _d_hedge_rate * 1.5 and _d_hedge_rate > 0:
        _ratio = _s_hedge_rate / max(_d_hedge_rate, 0.001)
        _interp_lines.append(
            f'<b>Spreader hedged {_ratio:.1f}× more than the fact-checker</b> '
            f'(<i>"some," "may," "could," "suggests"</i>). Across our 960-episode study, '
            f'spreaders hedge 2.4× more on average — it&apos;s a tell that they know the '
            f'claims are vulnerable to evidence.'
        )
    elif _d_hedge_rate > _s_hedge_rate * 1.5 and _s_hedge_rate > 0:
        _ratio = _d_hedge_rate / max(_s_hedge_rate, 0.001)
        _interp_lines.append(
            f'<b>Fact-checker hedged {_ratio:.1f}× more than the spreader</b> — unusual. '
            f'In our research the spreader typically hedges more. A confident spreader '
            f'sometimes signals an unfalsifiable claim where they can&apos;t be pinned down.'
        )

    _s_consp_rate = spr_consp / spr_n if spr_n else 0
    _d_consp_rate = deb_consp / deb_n if deb_n else 0
    if _s_consp_rate > 0.05 and _s_consp_rate > _d_consp_rate * 2:
        _interp_lines.append(
            f'<b>Spreader leans on conspiratorial framing</b> (<i>"hidden," "suppress," '
            f'"rigged"</i> in {_s_consp_rate*100:.0f}% of citation contexts). This is '
            f'the &quot;source weaponization&quot; pattern: cite real institutions, then '
            f'frame them as compromised.'
        )

    if _interp_lines:
        _interp_html = "".join(f'<li style="margin-bottom:0.3rem">{line}</li>' for line in _interp_lines)
        st.markdown(
            f'<div style="background:var(--color-surface-alt,#1A1A1A);'
            f'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
            f'padding:0.8rem 1rem;margin:0.6rem 0;">'
            f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'color:#9ca3af;font-weight:700;margin-bottom:0.4rem;">What this tells us</div>'
            f'<ul style="margin:0;padding-left:1.1rem;font-size:0.88rem;line-height:1.55;'
            f'color:var(--color-text-primary,#E8E4D9)">{_interp_html}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Per-turn transcript — anchor target for Citation drill-down links ──
    _ct_pairs = _normalize_turn_pairs(ep)
    if _ct_pairs:
        _render_per_turn_transcript(
            ep, [], _ct_pairs,
            anchor_prefix="cite-turn",
            caption=("Click any Turn N ↓ in the Citation drill-down to jump to that "
                     "turn's full transcript here."),
        )


# ---------------------------------------------------------------------------
# Comparison renderer
# ---------------------------------------------------------------------------

def _ep_summary_label(ep: dict) -> str:
    """Short human label for an episode used in selectors."""
    cfg = ep.get("config_snapshot", {}).get("agents", {})
    spr = _short(cfg.get("spreader", {}).get("model", "?"))
    deb = _short(cfg.get("debunker", {}).get("model", "?"))
    res = ep.get("results", {})
    winner = (res.get("winner") or "?").title()
    totals = res.get("totals", {})
    margin = (totals.get("debunker", 0) or 0) - (totals.get("spreader", 0) or 0)
    claim_short = (ep.get("claim") or "")[:48]
    return f"{spr} vs {deb} · {winner} ({margin:+.1f}) — {claim_short}"


def _render_compare_card(ep: dict, label: str):
    """Render one episode summary card for the side-by-side comparison grid."""
    res = ep.get("results", {})
    cfg = ep.get("config_snapshot", {}).get("agents", {})
    spr_m = _short(cfg.get("spreader", {}).get("model", "?"))
    deb_m = _short(cfg.get("debunker", {}).get("model", "?"))
    winner = (res.get("winner") or "?").title()
    totals = res.get("totals", {})
    margin = (totals.get("debunker", 0) or 0) - (totals.get("spreader", 0) or 0)
    confidence = res.get("judge_confidence", 0)
    claim = ep.get("claim", "")
    sa = ep.get("strategy_analysis") or {}
    spr_primary = _label_plain(sa.get("spreader_primary", ""))
    deb_primary = _label_plain(sa.get("debunker_primary", ""))

    winner_color = "#2ECC71" if winner == "Debunker" else SPREADER_COLOR
    from arena.claim_metadata import domain_badge_html
    _dom_chip = domain_badge_html(ep.get("claim_type", ""), size="sm")
    st.markdown(
        f'<div class="rp-strat-card">'
        f'<div style="font-size:0.68rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">{label}</div>'
        f'<div style="font-size:0.95rem;font-weight:700;color:var(--color-text-primary,#E8E4D9);margin-top:0.2rem;">'
        f'{spr_m} vs {deb_m}</div>'
        f'<div style="margin-top:0.3rem">{_dom_chip}</div>'
        f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.3rem;font-style:italic;">'
        f'&ldquo;{claim[:60]}{"…" if len(claim) > 60 else ""}&rdquo;</div>'
        f'<div style="font-size:0.85rem;color:#9ca3af;margin-top:0.4rem">'
        f'Winner: <strong style="color:{winner_color}">{winner}</strong> '
        f'· Margin: {margin:+.1f} · Confidence: {confidence:.0%}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if spr_primary or deb_primary:
        st.markdown(
            f'<div style="font-size:0.78rem;color:#9ca3af;margin:0.4rem 0 0.2rem 0;">Primary tactics:</div>'
            f'<div style="font-size:0.82rem;color:{SPREADER_COLOR};margin:0.05rem 0;">Spr: {spr_primary or "—"}</div>'
            f'<div style="font-size:0.82rem;color:{DEBUNKER_COLOR};margin:0.05rem 0;">FC: {deb_primary or "—"}</div>',
            unsafe_allow_html=True,
        )

    # Top scorecard deltas
    scorecard = res.get("scorecard", [])
    if scorecard:
        st.markdown(
            '<div style="font-size:0.78rem;color:#9ca3af;margin:0.4rem 0 0.15rem 0;">Top score gaps:</div>',
            unsafe_allow_html=True,
        )
        for s in sorted(scorecard, key=lambda x: abs(x.get("debunker", 0) - x.get("spreader", 0)), reverse=True)[:3]:
            delta = s.get("debunker", 0) - s.get("spreader", 0)
            color = DEBUNKER_COLOR if delta > 0 else SPREADER_COLOR
            st.markdown(
                f'<div style="font-size:0.82rem;color:{color};margin:0.05rem 0">'
                f'{_label(s.get("metric",""))}: {delta:+.1f}</div>',
                unsafe_allow_html=True,
            )


def _render_comparison(selected_ep, all_episodes):
    """Side-by-side comparison.

    The comparison mode is *implicit*, derived from what the user selects:
      - All selections share the current episode's claim → "same_claim" mode
        (the cleanest comparison — isolates model variable)
      - Any selection is a different claim in the same domain → "same_domain"
        mode (controls for domain, isolates claim-specific behavior)
    Different-domain claims are excluded entirely (would confound topic and model).
    """
    cur_claim = selected_ep.get("claim", "")
    cur_claim_type = (selected_ep.get("claim_type") or "").strip()
    cur_key = (selected_ep.get("run_id"), selected_ep.get("episode_id"))

    if not cur_claim:
        st.info("No claim data on the current episode.")
        return

    # ── Build two candidate pools ─────────────────────────────────────────
    same_claim_pool = []
    same_domain_pool = []
    for e in all_episodes:
        if (e.get("run_id"), e.get("episode_id")) == cur_key:
            continue
        if e.get("claim") == cur_claim:
            same_claim_pool.append(e)
        elif cur_claim_type and (e.get("claim_type") or "").strip() == cur_claim_type:
            # Same domain, different claim
            same_domain_pool.append(e)

    if not same_claim_pool and not same_domain_pool:
        from arena.claim_metadata import get_domain_display
        _dom_display, _ = get_domain_display(cur_claim_type)
        st.info(
            f"No related episodes yet. Run the same claim again with different models "
            f"to populate this view. Episodes on other **{_dom_display}** claims would "
            f"also appear here once you have them."
        )
        return

    st.caption(
        "Pick candidates from the same claim (cleanest comparison — isolates model) "
        "or other claims in the same domain (isolates claim-specific behavior). "
        "Different-domain claims are excluded — they confound the topic and the model."
    )

    # ── Build the combined candidate list with relationship labels ────────
    # Each entry: (display_label, ep_dict, relationship)
    candidates: list[tuple[str, dict, str]] = []
    for e in same_claim_pool:
        candidates.append((f"[Same claim] {_ep_summary_label(e)}", e, "same_claim"))
    for e in same_domain_pool:
        candidates.append((f"[Same domain] {_ep_summary_label(e)}", e, "same_domain"))

    st.markdown(
        f'<div class="rp-section-label">'
        f'{len(same_claim_pool)} on this exact claim · {len(same_domain_pool)} in same domain'
        f'</div>',
        unsafe_allow_html=True,
    )

    options = [c[0] for c in candidates]
    # Default selection: prefer a same-claim entry if any exist
    default = [options[0]] if options else []
    selections = st.multiselect(
        "Choose 1–2 episodes to compare against the current one",
        options=options,
        default=default,
        max_selections=2,
        key="compare_multi_auto",
    )

    if not selections:
        st.caption("Pick at least one episode above to see a side-by-side comparison.")
        return

    # Resolve selections back to (ep, relationship)
    chosen = [c for c in candidates if c[0] in selections]
    chosen_eps = [c[1] for c in chosen]
    chosen_rels = [c[2] for c in chosen]
    # Mode is "same_domain" if ANY selection is cross-claim; otherwise same_claim
    comparison_mode = "same_domain" if "same_domain" in chosen_rels else "same_claim"

    grid = [(selected_ep, "Current")] + [(ep, f"Comparison {i + 1}") for i, ep in enumerate(chosen_eps)]

    st.markdown('<div class="rp-compare-vs">Side-by-side</div>', unsafe_allow_html=True)
    cols = st.columns(len(grid))
    for col, (ep, label) in zip(cols, grid):
        with col:
            _render_compare_card(ep, label)

    # The three widgets below (tactic-by-tactic table, dimension heatmap,
    # turn-by-turn transcript alignment) only make sense for same-claim
    # comparisons — they assume tactics, dimensions, and turn positions
    # are directly comparable. In same-domain mode the claims differ,
    # so we swap in cross-claim-appropriate views instead.
    if comparison_mode == "same_domain":
        _render_same_domain_widgets(grid)
        _summary = _build_comparison_summary(grid, mode=comparison_mode)
        if _summary:
            st.markdown(
                f'<div style="background:var(--color-surface-alt,#1A1A1A);border:1px solid var(--color-border,#2A2A2A);'
                f'border-radius:6px;padding:0.9rem 1.1rem;margin-top:1rem;">'
                f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
                f'color:#9ca3af;font-weight:700;margin-bottom:0.4rem;">What this comparison shows</div>'
                f'<div style="font-size:0.92rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">{_summary}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        return  # don't fall through to same-claim widgets

    # ──────────────────────────────────────────────────────────────────
    # Tactic-by-tactic comparison strip — every tactic, every turn,
    # every chip clickable. Turn chips jump to the matching transcript
    # block below for that exact episode.
    # ──────────────────────────────────────────────────────────────────
    _grid_eps = [ep for ep, _ in grid]
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Tactic comparison</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Every tactic each side used across the selected matchups. "
        "Click any turn chip to jump to where that tactic appeared."
    )

    def _per_turn_tactics_for_side(ep, sa_key):
        """Build {tactic_plain: sorted[turn_ints]} from per_turn_strategies."""
        out: dict[str, set] = {}
        for entry in (ep.get("per_turn_strategies") or []):
            t = entry.get("turn", entry.get("turn_index"))
            try:
                t_int = int(t)
            except (TypeError, ValueError):
                continue
            for s in (entry.get(sa_key) or []):
                plain = _label_plain(s)
                if not plain:
                    continue
                out.setdefault(plain, set()).add(t_int)
        return {k: sorted(v) for k, v in out.items()}

    def _agg_tactics_for_side(ep, sa_key):
        """Plain-label set from the episode-level strategy_analysis aggregate."""
        sa = ep.get("strategy_analysis") or {}
        return {_label_plain(s) for s in (sa.get(sa_key) or []) if s}

    def _render_all_tactics_table(role_label, sa_key, color):
        ep_per_turn = [_per_turn_tactics_for_side(ep, sa_key) for ep, _ in grid]
        ep_agg = [_agg_tactics_for_side(ep, sa_key) for ep, _ in grid]

        # Source of truth = per_turn_strategies. Aggregate-only labels get
        # filtered out because they have no turn anchor to jump to.
        all_tactics: set[str] = set()
        for m in ep_per_turn:
            all_tactics.update(m.keys())

        # Legacy fallback: if NOTHING in the grid has per-turn data,
        # fall back to the aggregate set so the table isn't empty for
        # older episodes.
        any_per_turn = any(ep_per_turn)
        if not any_per_turn:
            for s in ep_agg:
                all_tactics.update(s)

        if not all_tactics:
            st.caption(f"No tactics recorded for {role_label.lower()}.")
            return

        def _total_count(tac):
            return sum(len(m.get(tac, [])) for m in ep_per_turn)

        sorted_tactics = sorted(all_tactics, key=lambda t: (-_total_count(t), t.lower()))

        hdr_html = (
            f'<th style="text-align:left;padding:0.45rem 0.65rem;font-size:0.72rem;'
            f'text-transform:uppercase;letter-spacing:0.07em;color:{color};font-weight:700;'
            f'border-bottom:2px solid var(--color-border,#2A2A2A);min-width:220px">'
            f'{role_label} tactic</th>'
        )
        for ep, label in grid:
            hdr_html += (
                f'<th style="text-align:left;padding:0.45rem 0.65rem;font-size:0.7rem;'
                f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                f'border-bottom:2px solid var(--color-border,#2A2A2A)">{label}</th>'
            )

        rows_html = ""
        for tactic in sorted_tactics:
            # Resolve a definition for this tactic so the row label can
            # carry it as a native browser tooltip. The HTML title attr
            # appears on hover without changing the layout.
            tactic_raw = tactic.lower().replace(" ", "_")
            tactic_desc = resolve_strategy_description(tactic_raw, primary_lookup=_STRATEGY_CONTEXT)
            title_attr = (
                f' title="{tactic_desc.replace(chr(34), chr(39))}"' if tactic_desc else ""
            )
            marker = ' <span style="color:#9ca3af;font-size:0.72rem">ⓘ</span>' if tactic_desc else ""
            rows_html += (
                f'<tr><td style="padding:0.45rem 0.65rem;color:var(--color-text-primary,#E8E4D9);'
                f'font-size:0.86rem;font-weight:500;border-bottom:1px solid var(--color-border,#2A2A2A);'
                f'cursor:help"{title_attr}>{tactic}{marker}</td>'
            )
            for ep_i, (ep, _lbl) in enumerate(grid):
                turns = ep_per_turn[ep_i].get(tactic, [])
                if turns:
                    chips = " ".join(
                        f'<a href="#cmp-ep{ep_i}-t{t}" '
                        f'style="display:inline-block;padding:0.1rem 0.5rem;margin:0.08rem 0.18rem 0.08rem 0;'
                        f'background:{color}22;color:{color};border:1px solid {color}66;border-radius:3px;'
                        f'font-family:\'IBM Plex Mono\',monospace;font-size:0.74rem;font-weight:700;'
                        f'text-decoration:none;cursor:pointer">T{t}</a>'
                        for t in turns
                    )
                    cell = chips
                else:
                    cell = '<span style="color:#3a3a3a;font-size:0.95rem">·</span>'
                rows_html += (
                    f'<td style="padding:0.35rem 0.65rem;'
                    f'border-bottom:1px solid var(--color-border,#2A2A2A)">{cell}</td>'
                )
            rows_html += '</tr>'

        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);'
            f'border-radius:6px;overflow:hidden;margin:0 0 0.9rem 0">'
            f'<thead><tr>{hdr_html}</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )

    _render_all_tactics_table("Spreader", "spreader_strategies", SPREADER_COLOR)
    _render_all_tactics_table("Fact-checker", "debunker_strategies", DEBUNKER_COLOR)

    # ──────────────────────────────────────────────────────────────────
    # Citation comparison — every cited institution, every turn it was
    # mentioned, every chip clickable. Mirrors the Tactic table.
    # ──────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Citation comparison</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Every named institution each side cited, with the turns it appeared in. "
        "Click any turn chip to jump to where it was cited."
    )

    def _per_turn_citations_for_side(ep, side_key):
        """{canonical_source: sorted[turn_ints]} by scanning each turn's text."""
        out: dict[str, set] = {}
        for i, p in enumerate(_normalize_turn_pairs(ep)):
            try:
                t_int = int(p.get("pair_idx", i + 1))
            except (TypeError, ValueError):
                t_int = i + 1
            text = (p.get(f"{side_key}_text") or "")
            if not text:
                continue
            cited = set()
            for src, pat in _SOURCE_PATTERNS.items():
                if pat.search(text):
                    cited.add(_canonical_source(src))
            for c in cited:
                out.setdefault(c, set()).add(t_int)
        return {k: sorted(v) for k, v in out.items()}

    def _render_all_citations_table(role_label, side_key, color):
        ep_data = [_per_turn_citations_for_side(ep, side_key) for ep, _ in grid]

        all_cites: set[str] = set()
        for m in ep_data:
            all_cites.update(m.keys())

        if not all_cites:
            st.caption(f"No named institutions cited by {role_label.lower()}.")
            return

        def _total_count(c):
            return sum(len(m.get(c, [])) for m in ep_data)

        sorted_cites = sorted(all_cites, key=lambda c: (-_total_count(c), c.lower()))

        hdr_html = (
            f'<th style="text-align:left;padding:0.45rem 0.65rem;font-size:0.72rem;'
            f'text-transform:uppercase;letter-spacing:0.07em;color:{color};font-weight:700;'
            f'border-bottom:2px solid var(--color-border,#2A2A2A);min-width:220px">'
            f'{role_label} citation</th>'
        )
        for ep, label in grid:
            hdr_html += (
                f'<th style="text-align:left;padding:0.45rem 0.65rem;font-size:0.7rem;'
                f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                f'border-bottom:2px solid var(--color-border,#2A2A2A)">{label}</th>'
            )

        rows_html = ""
        for src in sorted_cites:
            # Surface a hover tooltip with the institution blurb.
            inst_info = get_institution_info(src)
            title_attr = (
                f' title="{inst_info.replace(chr(34), chr(39))}"' if inst_info else ""
            )
            marker = ' <span style="color:#9ca3af;font-size:0.72rem">ⓘ</span>' if inst_info else ""
            rows_html += (
                f'<tr><td style="padding:0.45rem 0.65rem;color:var(--color-text-primary,#E8E4D9);'
                f'font-size:0.86rem;font-weight:500;border-bottom:1px solid var(--color-border,#2A2A2A);'
                f'cursor:help"{title_attr}>{src}{marker}</td>'
            )
            for ep_i, _ in enumerate(grid):
                turns = ep_data[ep_i].get(src, [])
                if turns:
                    chips = " ".join(
                        f'<a href="#cmp-ep{ep_i}-t{t}" '
                        f'style="display:inline-block;padding:0.1rem 0.5rem;margin:0.08rem 0.18rem 0.08rem 0;'
                        f'background:{color}22;color:{color};border:1px solid {color}66;border-radius:3px;'
                        f'font-family:\'IBM Plex Mono\',monospace;font-size:0.74rem;font-weight:700;'
                        f'text-decoration:none;cursor:pointer">T{t}</a>'
                        for t in turns
                    )
                    cell = chips
                else:
                    cell = '<span style="color:#3a3a3a;font-size:0.95rem">·</span>'
                rows_html += (
                    f'<td style="padding:0.35rem 0.65rem;'
                    f'border-bottom:1px solid var(--color-border,#2A2A2A)">{cell}</td>'
                )
            rows_html += '</tr>'

        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);'
            f'border-radius:6px;overflow:hidden;margin:0 0 0.9rem 0">'
            f'<thead><tr>{hdr_html}</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )

    _render_all_citations_table("Spreader", "spreader", SPREADER_COLOR)
    _render_all_citations_table("Fact-checker", "debunker", DEBUNKER_COLOR)

    # ──────────────────────────────────────────────────────────────────
    # Per-dimension delta heatmap
    # ──────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Dimension deltas (Fact-checker − Spreader)</div>',
        unsafe_allow_html=True,
    )
    st.caption("Green = fact-checker advantage. Amber = spreader advantage. Sized by gap.")

    # Collect dimension names (union across all selected episodes)
    _dim_set = []
    _dim_seen = set()
    for ep, _l in grid:
        for s in (ep.get("results", {}).get("scorecard", []) or []):
            m = s.get("metric", "")
            if m and m not in _dim_seen:
                _dim_seen.add(m)
                _dim_set.append(m)

    if _dim_set:
        _hm_hdr = '<th style="text-align:left;padding:0.4rem 0.6rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700"></th>'
        for ep, label in grid:
            _hm_hdr += (
                f'<th style="text-align:center;padding:0.4rem 0.6rem;font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.07em;color:#9ca3af;font-weight:700">{label}</th>'
            )
        _hm_rows = ""
        for dim in _dim_set:
            _hm_rows += f'<tr><td style="padding:0.4rem 0.6rem;color:var(--color-text-primary,#E8E4D9);font-size:0.84rem">{_label(dim)}</td>'
            for ep, _l in grid:
                _sc = ep.get("results", {}).get("scorecard", []) or []
                _entry = next((s for s in _sc if s.get("metric") == dim), None)
                if _entry is None:
                    _hm_rows += '<td style="padding:0.4rem 0.6rem;text-align:center;color:#6b7280">—</td>'
                    continue
                d = float(_entry.get("debunker", 0) or 0) - float(_entry.get("spreader", 0) or 0)
                # Map |d| (typically 0–10) to alpha 0.1–0.9
                _alpha = min(0.85, 0.10 + abs(d) / 10 * 0.75)
                if d > 0.1:
                    bg = f"rgba(46,204,113,{_alpha:.2f})"
                    fg = "#FFFFFF" if _alpha > 0.45 else "#2ECC71"
                elif d < -0.1:
                    bg = f"rgba(212,168,67,{_alpha:.2f})"
                    fg = "#FFFFFF" if _alpha > 0.45 else SPREADER_COLOR
                else:
                    bg = "rgba(128,128,128,0.10)"
                    fg = "#9ca3af"
                _hm_rows += (
                    f'<td style="padding:0.4rem 0.6rem;text-align:center;background:{bg};color:{fg};'
                    f'font-family:\'IBM Plex Mono\',monospace;font-size:0.84rem;font-weight:600">{d:+.1f}</td>'
                )
            _hm_rows += '</tr>'
        st.markdown(
            f'<table style="width:100%;border-collapse:separate;border-spacing:2px;">'
            f'<thead><tr>{_hm_hdr}</tr></thead><tbody>{_hm_rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    # ──────────────────────────────────────────────────────────────────
    # Transcript snippet alignment — every turn, side-by-side
    # ──────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">Turn-by-turn — how each matchup argued</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Each turn shown side-by-side across the selected matchups. Reading down a column "
        "follows one debate; reading across a row compares how different models handled the same turn."
    )

    # Pre-compute the turn pairs for every grid episode once.
    _grid_pairs = []
    for ep, label in grid:
        cfg = ep.get("config_snapshot", {}).get("agents", {})
        _spr_m = _short(cfg.get("spreader", {}).get("model", "?"))
        _deb_m = _short(cfg.get("debunker", {}).get("model", "?"))
        _grid_pairs.append({
            "label":  label,
            "spr_m":  _spr_m,
            "deb_m":  _deb_m,
            "pairs":  _normalize_turn_pairs(ep),
        })

    _max_turns = max((len(g["pairs"]) for g in _grid_pairs), default=0)

    if _max_turns == 0:
        st.caption("No transcript data on any of the compared episodes.")
    else:
        # Column headers — one per episode
        _hdr_cols = st.columns(len(_grid_pairs))
        for col, g in zip(_hdr_cols, _grid_pairs):
            with col:
                st.markdown(
                    f'<div style="font-size:0.7rem;color:#9ca3af;text-transform:uppercase;'
                    f'letter-spacing:0.07em;font-weight:700;padding:0.4rem 0;'
                    f'border-bottom:2px solid var(--color-border,#2A2A2A);margin-bottom:0.5rem">'
                    f'{g["label"]} · {g["spr_m"]} vs {g["deb_m"]}</div>',
                    unsafe_allow_html=True,
                )

        # One row per turn
        for turn_idx in range(_max_turns):
            st.markdown(
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.74rem;'
                f'color:#9ca3af;font-weight:700;letter-spacing:0.08em;'
                f'margin:0.8rem 0 0.3rem 0;text-transform:uppercase;">TURN {turn_idx + 1}</div>',
                unsafe_allow_html=True,
            )
            _row_cols = st.columns(len(_grid_pairs))
            for ep_i, (col, g) in enumerate(zip(_row_cols, _grid_pairs)):
                with col:
                    # Anchor target for the tactic-comparison links above —
                    # one anchor per (episode, turn) pair. scroll-margin gives
                    # the jump a little breathing room beneath the sticky header.
                    _anchor = f"cmp-ep{ep_i}-t{turn_idx + 1}"
                    st.markdown(
                        f'<div id="{_anchor}" style="scroll-margin-top:80px"></div>',
                        unsafe_allow_html=True,
                    )
                    if turn_idx >= len(g["pairs"]):
                        st.markdown(
                            f'<div style="font-size:0.82rem;color:#6b7280;font-style:italic;'
                            f'padding:0.4rem 0">— debate ended at turn {len(g["pairs"])} —</div>',
                            unsafe_allow_html=True,
                        )
                        continue
                    _p = g["pairs"][turn_idx]
                    _spr_t = (_p.get("spreader_text") or "").strip() or "—"
                    _deb_t = (_p.get("debunker_text") or "").strip() or "—"
                    st.markdown(
                        f'<div style="font-size:0.7rem;color:{SPREADER_COLOR};font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.15rem">Spreader</div>'
                        f'<div style="font-size:0.84rem;line-height:1.55;background:rgba(212,168,67,0.05);'
                        f'border-left:3px solid {SPREADER_COLOR};border-radius:0 4px 4px 0;'
                        f'padding:0.55rem 0.7rem;margin-bottom:0.5rem;color:var(--color-text-primary,#E8E4D9);'
                        f'white-space:pre-wrap">{_spr_t}</div>'
                        f'<div style="font-size:0.7rem;color:{DEBUNKER_COLOR};font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.15rem">Fact-checker</div>'
                        f'<div style="font-size:0.84rem;line-height:1.55;background:rgba(74,127,165,0.05);'
                        f'border-left:3px solid {DEBUNKER_COLOR};border-radius:0 4px 4px 0;'
                        f'padding:0.55rem 0.7rem;color:var(--color-text-primary,#E8E4D9);'
                        f'white-space:pre-wrap">{_deb_t}</div>',
                        unsafe_allow_html=True,
                    )

    # ──────────────────────────────────────────────────────────────────
    # Auto-generated interpretation footer
    # ──────────────────────────────────────────────────────────────────
    _summary = _build_comparison_summary(grid, mode=comparison_mode)
    if _summary:
        st.markdown(
            f'<div style="background:var(--color-surface-alt,#1A1A1A);border:1px solid var(--color-border,#2A2A2A);'
            f'border-radius:6px;padding:0.9rem 1.1rem;margin-top:1rem;">'
            f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'color:#9ca3af;font-weight:700;margin-bottom:0.4rem;">What this comparison shows</div>'
            f'<div style="font-size:0.92rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">{_summary}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_same_domain_widgets(grid: list) -> None:
    """Cross-claim within-domain widgets.

    Replaces the model-fingerprint widgets (which assume same claim) with
    views that answer the questions a user actually has when looking at
    two different claims in the same domain:
        1. Tactic consistency / divergence per side
        2. Citation continuity per side
        3. Per-side fingerprint metrics (hedge rate, citations, etc.)
    """
    grid_labels = [lbl for _ep, lbl in grid]
    grid_eps    = [ep for ep, _lbl in grid]

    # ── 1. Tactic consistency ─────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">'
        'Tactic consistency — what each side did on each claim'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Each tactic the side used in any of the selected claims. ✓ marks where "
        "they used it. Tactics with ✓ in every column are domain-consistent; "
        "tactics in only one column are claim-specific."
    )

    def _render_tactic_consistency(side_key, side_label, color):
        # Collect tactics per episode for this side
        tactics_per_ep = []
        for ep in grid_eps:
            sa = ep.get("strategy_analysis") or {}
            raws = sa.get(f"{side_key}_strategies") or []
            tactics_per_ep.append({_label_plain(t) for t in raws if t})
        all_tactics = sorted({t for s in tactics_per_ep for t in s})
        if not all_tactics:
            st.caption(f"— no {side_label.lower()} tactics recorded —")
            return
        consistent = [t for t in all_tactics if all(t in s for s in tactics_per_ep)]
        unique = [t for t in all_tactics if sum(1 for s in tactics_per_ep if t in s) == 1]

        # Header chip with counts
        st.markdown(
            f'<div style="font-size:0.74rem;color:{color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin:0.4rem 0 0.3rem 0">'
            f'{side_label} · {len(all_tactics)} unique tactic{"s" if len(all_tactics) != 1 else ""} · '
            f'<span style="color:#16a34a">{len(consistent)} consistent</span> · '
            f'<span style="color:#D4A843">{len(unique)} claim-specific</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _hdr = '<th style="text-align:left;padding:0.4rem 0.5rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;border-bottom:2px solid var(--color-border,#2A2A2A)">Tactic</th>'
        for lbl in grid_labels:
            _hdr += (
                f'<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.7rem;'
                f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                f'border-bottom:2px solid var(--color-border,#2A2A2A)">{lbl}</th>'
            )
        _rows = ""
        for tac in all_tactics:
            uses = [tac in s for s in tactics_per_ep]
            all_use = all(uses)
            row_bg = "rgba(22,163,74,0.06)" if all_use else "transparent"
            _rows += f'<tr style="background:{row_bg}"><td style="padding:0.35rem 0.5rem;color:{color};font-size:0.85rem;font-weight:500;border-bottom:1px solid var(--color-border,#2A2A2A)">{tac}</td>'
            for u in uses:
                if u:
                    _rows += (
                        f'<td style="padding:0.35rem 0.5rem;text-align:center;'
                        f'color:#16a34a;font-weight:700;font-size:0.95rem;'
                        f'border-bottom:1px solid var(--color-border,#2A2A2A)">✓</td>'
                    )
                else:
                    _rows += (
                        f'<td style="padding:0.35rem 0.5rem;text-align:center;'
                        f'color:#3a3a3a;font-size:0.95rem;'
                        f'border-bottom:1px solid var(--color-border,#2A2A2A)">·</td>'
                    )
            _rows += '</tr>'
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);'
            f'border-radius:6px;overflow:hidden;margin-bottom:0.8rem">'
            f'<thead><tr>{_hdr}</tr></thead><tbody>{_rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    _render_tactic_consistency("spreader", "Spreader", SPREADER_COLOR)
    _render_tactic_consistency("debunker", "Fact-checker", DEBUNKER_COLOR)

    # ── 2. Citation continuity ────────────────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">'
        'Citation continuity — what each side cited on each claim'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Each named institution that side mentioned in any of the selected claims. "
        "Sources cited in every column = consistent reliance. Only one column = "
        "claim-specific sourcing."
    )

    def _render_citation_continuity(side_key, side_label, color):
        cites_per_ep = []
        for ep in grid_eps:
            pairs = _normalize_turn_pairs(ep)
            text = " ".join((p.get(f"{side_key}_text") or "") for p in pairs)
            cited = set()
            for src, pat in _SOURCE_PATTERNS.items():
                if pat.search(text):
                    cited.add(_canonical_source(src))
            cites_per_ep.append(cited)
        all_cites = sorted({c for s in cites_per_ep for c in s})
        if not all_cites:
            st.caption(f"— no named institutions cited by {side_label.lower()} —")
            return
        consistent = [c for c in all_cites if all(c in s for s in cites_per_ep)]
        unique = [c for c in all_cites if sum(1 for s in cites_per_ep if c in s) == 1]

        st.markdown(
            f'<div style="font-size:0.74rem;color:{color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin:0.4rem 0 0.3rem 0">'
            f'{side_label} · {len(all_cites)} unique institution{"s" if len(all_cites) != 1 else ""} · '
            f'<span style="color:#16a34a">{len(consistent)} consistent</span> · '
            f'<span style="color:#D4A843">{len(unique)} claim-specific</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _hdr = '<th style="text-align:left;padding:0.4rem 0.5rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;border-bottom:2px solid var(--color-border,#2A2A2A)">Institution</th>'
        for lbl in grid_labels:
            _hdr += (
                f'<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.7rem;'
                f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                f'border-bottom:2px solid var(--color-border,#2A2A2A)">{lbl}</th>'
            )
        _rows = ""
        for src in all_cites:
            uses = [src in s for s in cites_per_ep]
            all_use = all(uses)
            row_bg = "rgba(22,163,74,0.06)" if all_use else "transparent"
            _rows += (
                f'<tr style="background:{row_bg}">'
                f'<td style="padding:0.35rem 0.5rem;color:var(--color-text-primary,#E8E4D9);'
                f'font-size:0.85rem;font-weight:500;border-bottom:1px solid var(--color-border,#2A2A2A)">{src}</td>'
            )
            for u in uses:
                if u:
                    _rows += (
                        f'<td style="padding:0.35rem 0.5rem;text-align:center;'
                        f'color:#16a34a;font-weight:700;font-size:0.95rem;'
                        f'border-bottom:1px solid var(--color-border,#2A2A2A)">✓</td>'
                    )
                else:
                    _rows += (
                        f'<td style="padding:0.35rem 0.5rem;text-align:center;'
                        f'color:#3a3a3a;font-size:0.95rem;'
                        f'border-bottom:1px solid var(--color-border,#2A2A2A)">·</td>'
                    )
            _rows += '</tr>'
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);'
            f'border-radius:6px;overflow:hidden;margin-bottom:0.8rem">'
            f'<thead><tr>{_hdr}</tr></thead><tbody>{_rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    _render_citation_continuity("spreader", "Spreader", SPREADER_COLOR)
    _render_citation_continuity("debunker", "Fact-checker", DEBUNKER_COLOR)

    # ── 3. Per-side fingerprint metrics ───────────────────────────────
    st.markdown(
        '<div class="rp-section-label" style="margin-top:1.4rem">'
        'Per-side fingerprint metrics'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Behavioural metrics that should be stable if the model has a domain-level "
        "playbook. Values that track tightly across claims = consistent style; values "
        "that diverge = claim-specific adaptation."
    )

    def _metrics_for(ep, side_key):
        pairs = _normalize_turn_pairs(ep)
        text = " ".join((p.get(f"{side_key}_text") or "") for p in pairs).strip()
        word_count = max(len(text.split()), 1)
        hedges = len(_HEDGING.findall(text))
        hedge_per_1k = hedges / word_count * 1000
        cited = set()
        for src, pat in _SOURCE_PATTERNS.items():
            if pat.search(text):
                cited.add(_canonical_source(src))
        sa = ep.get("strategy_analysis") or {}
        tac_set = {_label_plain(t) for t in (sa.get(f"{side_key}_strategies") or []) if t}
        pts = ep.get("per_turn_strategies") or []
        if pts and len(pts) > 1:
            adapt_count = sum(1 for t in pts if t.get(f"{side_key}_adapted"))
            adapt_rate = adapt_count / max(len(pts) - 1, 1)
        else:
            adapt_rate = None
        res = ep.get("results", {})
        totals = res.get("totals", {}) or {}
        my_score = float(totals.get("spreader" if side_key == "spreader" else "debunker", 0) or 0)
        their_score = float(totals.get("debunker" if side_key == "spreader" else "spreader", 0) or 0)
        margin = my_score - their_score
        return {
            "hedge_per_1k": hedge_per_1k,
            "citations":   len(cited),
            "tactic_div":  len(tac_set),
            "adapt_rate":  adapt_rate,
            "margin":      margin,
        }

    _METRIC_ROWS = [
        ("Hedge rate",       "hedge_per_1k", lambda v: f"{v:.1f}/1k"),
        ("Institutions cited", "citations",  lambda v: f"{v}"),
        ("Tactic diversity", "tactic_div",   lambda v: f"{v}"),
        ("Adaptation rate",  "adapt_rate",   lambda v: f"{v*100:.0f}%" if v is not None else "—"),
        ("Score margin",     "margin",       lambda v: f"{v:+.1f}"),
    ]

    def _render_fingerprint_block(side_key, side_label, color):
        st.markdown(
            f'<div style="font-size:0.74rem;color:{color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin:0.5rem 0 0.3rem 0">'
            f'{side_label}</div>',
            unsafe_allow_html=True,
        )
        metrics_per_ep = [_metrics_for(ep, side_key) for ep in grid_eps]

        _hdr = '<th style="text-align:left;padding:0.4rem 0.6rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;border-bottom:2px solid var(--color-border,#2A2A2A)">Metric</th>'
        for lbl in grid_labels:
            _hdr += (
                f'<th style="text-align:center;padding:0.4rem 0.6rem;font-size:0.7rem;'
                f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                f'border-bottom:2px solid var(--color-border,#2A2A2A)">{lbl}</th>'
            )
        _rows = ""
        for label_h, key, fmt in _METRIC_ROWS:
            _rows += f'<tr><td style="padding:0.35rem 0.6rem;color:var(--color-text-primary,#E8E4D9);font-size:0.85rem;border-bottom:1px solid var(--color-border,#2A2A2A)">{label_h}</td>'
            # Determine variance to color-code: if values span <20% of max, call it "consistent"
            numeric_vals = [m[key] for m in metrics_per_ep if isinstance(m[key], (int, float))]
            consistent_flag = False
            if numeric_vals and len(numeric_vals) == len(metrics_per_ep):
                spread = max(numeric_vals) - min(numeric_vals)
                base = max(abs(max(numeric_vals)), abs(min(numeric_vals)), 1)
                if spread / base < 0.20:
                    consistent_flag = True
            for m in metrics_per_ep:
                val_disp = fmt(m[key])
                cell_color = "#16a34a" if consistent_flag and isinstance(m[key], (int, float)) else "var(--color-text-primary,#E8E4D9)"
                _rows += (
                    f'<td style="padding:0.35rem 0.6rem;text-align:center;'
                    f'font-family:\'IBM Plex Mono\',monospace;font-size:0.84rem;'
                    f'color:{cell_color};border-bottom:1px solid var(--color-border,#2A2A2A)">'
                    f'{val_disp}</td>'
                )
            _rows += '</tr>'
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:var(--color-surface,#111);'
            f'border-radius:6px;overflow:hidden;margin-bottom:0.6rem">'
            f'<thead><tr>{_hdr}</tr></thead><tbody>{_rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    _render_fingerprint_block("spreader", "Spreader", SPREADER_COLOR)
    _render_fingerprint_block("debunker", "Fact-checker", DEBUNKER_COLOR)
    st.caption(
        "Values shown in green = tightly consistent across claims (variance < 20% of max). "
        "Other values mean the metric varies meaningfully claim-to-claim."
    )


def _build_comparison_summary(grid: list, mode: str = "same_claim") -> str:
    """Generate a one-paragraph interpretation of the comparison.

    Branches on mode (auto-detected from the user's selections in the
    caller): 'same_claim' isolates the model variable; 'same_domain'
    isolates claim-specific behavior within a controlled topic area.
    """
    if len(grid) < 2:
        return ""
    sentences = []

    # Outcome summary
    winners = []
    for ep, lbl in grid:
        w = (ep.get("results", {}).get("winner") or "?").lower()
        winners.append(w)
    debunker_wins = sum(1 for w in winners if w == "debunker")
    spreader_wins = sum(1 for w in winners if w == "spreader")
    total = len(grid)
    if debunker_wins == total:
        sentences.append("The fact-checker won every matchup.")
    elif spreader_wins == total:
        sentences.append("The spreader won every matchup.")
    elif debunker_wins > 0 and spreader_wins > 0:
        sentences.append(f"Outcomes split: {debunker_wins} fact-checker / {spreader_wins} spreader.")

    if mode == "same_domain":
        # Cross-claim within one domain — look at tactic consistency by side
        from arena.claim_metadata import get_domain_display
        dom_display, _ = get_domain_display((grid[0][0].get("claim_type") or ""))
        claim_lines = []
        for ep, lbl in grid:
            sa = ep.get("strategy_analysis") or {}
            tac_spr = _label_plain(sa.get("spreader_primary", "")) or "—"
            tac_deb = _label_plain(sa.get("debunker_primary", "")) or "—"
            claim_short = (ep.get("claim") or "")[:60]
            claim_lines.append(
                f"On <i>&ldquo;{claim_short}…&rdquo;</i>: spreader=<b>{tac_spr}</b>, "
                f"fact-checker=<b>{tac_deb}</b>"
            )
        sentences.append(
            f"Within the <b>{dom_display}</b> domain, each side's primary tactic per claim:"
        )
        for line in claim_lines:
            sentences.append("• " + line)
        sentences.append(
            "If tactics stay consistent across these different claims, you're seeing "
            "domain-level model behavior. If they vary, the model is adapting to "
            "claim-specific features even within the same topic area."
        )
    else:
        # Same claim, different models — the canonical F2 fingerprint test
        tactics = []
        for ep, lbl in grid:
            sa = ep.get("strategy_analysis") or {}
            tac = _label_plain(sa.get("spreader_primary", "")) or "—"
            cfg = ep.get("config_snapshot", {}).get("agents", {})
            spr_m = _short(cfg.get("spreader", {}).get("model", "?"))
            tactics.append(f"<b>{spr_m}</b> leaned on <b>{tac}</b>")
        distinct_tactics = set(t.split("<b>")[2] for t in tactics if t.count("<b>") >= 2)
        if len(distinct_tactics) > 1:
            sentences.append(
                "Different models picked different opening tactics: "
                + "; ".join(tactics) + "."
            )
            sentences.append(
                "This is the model-fingerprint effect (F2): training shapes which rhetorical "
                "patterns a model defaults to, even with identical instructions on the same claim."
            )

    # Margin spread
    margins = []
    for ep, lbl in grid:
        t = ep.get("results", {}).get("totals", {}) or {}
        margins.append((t.get("debunker", 0) or 0) - (t.get("spreader", 0) or 0))
    if margins and max(margins) - min(margins) > 1.5:
        sentences.append(
            f"Score margins ranged from <b>{min(margins):+.1f}</b> to <b>{max(margins):+.1f}</b> — "
            f"the matchup matters even when the winner doesn't change."
        )

    return " ".join(sentences) if sentences else ""


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_explore_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    inject_replay_css()
    _inject_styles()

    st.markdown('<p class="rp-title">Episode Replay</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-subtitle">'
        'Select an episode to view the verdict, download the transcript, '
        'analyze strategies, inspect citations, or compare with other matchups on the same claim.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load data
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No episodes yet. Run a debate in the Arena tab first.")
        return

    episodes = _load_all_episodes(tuple(run_ids), RUNS_DIR, token)
    if not episodes:
        st.info("No episodes found.")
        return

    # ── Episode table (7 columns: Domain + Falsifiability up front)
    from arena.claim_metadata import get_domain_display, classify_falsifiability
    _FALS_DISPLAY = {
        "falsifiable":   "Falsifiable",
        "unfalsifiable": "Unfalsifiable",
        "unknown":       "—",
    }
    table_rows = []
    for i, ep in enumerate(episodes):
        t = ep.get("results", {}).get("totals", {})
        margin = (t.get("debunker", 0) or 0) - (t.get("spreader", 0) or 0)
        cfg = ep.get("config_snapshot", {}).get("agents", {})
        domain_display, _domain_color = get_domain_display(ep.get("claim_type", ""))
        fals_label, _ = classify_falsifiability(ep.get("claim", ""))
        table_rows.append({
            "idx": i,
            "Domain": domain_display,
            "Falsifiable?": _FALS_DISPLAY.get(fals_label, "—"),
            "Claim": ep.get("claim", "")[:40] + ("..." if len(ep.get("claim", "")) > 40 else ""),
            "Spreader": _short(cfg.get("spreader", {}).get("model", "")),
            "Fact-checker": _short(cfg.get("debunker", {}).get("model", "")),
            "Winner": ep.get("results", {}).get("winner", "").title(),
            "Margin": f"{margin:+.1f}",
        })

    table_df = pd.DataFrame(table_rows)
    display_df = table_df.drop(columns=["idx"])

    # ── Build a colored Styler so the categorical columns read at a glance ──
    from arena.claim_metadata import _DOMAIN_DISPLAY as _DOMAIN_MAP
    # Build a {display_name: hex_color} lookup from the (display, color) tuples
    _domain_color_by_display = {disp: col for disp, col in _DOMAIN_MAP.values()}

    def _rgb_tuple(hex_color: str):
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            return 128, 128, 128

    def _style_domain_cell(val):
        color = _domain_color_by_display.get(val)
        if not color:
            return ""
        r, g, b = _rgb_tuple(color)
        return (
            f"background-color: rgba({r},{g},{b},0.18); color: {color}; "
            f"font-weight: 600; text-align: center;"
        )

    def _style_falsifiable_cell(val):
        if val == "Falsifiable":
            return ("background-color: rgba(22,163,74,0.18); color: #16a34a; "
                    "font-weight: 600; text-align: center;")
        if val == "Unfalsifiable":
            return ("background-color: rgba(212,168,67,0.18); color: #D4A843; "
                    "font-weight: 600; text-align: center;")
        return "color: #6b7280; text-align: center;"

    def _style_winner_cell(val):
        if val == "Debunker":
            return "color: #16a34a; font-weight: 600;"
        if val == "Spreader":
            return "color: #D4A843; font-weight: 600;"
        if val == "Draw":
            return "color: #9ca3af; font-style: italic;"
        return ""

    def _style_margin_cell(val):
        try:
            v = float(val)
        except (ValueError, TypeError):
            return ""
        if v >= 1.0:
            return "color: #16a34a; font-weight: 600; font-family: 'IBM Plex Mono', monospace;"
        if v <= -1.0:
            return "color: #D4A843; font-weight: 600; font-family: 'IBM Plex Mono', monospace;"
        return "color: #9ca3af; font-family: 'IBM Plex Mono', monospace;"

    styled = (display_df.style
              .map(_style_domain_cell,      subset=["Domain"])
              .map(_style_falsifiable_cell, subset=["Falsifiable?"])
              .map(_style_winner_cell,      subset=["Winner"])
              .map(_style_margin_cell,      subset=["Margin"]))

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=min(350, 60 + len(table_rows) * 35),
        key="rp_episode_table",
        column_config={
            "Domain": st.column_config.TextColumn("Domain", width="small"),
            "Falsifiable?": st.column_config.TextColumn("Falsifiable?", width="small"),
            "Claim": st.column_config.TextColumn("Claim", width="medium"),
            "Spreader": st.column_config.TextColumn("Spreader", width="small"),
            "Fact-checker": st.column_config.TextColumn("Fact-checker", width="small"),
            "Winner": st.column_config.TextColumn("Winner", width="small"),
            "Margin": st.column_config.TextColumn("Margin", width="small"),
        },
    )

    # ── Episode detail
    sel_rows = (event.selection.rows or []) if event.selection else []

    if not sel_rows:
        st.markdown(
            '<p style="font-size:0.9rem;color:#9ca3af;text-align:center;margin:2rem 0">'
            'Click a row above to view the episode.</p>',
            unsafe_allow_html=True,
        )
        return

    sel_idx = sel_rows[0]
    selected_ep = episodes[sel_idx]

    # Header
    cfg = selected_ep.get("config_snapshot", {}).get("agents", {})
    spr_m = _short(cfg.get("spreader", {}).get("model", ""))
    deb_m = _short(cfg.get("debunker", {}).get("model", ""))
    claim = selected_ep.get("claim", "")
    winner = selected_ep.get("results", {}).get("winner", "").title()

    from arena.claim_metadata import domain_badge_html, falsifiability_badge_html
    _domain_chip = domain_badge_html(selected_ep.get("claim_type", ""), size="md")
    _fals_chip   = falsifiability_badge_html(claim, size="md")
    st.markdown(f'<p class="rp-detail-header">{spr_m} vs {deb_m} · {winner} wins</p>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="rp-claim-box"><b>Claim:</b> {claim}<br>'
        f'<div style="margin-top:0.45rem;display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center">'
        f'{_domain_chip}{_fals_chip}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Detail tabs
    dt_verdict, dt_transcript, dt_strategy, dt_citations, dt_compare = st.tabs([
        "Verdict", "Transcript", "Strategy", "Citations", "Compare"
    ])

    with dt_verdict:
        _render_verdict(selected_ep)
    with dt_transcript:
        _render_transcript(selected_ep)
    with dt_strategy:
        _render_strategy(selected_ep)
    with dt_citations:
        _render_citations(selected_ep)
    with dt_compare:
        _render_comparison(selected_ep, episodes)
