"""
Explore Page — unified episode browser + detail viewer.

Top: Claim type context + filters + episode table
Bottom: Episode detail (Verdict, Transcript, Strategy, Citations)

Replaces the separate Explore and Replay tabs.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

import pandas as pd
import streamlit as st

from arena.io.run_store_v2_read import load_episodes
from arena.analysis.strategy_lens import extract_strategy_signals
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.components.replay_styles import inject_replay_css, verdict_card_html

RUNS_DIR = "runs"
SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"

_MODEL_SHORT = {
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4-20250514": "Claude Sonnet",
    "claude-sonnet-4": "Claude Sonnet",
    "gemini-2.5-flash": "Gemini Flash",
}

SIGNAL_LABELS = {
    "citation_like":          "Citations / source references",
    "numeric_specificity":    "Specific numbers & statistics",
    "causal_markers":         "Causal reasoning",
    "counterargument":        "Direct counterarguments",
    "rhetorical_questions":   "Rhetorical questions",
    "emotional_framing":      "Emotional framing",
    "conspiracy_framing":     "Conspiracy / distrust framing",
    "vague_sources":          "Vague or unnamed sources",
    "refutation_structure":   "Structured refutation",
    "uncertainty_calibration":"Acknowledgment of uncertainty",
}

_NAMED_SOURCES = [
    "CDC", "WHO", "FDA", "EPA", "NASA", "NIH", "IPCC",
    "Harvard", "Stanford", "MIT", "Oxford", "Yale", "Cambridge",
    "Nature", "Lancet", "Science", "JAMA", "BMJ", "NEJM",
    "Pew Research", "Gallup", "Reuters", "AP News", "BBC",
    "Amnesty International", "Human Rights Watch", "United Nations",
]


def _short(model: str) -> str:
    return _MODEL_SHORT.get(model, model[:15])

def _label(s: str) -> str:
    return (s or "").replace("_", " ").title()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_experiment_episodes(run_ids: tuple, runs_dir: str, token: float) -> list[dict]:
    episodes = []
    for run_id in run_ids:
        eps, _ = load_episodes(run_id, runs_dir, token)
        for ep in eps:
            if ep.get("study_id") != "experiment":
                continue
            if ep.get("results", {}).get("winner") == "error":
                continue
            if (ep.get("created_at") or "") < "2026-04-13T21":
                continue
            episodes.append(ep)
    return episodes


def _normalize_turn_pairs(ep: dict) -> list[dict]:
    """Convert episode turns to normalized pair format."""
    turns = ep.get("turns") or []
    pairs = []
    for i, t in enumerate(turns):
        if "spreader_message" in t or "debunker_message" in t:
            s_msg = t.get("spreader_message") or {}
            d_msg = t.get("debunker_message") or {}
            pairs.append({
                "pair_idx": i + 1,
                "spreader_text": s_msg.get("content", "") if isinstance(s_msg, dict) else str(s_msg),
                "debunker_text": d_msg.get("content", "") if isinstance(d_msg, dict) else str(d_msg),
            })
        elif t.get("name") and t.get("content"):
            idx = t.get("turn_index", i // 2)
            if t["name"] == "spreader":
                if not pairs or pairs[-1].get("spreader_text"):
                    pairs.append({"pair_idx": idx + 1, "spreader_text": "", "debunker_text": ""})
                pairs[-1]["spreader_text"] = t["content"]
            else:
                if not pairs:
                    pairs.append({"pair_idx": idx + 1, "spreader_text": "", "debunker_text": ""})
                pairs[-1]["debunker_text"] = t["content"]
    return pairs


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _inject_styles():
    st.markdown("""
    <style>
    .ex-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem; font-weight: 700; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0; text-align: center;
    }
    .ex-subtitle {
        font-size: 1rem; color: var(--color-text-muted, #888);
        margin: 0 0 1.5rem 0; text-align: center; line-height: 1.5;
    }
    .ex-section {
        font-size: 1.2rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin: 1.5rem 0 0.3rem 0; padding-bottom: 0.3rem;
        border-bottom: 2px solid var(--color-border, #2A2A2A);
    }
    .ex-context {
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1rem;
    }
    .ex-context-label {
        font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.07em;
        color: #9ca3af; font-weight: 700; margin-bottom: 0.2rem;
    }
    .ex-context-value {
        font-size: 1rem; color: var(--color-text-primary, #E8E4D9); font-weight: 600;
    }
    .ex-context-sub { font-size: 0.8rem; color: #9ca3af; }
    .ex-kpi-row {
        display: flex; gap: 0.8rem; flex-wrap: wrap; margin: 0.5rem 0 1rem 0;
    }
    .ex-kpi {
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.5rem 0.8rem; flex: 1; min-width: 90px;
    }
    .ex-kpi-label {
        font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.07em; color: #9ca3af;
    }
    .ex-kpi-val {
        font-size: 1.3rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
    }
    .ex-detail-header {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.3rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin: 2rem 0 0.5rem 0; padding-bottom: 0.3rem;
        border-bottom: 3px solid var(--color-accent-red, #C9363E);
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Episode detail renderers
# ---------------------------------------------------------------------------

def _render_verdict(ep):
    """Render verdict card + scorecard."""
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

    # Top drivers — verdict_card_html expects list of (metric, direction) tuples
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

    # Scorecard
    if scorecard:
        st.markdown("**Score breakdown**")
        sc_rows = []
        for s in sorted(scorecard, key=lambda x: x.get("metric", "")):
            delta = s.get("debunker", 0) - s.get("spreader", 0)
            sc_rows.append({
                "Dimension": _label(s.get("metric", "")),
                "Spreader": s.get("spreader", 0),
                "Debunker": s.get("debunker", 0),
                "Delta": f"{delta:+.1f}",
            })
        st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True)


def _render_transcript(ep):
    """Render the debate transcript with chat bubbles."""
    pairs = _normalize_turn_pairs(ep)
    planned = (ep.get("config_snapshot") or {}).get("planned_max_turns") or len(pairs)

    if not pairs:
        st.info("No transcript data for this episode.")
        return

    st.markdown(
        f'<p style="font-size:0.85rem;color:#6b7280;margin-bottom:0.8rem">'
        f'{len(pairs)} turn pairs · '
        f'<span style="color:{SPREADER_COLOR};font-weight:600">Spreader</span> vs '
        f'<span style="color:{DEBUNKER_COLOR};font-weight:600">Fact-checker</span></p>',
        unsafe_allow_html=True,
    )

    for p in pairs:
        turn_num = p.get("pair_idx", "?")
        s_text = (p.get("spreader_text") or "").strip()
        d_text = (p.get("debunker_text") or "").strip()

        st.markdown(
            f'<p style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'color:#9ca3af;font-weight:700;margin:1rem 0 0.3rem 0">Turn {turn_num} of {planned}</p>',
            unsafe_allow_html=True,
        )
        if s_text:
            st.markdown(
                f'<div style="border-left:3px solid {SPREADER_COLOR};'
                f'background:rgba(212,168,67,0.06);border-radius:0 8px 8px 0;'
                f'padding:0.7rem 1rem;margin-bottom:0.5rem">'
                f'<div style="font-size:0.7rem;font-weight:700;color:{SPREADER_COLOR};'
                f'text-transform:uppercase;margin-bottom:0.3rem">Spreader</div>'
                f'<div style="font-size:0.9rem;color:var(--color-text-primary,#E8E4D9);'
                f'line-height:1.6;white-space:pre-wrap">{s_text}</div></div>',
                unsafe_allow_html=True,
            )
        if d_text:
            st.markdown(
                f'<div style="border-left:3px solid {DEBUNKER_COLOR};'
                f'background:rgba(74,127,165,0.06);border-radius:0 8px 8px 0;'
                f'padding:0.7rem 1rem;margin-bottom:0.5rem">'
                f'<div style="font-size:0.7rem;font-weight:700;color:{DEBUNKER_COLOR};'
                f'text-transform:uppercase;margin-bottom:0.3rem">Fact-checker</div>'
                f'<div style="font-size:0.9rem;color:var(--color-text-primary,#E8E4D9);'
                f'line-height:1.6;white-space:pre-wrap">{d_text}</div></div>',
                unsafe_allow_html=True,
            )


def _render_strategy(ep):
    """Render strategy lens — regex signals + AI labels."""
    pairs = _normalize_turn_pairs(ep)
    signals = extract_strategy_signals(pairs)
    spr = signals.get("spreader") or {}
    deb = signals.get("debunker") or {}

    all_keys = sorted(set(spr) | set(deb))
    active = [(k, spr.get(k, 0), deb.get(k, 0)) for k in all_keys if spr.get(k, 0) + deb.get(k, 0) > 0]

    # AI-labeled strategies first
    sa = ep.get("strategy_analysis") or {}
    if sa.get("status") == "ok":
        st.markdown("**AI-labeled strategies**")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                        f'color:{SPREADER_COLOR};font-weight:700;margin-bottom:0.3rem">Spreader</div>',
                        unsafe_allow_html=True)
            st.markdown(f"**Primary:** {_label(sa.get('spreader_primary', '—'))}")
            for lbl in sa.get("spreader_strategies", []):
                st.markdown(f"- {_label(lbl)}")
        with c2:
            st.markdown(f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                        f'color:{DEBUNKER_COLOR};font-weight:700;margin-bottom:0.3rem">Fact-checker</div>',
                        unsafe_allow_html=True)
            st.markdown(f"**Primary:** {_label(sa.get('debunker_primary', '—'))}")
            for lbl in sa.get("debunker_strategies", []):
                st.markdown(f"- {_label(lbl)}")
        if sa.get("notes"):
            st.caption(sa["notes"])

    # Regex signal table
    if active:
        st.markdown("**Per-turn signal detection (regex-based)**")
        st.caption("Signal counts detected from the transcript text. Not LLM-generated.")
        sig_rows = []
        for k, s_cnt, d_cnt in active:
            sig_rows.append({
                "Tactic": SIGNAL_LABELS.get(k, _label(k)),
                "Spreader": s_cnt,
                "Debunker": d_cnt,
            })
        st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)


def _render_citations(ep):
    """Render citation analysis for the episode."""
    pairs = _normalize_turn_pairs(ep)
    if not pairs:
        st.info("No transcript data.")
        return

    spr_named, spr_vague, spr_urls = 0, 0, 0
    deb_named, deb_vague, deb_urls = 0, 0, 0
    spr_sources = []
    deb_sources = []

    for p in pairs:
        for text, prefix in [(p.get("spreader_text", ""), "spr"), (p.get("debunker_text", ""), "deb")]:
            tl = text.lower()
            sources_list = spr_sources if prefix == "spr" else deb_sources
            if "http" in tl:
                if prefix == "spr": spr_urls += 1
                else: deb_urls += 1
            for src in _NAMED_SOURCES:
                if src.lower() in tl:
                    if prefix == "spr": spr_named += 1
                    else: deb_named += 1
                    sources_list.append(src)
                    break
            for kw in ["research shows", "studies show", "experts say", "scientists say", "evidence suggests"]:
                if kw in tl:
                    if prefix == "spr": spr_vague += 1
                    else: deb_vague += 1
                    break

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                    f'color:{SPREADER_COLOR};font-weight:700;margin-bottom:0.3rem">Spreader</div>',
                    unsafe_allow_html=True)
        st.markdown(f"Named sources: **{spr_named}** · Vague appeals: **{spr_vague}** · URLs: **{spr_urls}**")
        if spr_sources:
            st.caption("Sources cited: " + ", ".join(sorted(set(spr_sources))))
    with c2:
        st.markdown(f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                    f'color:{DEBUNKER_COLOR};font-weight:700;margin-bottom:0.3rem">Fact-checker</div>',
                    unsafe_allow_html=True)
        st.markdown(f"Named sources: **{deb_named}** · Vague appeals: **{deb_vague}** · URLs: **{deb_urls}**")
        if deb_sources:
            st.caption("Sources cited: " + ", ".join(sorted(set(deb_sources))))


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_explore_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    inject_replay_css()
    _inject_styles()

    st.markdown('<p class="ex-title">Explore</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ex-subtitle">'
        'Filter episodes, browse results, and read full transcripts. '
        'Select an episode from the table to view its detail below.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load data ────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No experiment data. Run the experiment first.")
        return

    episodes = _load_experiment_episodes(tuple(run_ids), RUNS_DIR, token)
    if not episodes:
        st.info("No experiment episodes found.")
        return

    # ── Filters ──────────────────────────────────────────────────────
    all_claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))
    all_spr_models = sorted(set(ep["config_snapshot"]["agents"]["spreader"]["model"] for ep in episodes))
    all_deb_models = sorted(set(ep["config_snapshot"]["agents"]["debunker"]["model"] for ep in episodes))

    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        type_filter = st.selectbox("Claim Type", ["All"] + all_claim_types, key="ex_type")
    with fc2:
        winner_filter = st.selectbox("Winner", ["All", "Spreader", "Debunker", "Draw"], key="ex_winner")
    with fc3:
        spr_filter = st.selectbox("Spreader", ["All"] + [_short(m) for m in all_spr_models], key="ex_spr")
    with fc4:
        deb_filter = st.selectbox("Debunker", ["All"] + [_short(m) for m in all_deb_models], key="ex_deb")
    with fc5:
        turn_filter = st.selectbox("Turns", ["All", "2", "6", "10"], key="ex_turns")

    # Apply filters
    filtered = episodes
    if type_filter != "All":
        filtered = [e for e in filtered if e.get("claim_type") == type_filter]
    if winner_filter != "All":
        filtered = [e for e in filtered if e["results"]["winner"] == winner_filter.lower()]
    if spr_filter != "All":
        filtered = [e for e in filtered if _short(e["config_snapshot"]["agents"]["spreader"]["model"]) == spr_filter]
    if deb_filter != "All":
        filtered = [e for e in filtered if _short(e["config_snapshot"]["agents"]["debunker"]["model"]) == deb_filter]
    if turn_filter != "All":
        filtered = [e for e in filtered if e["results"]["completed_turn_pairs"] == int(turn_filter)]

    if not filtered:
        st.warning("No episodes match the current filters.")
        return

    # ── Claim type context ───────────────────────────────────────────
    if type_filter != "All":
        winners_ct = Counter(e["results"]["winner"] for e in filtered)
        spr_strats_ct = Counter()
        deb_strats_ct = Counter()
        for e in filtered:
            sa = e.get("strategy_analysis") or {}
            p = sa.get("spreader_primary", "")
            if p: spr_strats_ct[p] += 1
            p = sa.get("debunker_primary", "")
            if p: deb_strats_ct[p] += 1

        top_spr_strat = spr_strats_ct.most_common(1)[0] if spr_strats_ct else ("—", 0)
        top_deb_strat = deb_strats_ct.most_common(1)[0] if deb_strats_ct else ("—", 0)
        spr_win_pct = winners_ct.get("spreader", 0) / len(filtered) * 100

        # Per-claim breakdown within type
        claim_stats = defaultdict(lambda: {"total": 0, "spr_wins": 0})
        for e in filtered:
            c = e.get("claim", "?")
            claim_stats[c]["total"] += 1
            if e["results"]["winner"] == "spreader":
                claim_stats[c]["spr_wins"] += 1

        ctx_cols = st.columns(4)
        with ctx_cols[0]:
            st.markdown(
                f'<div class="ex-context"><div class="ex-context-label">Episodes</div>'
                f'<div class="ex-context-value">{len(filtered)}</div>'
                f'<div class="ex-context-sub">Spreader wins: {spr_win_pct:.0f}%</div></div>',
                unsafe_allow_html=True,
            )
        with ctx_cols[1]:
            st.markdown(
                f'<div class="ex-context"><div class="ex-context-label">Top Spreader Tactic</div>'
                f'<div class="ex-context-value">{_label(top_spr_strat[0])}</div>'
                f'<div class="ex-context-sub">Used in {top_spr_strat[1]} episodes</div></div>',
                unsafe_allow_html=True,
            )
        with ctx_cols[2]:
            st.markdown(
                f'<div class="ex-context"><div class="ex-context-label">Top Debunker Tactic</div>'
                f'<div class="ex-context-value">{_label(top_deb_strat[0])}</div>'
                f'<div class="ex-context-sub">Used in {top_deb_strat[1]} episodes</div></div>',
                unsafe_allow_html=True,
            )
        with ctx_cols[3]:
            # Show claim difficulty within type
            hardest = max(claim_stats.items(), key=lambda x: x[1]["spr_wins"]/max(x[1]["total"],1))
            easiest = min(claim_stats.items(), key=lambda x: x[1]["spr_wins"]/max(x[1]["total"],1))
            st.markdown(
                f'<div class="ex-context"><div class="ex-context-label">Claim Difficulty</div>'
                f'<div class="ex-context-value" style="font-size:0.85rem">'
                f'Hardest: {hardest[0][:25]}…</div>'
                f'<div class="ex-context-sub">'
                f'{hardest[1]["spr_wins"]}/{hardest[1]["total"]} spreader wins</div></div>',
                unsafe_allow_html=True,
            )
    else:
        # General KPIs when no type selected
        winners_all = Counter(e["results"]["winner"] for e in filtered)
        margins = [(e["results"].get("totals",{}).get("debunker",0) or 0) -
                   (e["results"].get("totals",{}).get("spreader",0) or 0) for e in filtered]
        avg_margin = sum(margins)/len(margins) if margins else 0

        st.markdown(
            f'<div class="ex-kpi-row">'
            f'<div class="ex-kpi"><div class="ex-kpi-label">Episodes</div>'
            f'<div class="ex-kpi-val">{len(filtered)}</div></div>'
            f'<div class="ex-kpi"><div class="ex-kpi-label">Debunker Wins</div>'
            f'<div class="ex-kpi-val" style="color:{DEBUNKER_COLOR}">{winners_all.get("debunker",0)}</div></div>'
            f'<div class="ex-kpi"><div class="ex-kpi-label">Spreader Wins</div>'
            f'<div class="ex-kpi-val" style="color:{SPREADER_COLOR}">{winners_all.get("spreader",0)}</div></div>'
            f'<div class="ex-kpi"><div class="ex-kpi-label">Draws</div>'
            f'<div class="ex-kpi-val">{winners_all.get("draw",0)}</div></div>'
            f'<div class="ex-kpi"><div class="ex-kpi-label">Avg Margin</div>'
            f'<div class="ex-kpi-val">{avg_margin:+.1f}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Episode table ────────────────────────────────────────────────
    table_rows = []
    for i, ep in enumerate(filtered):
        sa = ep.get("strategy_analysis") or {}
        t = ep["results"].get("totals", {})
        margin = (t.get("debunker", 0) or 0) - (t.get("spreader", 0) or 0)
        table_rows.append({
            "idx": i,
            "Claim": (ep.get("claim", "")[:30] + "…") if len(ep.get("claim", "")) > 30 else ep.get("claim", ""),
            "Type": ep.get("claim_type", ""),
            "Spreader": _short(ep["config_snapshot"]["agents"]["spreader"]["model"]),
            "Debunker": _short(ep["config_snapshot"]["agents"]["debunker"]["model"]),
            "Turns": ep["results"]["completed_turn_pairs"],
            "Winner": ep["results"]["winner"].title(),
            "Margin": f"{margin:+.1f}",
            "Spr Primary": _label(sa.get("spreader_primary", "")),
            "Deb Primary": _label(sa.get("debunker_primary", "")),
        })

    table_df = pd.DataFrame(table_rows)
    display_df = table_df.drop(columns=["idx"])

    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=350,
        key="ex_episode_table",
    )

    # ── Episode detail ───────────────────────────────────────────────
    sel_rows = (event.selection.rows or []) if event.selection else []

    if not sel_rows:
        st.markdown(
            '<p style="font-size:0.9rem;color:#9ca3af;text-align:center;margin:2rem 0">'
            'Click a row above to view the episode detail.</p>',
            unsafe_allow_html=True,
        )
        return

    sel_idx = sel_rows[0]
    selected_ep = filtered[sel_idx]

    # Header
    spr_m = _short(selected_ep["config_snapshot"]["agents"]["spreader"]["model"])
    deb_m = _short(selected_ep["config_snapshot"]["agents"]["debunker"]["model"])
    claim = selected_ep.get("claim", "")
    turns = selected_ep["results"]["completed_turn_pairs"]
    winner = selected_ep["results"]["winner"].title()

    st.markdown(
        f'<p class="ex-detail-header">'
        f'{spr_m} vs {deb_m} · {turns} turns · {winner} wins</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:var(--color-surface,#111);border-left:4px solid {DEBUNKER_COLOR};'
        f'border-radius:0 8px 8px 0;padding:0.6rem 1rem;margin-bottom:1rem;'
        f'font-size:0.95rem;color:var(--color-text-primary,#E8E4D9)">'
        f'<b>Claim:</b> {claim}</div>',
        unsafe_allow_html=True,
    )

    # Detail tabs
    dt_verdict, dt_transcript, dt_strategy, dt_citations = st.tabs([
        "Verdict", "Transcript", "Strategy", "Citations"
    ])

    with dt_verdict:
        _render_verdict(selected_ep)
    with dt_transcript:
        _render_transcript(selected_ep)
    with dt_strategy:
        _render_strategy(selected_ep)
    with dt_citations:
        _render_citations(selected_ep)

    # Download
    st.download_button(
        "Download episode JSON",
        json.dumps(selected_ep, indent=2, default=str),
        file_name=f"episode_{selected_ep.get('episode_id', '')}.json",
        mime="application/json",
    )
