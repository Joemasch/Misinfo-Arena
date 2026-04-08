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
    """Render the sidebar with agent configuration, judge settings, API keys, and data management."""

    # ── Agent Models ──────────────────────────────────────────────────────
    st.sidebar.markdown("**Agent Models**")
    st.sidebar.caption("Select which LLM powers each side of the debate.")

    default_idx = get_default_model_index(AVAILABLE_MODELS)

    st.sidebar.selectbox(
        "Spreader",
        options=AVAILABLE_MODELS,
        index=default_idx,
        key="spreader_model",
    )
    st.sidebar.selectbox(
        "Fact-checker",
        options=AVAILABLE_MODELS,
        index=default_idx,
        key="debunker_model",
    )

    # ── Judge Configuration ───────────────────────────────────────────────
    st.sidebar.markdown("**Judge**")
    st.sidebar.caption("The judge evaluates each debate using a 6-dimension rubric.")

    _judge_models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
    st.sidebar.selectbox(
        "Judge model",
        options=_judge_models,
        index=0,
        key="judge_model_select",
        help="Which model scores the debate. gpt-4o-mini is cheapest; gpt-4o is most capable.",
    )

    st.sidebar.selectbox(
        "Reliability runs",
        options=[1, 3, 5],
        index=0,
        key="judge_consistency_runs",
        help=(
            "How many times the judge scores each debate. "
            "At 1× (default), the judge runs once. "
            "At 3× or 5×, it runs multiple times and averages the scores "
            "to reduce randomness from the LLM. "
            "Higher = more reliable scores but slower and more expensive."
        ),
    )
    _jcr = st.session_state.get("judge_consistency_runs", 1)
    if _jcr and int(_jcr) > 1:
        st.sidebar.caption(f"Each debate will be judged **{_jcr} times** and scores averaged.")

    # ── Temperature (fixed) ───────────────────────────────────────────────
    st.session_state["spreader_temperature"] = DEFAULT_SPREADER_TEMPERATURE
    st.session_state["debunker_temperature"] = DEFAULT_DEBUNKER_TEMPERATURE
    st.sidebar.caption(
        f"Temperature: Spreader {DEFAULT_SPREADER_TEMPERATURE} · "
        f"FC {DEFAULT_DEBUNKER_TEMPERATURE} · Judge 0.10 (fixed)"
    )

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

    if st.sidebar.button("Load sample data", key="load_sample_btn", help="Generate 60 sample episodes across 5 domains and 3 models to explore all features."):
        from arena.sample_data import generate_sample_data
        result = generate_sample_data()
        st.session_state["runs_refresh_token"] = st.session_state.get("runs_refresh_token", 0) + 1
        st.sidebar.success(f"Loaded {result['episodes']} sample episodes across {result['runs']} runs")
        st.rerun()

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

    # Auto-run queue state
    st.session_state.setdefault("auto_run_active", False)
    st.session_state.setdefault("auto_run_queue_idx", 0)
    st.session_state.setdefault("auto_run_total_episodes_done", 0)
    st.session_state.setdefault("auto_run_started_at", None)

    # ===================================================================
    # AUTO-RUN QUEUE ADVANCE — fires before UI, advances when prev run done
    # ===================================================================
    if st.session_state.get("auto_run_active"):
        _ar_queue = st.session_state.get("sc_run_queue") or []
        _ar_idx = st.session_state.get("auto_run_queue_idx", 0)
        _ar_run_active = st.session_state.get("run_active", False)
        _ar_pending = st.session_state.get("_pending_chain", False)
        _ar_match_ip = st.session_state.get("match_in_progress", False)
        _ar_debate_run = st.session_state.get("debate_running", False)

        # Previous run finished: not active, no pending chain, no match in progress
        _ar_prev_done = (not _ar_run_active and not _ar_pending
                         and not _ar_match_ip and not _ar_debate_run)

        if _ar_prev_done and _ar_idx < len(_ar_queue):
            _ar_next = _ar_queue[_ar_idx]
            ss = st.session_state

            # Tally episodes from the just-finished run
            _ar_just_done = ss.get("episodes_completed", 0)
            ss["auto_run_total_episodes_done"] = (
                ss.get("auto_run_total_episodes_done", 0) + _ar_just_done
            )

            # Load queue entry settings
            _ar_ui_claim = _ar_next["claim"]
            _ar_turn_plan = _ar_next.get("turn_plan", [5])
            _ar_num_eps = _ar_next.get("num_episodes", len(_ar_turn_plan))
            _ar_ct = _ar_next.get("claim_type", "")

            ss["claim_text"] = _ar_ui_claim
            ss["arena_mode"] = "single_claim"
            ss["turn_plan"] = _ar_turn_plan
            ss["turn_plan_csv"] = ",".join(str(t) for t in _ar_turn_plan)
            ss["turn_plan_valid"] = True
            ss["max_turns"] = _ar_turn_plan[0] if _ar_turn_plan else 5
            ss["num_episodes"] = _ar_num_eps
            if _ar_ct:
                ss["claim_type"] = _ar_ct

            # Apply model overrides from queue entry
            if _ar_next.get("spreader_model"):
                ss["spreader_model"] = _ar_next["spreader_model"]
            if _ar_next.get("debunker_model"):
                ss["debunker_model"] = _ar_next["debunker_model"]
            if _ar_next.get("judge_model"):
                ss["judge_model_select"] = _ar_next["judge_model"]

            # --- Start the run (mirrors "Start debate" button logic) ---
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

            ss["topic"] = _ar_ui_claim
            ss["current_claim"] = _ar_ui_claim
            ss["claim"] = _ar_ui_claim
            ss["debate_messages"] = []
            ss["episode_transcript"] = []
            ss["completed_turn_pairs"] = 0
            ss["turn_idx"] = 0
            ss["debate_phase"] = "spreader"

            if _ar_is_sc:
                apply_turn_plan_to_episode(ss, 1)

            ss["match_in_progress"] = True
            ss["debate_running"] = True
            ss["debate_autoplay"] = True
            ss["match_id"] = f"match_{ss['episode_idx']}"

            # Advance queue pointer
            ss["auto_run_queue_idx"] = _ar_idx + 1

            st.rerun()

        elif _ar_prev_done and _ar_idx >= len(_ar_queue):
            # All runs in queue finished
            _ar_just_done = st.session_state.get("episodes_completed", 0)
            st.session_state["auto_run_total_episodes_done"] = (
                st.session_state.get("auto_run_total_episodes_done", 0)
                + _ar_just_done
            )
            _ar_total_done = st.session_state["auto_run_total_episodes_done"]
            _ar_started = st.session_state.get("auto_run_started_at")
            _ar_elapsed = ""
            if _ar_started:
                _ar_secs = int(time.time() - _ar_started)
                _ar_mins, _ar_s = divmod(_ar_secs, 60)
                _ar_elapsed = f" in {_ar_mins}m {_ar_s}s" if _ar_mins else f" in {_ar_s}s"

            st.session_state["auto_run_active"] = False
            st.session_state["auto_run_queue_idx"] = 0
            st.session_state["auto_run_completed_msg"] = (
                f"Auto-run complete: {len(_ar_queue)} runs, "
                f"{_ar_total_done} episodes{_ar_elapsed}."
            )
            st.session_state["auto_run_total_episodes_done"] = 0
            st.session_state["auto_run_started_at"] = None

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
    st.markdown('<div class="ar-section">Claim & Run Plan</div>', unsafe_allow_html=True)

    _sc_method = st.radio(
        "Input method",
        options=["manual", "csv"],
        format_func=lambda x: "Manual entry" if x == "manual" else "Upload CSV",
        horizontal=True,
        key="sc_input_method",
    )

    if _sc_method == "csv":
        st.markdown(
            '<div style="font-size:0.88rem;color:#555;margin-bottom:0.8rem;">'
            'Upload a CSV with one row per episode. Required: <code>claim</code>. '
            'Optional: <code>run</code>, <code>claim_type</code>, <code>max_turns</code>, '
            '<code>spreader_model</code>, <code>debunker_model</code>, <code>judge_model</code>. '
            'Model columns override the sidebar selection for that run.</div>',
            unsafe_allow_html=True,
        )

        # Visual format example
        st.markdown(
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:0.7rem 1rem;margin-bottom:0.8rem;font-family:monospace;font-size:0.8rem;'
            'line-height:1.6;color:#374151">'
            '<span style="color:#9ca3af">CSV format:</span><br>'
            'claim,run,claim_type,max_turns,spreader_model,debunker_model,judge_model<br>'
            'Vaccines cause autism,1,Health / Vaccine,2,gpt-4o-mini,gpt-4o-mini,gpt-4o-mini<br>'
            'Vaccines cause autism,1,Health / Vaccine,4,gpt-4o-mini,gpt-4o-mini,gpt-4o-mini<br>'
            'Vaccines cause autism,1,Health / Vaccine,6,gpt-4o-mini,gpt-4o-mini,gpt-4o-mini<br>'
            'Vaccines cause autism,2,Health / Vaccine,4,gemini-2.0-flash,gemini-2.0-flash,gpt-4o-mini<br>'
            'Vaccines cause autism,2,Health / Vaccine,6,gemini-2.0-flash,gemini-2.0-flash,gpt-4o-mini<br>'
            'Climate change is a hoax,3,Environmental,4,grok-3-mini,gpt-4o-mini,gpt-4o-mini<br>'
            'Climate change is a hoax,3,Environmental,6,grok-3-mini,gpt-4o-mini,gpt-4o-mini'
            '</div>',
            unsafe_allow_html=True,
        )

        _sc_file = st.file_uploader("Upload single-claim CSV", type=["csv", "xlsx"], key="sc_csv_upload")
        if _sc_file is not None:
            try:
                _sc_df = _pd.read_csv(_sc_file) if _sc_file.name.endswith(".csv") else _pd.read_excel(_sc_file)
                _sc_df.columns = [c.strip().lower().replace(" ", "_") for c in _sc_df.columns]
                # Auto-classify claims missing claim_type
                _sc_df = _auto_classify_df(_sc_df)
                if "claim" not in _sc_df.columns:
                    st.error("CSV must have a `claim` column.")
                else:
                    # Group by run column if present
                    has_run_col = "run" in _sc_df.columns
                    if has_run_col:
                        _run_groups = list(_sc_df.groupby("run", sort=True))
                    else:
                        _run_groups = [(1, _sc_df)]

                    _run_queue = []
                    for _run_num, _run_df in _run_groups:
                        _claim = str(_run_df["claim"].iloc[0]).strip()
                        if "max_turns" in _run_df.columns:
                            _turns = [int(t) for t in _run_df["max_turns"].fillna(5)]
                        else:
                            _turns = [5] * len(_run_df)
                        _ct = str(_run_df["claim_type"].iloc[0]).strip() if "claim_type" in _run_df.columns and _pd.notna(_run_df["claim_type"].iloc[0]) else ""
                        # Extract model overrides if present
                        _spr_model = str(_run_df["spreader_model"].iloc[0]).strip() if "spreader_model" in _run_df.columns and _pd.notna(_run_df["spreader_model"].iloc[0]) else ""
                        _deb_model = str(_run_df["debunker_model"].iloc[0]).strip() if "debunker_model" in _run_df.columns and _pd.notna(_run_df["debunker_model"].iloc[0]) else ""
                        _jud_model = str(_run_df["judge_model"].iloc[0]).strip() if "judge_model" in _run_df.columns and _pd.notna(_run_df["judge_model"].iloc[0]) else ""
                        _run_queue.append({
                            "run": _run_num,
                            "claim": _claim,
                            "claim_type": _ct,
                            "turn_plan": _turns,
                            "num_episodes": len(_run_df),
                            "spreader_model": _spr_model,
                            "debunker_model": _deb_model,
                            "judge_model": _jud_model,
                        })

                    st.session_state["sc_run_queue"] = _run_queue

                    # Set first run as active
                    _first = _run_queue[0]
                    st.session_state["claim_text"] = _first["claim"]
                    st.session_state["num_episodes"] = _first["num_episodes"]
                    st.session_state["turn_plan"] = _first["turn_plan"]
                    st.session_state["turn_plan_csv"] = ",".join(str(t) for t in _first["turn_plan"])
                    st.session_state["turn_plan_valid"] = True
                    st.session_state["max_turns"] = _first["turn_plan"][0] if _first["turn_plan"] else 5
                    if _first["claim_type"]:
                        st.session_state["claim_type"] = _first["claim_type"]
                    # Apply model overrides from CSV
                    if _first.get("spreader_model"):
                        st.session_state["spreader_model"] = _first["spreader_model"]
                    if _first.get("debunker_model"):
                        st.session_state["debunker_model"] = _first["debunker_model"]
                    if _first.get("judge_model"):
                        st.session_state["judge_model_select"] = _first["judge_model"]

                    # Summary
                    _total_eps = sum(r["num_episodes"] for r in _run_queue)
                    st.success(f"Loaded {len(_run_queue)} run(s), {_total_eps} total episodes")
                    with st.expander(f"Run queue ({len(_run_queue)} runs)", expanded=False):
                        for r in _run_queue:
                            _turns_str = ",".join(str(t) for t in r["turn_plan"])
                            _models = ""
                            if r.get("spreader_model") or r.get("debunker_model"):
                                _models = f' · models: {r.get("spreader_model", "default")} vs {r.get("debunker_model", "default")}'
                                if r.get("judge_model"):
                                    _models += f' (judge: {r["judge_model"]})'
                            st.caption(f"**Run {r['run']}:** \"{r['claim'][:50]}\" — {r['num_episodes']} eps ({_turns_str} turns) · {r['claim_type'] or '—'}{_models}")
            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")
                st.session_state["turn_plan_valid"] = False
        else:
            st.session_state.setdefault("turn_plan_valid", True)
    else:
        # Manual entry
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

        st.markdown('<div class="ar-section">Run Plan</div>', unsafe_allow_html=True)
        num_episodes = st.number_input(
            "Episodes",
            min_value=1,
            max_value=20,
            value=st.session_state["num_episodes"],
            key="num_episodes",
            help="Number of episodes in this run",
        )
        turn_plan_csv = st.text_input(
            "Turn plan (comma-separated)",
            value=st.session_state.get("turn_plan_csv", str(st.session_state.get("max_turns", 5))),
            key="turn_plan_csv",
            help="Turns per episode. Single value (e.g. 6) applies to all, or one per episode (e.g. 2,4,6,8,10)",
        )
        try:
            from arena.ui.run_planner import parse_turn_plan_csv
        except ImportError:
            sys.path.insert(0, "src")
            from arena.ui.run_planner import parse_turn_plan_csv
        plan, plan_err = parse_turn_plan_csv(
            st.session_state.get("turn_plan_csv", ""),
            st.session_state["num_episodes"],
            st.session_state.get("max_turns", 5),
        )
        if plan_err:
            st.error(plan_err)
            st.session_state["turn_plan_valid"] = False
        else:
            st.session_state["turn_plan"] = plan
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
    col_run_start, col_run_stop = st.columns(2)
    with col_run_start:
        if st.button("Start debate", type="primary", use_container_width=True, key="arena_start_debate_btn"):
            ss = st.session_state

            # ── Validate API keys ──
            from arena.utils.api_keys import get_key_status
            from arena.agents import is_anthropic_model, is_gemini_model, is_grok_model
            _ks = get_key_status()
            _missing = []
            for _role, _mk in [("Spreader", "spreader_model"), ("Fact-checker", "debunker_model")]:
                _m = ss.get(_mk, "gpt-4o-mini")
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
                st.error("Fix the Run Plan (turn plan must be valid).")
                st.stop()

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

            apply_turn_plan_to_episode(ss, ss.get("episode_idx", 1))

            ss["match_in_progress"] = True
            ss["debate_running"] = True
            ss["debate_autoplay"] = True
            ss["match_id"] = f"match_{ss['episode_idx']}"

            st.rerun()

    with col_run_stop:
        if st.button("Stop", use_container_width=True, key="arena_stop_run_btn"):
            st.session_state["run_active"] = False
            st.session_state["debate_running"] = False
            st.session_state["match_in_progress"] = False
            st.session_state["auto_run_active"] = False
            st.rerun()

    # ===================================================================
    # AUTO-RUN ALL — batch-process entire run queue
    # ===================================================================
    _ar_full_queue = st.session_state.get("sc_run_queue") or []
    _ar_is_active = st.session_state.get("auto_run_active", False)

    # Show completion message if just finished
    _ar_done_msg = st.session_state.pop("auto_run_completed_msg", None)
    if _ar_done_msg:
        st.success(_ar_done_msg)

    if len(_ar_full_queue) > 1 or _ar_is_active:
        st.markdown('<div class="ar-section">Auto-Run Queue</div>', unsafe_allow_html=True)

        if _ar_is_active:
            # Show progress while running
            _ar_q_idx = st.session_state.get("auto_run_queue_idx", 0)
            _ar_q_total = len(_ar_full_queue)
            _ar_ep_done = st.session_state.get("auto_run_total_episodes_done", 0)
            _ar_ep_cur_run = st.session_state.get("episodes_completed", 0)
            _ar_ep_running = _ar_ep_done + _ar_ep_cur_run

            st.info(
                f"Auto-running: run **{min(_ar_q_idx, _ar_q_total)}/{_ar_q_total}** "
                f"({_ar_ep_running} episodes completed so far)"
            )
            _ar_prog = min(_ar_q_idx / _ar_q_total, 1.0) if _ar_q_total > 0 else 0
            st.progress(_ar_prog, text=f"Queue: {_ar_q_idx}/{_ar_q_total} runs started")

            if st.button("Cancel auto-run", use_container_width=True, key="auto_run_cancel_btn"):
                st.session_state["auto_run_active"] = False
                st.info("Auto-run cancelled. Current run will finish.")
                st.rerun()
        else:
            # Show queue summary and start button
            _ar_total_runs = len(_ar_full_queue)
            _ar_total_eps = sum(r.get("num_episodes", 1) for r in _ar_full_queue)

            # Cost estimate
            _ar_model = st.session_state.get("spreader_model", "gpt-4o")
            _ar_cost_per_turn = 0.0085 if ("mini" not in _ar_model and "haiku" not in _ar_model and "flash" not in _ar_model) else 0.0006
            _ar_avg_turns = 6
            _ar_est = _ar_total_eps * _ar_avg_turns * 2 * _ar_cost_per_turn  # x2 for both agents
            _ar_est_low = _ar_est * 0.7
            _ar_est_high = _ar_est * 1.3

            st.markdown(
                f"**{_ar_total_runs}** runs queued with **{_ar_total_eps}** total episodes. "
                f"Estimated cost: **${_ar_est_low:.2f} -- ${_ar_est_high:.2f}**."
            )

            if st.button(
                "Auto-run all queued runs",
                type="primary",
                use_container_width=True,
                key="auto_run_start_btn",
            ):
                st.session_state["auto_run_active"] = True
                st.session_state["auto_run_queue_idx"] = 0
                st.session_state["auto_run_total_episodes_done"] = 0
                st.session_state["auto_run_started_at"] = time.time()
                # Clear any stale run state so the advance logic fires immediately
                st.session_state["run_active"] = False
                st.session_state["debate_running"] = False
                st.session_state["match_in_progress"] = False
                st.session_state["_pending_chain"] = False
                st.rerun()

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
    # PROGRESS BARS - Always visible (show current state)
    # ===================================================================
    st.markdown('<div class="ar-section">Progress</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        completed_turns = sum(1 for m in st.session_state.get("debate_messages", [])
                            if m.get("speaker") == "debunker" and m.get("status") == "final")
        total = st.session_state.get("max_turns", 5)
        progress_value = 0 if total == 0 else min(completed_turns / total, 1.0)
        phase = st.session_state.get("debate_phase", "spreader")
        phase_display = f" (Phase: {phase})" if st.session_state.get("debate_running") else ""
        st.progress(progress_value, text=f"Turns: {completed_turns}/{total}{phase_display}")

    with col2:
        episodes_completed = st.session_state.get("episodes_completed", 0)
        total_episodes = st.session_state.get("num_episodes", 1)
        if st.session_state.get("match_in_progress", False) or st.session_state.get("run_active", False):
            episode_progress = min(episodes_completed / total_episodes, 1.0) if total_episodes > 0 else 0
            st.progress(episode_progress, text=f"Episodes: {episodes_completed}/{total_episodes}")
        else:
            st.progress(0.0, text=f"Episodes: 0/{total_episodes}")

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
