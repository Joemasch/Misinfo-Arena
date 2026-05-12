"""
Arena Page — Live debate setup, execution, and results.

Extracted from app.py to reduce monolith size.
Contains the full Arena tab UI including sidebar configuration,
claim input, debate controls, live chat, and judge report display.
"""

import os
import sys
import time

import streamlit as st
import streamlit.components.v1 as components

from arena.config import (
    AVAILABLE_MODELS,
    get_default_model_index,
    DEFAULT_SPREADER_TEMPERATURE,
    DEFAULT_DEBUNKER_TEMPERATURE,
)
from arena.presentation.streamlit.components.arena.judge_report import render_judge_report
from arena.presentation.streamlit.components.arena.debate_insights import render_debate_insights


# ---------------------------------------------------------------------------
# Local helpers (avoid circular import with app.py)
# ---------------------------------------------------------------------------

_DEBUG_ARENA = os.getenv("DEBUG_ARENA", "0") == "1"


def _arena_dbg(tag: str, **kv):
    """Debug logging for Arena system invariants."""
    if not _DEBUG_ARENA:
        return
    safe = {}
    for k, v in kv.items():
        try:
            if isinstance(v, str) and len(v) > 180:
                safe[k] = v[:180] + "..."
            else:
                safe[k] = v
        except Exception:
            safe[k] = "<unprintable>"
    print(f"[ARENA][{tag}] " + " ".join(f"{k}={safe[k]!r}" for k in safe))


def _get_ui_claim() -> str:
    """Get the current claim text from UI input."""
    return (st.session_state.get("claim_text") or "").strip()


def _auto_classify_df(df) -> "pd.DataFrame":
    """
    Auto-classify claims in a DataFrame. If claim_type column is missing
    or has empty values, fill them using the heuristic classifier.
    Returns the DataFrame with claim_type populated.
    """
    import pandas as _pd
    from arena.claim_metadata import classify_claim

    if "claim" not in df.columns:
        return df

    if "claim_type" not in df.columns:
        df["claim_type"] = ""

    for idx, row in df.iterrows():
        current_type = str(row.get("claim_type", "") or "").strip()
        if not current_type or current_type.lower() in ("", "unknown", "nan", "none"):
            claim_text = str(row["claim"]).strip()
            if claim_text:
                classified, _source = classify_claim(claim_text, use_llm_fallback=False)
                if classified and classified != "unknown":
                    df.at[idx, "claim_type"] = classified

    return df


# ---------------------------------------------------------------------------
# Functions moved from app.py
# ---------------------------------------------------------------------------

def _render_sidebar():
    """Render the sidebar with judge settings, API keys, and data management.

    Note: Spreader and Fact-checker model selectors used to live here. They
    have been moved into the Arena main column (per-episode rows under
    "Episodes & Models") so users can configure different models per episode.
    """

    # Seed defaults so other code paths that read these keys keep working.
    default_idx = get_default_model_index(AVAILABLE_MODELS)
    _default_model = AVAILABLE_MODELS[default_idx] if AVAILABLE_MODELS else "gpt-4o-mini"
    st.session_state.setdefault("spreader_model", _default_model)
    st.session_state.setdefault("debunker_model", _default_model)

    # ── Judge Configuration ───────────────────────────────────────────────
    st.sidebar.markdown("**Judge**")

    _judge_models = [m for m in AVAILABLE_MODELS if "turbo" not in m and "3.5" not in m and "2.0" not in m]
    st.sidebar.selectbox(
        "Judge model",
        options=_judge_models,
        index=_judge_models.index("gpt-4o-mini") if "gpt-4o-mini" in _judge_models else 0,
        key="judge_model_select",
        help="Which model scores the debate. Supports OpenAI, Anthropic, Google, and xAI models.",
    )

    # Fixed temperatures (no UI — kept here because the agents need the values).
    st.session_state["spreader_temperature"] = DEFAULT_SPREADER_TEMPERATURE
    st.session_state["debunker_temperature"] = DEFAULT_DEBUNKER_TEMPERATURE

    st.sidebar.divider()

    # ── API Keys ──────────────────────────────────────────────────────────
    st.sidebar.markdown("**API Keys**")
    from arena.utils.api_keys import get_key_status, mask_key
    key_status = get_key_status()

    _providers = [
        ("openai",    "OPENAI_API_KEY",    "OpenAI",    "sk-..."),
        ("anthropic", "ANTHROPIC_API_KEY",  "Anthropic", "sk-ant-..."),
        ("gemini",    "GEMINI_API_KEY",     "Gemini",    "AI..."),
    ]

    for provider_id, env_name, label, placeholder in _providers:
        info = key_status.get(provider_id, {})
        if info.get("set"):
            st.sidebar.caption(f"{label}: `{info['masked']}` ({info['source']})")
        else:
            _val = st.sidebar.text_input(
                f"{label} API Key",
                type="password",
                key=env_name,
                placeholder=placeholder,
                help=f"Paste your {label} key. Session only — not saved to disk.",
            )
            if _val and _val.strip():
                import os
                os.environ[env_name] = _val.strip()
                st.sidebar.caption(f"{label}: `{mask_key(_val)}` (sidebar)")

    st.sidebar.caption("Keys from `.streamlit/secrets.toml` or env vars load automatically.")

    st.sidebar.divider()

    # -- Data management ───────────────────────────────────────────────────
    st.sidebar.markdown("**Data**")

    if st.sidebar.button("Clear all runs", key="clear_all_runs_btn", help="Archive all runs to runs_archive/ and start fresh."):
        st.session_state["_confirm_clear_runs"] = True

    if st.session_state.get("_confirm_clear_runs"):
        st.sidebar.warning("This will move ALL runs to `runs_archive/`. Are you sure?")
        _c1, _c2 = st.sidebar.columns(2)
        with _c1:
            if st.button("Yes, clear", key="confirm_clear_yes", type="primary"):
                import shutil
                from pathlib import Path
                from datetime import datetime
                _runs_dir = Path("runs")
                _archive = Path("runs_archive") / f"cleared_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                _archive.mkdir(parents=True, exist_ok=True)
                _count = 0
                for d in _runs_dir.iterdir():
                    if d.is_dir():
                        shutil.move(str(d), str(_archive / d.name))
                        _count += 1
                # Also move matches.jsonl if it exists
                _mj = _runs_dir / "matches.jsonl"
                if _mj.exists():
                    shutil.move(str(_mj), str(_archive / "matches.jsonl"))
                st.session_state.pop("_confirm_clear_runs", None)
                # Bump refresh token so analytics/replay update
                st.session_state["runs_refresh_token"] = st.session_state.get("runs_refresh_token", 0) + 1
                st.sidebar.success(f"Archived {_count} run(s) to `{_archive.name}`")
                st.rerun()
        with _c2:
            if st.button("Cancel", key="confirm_clear_no"):
                st.session_state.pop("_confirm_clear_runs", None)
                st.rerun()


def _generate_agent_message(agent, context):
    """Generate a message from an agent with the given context."""
    return agent.generate(context)


def _get_last_message_text(role: str) -> str:
    """
    Safely get the last message text for a given role from the transcript.

    Args:
        role: "spreader" or "debunker"

    Returns:
        Last message content for the role, or empty string if none found
    """
    # Try episode transcript first (most current)
    transcript = st.session_state.get("episode_transcript", [])
    for msg in reversed(transcript):
        msg_role = msg.get("role", "").lower()
        if msg_role == role.lower():
            return msg.get("content", "")

    # Fallback to global messages
    messages = st.session_state.get("messages", [])
    for msg in reversed(messages):
        msg_role = msg.get("role", "").lower()
        if msg_role == role.lower():
            return msg.get("content", "")

    # Final fallback to session state stored messages
    stored_key = f"last_{role.lower()}_message"
    return st.session_state.get(stored_key, "")


def _show_typing_indicator(status_placeholder, agent_name, avatar):
    """Show typing indicator for an agent."""
    with status_placeholder.container():
        st.markdown(f"{avatar} **{agent_name}** is typing...")


def _update_chat_display(chat_placeholder, status_placeholder, progress_bar, turn_idx, max_turns):
    """Update the chat display with current messages and status."""
    # Status display
    if st.session_state.get("match_in_progress", False):
        completed_turns = st.session_state.get("completed_turn_pairs", 0)
        st.caption(f"Turn {completed_turns}/{max_turns} completed")
    elif st.session_state.get("match_completed", False):
        reason = st.session_state.get("early_stop_reason", "Unknown reason")
        st.caption(f"Debate completed - {reason}")

    # Note: Transcript rendering is now handled statically in the main Arena UI

    # Clear status placeholder (used for typing indicators)
    status_placeholder.empty()

    # Update progress bar
    completed_turns = st.session_state.get("completed_turn_pairs", 0)
    progress_bar.progress(min(completed_turns / max_turns, 1.0), text=f"Turn {completed_turns}/{max_turns}")


# ---------------------------------------------------------------------------
# Main page renderer
# ---------------------------------------------------------------------------

def _reset_live_insights():
    """Clear the live citation + strategy accumulators when a new debate starts."""
    for k in ("live_citations", "live_strategies", "_live_toasted_ids", "_live_detect_last_turn"):
        st.session_state.pop(k, None)


def _run_live_detection():
    """After each turn pair completes, detect new citations and strategies.

    Citations: regex scan, instant. Strategies: LLM call (~1-2s latency).
    Fires st.toast for each new event and appends to session state lists
    that drive the Live Insights panel.
    """
    ss = st.session_state
    pairs_done = int(ss.get("completed_turn_pairs", 0) or 0)
    last_done  = int(ss.get("_live_detect_last_turn", 0) or 0)
    if pairs_done <= last_done:
        return

    ss.setdefault("live_citations", [])
    ss.setdefault("live_strategies", [])
    toasted_ids = ss.setdefault("_live_toasted_ids", set())

    # ── Group debate_messages into turn pairs (only fully-final ones) ───
    msgs = ss.get("debate_messages", [])
    turns_by_idx = {}
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if m.get("status") != "final":
            continue
        t_idx = int(m.get("turn") or 0)
        side = (m.get("speaker") or m.get("role") or "").lower()
        if side not in ("spreader", "debunker"):
            continue
        turns_by_idx.setdefault(t_idx, {})[side] = (m.get("content") or "").strip()

    new_turn_indices = sorted(t for t in turns_by_idx if t > last_done
                              and turns_by_idx[t].get("spreader")
                              and turns_by_idx[t].get("debunker"))
    if not new_turn_indices:
        return

    # ── Citation detection (regex, instant) ─────────────────────────────
    try:
        from arena.presentation.streamlit.pages.explore_page import (
            _SOURCE_PATTERNS, _canonical_source,
        )
    except Exception:
        _SOURCE_PATTERNS = {}
        _canonical_source = lambda s: s  # noqa: E731

    for t_idx in new_turn_indices:
        pair = turns_by_idx[t_idx]
        for side_name in ("spreader", "debunker"):
            text = pair.get(side_name, "")
            for src, pat in _SOURCE_PATTERNS.items():
                if not pat.search(text):
                    continue
                # Canonicalize so "World Health Organization" and "WHO" mentions
                # produce a single toast / panel entry rather than two.
                canon = _canonical_source(src)
                event_id = f"cite::{t_idx}::{side_name}::{canon}"
                if event_id in toasted_ids:
                    continue
                ss["live_citations"].append({
                    "turn": t_idx, "side": side_name, "source": canon,
                })
                toasted_ids.add(event_id)
                side_label = "Spreader" if side_name == "spreader" else "Fact-checker"
                icon = "📎"
                st.toast(f"{canon} cited by {side_label} (Turn {t_idx})", icon=icon)

    # ── Strategy detection (LLM call on accumulated turns) ──────────────
    try:
        from arena.strategy_analyst import analyze_per_turn_strategies
        from arena.presentation.streamlit.pages.atlas_page import _plain_name_for

        # Build flat-format turns list for the analyst
        turns_for_analyst = []
        for t_idx in sorted(turns_by_idx.keys()):
            pair = turns_by_idx[t_idx]
            if pair.get("spreader"):
                turns_for_analyst.append({"name": "spreader", "content": pair["spreader"],
                                           "turn_index": t_idx - 1})
            if pair.get("debunker"):
                turns_for_analyst.append({"name": "debunker", "content": pair["debunker"],
                                           "turn_index": t_idx - 1})

        claim = ss.get("topic", "") or ss.get("claim_text", "")
        results = analyze_per_turn_strategies(claim=claim, transcript_turns=turns_for_analyst) or []

        for r in results:
            t_idx = int(r.get("turn", 0) or 0)
            if t_idx not in new_turn_indices:
                continue
            for side_name in ("spreader", "debunker"):
                raws = r.get(f"{side_name}_strategies") or []
                for j, raw in enumerate(raws):
                    plain = _plain_name_for(raw) or raw.replace("_", " ").title()
                    event_id = f"strat::{t_idx}::{side_name}::{plain}"
                    if event_id in toasted_ids:
                        continue
                    ss["live_strategies"].append({
                        "turn": t_idx, "side": side_name,
                        "tactic": plain, "raw": raw,
                    })
                    toasted_ids.add(event_id)
                    # Only toast the PRIMARY tactic per side per turn (avoid spam).
                    if j == 0:
                        side_label = "Spreader" if side_name == "spreader" else "Fact-checker"
                        icon = "🎯"
                        st.toast(f"{side_label} used: {plain} (Turn {t_idx})", icon=icon)
    except Exception as e:
        print(f"[LIVE_DETECT] strategy analysis skipped: {e}")

    ss["_live_detect_last_turn"] = pairs_done


def _render_live_insights_panel():
    """Show accumulated live insights below the transcript."""
    cites = st.session_state.get("live_citations") or []
    strats = st.session_state.get("live_strategies") or []
    if not cites and not strats:
        return

    st.markdown(
        '<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.07em;margin:1.5rem 0 0.5rem 0;'
        'padding-bottom:0.3rem;border-bottom:1px solid var(--color-border,#2A2A2A)">'
        'Live insights — what we spotted in this debate</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Citations are detected instantly via text matching. Strategies are scored "
        "by an LLM after each turn pair. Both link to fuller definitions in the Atlas tab."
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            f'<div style="font-size:0.7rem;color:#16a34a;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.4rem">'
            f'Citations spotted · {len(cites)}</div>',
            unsafe_allow_html=True,
        )
        if not cites:
            st.caption("— none yet —")
        for ev in cites[-15:]:
            color = "#D4A843" if ev["side"] == "spreader" else "#4A7FA5"
            side_label = "Spr" if ev["side"] == "spreader" else "FC"
            st.markdown(
                f'<div style="font-size:0.84rem;margin:0.2rem 0;'
                f'padding:0.3rem 0.6rem;border-left:3px solid #16a34a;'
                f'background:rgba(22,163,74,0.05);border-radius:0 4px 4px 0;'
                f'color:var(--color-text-primary,#E8E4D9)">'
                f'<span style="color:{color};font-weight:600">{side_label}</span> · '
                f'<b>{ev["source"]}</b> '
                f'<span style="color:#9ca3af;font-family:\'IBM Plex Mono\',monospace;font-size:0.78rem">'
                f'Turn {ev["turn"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with cols[1]:
        st.markdown(
            f'<div style="font-size:0.7rem;color:#D4A843;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.4rem">'
            f'Tactics detected · {len(strats)}</div>',
            unsafe_allow_html=True,
        )
        if not strats:
            st.caption("— LLM analysing the most recent turn… —")
        for ev in strats[-15:]:
            color = "#D4A843" if ev["side"] == "spreader" else "#4A7FA5"
            side_label = "Spr" if ev["side"] == "spreader" else "FC"
            st.markdown(
                f'<div style="font-size:0.84rem;margin:0.2rem 0;'
                f'padding:0.3rem 0.6rem;border-left:3px solid {color};'
                f'background:rgba(255,255,255,0.02);border-radius:0 4px 4px 0;'
                f'color:var(--color-text-primary,#E8E4D9)">'
                f'<span style="color:{color};font-weight:600">{side_label}</span> · '
                f'<b>{ev["tactic"]}</b> '
                f'<span style="color:#9ca3af;font-family:\'IBM Plex Mono\',monospace;font-size:0.78rem">'
                f'Turn {ev["turn"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_arena_page():
    """Render the full Arena tab content."""
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()

    # -- Arena page CSS ----------------------------------------------------
    st.markdown("""
    <style>
    /* Arena section labels */
    .ar-section {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: var(--color-text-muted, #888);
        border-bottom: 1px solid var(--color-border, #2A2A2A);
        padding-bottom: 0.3rem;
        margin: 1.4rem 0 0.75rem 0;
    }
    .ar-section:first-child { margin-top: 0; }

    /* Active claim banner */
    .ar-claim-banner {
        border-left: 4px solid var(--color-accent-blue, #4A7FA5);
        background: rgba(74, 127, 165, 0.08);
        border-radius: 0 4px 4px 0;
        padding: 0.75rem 1.1rem;
        margin: 0.5rem 0 1rem 0;
    }
    .ar-claim-label {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: var(--color-accent-blue, #4A7FA5);
        margin-bottom: 0.2rem;
    }
    .ar-claim-text {
        font-size: 1rem;
        font-weight: 600;
        color: var(--color-text-primary, #E8E4D9);
        line-height: 1.4;
    }

    /* Status strip */
    .ar-status-strip {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        margin: 0.5rem 0 1rem 0;
    }
    .ar-status-badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.2rem 0.65rem;
        border-radius: 4px;
        border: 1px solid var(--color-border, #2A2A2A);
        color: var(--color-text-muted, #888);
        font-family: 'IBM Plex Mono', monospace;
    }
    .ar-status-badge.active {
        border-color: rgba(76, 175, 125, 0.5);
        color: var(--color-accent-green, #4CAF7D);
        background: rgba(76, 175, 125, 0.1);
    }
    .ar-status-badge.running {
        border-color: rgba(74, 127, 165, 0.5);
        color: var(--color-accent-blue, #4A7FA5);
        background: rgba(74, 127, 165, 0.1);
    }
    .ar-status-badge.idle {
        border-color: var(--color-border, #2A2A2A);
        color: var(--color-text-faint, #444);
    }

    /* Page title */
    .ar-page-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0;
        line-height: 1.2;
        text-align: center;
    }
    .ar-page-sub {
        font-size: 0.95rem;
        color: var(--color-text-muted, #888);
        margin: 0 0 1.2rem 0;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    # -- Arena page header -------------------------------------------------
    st.markdown(
        '<div class="ar-page-title">Arena</div>'
        '<div class="ar-page-sub">Configure agents, enter a claim, and run a structured AI debate.</div>',
        unsafe_allow_html=True,
    )

    # ===================================================================
    # SIDEBAR - Configuration controls
    # ===================================================================
    _render_sidebar()

    # ===================================================================
    # SESSION STATE INITIALIZATION - Ensure consistent keys (BEFORE button handling)
    # ===================================================================
    # Use setdefault to avoid overwriting values set by button clicks
    st.session_state.setdefault("claim_text", "")
    st.session_state.setdefault("is_running", False)
    st.session_state.setdefault("debate_in_progress", False)  # Canonical key
    st.session_state.setdefault("messages", [])   # transcript
    st.session_state.setdefault("episode_transcript", [])  # current episode transcript
    # Render-time default only; "Start new run" sets episode_idx and run boundary.
    st.session_state.setdefault("episode_idx", 1)
    st.session_state.setdefault("run_active", False)
    st.session_state.setdefault("episodes_completed", 0)
    st.session_state.setdefault("run_started_at", None)
    st.session_state.setdefault("turn_idx", 0)  # Canonical key: completed exchanges
    st.session_state.setdefault("current_turn_idx", 0)  # Canonical key (alias)
    st.session_state.setdefault("num_episodes", 1)
    st.session_state.setdefault("max_turns", 5)  # Canonical key
    st.session_state.setdefault("turn_plan_csv", str(st.session_state["max_turns"]))
    st.session_state.setdefault("turn_plan_valid", True)  # set False by Run Plan parse when invalid
    st.session_state.setdefault("current_match_result", None)  # Canonical key
    st.session_state.setdefault("debug_events", [])  # Debug event ring buffer
    st.session_state.setdefault("pending_stop", False)  # stop at end of current turn
    st.session_state.setdefault("stop_reason", None)  # "max_turns", "concession", "user_stop"
    st.session_state.setdefault("episode_completed", False)  # prevent multiple episode_complete calls
    st.session_state.setdefault("is_generating_turn", False)  # Prevent concurrent turn generation

    # Diagnostic fields for troubleshooting stalls
    st.session_state.setdefault("arena_debug", False)
    st.session_state.setdefault("_pending_chain", False)
    st.session_state.setdefault("_pending_chain_next_episode_idx", None)
    st.session_state.setdefault("_pending_chain_next_claim_index", None)
    st.session_state.setdefault("arena_mode", "single_claim")
    st.session_state.setdefault("claims_list", [])
    st.session_state.setdefault("claim_metadata_list", [])
    st.session_state.setdefault("current_claim_index", 0)
    st.session_state.setdefault("total_claims", 1)
    st.session_state.setdefault("last_step", None)
    st.session_state.setdefault("last_step_ts", None)
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("last_error_trace", None)
    st.session_state.setdefault("last_guard_block", None)

    # ===================================================================
    # MULTI-EPISODE CHAIN — when one debate ends, auto-start the next
    # if the user queued additional episode configs (via the form or Showdown).
    # ===================================================================
    st.session_state.setdefault("pending_episodes", [])  # list[dict]

    _pe_list = st.session_state.get("pending_episodes") or []
    _run_active = st.session_state.get("run_active", False)
    _match_ip = st.session_state.get("match_in_progress", False)
    _debate_run = st.session_state.get("debate_running", False)
    _pending_chain = st.session_state.get("_pending_chain", False)
    _prev_done = (not _run_active and not _match_ip
                  and not _debate_run and not _pending_chain)

    if _pe_list and _prev_done:
        _next = _pe_list[0]
        st.session_state["pending_episodes"] = _pe_list[1:]
        ss = st.session_state

        _next_claim = _next.get("claim") or ss.get("claim_text") or ""
        _next_exch  = int(_next.get("exchanges") or _next.get("max_turns") or 5)
        ss["claim_text"]   = _next_claim
        ss["topic"]        = _next_claim
        ss["current_claim"] = _next_claim
        ss["claim"]        = _next_claim
        ss["arena_mode"]   = "single_claim"
        ss["max_turns"]    = _next_exch
        ss["turn_plan"]    = [_next_exch]
        ss["turn_plan_csv"] = str(_next_exch)
        ss["turn_plan_valid"] = True
        if _next.get("spreader_model"):
            ss["spreader_model"] = _next["spreader_model"]
        if _next.get("debunker_model"):
            ss["debunker_model"] = _next["debunker_model"]
        if _next.get("claim_type"):
            ss["claim_type"] = _next["claim_type"]

        ss["run_active"] = True
        ss["episodes_completed"] = 0
        ss["episode_idx"] = 1
        # Each chain entry is its own single-episode run; the cross-episode
        # chain happens via pending_episodes, not the runner's internal loop.
        ss["num_episodes"] = 1
        if "run_id" in ss:
            del ss["run_id"]

        try:
            from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
        except ImportError:
            sys.path.insert(0, "src")
            from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
        reset_episode_state_for_chaining(ss)

        ss["debate_messages"]      = []
        ss["episode_transcript"]   = []
        ss["completed_turn_pairs"] = 0
        ss["turn_idx"]             = 0
        ss["debate_phase"]         = "spreader"

        # Reset live insights accumulators for the new episode
        _reset_live_insights()

        apply_turn_plan_to_episode(ss, 1)

        ss["match_in_progress"] = True
        ss["debate_running"]    = True
        ss["debate_autoplay"]   = True
        ss["match_id"]          = f"match_{ss['episode_idx']}"

        # If this was the last episode in a multi-run, mark showdown_completed
        # so the post-verdict nudges adapt (skip "switch models" suggestion).
        if not ss["pending_episodes"] and ss.get("showdown_run_size", 0) > 1:
            ss["showdown_completed"] = True
            ss["showdown_run_size"] = 0

        st.rerun()

    # ===================================================================
    # ARENA MODE - Quick Debate vs Experiment
    # ===================================================================
    arena_top_mode = st.radio(
        "Arena mode",
        options=["quick_debate", "experiment"],
        format_func=lambda x: "Quick Debate" if x == "quick_debate" else "Experiment",
        horizontal=True,
        key="arena_top_mode",
        label_visibility="collapsed",
    )

    # ── Experiment mode: delegate to spec CSV runner ─────────────────
    if arena_top_mode == "experiment":
        from arena.presentation.streamlit.pages.experiment_page import render_experiment_page
        render_experiment_page()
        return

    # Quick Debate mode uses single_claim internally
    arena_mode = "single_claim"
    st.session_state["arena_mode"] = arena_mode

    # ===================================================================
    # CLAIM INPUT + RUN PLAN (combined — depends on mode)
    # ===================================================================
    import pandas as _pd

    # ===================================================================
    # CLAIM INPUT + RUN PLAN (Quick Debate mode)
    # ===================================================================

    # ── Quickstart: suggested claims ─────────────────────────────────────
    from arena.claim_metadata import SUGGESTED_CLAIMS, classify_falsifiability

    st.markdown('<div class="ar-section">Quickstart — Try a Claim</div>', unsafe_allow_html=True)
    st.caption("Click any claim to load it. Or enter your own below.")
    _qs_cols = st.columns(3)
    for _i, _qs in enumerate(SUGGESTED_CLAIMS):
        with _qs_cols[_i % 3]:
            _qs_label = f"{_qs['domain']}: {_qs['text']}"
            if st.button(_qs_label, key=f"arena_qs_claim_{_i}", use_container_width=True):
                st.session_state["claim_text"] = _qs["text"]
                st.rerun()

    st.markdown('<div class="ar-section">Claim & Run Plan</div>', unsafe_allow_html=True)

    claim = st.text_area(
    "Claim",
    value=st.session_state.claim_text,
    placeholder="e.g. The COVID-19 vaccine causes infertility",
    key="claim_text",
    height=80,
    help="The misinformation claim to debate.",
    label_visibility="collapsed",
    )
    _arena_dbg("CLAIM_INPUT", ui_claim=_get_ui_claim(),
           ss_topic=st.session_state.get("topic", ""))

    # ── Falsifiability badge (surfaces F1 — biggest predictor of outcome) ──
    _current_claim_text = (st.session_state.get("claim_text") or "").strip()
    if _current_claim_text:
        _fals_label, _fals_source = classify_falsifiability(_current_claim_text)
        if _fals_label == "falsifiable":
            st.markdown(
                '<div style="display:inline-block; padding:0.25rem 0.7rem; '
                'border-radius:4px; background:rgba(76,175,125,0.15); '
                'border:1px solid rgba(76,175,125,0.5); color:#4CAF7D; '
                'font-size:0.78rem; font-weight:600; font-family:\'IBM Plex Mono\', monospace;">'
                'FALSIFIABLE CLAIM'
                '</div>'
                '<span style="margin-left:0.6rem; color:#888; font-size:0.82rem;">'
                'Evidence can settle this. Historically the fact-checker wins ~95% of these debates.'
                '</span>',
                unsafe_allow_html=True,
            )
        elif _fals_label == "unfalsifiable":
            st.markdown(
                '<div style="display:inline-block; padding:0.25rem 0.7rem; '
                'border-radius:4px; background:rgba(212,168,67,0.15); '
                'border:1px solid rgba(212,168,67,0.5); color:#D4A843; '
                'font-size:0.78rem; font-weight:600; font-family:\'IBM Plex Mono\', monospace;">'
                'UNFALSIFIABLE CLAIM'
                '</div>'
                '<span style="margin-left:0.6rem; color:#888; font-size:0.82rem;">'
                'No evidence can fully settle this. Debates split closer to ~53% / 47%.'
                '</span>',
                unsafe_allow_html=True,
            )

        # ── Predicted Outcome panel (study baseline for this claim's cell) ──
        from arena.presentation.streamlit.components.arena.baseline_panels import (
            render_predicted_outcome_panel,
        )
        render_predicted_outcome_panel(_current_claim_text)

    st.markdown('<div class="ar-section">Episodes & Models</div>', unsafe_allow_html=True)
    st.caption(
        "Pick the models and number of exchanges for each episode. "
        "An exchange is one back-and-forth (spreader speaks, then fact-checker replies)."
    )

    # Widget key is decoupled from the runner's `num_episodes` so the Start
    # button can override the runtime value to 1 (each chain entry is its own
    # one-episode run). The widget preserves the user's form selection
    # across reruns; we mirror it into `num_episodes` below for display.
    if "form_num_episodes" not in st.session_state:
        st.session_state["form_num_episodes"] = int(st.session_state.get("num_episodes", 1) or 1)
    num_episodes = st.number_input(
        "How many episodes?",
        min_value=1,
        max_value=20,
        value=st.session_state["form_num_episodes"],
        key="form_num_episodes",
        help="Each episode is a separate debate. With more than one, they'll run back-to-back.",
    )
    # Sync runtime variable — ONLY when no debate is in flight. While a
    # multi-episode chain is running, the Start handler set num_episodes=1
    # so the runner's internal chain doesn't fire; we must not clobber that
    # by re-mirroring the form value here.
    _run_in_flight_for_neps = (
        st.session_state.get("run_active")
        or st.session_state.get("match_in_progress")
        or st.session_state.get("debate_running")
        or st.session_state.get("pending_episodes")
    )
    if not _run_in_flight_for_neps:
        st.session_state["num_episodes"] = int(num_episodes)

    # ── Per-episode configuration rows ────────────────────────────────────
    _default_model_idx = get_default_model_index(AVAILABLE_MODELS)
    _default_model = AVAILABLE_MODELS[_default_model_idx] if AVAILABLE_MODELS else "gpt-4o-mini"

    # Seed the persistent config list to match num_episodes.
    _eps_cfg = list(st.session_state.get("episode_configs") or [])
    while len(_eps_cfg) < num_episodes:
        _prev = _eps_cfg[-1] if _eps_cfg else {
            "spreader": st.session_state.get("spreader_model", _default_model),
            "debunker": st.session_state.get("debunker_model", _default_model),
            "exchanges": int(st.session_state.get("max_turns", 5) or 5),
        }
        _eps_cfg.append({**_prev})
    _eps_cfg = _eps_cfg[:num_episodes]
    st.session_state["episode_configs"] = _eps_cfg

    # Render header row + episode rows
    _hdr_cols = st.columns([0.5, 2, 2, 1])
    _hdr_cols[0].markdown('<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Ep</div>', unsafe_allow_html=True)
    _hdr_cols[1].markdown('<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Spreader</div>', unsafe_allow_html=True)
    _hdr_cols[2].markdown('<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Fact-checker</div>', unsafe_allow_html=True)
    _hdr_cols[3].markdown('<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Exchanges</div>', unsafe_allow_html=True)

    for _idx in range(num_episodes):
        _row = _eps_cfg[_idx]
        _cols = st.columns([0.5, 2, 2, 1])
        with _cols[0]:
            st.markdown(f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.95rem;padding-top:0.5rem;color:var(--color-text-primary,#E8E4D9);">{_idx + 1}</div>', unsafe_allow_html=True)
        with _cols[1]:
            _spr_options = AVAILABLE_MODELS
            _spr_idx = _spr_options.index(_row["spreader"]) if _row["spreader"] in _spr_options else _default_model_idx
            _new_spr = st.selectbox(
                "Spreader",
                options=_spr_options,
                index=_spr_idx,
                key=f"ep_spr_{_idx}",
                label_visibility="collapsed",
            )
        with _cols[2]:
            _deb_idx = _spr_options.index(_row["debunker"]) if _row["debunker"] in _spr_options else _default_model_idx
            _new_deb = st.selectbox(
                "Fact-checker",
                options=_spr_options,
                index=_deb_idx,
                key=f"ep_deb_{_idx}",
                label_visibility="collapsed",
            )
        with _cols[3]:
            _new_xch = st.number_input(
                "Exchanges",
                min_value=1,
                max_value=20,
                value=int(_row.get("exchanges", 5) or 5),
                step=1,
                key=f"ep_xch_{_idx}",
                label_visibility="collapsed",
            )
        # Persist back to the canonical list
        _eps_cfg[_idx] = {"spreader": _new_spr, "debunker": _new_deb, "exchanges": int(_new_xch)}

    st.session_state["episode_configs"] = _eps_cfg

    # Sync the legacy session-state keys used by the rest of the app from
    # episode 1 — but ONLY when no debate is running. During an active run
    # (especially a multi-episode chain), the chain handler sets these keys
    # to the *current* episode's models; we must not overwrite them here.
    _run_in_flight = (
        st.session_state.get("run_active")
        or st.session_state.get("match_in_progress")
        or st.session_state.get("debate_running")
    )
    if _eps_cfg and not _run_in_flight:
        _first = _eps_cfg[0]
        st.session_state["spreader_model"] = _first["spreader"]
        st.session_state["debunker_model"] = _first["debunker"]
        st.session_state["max_turns"] = int(_first["exchanges"])
        # Build the legacy turn_plan from the rows
        st.session_state["turn_plan"] = [int(r["exchanges"]) for r in _eps_cfg]
        st.session_state["turn_plan_csv"] = ",".join(str(int(r["exchanges"])) for r in _eps_cfg)
        st.session_state["turn_plan_valid"] = True

    # (Multi-claim mode removed — use Experiment mode for batch runs)

    # ===================================================================
    # CLAIM TAXONOMY - fully automatic, no dropdown
    # ===================================================================
    from arena.claim_metadata import classify_claim

    _current_claim = st.session_state.get("claim_text", "")
    _last_classified = st.session_state.get("_last_classified_claim", "")

    # Auto-classify whenever the claim text changes
    if _current_claim and _current_claim.strip() != _last_classified:
        _auto_type, _auto_source = classify_claim(_current_claim.strip(), use_llm_fallback=False)
        if _auto_type and _auto_type != "unknown":
            st.session_state["claim_type"] = _auto_type
            st.session_state["_auto_classify_source"] = _auto_source
        else:
            st.session_state["claim_type"] = ""
            st.session_state["_auto_classify_source"] = ""
        st.session_state["_last_classified_claim"] = _current_claim.strip()

    st.session_state.setdefault("claim_type", "")

    # ===================================================================
    # RUN CONTROLS - Single button to start run + first match
    # ===================================================================
    st.markdown('<div class="ar-section">Run Controls</div>', unsafe_allow_html=True)
    col_run_start, col_run_showdown, col_run_stop = st.columns([2, 2, 1])
    with col_run_start:
        if st.button("Start debate", type="primary", use_container_width=True, key="arena_start_debate_btn"):
            ss = st.session_state

            # ── Validate API keys ──
            from arena.utils.api_keys import get_key_status
            from arena.agents import is_anthropic_model, is_gemini_model, is_grok_model
            _ks = get_key_status()
            _missing = []

            # Validate keys across every episode's chosen models (not just the first row).
            _eps_to_validate = ss.get("episode_configs") or [{
                "spreader": ss.get("spreader_model", "gpt-4o-mini"),
                "debunker": ss.get("debunker_model", "gpt-4o-mini"),
            }]
            _checked = set()
            for _ep in _eps_to_validate:
                for _role, _m in [("Spreader", _ep.get("spreader", "")), ("Fact-checker", _ep.get("debunker", ""))]:
                    if (_role, _m) in _checked or not _m:
                        continue
                    _checked.add((_role, _m))
                    if is_anthropic_model(_m) and not _ks.get("anthropic", {}).get("set"):
                        _missing.append(f"{_role} ({_m}): set ANTHROPIC_API_KEY")
                    elif is_gemini_model(_m) and not _ks.get("gemini", {}).get("set"):
                        _missing.append(f"{_role} ({_m}): set GEMINI_API_KEY")
                    elif is_grok_model(_m) and not _ks.get("xai", {}).get("set"):
                        _missing.append(f"{_role} ({_m}): set XAI_API_KEY")
                    elif not is_anthropic_model(_m) and not is_gemini_model(_m) and not is_grok_model(_m) and not _ks.get("openai", {}).get("set"):
                        _missing.append(f"{_role} ({_m}): set OPENAI_API_KEY")
            if _missing:
                st.error("**Missing API key(s).** " + " · ".join(_missing) + ". Paste in the sidebar or `.streamlit/secrets.toml`.")
                st.stop()

            # ── Validate claim input ──
            ui_claim = _get_ui_claim()
            if not ui_claim:
                st.warning("Please enter a claim to debate.")
                st.stop()

            if ss.get("turn_plan_valid") is False:
                st.error("Fix the episode plan (exchanges must be valid).")
                st.stop()

            # ── Multi-episode runs (N > 1): chain the rest. ──
            _eps_cfg = ss.get("episode_configs") or []
            ss["chain_total"] = max(1, len(_eps_cfg))
            if len(_eps_cfg) > 1:
                _ct = ss.get("claim_type", "")
                # First episode runs immediately below.
                # Episodes 2..N are queued for the chain handler to pick up
                # when the previous one finishes.
                ss["pending_episodes"] = [
                    {
                        "claim":          ui_claim,
                        "claim_type":     _ct,
                        "exchanges":      int(_ep.get("exchanges", 5)),
                        "spreader_model": _ep.get("spreader"),
                        "debunker_model": _ep.get("debunker"),
                    }
                    for _ep in _eps_cfg[1:]
                ]
                # Use the FIRST episode's models for the run we're about to start.
                ss["spreader_model"] = _eps_cfg[0]["spreader"]
                ss["debunker_model"] = _eps_cfg[0]["debunker"]
                ss["max_turns"]      = int(_eps_cfg[0]["exchanges"])
                # CRITICAL: the runner has its own internal episode chain that
                # reuses the current models. Force num_episodes=1 so each
                # chained debate is its own one-episode run; episodes 2..N
                # come from pending_episodes (with their own models).
                ss["num_episodes"] = 1
            else:
                ss["pending_episodes"] = []
                ss["num_episodes"]     = 1

            # Sync episode 1's models (works for both N=1 and N>1, since
            # episode 1 always runs first; episodes 2..N are chained via
            # pending_episodes when this one completes).
            if _eps_cfg:
                ss["spreader_model"] = _eps_cfg[0]["spreader"]
                ss["debunker_model"] = _eps_cfg[0]["debunker"]
                ss["max_turns"] = int(_eps_cfg[0]["exchanges"])

            # ── Create run boundary ──
            ss["run_active"] = True
            ss["episodes_completed"] = 0
            ss["episode_idx"] = 1
            ss["current_claim_index"] = ss.get("current_claim_index", 0)
            if "run_id" in ss:
                del ss["run_id"]

            try:
                from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
            except ImportError:
                sys.path.insert(0, "src")
                from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
            reset_episode_state_for_chaining(ss)

            # ── Start first match immediately ──
            ss["topic"] = ui_claim
            ss["current_claim"] = ui_claim
            ss["claim"] = ui_claim
            ss["debate_messages"] = []
            ss["episode_transcript"] = []
            ss["completed_turn_pairs"] = 0
            ss["turn_idx"] = 0
            ss["debate_phase"] = "spreader"

            # Reset live insights accumulators for the new debate
            _reset_live_insights()

            apply_turn_plan_to_episode(ss, ss.get("episode_idx", 1))

            ss["match_in_progress"] = True
            ss["debate_running"] = True
            ss["debate_autoplay"] = True
            ss["match_id"] = f"match_{ss['episode_idx']}"

            st.rerun()

    with col_run_showdown:
        _show_clicked = st.button(
            "🎯 Run Showdown",
            use_container_width=True,
            key="arena_showdown_btn",
            help=(
                "Runs the current claim through several model matchups in sequence "
                "(GPT-4o-mini vs itself, Claude vs Claude, mixed pairs). When done, "
                "compare them side-by-side in the Explore tab to see how different "
                "models argue the same claim."
            ),
        )
        # Nudge from the verdict can also trigger this
        if st.session_state.pop("showdown_request", False):
            _show_clicked = True

        if _show_clicked:
            ss = st.session_state
            ui_claim = _get_ui_claim()
            if not ui_claim:
                st.warning("Enter or select a claim first.")
                st.stop()

            # Build a Showdown chain: same claim, 4 model matchups.
            _SHOWDOWN_MATCHUPS = [
                ("gpt-4o-mini",             "gpt-4o-mini"),
                ("claude-sonnet-4-20250514","claude-sonnet-4-20250514"),
                ("gpt-4o-mini",             "claude-sonnet-4-20250514"),
                ("claude-sonnet-4-20250514","gpt-4o-mini"),
            ]
            _ct = ss.get("claim_type", "")
            _exch = int(ss.get("max_turns", 5) or 5)
            ss["pending_episodes"] = [
                {
                    "claim":          ui_claim,
                    "claim_type":     _ct,
                    "exchanges":      _exch,
                    "spreader_model": _spr_m,
                    "debunker_model": _deb_m,
                }
                for _spr_m, _deb_m in _SHOWDOWN_MATCHUPS
            ]
            ss["chain_total"]        = len(_SHOWDOWN_MATCHUPS)
            ss["showdown_run_size"]  = len(_SHOWDOWN_MATCHUPS)
            ss["showdown_completed"] = False
            st.rerun()

    with col_run_stop:
        if st.button("Stop", use_container_width=True, key="arena_stop_run_btn"):
            st.session_state["run_active"]        = False
            st.session_state["debate_running"]    = False
            st.session_state["match_in_progress"] = False
            st.session_state["pending_episodes"]  = []
            st.session_state["showdown_run_size"] = 0
            st.session_state["chain_total"]       = 1
            st.rerun()

    # ───────────────────────────────────────────────────────────────────
    # Multi-episode chain status — show what's queued behind the current run.
    # ───────────────────────────────────────────────────────────────────
    _pe_pending = st.session_state.get("pending_episodes") or []
    if _pe_pending and st.session_state.get("run_active"):
        st.info(
            f"⏭ **{len(_pe_pending)} more episode(s) queued.** "
            f"They'll start automatically when the current one finishes."
        )

    # ===================================================================
    # ACTIVE CLAIM BANNER + STATUS -- visible when run is live
    # ===================================================================
    _active_claim = (st.session_state.get("topic") or st.session_state.get("current_claim") or "").strip()
    _run_active = st.session_state.get("run_active", False)
    _match_live = st.session_state.get("match_in_progress", False)
    _debate_run = st.session_state.get("debate_running", False)

    if _run_active and _active_claim:
        run_badge = '<span class="ar-status-badge active">Run active</span>'
        match_badge = (
            '<span class="ar-status-badge running">Debate running</span>'
            if _debate_run else
            '<span class="ar-status-badge idle">Waiting for match</span>'
        )
        ep_done = st.session_state.get("episodes_completed", 0)
        ep_total = st.session_state.get("num_episodes", 1)
        ep_badge = f'<span class="ar-status-badge idle">Episode {ep_done + 1 if _debate_run else ep_done}/{ep_total}</span>'
        st.markdown(
            f'<div class="ar-claim-banner">'
            f'<div class="ar-claim-label">Active claim</div>'
            f'<div class="ar-claim-text">{_active_claim}</div>'
            f'</div>'
            f'<div class="ar-status-strip">{run_badge}{match_badge}{ep_badge}</div>',
            unsafe_allow_html=True,
        )

    # ===================================================================
    # PROGRESS & MOMENTUM - Episode · Exchange · Phase
    # ===================================================================
    completed_turns = sum(1 for m in st.session_state.get("debate_messages", [])
                          if m.get("speaker") == "debunker" and m.get("status") == "final")
    total_exch = int(st.session_state.get("max_turns", 5) or 5)
    is_running  = st.session_state.get("debate_running", False)

    # Episode position in a (possibly chained) run.
    _chain_total    = int(st.session_state.get("chain_total", 1) or 1)
    _pending_count  = len(st.session_state.get("pending_episodes") or [])
    # Clamp so it always shows 1..N
    _chain_position = max(1, min(_chain_total, _chain_total - _pending_count))

    # Phase label — what the live agent is doing.
    _phase = (st.session_state.get("debate_phase") or "spreader").lower()
    if "spread" in _phase:
        _phase_label = "Spreader is preparing response…"
    elif "debunk" in _phase or "fact" in _phase:
        _phase_label = "Fact-checker is preparing response…"
    else:
        _phase_label = "Preparing response…"

    progress_value = 0 if total_exch == 0 else min(completed_turns / total_exch, 1.0)

    # Build the progress text in three parts: Episode · Exchange · Phase
    _parts = []
    if _chain_total > 1:
        _parts.append(f"Episode {_chain_position}/{_chain_total}")
    _parts.append(f"Exchange {min(completed_turns + (1 if is_running else 0), total_exch)}/{total_exch}")
    if is_running:
        _parts.append(_phase_label)
    elif completed_turns >= total_exch and total_exch > 0:
        _parts.append("complete")

    st.progress(progress_value, text=" · ".join(_parts))

    # Momentum bar — shows who's winning based on scorecard if available
    messages = st.session_state.get("debate_messages", [])
    if len(messages) >= 2 and is_running:
        # Count tactic signals as a rough momentum proxy
        spr_msgs = [m for m in messages if m.get("speaker") == "spreader" and m.get("status") == "final"]
        deb_msgs = [m for m in messages if m.get("speaker") == "debunker" and m.get("status") == "final"]
        spr_len = sum(len(m.get("content", "")) for m in spr_msgs)
        deb_len = sum(len(m.get("content", "")) for m in deb_msgs)
        total_len = spr_len + deb_len
        if total_len > 0:
            deb_pct = deb_len / total_len
            # Normalize to 20-80 range so it never looks completely one-sided
            bar_pct = 0.2 + (deb_pct * 0.6)
            spr_width = int((1 - bar_pct) * 100)
            deb_width = int(bar_pct * 100)
            st.markdown(f"""
            <div style="display:flex; height:8px; border-radius:4px; overflow:hidden; margin:0.3rem 0 1rem 0;">
                <div style="width:{spr_width}%; background:linear-gradient(90deg, #C9363E, #D4A843);"></div>
                <div style="width:{deb_width}%; background:linear-gradient(90deg, #4A7FA5, #2ECC71);"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.7rem; color:#888; margin-top:-0.5rem; margin-bottom:0.5rem;">
                <span>Spreader</span>
                <span>Momentum</span>
                <span>Fact-checker</span>
            </div>
            """, unsafe_allow_html=True)

    # Optional debug invariant checks (gate with debug_mode or env)
    if st.session_state.get("debug_mode", False) or os.environ.get("ARENA_DEBUG_INVARIANTS"):
        try:
            from arena.ui.run_planner import check_debate_invariants
            check_debate_invariants(st.session_state)
        except ImportError:
            pass

    # ===================================================================
    # SANITY CHECK - Debug-only visibility confirmation
    # ===================================================================
    if st.session_state.get("DEV_MODE", False):
        st.caption("UI sanity: claim input + progress bars + transcript should be visible below.")

    # ===================================================================
    # LIVE DEBATE CHAT - Scrollable conversation feed
    # ===================================================================

    # Import and initialize debate chat
    from arena.ui.debate_chat import (
        inject_debate_chat_css,
        init_debate_chat_state,
        render_debate_chat,
        render_debate_controls,
        run_debate_step,
    )

    inject_debate_chat_css()
    init_debate_chat_state()

    # Define agent generation functions
    def generate_spreader_fn(context):
        """Generate a spreader message using existing logic."""
        turn_idx = st.session_state.debate_turn_idx

        spreader_context = {
            "topic": st.session_state.get("topic", ""),
            "turn_idx": turn_idx,
            "last_opponent_text": _get_last_message_text("debunker"),
            "system_prompt": st.session_state.get("spreader_prompt", ""),
        }

        _arena_dbg("CONTEXT_BUILD", speaker="spreader",
                   ui_claim=_get_ui_claim()[:50],
                   ss_topic=st.session_state.get("topic", "")[:50],
                   context_topic=spreader_context.get("topic", "")[:50])

        return _generate_agent_message(
            st.session_state.get("spreader_agent"),
            spreader_context
        )

    def generate_debunker_fn(context):
        """Generate a debunker message using existing logic."""
        turn_idx = st.session_state.debate_turn_idx

        debunker_context = {
            "topic": st.session_state.get("topic", ""),
            "turn_idx": turn_idx,
            "last_opponent_text": _get_last_message_text("spreader"),
            "system_prompt": st.session_state.get("debunker_prompt", ""),
        }

        return _generate_agent_message(
            st.session_state.get("debunker_agent"),
            debunker_context
        )

    # Render controls
    render_debate_controls()

    # I5: Track renderer input
    _arena_dbg("RENDER", debate_messages_count=len(st.session_state.debate_messages),
               last_msg_turn=st.session_state.debate_messages[-1].get('turn') if st.session_state.debate_messages else 'none',
               last_msg_speaker=st.session_state.debate_messages[-1].get('speaker') if st.session_state.debate_messages else 'none')

    # Render chat
    if st.session_state.get("debug_mode", False):
        print(f"[ARENA] RENDER episode_idx={st.session_state.get('episode_idx')} episodes_completed={st.session_state.get('episodes_completed')} len(debate_messages)={len(st.session_state.get('debate_messages', []))} debate_running={st.session_state.get('debate_running')} _pending_chain={st.session_state.get('_pending_chain')}")
    render_debate_chat(st.session_state.debate_messages)

    # Detect newly-completed turn pairs → fire toasts + accumulate panel events.
    _run_live_detection()
    # Show the accumulated panel beneath the transcript.
    _render_live_insights_panel()

    # Run debate step if active or pending deferred chain
    if st.session_state.get("debate_running", False) or st.session_state.get("_pending_chain", False):
        max_turns = st.session_state.get("max_turns", 5)
        did_advance = run_debate_step(
            max_turns=max_turns,
            generate_spreader_fn=generate_spreader_fn,
            generate_debunker_fn=generate_debunker_fn,
        )
        # I6: Track rerun decision
        _arena_dbg("RERUN_DECISION", did_advance=did_advance,
                   debate_autoplay=st.session_state.get("debate_autoplay", True),
                   debate_running=st.session_state.get("debate_running", False),
                   will_rerun=(did_advance and st.session_state.get("debate_autoplay", True) and st.session_state.debate_running))

        # Auto-rerun if autoplay is enabled and we completed a message
        if did_advance and st.session_state.get("debate_autoplay", True) and st.session_state.debate_running:
            time.sleep(0.15)  # Brief pause for readability
            _arena_dbg("RERUN_EXECUTED")
            st.rerun()

    # Force one final UI rerun after completion to render all messages
    if st.session_state.get("_arena_needs_final_rerun", False):
        _arena_dbg("RERUN_EXECUTED", reason="final_render_after_completion")
        st.session_state["_arena_needs_final_rerun"] = False
        st.rerun()

    # ===================================================================
    # DEBUG PANEL - Show internal state for troubleshooting
    # ===================================================================
    show_debug_panel = st.session_state.get("show_debug_panel", False)
    if show_debug_panel:
        with st.expander("Transcript Debug Panel", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Episode ID", st.session_state.get("episode_idx", 1))
                st.metric("Max Turns", st.session_state.get("max_turns", 5))
                st.metric("Transcript Len", len(st.session_state.get("episode_transcript", [])))

            with col2:
                completed_turns = len([msg for msg in st.session_state.get("episode_transcript", []) if msg.get("role") == "debunker"])
                st.metric("Completed Turns", completed_turns)
                last_turn_id = completed_turns if completed_turns > 0 else 0
                st.metric("Last Turn ID", last_turn_id)
                st.metric("Is Generating", st.session_state.get("is_generating_turn", False))

            with col3:
                is_running = st.session_state.get("is_running", False)
                st.metric("Is Running", str(is_running))
                debate_active = st.session_state.get("debate_active", False)
                st.metric("Debate Active", str(debate_active))
                last_error = st.session_state.get("last_error", "None")
                if last_error and len(str(last_error)) > 20:
                    last_error = str(last_error)[:17] + "..."
                st.metric("Last Error", last_error)

    # ===================================================================
    # OPENAI ERROR DISPLAY - Show after transcript area
    # ===================================================================
    if st.session_state.get("last_openai_error"):
        st.error(f"OpenAI API Error: {st.session_state['last_openai_error']}")
        if st.button("Clear Error", help="Dismiss this error message"):
            del st.session_state["last_openai_error"]
            st.rerun()

    # ===================================================================
    # JUDGE REPORT + INSIGHTS - Show when debate completes
    # ===================================================================
    if st.session_state.get("match_completed") or st.session_state.get("judge_decision"):
        st.markdown('<div class="ar-section">Results</div>', unsafe_allow_html=True)

    render_judge_report()
    render_debate_insights()
