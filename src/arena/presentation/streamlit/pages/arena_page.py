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
    TEMPERATURE_PRESETS,
    DEFAULT_TEMPERATURE_PRESET,
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


# ---------------------------------------------------------------------------
# Functions moved from app.py
# ---------------------------------------------------------------------------

def _render_sidebar():
    """
    Render the sidebar with model configuration and temperature controls.

    Agent model selection and temperature settings for Spreader and Debunker.
    """
    st.sidebar.markdown("**Models**")

    # Get default model index using module-level function
    default_idx = get_default_model_index(AVAILABLE_MODELS)

    spreader_model = st.sidebar.selectbox(
        "Spreader",
        options=AVAILABLE_MODELS,
        index=default_idx,
        key="spreader_model"
    )

    debunker_model = st.sidebar.selectbox(
        "Fact-checker",
        options=AVAILABLE_MODELS,
        index=default_idx,
        key="debunker_model"
    )

    # -- Temperature presets ------------------------------------------------
    st.sidebar.markdown("**Temperature**")

    preset_names = [p["name"] for p in TEMPERATURE_PRESETS]

    if "temperature_preset" not in st.session_state:
        st.session_state["temperature_preset"] = DEFAULT_TEMPERATURE_PRESET
    if "spreader_temperature" not in st.session_state:
        st.session_state["spreader_temperature"] = DEFAULT_SPREADER_TEMPERATURE
    if "debunker_temperature" not in st.session_state:
        st.session_state["debunker_temperature"] = DEFAULT_DEBUNKER_TEMPERATURE

    selected_preset_name = st.sidebar.selectbox(
        "Temperature preset",
        options=preset_names,
        index=preset_names.index(
            st.session_state.get("temperature_preset", DEFAULT_TEMPERATURE_PRESET)
        ),
        key="temperature_preset",
        label_visibility="collapsed",
    )

    preset = next(p for p in TEMPERATURE_PRESETS if p["name"] == selected_preset_name)
    st.sidebar.caption(preset["description"])

    if preset["spreader"] is not None:
        # Auto-set temperatures from preset
        st.session_state["spreader_temperature"] = preset["spreader"]
        st.session_state["debunker_temperature"] = preset["debunker"]
        st.sidebar.caption(
            f"Spreader **{preset['spreader']}** \u00b7 Fact-checker **{preset['debunker']}** \u00b7 Judge **0.10**"
        )
    else:
        # Custom -- show sliders
        st.sidebar.slider(
            "Spreader temperature",
            min_value=0.0, max_value=1.5,
            value=float(st.session_state["spreader_temperature"]),
            step=0.05, key="spreader_temperature",
        )
        st.sidebar.slider(
            "Fact-checker temperature",
            min_value=0.0, max_value=1.5,
            value=float(st.session_state["debunker_temperature"]),
            step=0.05, key="debunker_temperature",
        )

    if st.session_state.get("match_in_progress"):
        st.sidebar.caption("Warning: Match running -- temperature changes apply to the next episode.")

    # -- Judge settings -----------------------------------------------------
    st.sidebar.markdown("**Judge**")
    st.sidebar.selectbox(
        "Consistency runs",
        options=[1, 3, 5],
        index=0,
        key="judge_consistency_runs",
        help="Run the judge N times and average scores for reliability. Higher = more consistent but slower and more expensive.",
    )
    _jcr = st.session_state.get("judge_consistency_runs", 1)
    if _jcr and int(_jcr) > 1:
        st.sidebar.caption(f"Judge will run **{_jcr}x** per episode and average scores.")

    # -- API Keys ----------------------------------------------------------
    from arena.utils.api_keys import get_key_status, mask_key
    st.sidebar.markdown("**API Keys**")

    key_status = get_key_status()

    _providers = [
        ("openai",    "OPENAI_API_KEY",    "OpenAI",    "sk-..."),
        ("anthropic", "ANTHROPIC_API_KEY",  "Anthropic", "sk-ant-..."),
        ("gemini",    "GEMINI_API_KEY",     "Gemini",    "AI..."),
        ("xai",       "XAI_API_KEY",        "xAI (Grok)", "xai-..."),
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
                help=f"Paste your {label} key. Stored in session only — not saved to disk.",
            )
            if _val and _val.strip():
                import os
                os.environ[env_name] = _val.strip()
                st.sidebar.caption(f"{label}: `{mask_key(_val)}` (sidebar)")

    st.sidebar.caption("Keys from `.streamlit/secrets.toml` or env vars load automatically.")


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

    # -- Arena page CSS ----------------------------------------------------
    st.markdown("""
    <style>
    /* Arena section labels -- match rp-tab-section pattern */
    .ar-section {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #9ca3af;
        border-bottom: 1px solid rgba(0,0,0,0.08);
        padding-bottom: 0.3rem;
        margin: 1.4rem 0 0.75rem 0;
    }
    .ar-section:first-child { margin-top: 0; }

    /* Active claim banner -- mirrors rp-claim-banner */
    .ar-claim-banner {
        border-left: 4px solid #3A7EC7;
        background: rgba(58,126,199,0.06);
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 1.1rem;
        margin: 0.5rem 0 1rem 0;
    }
    .ar-claim-label {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #3A7EC7;
        margin-bottom: 0.2rem;
    }
    .ar-claim-text {
        font-size: 1rem;
        font-weight: 600;
        color: #1f2937;
        line-height: 1.4;
    }

    /* Status strip -- run/match state at a glance */
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
        border-radius: 999px;
        border: 1px solid rgba(128,128,128,0.25);
        color: #374151;
    }
    .ar-status-badge.active {
        border-color: rgba(34,197,94,0.5);
        color: #166534;
        background: rgba(34,197,94,0.07);
    }
    .ar-status-badge.running {
        border-color: rgba(58,126,199,0.5);
        color: #1a5fa8;
        background: rgba(58,126,199,0.07);
    }
    .ar-status-badge.idle {
        border-color: rgba(107,114,128,0.4);
        color: #6b7280;
    }

    /* Page title */
    .ar-page-title {
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        color: #111;
        margin: 0 0 0.2rem 0;
        line-height: 1.2;
    }
    .ar-page-sub {
        font-size: 0.95rem;
        color: #6b7280;
        margin: 0 0 1.2rem 0;
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
    # ARENA MODE - Single-Claim vs Multi-Claim
    # ===================================================================
    st.markdown('<div class="ar-section">Mode</div>', unsafe_allow_html=True)
    arena_mode = st.selectbox(
        "Arena mode",
        options=["single_claim", "multi_claim"],
        format_func=lambda x: "Single debate" if x == "single_claim" else "Multi-claim batch",
        key="arena_mode_select",
        label_visibility="collapsed",
    )
    st.session_state["arena_mode"] = arena_mode

    # ===================================================================
    # CLAIM INPUT + RUN PLAN (combined — depends on mode)
    # ===================================================================
    import pandas as _pd

    if arena_mode == "single_claim":
        # ── Single-claim: one claim, variable turn schedule ───────────
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
                'Optional: <code>run</code> (group episodes into separate runs), '
                '<code>claim_type</code>, <code>max_turns</code> (defaults to 5).</div>',
                unsafe_allow_html=True,
            )

            # Visual format example
            st.markdown(
                '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
                'padding:0.7rem 1rem;margin-bottom:0.8rem;font-family:monospace;font-size:0.8rem;'
                'line-height:1.6;color:#374151">'
                '<span style="color:#9ca3af">CSV format:</span><br>'
                'claim,run,claim_type,max_turns<br>'
                'Vaccines cause autism,1,Health / Vaccine,2<br>'
                'Vaccines cause autism,1,Health / Vaccine,4<br>'
                'Vaccines cause autism,1,Health / Vaccine,6<br>'
                'Vaccines cause autism,1,Health / Vaccine,8<br>'
                'Vaccines cause autism,1,Health / Vaccine,10<br>'
                'Climate change is a hoax,2,Environmental,2<br>'
                'Climate change is a hoax,2,Environmental,4<br>'
                'Climate change is a hoax,2,Environmental,6<br>'
                'Climate change is a hoax,2,Environmental,8<br>'
                'Climate change is a hoax,2,Environmental,10<br>'
                'The 2020 election was stolen,3,Political / Election,2<br>'
                'The 2020 election was stolen,3,Political / Election,4<br>'
                'The 2020 election was stolen,3,Political / Election,6<br>'
                'The 2020 election was stolen,3,Political / Election,8<br>'
                'The 2020 election was stolen,3,Political / Election,10'
                '</div>',
                unsafe_allow_html=True,
            )

            _sc_file = st.file_uploader("Upload single-claim CSV", type=["csv", "xlsx"], key="sc_csv_upload")
            if _sc_file is not None:
                try:
                    _sc_df = _pd.read_csv(_sc_file) if _sc_file.name.endswith(".csv") else _pd.read_excel(_sc_file)
                    _sc_df.columns = [c.strip().lower().replace(" ", "_") for c in _sc_df.columns]
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
                            _run_queue.append({
                                "run": _run_num,
                                "claim": _claim,
                                "claim_type": _ct,
                                "turn_plan": _turns,
                                "num_episodes": len(_run_df),
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

                        # Summary
                        _total_eps = sum(r["num_episodes"] for r in _run_queue)
                        st.success(f"Loaded {len(_run_queue)} run(s), {_total_eps} total episodes")
                        with st.expander(f"Run queue ({len(_run_queue)} runs)", expanded=False):
                            for r in _run_queue:
                                _turns_str = ",".join(str(t) for t in r["turn_plan"])
                                st.caption(f"**Run {r['run']}:** \"{r['claim'][:60]}\" — {r['num_episodes']} episodes ({_turns_str} turns) · {r['claim_type'] or '—'}")
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

    else:
        # ── Multi-claim: many claims, each with domain ────────────────
        st.markdown('<div class="ar-section">Claims</div>', unsafe_allow_html=True)

        _mc_method = st.radio(
            "Input method",
            options=["manual", "csv"],
            format_func=lambda x: "Manual entry" if x == "manual" else "Upload CSV",
            horizontal=True,
            key="mc_input_method",
        )
        st.session_state["turn_plan_valid"] = True

        claims_list = []
        claim_metadata_list = []

        if _mc_method == "csv":
            st.markdown(
                '<div style="font-size:0.88rem;color:#555;margin-bottom:0.8rem;">'
                'Upload a CSV with one claim per row. Required: <code>claim</code>. '
                'Optional: <code>run</code> (group claims into separate runs), '
                '<code>claim_type</code>.</div>',
                unsafe_allow_html=True,
            )

            # Visual format example
            st.markdown(
                '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;'
                'padding:0.7rem 1rem;margin-bottom:0.8rem;font-family:monospace;font-size:0.8rem;'
                'line-height:1.6;color:#374151">'
                '<span style="color:#9ca3af">CSV format:</span><br>'
                'claim,run,claim_type<br>'
                'Vaccines cause autism,1,Health / Vaccine<br>'
                '5G towers spread COVID,1,Health / Vaccine<br>'
                'Big Pharma hides cancer cures,1,Institutional Conspiracy<br>'
                'Climate change is a hoax,2,Environmental<br>'
                'The 2020 election was stolen,2,Political / Election<br>'
                'AI will replace all human jobs,2,Economic<br>'
                'Fluoride in water is mind control,3,Institutional Conspiracy<br>'
                'Chemtrails are poisoning us,3,Institutional Conspiracy'
                '</div>',
                unsafe_allow_html=True,
            )

            _mc_file = st.file_uploader("Upload multi-claim CSV", type=["csv", "xlsx"], key="mc_csv_upload")
            if _mc_file is not None:
                try:
                    _mc_df = _pd.read_csv(_mc_file) if _mc_file.name.endswith(".csv") else _pd.read_excel(_mc_file)
                    _mc_df.columns = [c.strip().lower().replace(" ", "_") for c in _mc_df.columns]
                    if "claim" not in _mc_df.columns:
                        st.error("CSV must have a `claim` column.")
                    else:
                        _has_run = "run" in _mc_df.columns
                        _mc_run_queue = []

                        if _has_run:
                            for _run_num, _run_df in _mc_df.groupby("run", sort=True):
                                _run_claims = []
                                _run_meta = []
                                for _, row in _run_df.iterrows():
                                    c = str(row["claim"]).strip()
                                    if c:
                                        _run_claims.append(c)
                                        meta = {}
                                        if "claim_type" in _run_df.columns and _pd.notna(row.get("claim_type")):
                                            meta["claim_type"] = str(row["claim_type"]).strip()
                                            meta["claim_domain"] = str(row["claim_type"]).strip()
                                        _run_meta.append(meta)
                                if _run_claims:
                                    _mc_run_queue.append({
                                        "run": _run_num,
                                        "claims": _run_claims,
                                        "metadata": _run_meta,
                                    })
                        else:
                            # No run column — all claims in one run
                            _one_claims = []
                            _one_meta = []
                            for _, row in _mc_df.iterrows():
                                c = str(row["claim"]).strip()
                                if c:
                                    _one_claims.append(c)
                                    meta = {}
                                    if "claim_type" in _mc_df.columns and _pd.notna(row.get("claim_type")):
                                        meta["claim_type"] = str(row["claim_type"]).strip()
                                        meta["claim_domain"] = str(row["claim_type"]).strip()
                                    _one_meta.append(meta)
                            if _one_claims:
                                _mc_run_queue = [{"run": 1, "claims": _one_claims, "metadata": _one_meta}]

                        st.session_state["mc_run_queue"] = _mc_run_queue

                        # Flatten first run for immediate use
                        if _mc_run_queue:
                            _first_run = _mc_run_queue[0]
                            claims_list = _first_run["claims"]
                            claim_metadata_list = _first_run["metadata"]

                        _total_claims = sum(len(r["claims"]) for r in _mc_run_queue)
                        st.success(f"Loaded {len(_mc_run_queue)} run(s), {_total_claims} total claims")

                        with st.expander(f"Preview ({len(_mc_run_queue)} runs, {_total_claims} claims)", expanded=False):
                            for r in _mc_run_queue:
                                st.markdown(f"**Run {r['run']}** — {len(r['claims'])} claims")
                                _types = [m.get("claim_type", "—") for m in r["metadata"]]
                                _preview_df = _pd.DataFrame({
                                    "Claim": [c[:70] + ("..." if len(c) > 70 else "") for c in r["claims"]],
                                    "Claim Type": _types,
                                })
                                st.dataframe(_preview_df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Failed to parse CSV: {e}")
        else:
            n_claims = st.number_input("Number of claims", min_value=1, max_value=50, value=3, key="multi_claim_n")
            for i in range(int(n_claims)):
                val = st.text_input(f"Claim {i + 1}", key=f"multi_claim_{i}")
                if val and str(val).strip():
                    claims_list.append(str(val).strip())

        st.session_state["claims_list"] = claims_list
        st.session_state["total_claims"] = len(claims_list)
        if claim_metadata_list:
            st.session_state["claim_metadata_list"] = claim_metadata_list

        # Cost estimate
        _n_claims_est = len(claims_list) or st.session_state.get("multi_claim_n", 3)
        _model = st.session_state.get("spreader_model", "gpt-4o")
        _cost_per_turn = 0.0085 if ("mini" not in _model and "haiku" not in _model and "flash" not in _model) else 0.0006
        _turns_per_ep = 10
        _est_low = _n_claims_est * _turns_per_ep * _cost_per_turn * 0.6
        _est_high = _n_claims_est * _turns_per_ep * _cost_per_turn * 1.4
        if _n_claims_est > 1:
            st.info(
                f"Estimated cost: ${_est_low:.2f}–${_est_high:.2f} for "
                f"{_n_claims_est} claims × 10 turns using **{_model}**."
            )

    # ===================================================================
    # CLAIM TAXONOMY - tag the claim's domain for research filtering
    # ===================================================================
    st.markdown('<div class="ar-section">Claim Type</div>', unsafe_allow_html=True)
    _claim_type_options = [
        "", "Health / Vaccine", "Political / Election",
        "Institutional Conspiracy", "Environmental", "Economic", "Hybrid",
    ]
    st.session_state.setdefault("claim_type", "")
    st.selectbox(
        "Claim type",
        options=_claim_type_options,
        key="claim_type",
        label_visibility="collapsed",
        help="Tag this claim's domain for analytics filtering and cross-claim comparison.",
    )

    # ===================================================================
    # RUN CONTROLS - Start new run boundary
    # ===================================================================
    st.markdown('<div class="ar-section">Run Controls</div>', unsafe_allow_html=True)
    col_run_start, col_run_stop = st.columns(2)
    with col_run_start:
        if st.button("Start new run", type="primary", use_container_width=True, key="arena_start_new_run_btn"):
            # Validate API keys for selected models before starting
            from arena.utils.api_keys import get_key_status
            from arena.agents import is_anthropic_model, is_gemini_model, is_grok_model
            _ks = get_key_status()
            _missing = []
            for _role, _mk in [("Spreader", "spreader_model"), ("Fact-checker", "debunker_model")]:
                _m = st.session_state.get(_mk, "gpt-4o-mini")
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

            if arena_mode == "multi_claim":
                claims_list = st.session_state.get("claims_list", [])
                if not claims_list:
                    st.error("Enter or upload at least one claim before starting.")
                    st.stop()
            st.session_state["run_active"] = True
            st.session_state["episodes_completed"] = 0
            st.session_state["episode_idx"] = 1
            st.session_state["current_claim_index"] = 0
            if "run_id" in st.session_state:
                del st.session_state["run_id"]
            try:
                from arena.ui.run_planner import reset_episode_state_for_chaining
            except ImportError:
                sys.path.insert(0, "src")
                from arena.ui.run_planner import reset_episode_state_for_chaining
            reset_episode_state_for_chaining(st.session_state)
            st.session_state["match_in_progress"] = False
            st.session_state["debate_running"] = False
            if arena_mode == "multi_claim":
                st.session_state["num_episodes"] = st.session_state.get("total_claims", 1)
                st.session_state["max_turns"] = 10
                st.session_state["claim_metadata_list"] = st.session_state.get("claim_metadata_list") or []
            if st.session_state.get("arena_debug", False):
                print("[ARENA] Start new run: episode_idx=1 episodes_completed=0 run_id cleared")
            st.rerun()
    with col_run_stop:
        if st.button("Stop run", use_container_width=True, key="arena_stop_run_btn"):
            st.session_state["run_active"] = False
            st.session_state["debate_running"] = False
            st.session_state["match_in_progress"] = False
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
        if arena_mode == "multi_claim":
            completed_claims = st.session_state.get("episodes_completed", 0)
            total_claims = st.session_state.get("total_claims", 1)
            progress_value = min(completed_claims / total_claims, 1.0) if total_claims > 0 else 0.0
            st.progress(progress_value, text=f"Running claim {completed_claims + 1 if st.session_state.get('debate_running') else completed_claims} of {total_claims}")
        else:
            completed_turns = sum(1 for m in st.session_state.get("debate_messages", [])
                                if m.get("speaker") == "debunker" and m.get("status") == "final")
            total = st.session_state.get("max_turns", 5)
            progress_value = 0 if total == 0 else min(completed_turns / total, 1.0)
            phase = st.session_state.get("debate_phase", "spreader")
            phase_display = f" (Phase: {phase})" if st.session_state.get("debate_running") else ""
            st.progress(progress_value, text=f"Turns: {completed_turns}/{total}{phase_display}")

    with col2:
        episodes_completed = st.session_state.get("episodes_completed", 0)
        total_episodes = st.session_state.get("total_claims", st.session_state.get("num_episodes", 1)) if arena_mode == "multi_claim" else st.session_state.get("num_episodes", 1)
        if st.session_state.get("match_in_progress", False) or st.session_state.get("run_active", False):
            episode_progress = min(episodes_completed / total_episodes, 1.0) if total_episodes > 0 else 0
            label = f"Claims: {episodes_completed}/{total_episodes}" if arena_mode == "multi_claim" else f"Episodes: {episodes_completed}/{total_episodes}"
            st.progress(episode_progress, text=label)
        else:
            label = f"Claims: 0/{total_episodes}" if arena_mode == "multi_claim" else f"Episodes: 0/{total_episodes}"
            st.progress(0.0, text=label)

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
