"""
Explore Page — filterable episode browser across all experiment data.

Lightweight data browser for comparing episodes across conditions.
Study Results has the curated findings; Explore lets you dig into the raw data.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from arena.io.run_store_v2_read import load_episodes
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

RUNS_DIR = "runs"

_MODEL_SHORT = {
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4-20250514": "Claude Sonnet",
    "claude-sonnet-4": "Claude Sonnet",
    "gemini-2.5-flash": "Gemini Flash",
}


def _short(model: str) -> str:
    return _MODEL_SHORT.get(model, model[:15])


def _label(s: str) -> str:
    return (s or "").replace("_", " ").title()


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


def render_explore_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()

    st.markdown(
        '<p style="font-family:Playfair Display,Georgia,serif;font-size:2.6rem;font-weight:700;'
        'letter-spacing:-0.02em;color:var(--color-text-primary,#E8E4D9);'
        'margin:0 0 0.2rem 0;text-align:center">Explore</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:1rem;color:var(--color-text-muted,#888);'
        'margin:0 0 1.5rem 0;text-align:center;line-height:1.5">'
        'Browse and filter all experiment episodes. Use Study Results for curated findings '
        'or Replay for full transcripts.'
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

    # ── Build filter options ─────────────────────────────────────────
    all_spr_models = sorted(set(ep["config_snapshot"]["agents"]["spreader"]["model"] for ep in episodes))
    all_deb_models = sorted(set(ep["config_snapshot"]["agents"]["debunker"]["model"] for ep in episodes))
    all_claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))
    all_turns = sorted(set(ep["results"]["completed_turn_pairs"] for ep in episodes))

    # ── Filters ──────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        winner_filter = st.selectbox("Winner", ["All", "Spreader", "Debunker", "Draw"], key="ex_winner")
    with fc2:
        spr_filter = st.selectbox("Spreader", ["All"] + [_short(m) for m in all_spr_models], key="ex_spr")
    with fc3:
        deb_filter = st.selectbox("Debunker", ["All"] + [_short(m) for m in all_deb_models], key="ex_deb")
    with fc4:
        type_filter = st.selectbox("Claim Type", ["All"] + all_claim_types, key="ex_type")
    with fc5:
        turn_filter = st.selectbox("Turns", ["All"] + [str(t) for t in all_turns], key="ex_turns")

    # ── Apply filters ────────────────────────────────────────────────
    filtered = episodes
    if winner_filter != "All":
        filtered = [e for e in filtered if e["results"]["winner"] == winner_filter.lower()]
    if spr_filter != "All":
        filtered = [e for e in filtered if _short(e["config_snapshot"]["agents"]["spreader"]["model"]) == spr_filter]
    if deb_filter != "All":
        filtered = [e for e in filtered if _short(e["config_snapshot"]["agents"]["debunker"]["model"]) == deb_filter]
    if type_filter != "All":
        filtered = [e for e in filtered if e.get("claim_type") == type_filter]
    if turn_filter != "All":
        filtered = [e for e in filtered if e["results"]["completed_turn_pairs"] == int(turn_filter)]

    # ── Summary stats ────────────────────────────────────────────────
    n = len(filtered)
    if n == 0:
        st.warning("No episodes match the current filters.")
        return

    from collections import Counter
    winners = Counter(e["results"]["winner"] for e in filtered)
    margins = []
    for e in filtered:
        t = e["results"].get("totals", {})
        if t.get("debunker") is not None and t.get("spreader") is not None:
            margins.append(t["debunker"] - t["spreader"])
    avg_margin = sum(margins) / len(margins) if margins else 0

    st.markdown(
        f'<div style="display:flex;gap:0.8rem;flex-wrap:wrap;margin:0.5rem 0 1rem 0">'
        f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:8px;padding:0.6rem 1rem;flex:1;min-width:100px">'
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">Episodes</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#E8E4D9">{n}</div></div>'
        f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:8px;padding:0.6rem 1rem;flex:1;min-width:100px">'
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">Debunker Wins</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#4A7FA5">{winners.get("debunker", 0)}</div></div>'
        f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:8px;padding:0.6rem 1rem;flex:1;min-width:100px">'
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">Spreader Wins</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#D4A843">{winners.get("spreader", 0)}</div></div>'
        f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:8px;padding:0.6rem 1rem;flex:1;min-width:100px">'
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">Draws</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#888">{winners.get("draw", 0)}</div></div>'
        f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
        f'border-radius:8px;padding:0.6rem 1rem;flex:1;min-width:100px">'
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">Avg Margin</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#E8E4D9">{avg_margin:+.1f}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Episode table ────────────────────────────────────────────────
    rows = []
    for ep in filtered:
        sa = ep.get("strategy_analysis") or {}
        t = ep["results"].get("totals", {})
        margin = (t.get("debunker", 0) or 0) - (t.get("spreader", 0) or 0)
        rows.append({
            "Claim": (ep.get("claim", "")[:35] + "…") if len(ep.get("claim", "")) > 35 else ep.get("claim", ""),
            "Type": ep.get("claim_type", ""),
            "Spreader": _short(ep["config_snapshot"]["agents"]["spreader"]["model"]),
            "Debunker": _short(ep["config_snapshot"]["agents"]["debunker"]["model"]),
            "Turns": ep["results"]["completed_turn_pairs"],
            "Winner": ep["results"]["winner"].title(),
            "Margin": f"{margin:+.1f}",
            "Confidence": f"{ep['results'].get('judge_confidence', 0):.0%}",
            "Spr Primary": _label(sa.get("spreader_primary", "")),
            "Deb Primary": _label(sa.get("debunker_primary", "")),
            "Spr Tactics": len(sa.get("spreader_strategies", [])),
            "Deb Tactics": len(sa.get("debunker_strategies", [])),
            "Run ID": ep.get("run_id", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    st.caption(
        f"Showing {len(df)} episodes. Use the filters above to narrow results. "
        "Find a Run ID and go to Replay to view the full transcript."
    )

    # ── Download filtered data ───────────────────────────────────────
    st.download_button(
        "Download filtered episodes as CSV",
        data=df.to_csv(index=False).encode(),
        file_name="filtered_episodes.csv",
        mime="text/csv",
    )
