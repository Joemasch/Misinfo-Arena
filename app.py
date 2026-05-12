"""
Misinformation Arena v2 - Streamlit Web Application

This is the main Streamlit application for running interactive debates between
misinformation spreaders and fact-checkers. Features a chat-like interface
with turn-based debate execution and automated judging.
"""

# ===================================================================
# IMPORTS
# ===================================================================

# Standard library
import html
import json
import math
import os
import re
import sys

# ===================================================================
# DEBUG CONFIGURATION
# ===================================================================

DEBUG_ARENA = os.getenv("DEBUG_ARENA", "0") == "1"

def get_ui_claim() -> str:
    """Get the current claim text from UI input."""
    return (st.session_state.get("claim_text") or "").strip()

def exec_guard(tag: str, data: dict | None = None):
    """Debug guard — logs when a code path is skipped."""
    arena_dbg(f"GUARD:{tag}", **(data or {}))

def exec_log(tag: str, data: dict | None = None):
    """Debug execution log."""
    arena_dbg(f"EXEC:{tag}", **(data or {}))

def log_event(tag: str, data: dict | None = None):
    """Debug event log."""
    arena_dbg(f"EVENT:{tag}", **(data or {}))


def arena_dbg(tag: str, **kv):
    """Debug logging for Arena system invariants."""
    if not DEBUG_ARENA:
        return
    safe = {}
    for k, v in kv.items():
        try:
            if isinstance(v, str) and len(v) > 180:
                safe[k] = v[:180] + "…"
            else:
                safe[k] = v
        except Exception:
            safe[k] = "<unprintable>"
    print(f"[ARENA][{tag}] " + " ".join(f"{k}={safe[k]!r}" for k in safe))
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import streamlit.components.v1 as components

# ===================================================================
# PATH SETUP - Ensure src directory is on sys.path for local imports
# ===================================================================
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    # Insert at beginning so src/arena/ takes precedence over local arena/
    # This enables the new modular structure while maintaining compatibility
    sys.path.insert(0, str(SRC))

# ===================================================================
# PREFLIGHT CHECKS - Verify import resolution before proceeding
# ===================================================================
from arena.preflight import run_preflight_checks
run_preflight_checks()

# Third-party libraries
from typing import Optional
import pandas as pd
import streamlit as st

# Internal/local imports
from arena.factories import (
    create_agent, create_judge, create_debate_engine,
    create_match_storage, create_analytics, create_default_setup,
    fetch_openai_models,
    DebateConfig, MatchState, AgentRole, Message, Turn, MatchResult,
)
from arena.types import JudgeDecision
from arena.concession import should_concede, check_keyword_concession, ConcessionRecommendation
from arena.config import (
    AVAILABLE_MODELS, get_default_model_index, get_default_model,
    DEFAULT_EPISODES, DEFAULT_MAX_TURNS,
    DEFAULT_SPREADER_MODEL, DEFAULT_DEBUNKER_MODEL,
    DEFAULT_SPREADER_TEMPERATURE, DEFAULT_DEBUNKER_TEMPERATURE
)
from arena.state import initialize_session_state, is_concession

# Page module imports
from arena.presentation.streamlit.pages.explore_page import render_explore_page
from arena.presentation.streamlit.pages.guide_page import render_guide_page
from arena.presentation.streamlit.pages.arena_page import render_arena_page
from arena.presentation.streamlit.pages.findings_page import render_findings_page

# Arena component imports
from arena.presentation.streamlit.components.arena.judge_report import render_judge_report
from arena.presentation.streamlit.components.arena.debate_insights import render_debate_insights

# Use case imports
from arena.application.use_cases.execute_next_turn import execute_next_turn as uc_execute_next_turn

# ===================================================================
# DEBUG CONFIGURATION - Disabled for production experimentation
# ===================================================================
# Set True for development/debugging; False for clean experiment runs
DEBUG_SANITY = False
DEBUG_DIAG = False

# OS import sanity check (DEBUG only)
if DEBUG_DIAG:
    print("OS_IMPORT_OK", os.__file__)

# Model configuration moved to arena.config

# ===================================================================
# HTML SANITIZATION HELPER
# ===================================================================
def _maybe_strip_leaked_html(text: str) -> str:
    """
    Strip HTML tags only if the text looks like leaked bubble markup.
    This prevents displaying raw HTML as text in the transcript.
    """
    if not isinstance(text, str):
        text = str(text)
    # Strip ANY HTML tags to be safe - we only want plain text in transcripts
    if "<" in text and ">" in text:
        text = re.sub(r"<[^>]+>", "", text)
    return text

# ===================================================================
# LOCAL SECRETS BRIDGE - Development API key injection
# ===================================================================
# Bridge the API key from local_secrets.py into environment for UI compatibility
# This allows the existing UI warning logic to work unchanged while using dev secrets
try:
    from local_secrets import OPENAI_API_KEY
    os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)
except ImportError:
    # local_secrets.py not found or OPENAI_API_KEY not defined - do nothing
    pass

# ===================================================================
# V1 SYSTEM PROMPTS - Hardcoded for initial implementation
# System prompts imported from arena.config (IME507 research-grounded versions)
from arena.config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT  # noqa: E402

# ===================================================================
# PROMPTS PERSISTENCE - JSON file storage
# ===================================================================

PROMPTS_PATH = Path("prompts.json")  # Stored at repo root

def load_prompts_file():
    """Load prompts from prompts.json file, with error handling."""
    if not PROMPTS_PATH.exists():
        return {}
    try:
        return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        # Log error but don't crash - return empty dict to use defaults
        print(f"Warning: Could not load prompts.json: {e}")
        return {}

def save_prompts_file(data: dict):
    """Save prompts to prompts.json file."""
    PROMPTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_prompt_snapshot(spreader_cfg, debunker_cfg, judge_weights):
    """
    Build a complete snapshot of prompts and generation parameters for reproducibility.

    This captures all the prompts, templates, and model parameters used in a match
    to ensure future runs can reproduce identical behavior and for auditing prompt changes.

    Args:
        spreader_cfg: AgentConfig for spreader agent
        debunker_cfg: AgentConfig for debunker agent
        judge_weights: Dict of judge scoring weights

    Returns:
        Dict containing complete prompt snapshot
    """
    try:
        from arena.agents import DEFAULT_USER_PROMPT_TEMPLATE
    except ImportError:
        DEFAULT_USER_PROMPT_TEMPLATE = "Debate claim: {topic}\nOpponent last message:\n{opponent_text}\n\nWrite your next reply:"

    return {
        "system_prompts": {
            "spreader": SPREADER_SYSTEM_PROMPT,
            "debunker": DEBUNKER_SYSTEM_PROMPT,
        },
        "user_prompt_template": DEFAULT_USER_PROMPT_TEMPLATE,
        "generation": {
            "spreader": {
                "agent_type": "OpenAI",
                "model": getattr(spreader_cfg, "model", None),
                "temperature": getattr(spreader_cfg, "temperature", None),
                "max_tokens": 500,  # Mirror current behavior in OpenAIAgent.generate()
            },
            "debunker": {
                "agent_type": "OpenAI",
                "model": getattr(debunker_cfg, "model", None),
                "temperature": getattr(debunker_cfg, "temperature", None),
                "max_tokens": 500,
            },
        },
        "judge": {
            "type": "heuristic",
            "weights": judge_weights,
        },
    }


def ss_init(key: str, default):
    """
    Initialize a Streamlit session_state key exactly once.

    WHY THIS HELPER EXISTS:
    - Prevents AttributeError from dot-style access (st.session_state.foo)
    - Uses dict-style access which is safer and more explicit
    - Centralizes initialization pattern for consistency
    - Makes it clear when we're initializing vs reading

    Args:
        key: Session state key name (string)
        default: Default value if key doesn't exist

    Returns:
        The value (either existing or newly initialized)
    """
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


# initialize_session_state moved to arena.state
def initialize_session_state():
    """
    Initialize all required session state variables with dict-style access.

    WHY DICT-STYLE ACCESS:
    - Prevents AttributeError from dot-style access (st.session_state.foo)
    - Safer and more explicit than attribute access
    - Consistent with ss_init() helper pattern

    CHAT UI ARCHITECTURE:
    - messages: List of chat messages for UI rendering (Streamlit format)
    - turns: List of structured turns for judge evaluation and logging
    - turn_idx: Current turn counter (0-based)
    - match_in_progress: Boolean flag for UI state management

    This design separates UI concerns (messages) from evaluation concerns (turns).
    """
    # ===================================================================
    # PHASE 1: CONFIGURATION DEFAULTS (no dependencies)
    # ===================================================================
    # Max turns is now configured in the main Arena UI form
    # Claim input starts empty, no defaults
    if "claim_text" not in st.session_state:
        st.session_state["claim_text"] = ""
    if "topic" not in st.session_state:
        st.session_state["topic"] = ""

    # Agent configuration - fixed values (no longer user-selectable)
    # ===================================================================
    # PHASE 1.2: AGENT MODEL SELECTION (new keys, backward compatible)
    # ===================================================================
    # --- Agent model selection defaults (new keys) ---
    default_model = get_default_model()
    if "spreader_model" not in st.session_state:
        st.session_state["spreader_model"] = default_model
    if "debunker_model" not in st.session_state:
        st.session_state["debunker_model"] = default_model

    # --- Guard against stale session values ---
    # If stored model is no longer available, reset to default
    if st.session_state["spreader_model"] not in AVAILABLE_MODELS:
        st.session_state["spreader_model"] = default_model
    if st.session_state["debunker_model"] not in AVAILABLE_MODELS:
        st.session_state["debunker_model"] = default_model

    # --- Backward compatibility: migrate old agent_type keys to new model keys ---
    # This ensures old session states don't break when we switched from agent types to models
    if "spreader_agent_type" in st.session_state:
        # Migrate old spreader agent type to model
        if not st.session_state.get("spreader_model") or st.session_state["spreader_model"] not in AVAILABLE_MODELS:
            st.session_state["spreader_model"] = default_model
        # Safe cleanup of old key
        del st.session_state["spreader_agent_type"]

    if "debunker_agent_type" in st.session_state:
        # Migrate old debunker agent type to model
        if not st.session_state.get("debunker_model") or st.session_state["debunker_model"] not in AVAILABLE_MODELS:
            st.session_state["debunker_model"] = default_model
        # Safe cleanup of old key
        del st.session_state["debunker_agent_type"]
    ss_init("spreader_temperature", 0.7)
    ss_init("debunker_temperature", 0.7)

    # ===================================================================
    # PHASE 1.5: PROMPTS (depend on constants but needed before agents)
    # ===================================================================
    # Load saved prompts from disk; resolve active prompt from library if active_*_id set
    data = load_prompts_file()
    from arena.prompts.judge_static_prompt import get_judge_static_prompt
    from arena.prompts.prompt_library import resolve_active_prompt
    spreader_text, _, _ = resolve_active_prompt("spreader", SPREADER_SYSTEM_PROMPT, data)
    debunker_text, _, _ = resolve_active_prompt("debunker", DEBUNKER_SYSTEM_PROMPT, data)
    judge_text, _, _ = resolve_active_prompt("judge", get_judge_static_prompt(), data)
    ss_init("spreader_prompt", spreader_text)
    ss_init("debunker_prompt", debunker_text)
    ss_init("judge_static_prompt", judge_text)

    # ===================================================================
    # PHASE 2: AGENTS (depend on config above)
    # ===================================================================
    if "spreader_agent" not in st.session_state:
        st.session_state["spreader_agent"] = create_agent(
            role="spreader",
            agent_type="OpenAI",
            model=st.session_state["spreader_model"],
            temperature=st.session_state["spreader_temperature"],
        )

    if "debunker_agent" not in st.session_state:
        st.session_state["debunker_agent"] = create_agent(
            role="debunker",
            agent_type="OpenAI",
            model=st.session_state["debunker_model"],
            temperature=st.session_state["debunker_temperature"],
        )

    # ===================================================================
    # PHASE 3: JUDGE (independent)
    # ===================================================================
    ss_init("judge", create_judge())

    # ===================================================================
    # PHASE 4: OTHER COMPONENTS (depend on storage)
    # ===================================================================
    ss_init("storage", create_match_storage())
    ss_init("analytics", create_analytics(st.session_state["storage"]))

    # ===================================================================
    # PHASE 4.5: CONCESSION DATA (Phase 2A)
    # ===================================================================
    if "concession_data" not in st.session_state:
        st.session_state["concession_data"] = {
            "early_stop_reason": None,
            "concession_method": None,       # "model" or "keyword"
            "conceded_by": None,             # "spreader" or "debunker"
            "concession_turn": None,         # int
            "concession_strength": None,     # float
            "concession_reason": None        # str
        }

    # ===================================================================
    # PHASE 5: CHAT UI STATE (reset between matches)
    # ===================================================================
    ss_init("messages", [])     # Chat messages for UI (Streamlit format)
    ss_init("turns", [])        # Structured turns for judge/logging
    ss_init("turn_idx", 0)      # Current turn counter (0-based)
    ss_init("match_in_progress", False)  # UI state flag
    ss_init("early_stop_reason", None)   # Reason for early termination
    ss_init("judge_decision", None)      # Final judge evaluation

    # Turn pair counters (new semantics: turn = spreader + debunker message pair)
    ss_init("spreader_msgs_count", 0)    # Number of spreader messages sent
    ss_init("debunker_msgs_count", 0)    # Number of debunker messages sent
    ss_init("completed_turn_pairs", 0)   # Number of complete turn pairs (spreader + debunker)


# is_concession moved to arena.state


def _convert_transcript_for_judge(transcript):
    """
    Convert flat message transcript to judge-expected Turn objects.

    Args:
        transcript: List of message dicts from episode_transcript

    Returns:
        List of Turn objects suitable for judge.evaluate_match()
    """
    from collections import defaultdict

    # Group messages by turn_index
    grouped = defaultdict(list)
    for msg in transcript:
        if isinstance(msg, dict) and "turn_index" in msg:
            turn_idx = int(msg.get("turn_index", 0))
            grouped[turn_idx].append(msg)

    judge_turns = []
    for turn_idx in sorted(grouped.keys()):
        messages = grouped[turn_idx]
        spreader_msg = None
        debunker_msg = None

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "spreader":
                spreader_msg = Message(role=AgentRole.SPREADER, content=content)
            elif role == "debunker":
                debunker_msg = Message(role=AgentRole.DEBUNKER, content=content)

        # Only include complete turns
        if spreader_msg and debunker_msg:
            judge_turns.append(Turn(
                turn_id=turn_idx + 1,  # Convert 0-based to 1-based
                spreader_message=spreader_msg,
                debunker_message=debunker_msg
            ))

    return judge_turns


def recreate_agents_if_needed():
    """
    Recreate agents if configuration has changed.

    Agents are now always OpenAI models.
    This function recreates agents when model/temperature settings change.
    """
    # Check if we need to recreate agents
    needs_recreate = (
        getattr(st.session_state["spreader_agent"], 'model', None) != st.session_state["spreader_model"] or
        getattr(st.session_state["spreader_agent"], 'temperature', None) != st.session_state["spreader_temperature"] or
        getattr(st.session_state["debunker_agent"], 'model', None) != st.session_state["debunker_model"] or
        getattr(st.session_state["debunker_agent"], 'temperature', None) != st.session_state["debunker_temperature"]
    )

    if needs_recreate:
        # Recreate agents with current configuration
        st.session_state["spreader_agent"] = create_agent(
            role="spreader",
            agent_type="OpenAI",
            model=st.session_state["spreader_model"],
            temperature=st.session_state["spreader_temperature"]
        )
        st.session_state["debunker_agent"] = create_agent(
            role="debunker",
            agent_type="OpenAI",
            model=st.session_state["debunker_model"],
            temperature=st.session_state["debunker_temperature"]
        )

        # Recreate engine with updated agents
        st.session_state["engine"] = create_debate_engine(
            st.session_state["spreader_agent"],
            st.session_state["debunker_agent"],
            st.session_state["judge"]
        )


def reset_match_state():
    """
    Reset the match state for a new debate.

    Clears all match-related state variables to prepare for a fresh debate.
    """
    st.session_state["match_state"] = None
    st.session_state["match_completed"] = False
    st.session_state["judge_report_visible"] = False


def start_new_match():
    """
    START NEW MATCH - Reset all state for a fresh debate.

    WHY COMPLETE RESET?
    ===================
    Each match should start with clean state to prevent
    cross-contamination between debates.

    CHAT UI RESET:
    ==============
    - Clear messages and turns for fresh conversation
    - Reset turn counter to 0
    - Clear any previous judge decisions
    - Set match as active
    """
    # ===================================================================
    # COMPLETE STATE RESET FOR FRESH MATCH
    # ===================================================================
    st.session_state["messages"] = []           # Clear chat transcript
    st.session_state["turns"] = []              # Clear structured turns
    st.session_state["turn_idx"] = 0            # Reset turn counter
    st.session_state["match_in_progress"] = True # Match is now active

    # Reset debate chat UI state
    st.session_state["debate_messages"] = []    # Clear rolling chat messages
    st.session_state["debate_turn_idx"] = 1     # Reset to 1-based counter
    st.session_state["debate_phase"] = "spreader"  # Start with spreader
    st.session_state["debate_running"] = False  # Will be set to True when debate starts

    # Reset turn pair counters
    st.session_state["spreader_msgs_count"] = 0     # Reset spreader message count
    st.session_state["debunker_msgs_count"] = 0     # Reset debunker message count
    st.session_state["completed_turn_pairs"] = 0    # Reset completed turn pairs
    st.session_state["early_stop_reason"] = None # Clear stop reason
    st.session_state["judge_decision"] = None   # Clear judge evaluation
    st.session_state["last_openai_error"] = None # Clear any previous API errors

    # Reset concession data for fresh match (Phase 2A)
    st.session_state["concession_data"] = {
        "early_stop_reason": None,
        "concession_method": None,       # "model" or "keyword"
        "conceded_by": None,             # "spreader" or "debunker"
        "concession_turn": None,         # int
        "concession_strength": None,     # float
        "concession_reason": None        # str
    }

    # ===================================================================
    # ENSURE AGENTS ARE UP TO DATE
    # ===================================================================
    recreate_agents_if_needed()


def execute_next_turn():
    # Thin wrapper preserved for Streamlit callbacks/UI buttons
    return uc_execute_next_turn()
## render_sidebar() — moved to arena.presentation.streamlit.pages.arena_page









def render_transcript_fallback(transcript: list) -> None:
    """
    Fallback transcript renderer using Streamlit components.
    Always works, shows partial turns clearly.
    Handles both message lists and Turn objects.
    """
    if not transcript:
        st.info("Enter a claim above and click Start Debate.")
        return

    # Handle message dicts with turn_index
    if transcript and isinstance(transcript[0], dict) and "turn_index" in transcript[0]:
        # Format: list of message dicts with turn_index
        from collections import defaultdict
        grouped = defaultdict(list)
        for msg in transcript:
            turn_idx = int(msg.get("turn_index", 0))
            grouped[turn_idx].append(msg)

        # Render each turn
        for turn_idx in sorted(grouped.keys()):
            messages = grouped[turn_idx]
            _render_turn_messages_fallback(turn_idx, messages)
    else:
        # Unknown format - show raw
        st.warning("Unknown transcript format, showing raw data:")
        st.code(str(transcript)[:500] + "..." if len(str(transcript)) > 500 else str(transcript))


def _render_turn_messages_fallback(turn_idx: int, messages: list) -> None:
    """Helper to render messages for a single turn in fallback mode."""
    # Turn header
    st.markdown(f"**--- Turn {turn_idx + 1} ---**")

    # Render messages for this turn
    spreader_found = False
    debunker_found = False

    for msg in messages:
        role = msg.get("role", "")
        name = msg.get("name", "Unknown")
        content = msg.get("content", "")

        if role == "spreader":
            spreader_found = True
            st.markdown(f"**Spreader:** {content}")
        elif role == "debunker":
            debunker_found = True
            st.markdown(f"**Fact-checker:** {content}")

    # Show pending status for incomplete turns
    if spreader_found and not debunker_found:
        st.caption("*⏳ Pending debunker response...*")
    elif not spreader_found and debunker_found:
        st.caption("*⏳ Pending spreader response...*")


def render_transcript_box(transcript: list) -> None:
    """
    Render the debate transcript using streamlit.components.v1.html for reliable HTML rendering.

    Features:
    - Single scrollable container (520px height)
    - Turn headers above each turn pair
    - Spreader then debunker messages per turn
    - Safe HTML escaping prevents markup leakage
    - Auto-scroll to newest message
    - Uses components.html to avoid Streamlit HTML escaping issues
    """
    # Filter out placeholder messages and sanitize content
    PLACEHOLDER_TEXT = "Enter a claim above and click Start Debate!"
    transcript = [msg for msg in transcript if PLACEHOLDER_TEXT not in str(msg.get("content", ""))]

    # Sanitize message content to ensure no HTML gets through
    transcript = [
        {**msg, "content": _maybe_strip_leaked_html(msg.get("content", ""))}
        for msg in transcript
    ]

    # If transcript is empty, show placeholder and return
    if not transcript:
        st.info("Enter a claim above and click Start Debate.")
        return

    # Group messages by turn_index
    grouped = defaultdict(list)

    if transcript and isinstance(transcript[0], dict) and "turn_index" in transcript[0]:
        # Format: message dicts with turn_index
        for msg in transcript:
            turn_idx = int(msg.get("turn_index", 0))
            grouped[turn_idx].append(msg)
    else:
        # Unknown format - skip HTML rendering
        raise ValueError(f"Unknown transcript format for HTML renderer: {type(transcript[0]) if transcript else 'empty'}")

    # Build complete HTML document with embedded CSS
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'IBM Plex Sans', sans-serif;
                color: #E8E4D9;
                background: #0A0A0A;
            }}
            #transcript-box {{
                height: 520px;
                overflow-y: auto;
                border: 1px solid #2A2A2A;
                padding: 12px;
                border-radius: 4px;
                background: #0A0A0A;
                box-sizing: border-box;
                color: #E8E4D9;
            }}
            .turn-header {{
                margin: 16px 0 10px 0;
                font-weight: 700;
                font-size: 18px;
                color: #E8E4D9;
                text-align: center;
                border-bottom: 1px solid #2A2A2A;
                padding-bottom: 6px;
            }}
            .message-bubble {{
                margin: 6px 0;
                padding: 10px 12px;
                border-radius: 10px;
                box-sizing: border-box;
            }}
            .spreader {{
                background-color: rgba(212, 168, 67, 0.1);
                border-left: 3px solid #D4A843;
                margin-left: 20%;
                margin-right: 0;
                text-align: right;
            }}
            .debunker {{
                background-color: rgba(74, 127, 165, 0.1);
                border-left: 3px solid #4A7FA5;
                margin-left: 0;
                margin-right: 20%;
                text-align: left;
            }}
            .role {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 15px;
                font-weight: 700;
                opacity: 0.95;
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.6px;
            }}
            .spreader .role {{
                color: #D4A843;
            }}
            .debunker .role {{
                color: #4A7FA5;
            }}
            .content {{
                white-space: pre-wrap;
                word-wrap: break-word;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
                line-height: 1.5;
                color: #E8E4D9;
            }}
        </style>
    </head>
    <body>
        <div id="transcript-box">
    """

    # Render each turn
    for turn_idx in sorted(grouped.keys()):
        messages = grouped[turn_idx]

        # Turn alignment debug: Log turn header computation
        if st.session_state.get("debug_turn_align", False):
            exec_log("render:turn_header", {
                "header_turn_number": turn_idx + 1,
                "how_computed": "from message.turn_index + 1 (TURN-BASED: turn_index is 0-based, display is 1-based)",
                "messages_in_group": len(messages),
                "roles_in_group": [msg.get("role") for msg in messages],
                "turn_idx_from_data": turn_idx
            })

        # Turn header
        html_content += f'<div class="turn-header">Turn {turn_idx + 1}</div>'

        # Render messages for this turn
        for msg in messages:
            role = msg.get("role", "")
            name = html.escape(msg.get("name", "Unknown"))
            content = _maybe_strip_leaked_html(msg.get("content", ""))
            content = html.escape(content)  # Always escape for safety

            # CSS class based on role
            css_class = "spreader" if role == "spreader" else "debunker"

            html_content += f"""
            <div class="message-bubble {css_class}">
                <div class="role">{name}</div>
                <div class="content">{content}</div>
            </div>
            """

    # Close the transcript box and add auto-scroll script
    html_content += """
        </div>
        <script>
            // Auto-scroll to bottom when content loads
            const transcriptBox = document.getElementById('transcript-box');
            if (transcriptBox) {
                // Use multiple attempts to ensure DOM is fully loaded
                setTimeout(() => {
                    transcriptBox.scrollTop = transcriptBox.scrollHeight;
                }, 50);
                setTimeout(() => {
                    transcriptBox.scrollTop = transcriptBox.scrollHeight;
                }, 100);
            }
        </script>
    </body>
    </html>
    """

    # Render using components.html for reliable HTML interpretation
    components.html(html_content, height=560, scrolling=False)



## update_chat_display(), show_typing_indicator()
## — moved to arena.presentation.streamlit.pages.arena_page

def generate_agent_message(agent, context):
    """
    Generate a message from an agent with the given context.
    """
    return agent.generate(context)




def assert_wiring():
    """
    Wiring integrity check - ensures all required factory functions are imported.

    WHY THIS CHECK?
    - Catches import issues immediately at startup
    - Prevents NameError crashes during runtime
    - Makes debugging factory problems fast and clear
    - Documents exactly what the app expects from factories

    This function should be called early in main() before any factory usage.
    """
    required_factories = [
        "create_agent",
        "create_judge",
        "create_debate_engine",
        "create_match_storage",
        "create_analytics",
        "create_default_setup",
        "fetch_openai_models",
        "DebateConfig",
        "MatchState",
        "AgentRole"
    ]

    missing = []
    for factory_name in required_factories:
        if factory_name not in globals():
            missing.append(factory_name)

    if missing:
        raise RuntimeError(
            f"🚨 WIRING FAILURE: Missing required factories from arena.factories: {missing}\n"
            f"This indicates an import problem. Check that arena/factories.py exports all required functions.\n"
            f"Expected: {required_factories}"
        )

    print(f"✅ Wiring check passed: All {len(required_factories)} factories imported successfully")


def main():
    """
    Main application entry point.

    Sets up the page configuration, initializes state, and renders all UI components.
    """
    # ===================================================================
    # DIAGNOSTIC PATHS CHECK - Debug file paths and working directory
    # ===================================================================
    if DEBUG_DIAG:
        from pathlib import Path
        print("=== DIAGNOSTIC PATHS ===")
        print(f"CWD={os.getcwd()}")
        print(f"APP_FILE={__file__}")
        print(f"REPO_ROOT_GUESS={Path(__file__).resolve().parent}")

        # Check runs/ directory existence
        runs_relative_cwd = Path("runs")
        runs_relative_app = Path(__file__).resolve().parent / "runs"
        print(f"runs_relative_to_cwd={runs_relative_cwd.resolve()} exists={runs_relative_cwd.exists()}")
        print(f"runs_relative_to_app={runs_relative_app.resolve()} exists={runs_relative_app.exists()}")
        print("=== END DIAGNOSTIC PATHS ===")

    # ===================================================================
    # WIRING INTEGRITY CHECK - Must pass before app starts
    # ===================================================================
    assert_wiring()

    # ===================================================================
    # TYPE IMPORT SELF-CHECK - Debug verification
    # ===================================================================
    if DEBUG_SANITY:
        try:
            # Verify core types are importable and instantiable
            msg = Message(role=AgentRole.SPREADER, content="test")
            turn = Turn(turn_index=0, spreader_message=msg, debunker_message=msg)
            # Note: MatchResult requires more complex setup, just check it's callable
            match_result_callable = callable(MatchResult)

            print(f"TYPE_IMPORT_OK Message=<arena.types.Message> Turn=<arena.types.Turn> MatchResult_callable={match_result_callable}")
        except Exception as e:
            print(f"TYPE_IMPORT_ERROR: {e}")
            raise

    # ===================================================================
    # OPENAI API KEY CHECK - Store status, don't block app
    # ===================================================================
    from arena.utils.openai_config import get_openai_api_key, mask_key

    api_key = get_openai_api_key()
    _api_key_missing = not api_key

    # Basic key format validation (looks like sk-...)
    if api_key and not api_key.startswith("sk-"):
        st.warning(f"⚠️ **API Key Format Warning**: Key should start with 'sk-'. You provided: {mask_key(api_key)}")
        st.info("The key format looks unusual but we'll try to use it. If you see 401 errors, double-check your key.")

    # ===================================================================
    # SESSION STATE INITIALIZATION - Must happen before any UI rendering
    # ===================================================================
    # WHY HERE? Prevents AttributeError by ensuring all session state keys
    # exist before any UI components try to access them.
    initialize_session_state()

    # ===================================================================
    # ARENA STATE INITIALIZATION - Simple debate state management
    # ===================================================================
    def init_arena_state():
        import streamlit as st
        st.session_state.setdefault("debate_running", False)
        st.session_state.setdefault("debate_done", False)
        st.session_state.setdefault("transcript", [])
        st.session_state.setdefault("turn_index", 0)
        st.session_state.setdefault("error", None)

    init_arena_state()

    # Page configuration
    st.set_page_config(
        page_title="Misinformation Arena v2",
        page_icon="MA",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Inject global design system CSS
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()

    # Navigation tabs (4 tabs — conference demo layout)
    tab_home, tab_arena, tab_replay, tab_findings = st.tabs([
        "Home", "Arena", "Replay", "Findings",
    ])

    with tab_home:
        render_guide_page()

    with tab_arena:
        if _api_key_missing:
            st.warning(
                "**API keys required to run live debates.** "
                "Set your keys in the sidebar or via environment variables. "
                "Replay and Findings tabs work without keys."
            )
        render_arena_page()

    with tab_replay:
        render_explore_page()

    with tab_findings:
        render_findings_page()

    # Footer
    st.markdown("---")
    st.caption("Built with Streamlit • Data persisted to `runs_archive/legacy/matches.jsonl`")


def normalize_explanation(explanation):
    """
    Normalize explanation field to handle various input types safely.

    Converts explanation into either a dict or None, handling:
    - dict: returned as-is
    - pandas NaN (float): converted to None
    - None: returned as None
    - stringified JSON: parsed to dict if valid
    - other types: converted to None

    This prevents AttributeError when calling .get() on float/NaN values.
    """
    if explanation is None:
        return None
    if isinstance(explanation, float) and math.isnan(explanation):
        return None
    if isinstance(explanation, dict):
        return explanation
    if isinstance(explanation, str):
        s = explanation.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return None
    return None


def get_last_message_text(role: str) -> str:
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


def _safe(obj):
    """
    Safely serialize objects for debug logging.
    """
    try:
        if obj is None:
            return None
        # pydantic
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # dataclass
        import dataclasses
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        # dict/list
        if isinstance(obj, (dict, list, str, int, float, bool)):
            return obj
        # fallback
        return str(obj)
    except Exception as e:
        return f"<unserializable {type(obj).__name__}: {e}>"


def _preview_text(s: str, n=400):
    """
    Truncate text for debug display.
    """
    if not s:
        return ""
    return s[:n] + ("…(truncated)" if len(s) > n else "")



def append_message(role, content, exchange_idx):
    """Append a message to the episode transcript."""
    import re
    def ensure_plain_text(x):
        if x is None:
            return ""
        x = str(x)
        x = re.sub(r"<[^>]+>", "", x)
        return x.strip()

    episode_idx = st.session_state.get("episode_idx", 1)
    message_id = f"ep{episode_idx}_ex{exchange_idx}_{role}"

    st.session_state["episode_transcript"].append({
        "role": role,
        "content": ensure_plain_text(content),
        "exchange_idx": exchange_idx,
        "message_id": message_id
    })


def execute_one_tick():
    """Execute exactly one message per rerun."""
    if not st.session_state.get("debate_in_progress"):
        return

    if st.session_state.get("exchange_idx", 0) >= st.session_state.get("max_turns", 0):
        st.session_state["debate_in_progress"] = False
        return

    phase = st.session_state.get("phase", "spreader")
    ex = st.session_state.get("exchange_idx", 0)

    if phase == "spreader":
        # Generate spreader message
        spreader_context = {
            "topic": st.session_state.get("claim_text", ""),
            "turn_idx": ex,
            "last_opponent_text": get_last_message_text("debunker"),
            "system_prompt": st.session_state.get("spreader_prompt", ""),
        }

        spreader_message = generate_agent_message(
            st.session_state.get("spreader_agent"),
            spreader_context
        )

        append_message(role="spreader", content=spreader_message, exchange_idx=ex)
        st.session_state["phase"] = "debunker"
        return

    if phase == "debunker":
        # Generate debunker message
        debunker_context = {
            "topic": st.session_state.get("claim_text", ""),
            "turn_idx": ex,
            "last_opponent_text": get_last_message_text("spreader"),
            "system_prompt": st.session_state.get("debunker_prompt", ""),
        }

        debunker_message = generate_agent_message(
            st.session_state.get("debunker_agent"),
            debunker_context
        )

        append_message(role="debunker", content=debunker_message, exchange_idx=ex)
        st.session_state["exchange_idx"] = ex + 1
        st.session_state["phase"] = "spreader"
        return


def test_transcript_rendering():
    """
    Test that transcript rendering works with message format.
    """
    # Test fallback renderer with message format
    message_transcript = [
        {"role": "spreader", "name": "Spreader", "content": "Test message 1", "turn_index": 0},
        {"role": "debunker", "name": "Debunker", "content": "Response 1", "turn_index": 0},
        {"role": "spreader", "name": "Spreader", "content": "Test message 2", "turn_index": 1},
        # Missing debunker for turn 2 - should show pending
    ]

    # These should not raise exceptions
    try:
        render_transcript_fallback(message_transcript)
        return "SUCCESS: Transcript rendering works with message format"
    except Exception as e:
        return f"FAILED: Transcript rendering failed: {str(e)}"


def generate_episode_insights_if_ready():
    """
    Generate insights ONLY when debate is fully finished.
    Called once per episode after debate completion.
    """
    # Guards: only generate if debate is fully finished
    debate_finished = (
        not st.session_state.get("debate_in_progress", False) and
        st.session_state.get("episode_completed", False)
    )

    if not debate_finished:
        st.session_state["last_guard_block"] = f"SKIP: insights generation - debate not finished (in_progress={st.session_state.get('debate_in_progress', False)}, completed={st.session_state.get('episode_completed', False)})"
        exec_guard("insights_debate_not_finished", {
            "debate_in_progress": st.session_state.get('debate_in_progress', False),
            "episode_completed": st.session_state.get('episode_completed', False)
        })
        return

    # Get current match result
    match_result = st.session_state.get("current_match_result")
    if not match_result:
        st.session_state["last_guard_block"] = "SKIP: insights generation - no match_result available"
        exec_guard("insights_no_match_result")
        return

    # Check if insights already exist
    existing_insights = getattr(match_result, 'insights', None)
    if existing_insights:
        st.session_state["last_guard_block"] = "SKIP: insights generation - insights already exist"
        exec_guard("insights_already_exist")
        return

    # Check single-flight guard
    if st.session_state.get("insights_in_flight", False):
        st.session_state["last_guard_block"] = "SKIP: insights generation - insights_in_flight=True"
        exec_guard("insights_in_flight")
        return

    # Generate insights using the existing logic from run_judge_evaluation
    episode_idx = st.session_state.get("episode_idx", 1)
    episode_transcript = st.session_state.get("episode_transcript", [])
    judge_decision = st.session_state.get("judge_decision")

    if not judge_decision or len(episode_transcript) == 0:
        st.session_state["last_guard_block"] = f"SKIP: insights generation - missing judge_decision or transcript (judge={judge_decision is not None}, transcript_len={len(episode_transcript)})"
        exec_guard("insights_missing_data", {
            "has_judge_decision": judge_decision is not None,
            "transcript_len": len(episode_transcript)
        })
        return

    # Compute match identifier
    match_id = f"match_{st.session_state['topic'].replace(' ', '_')}_{len(st.session_state.get('turns', []))}"

    # Check if already generated
    already_generated = match_id in st.session_state.get("insights_generated_match_ids", set())
    force_regen = st.session_state.get("force_regen_insights", False)

    if not force_regen and already_generated:
        return

    # Set single-flight flag
    st.session_state["insights_in_flight"] = True

    try:
        from arena.insights import get_insights_agent
        insights_agent = get_insights_agent()

        if not insights_agent.is_available():
            return

        # Generate insights
        if judge_decision and hasattr(judge_decision, '__dict__'):
            safe_verdict = vars(judge_decision)
        elif judge_decision and hasattr(judge_decision, 'model_dump'):
            safe_verdict = judge_decision.model_dump()
        else:
            safe_verdict = judge_decision

        insights_obj = insights_agent.generate_insights(
            claim=st.session_state.get("current_claim", ""),
            transcript=episode_transcript,
            judge_verdict=safe_verdict,
            diagnostics=None  # No diagnostics in production
        )

        # Store in match result
        if hasattr(match_result, 'insights'):
            # It's an object, set attribute
            match_result.insights = insights_obj
        else:
            # It's a dict, store as dict
            match_result["insights"] = insights_obj.model_dump() if hasattr(insights_obj, 'model_dump') else insights_obj

        # Mark as generated
        st.session_state["insights_generated_match_ids"].add(match_id)

        # Clear force flag
        st.session_state["force_regen_insights"] = False

    except Exception as e:
        # Store error in match result
        error_msg = f"Insights generation failed: {str(e)}"
        if hasattr(match_result, 'insights_error'):
            match_result.insights_error = error_msg
        else:
            match_result["insights_error"] = error_msg

    finally:
        # Clear single-flight flag
        st.session_state["insights_in_flight"] = False


def episode_complete():
    """
    Handle episode completion: save transcript, run judge evaluation.
    Guard prevents multiple calls.
    NOTE: Insights generation happens separately after debate is fully finished.
    """
    # Guard against multiple calls
    if st.session_state.get("episode_completed", False):
        return

    st.session_state["episode_completed"] = True

    # Debug instrumentation
    completed_turns = len([msg for msg in st.session_state.get("episode_transcript", []) if msg.get("role") == "debunker"])
    log_event("episode_complete:enter", {
        "episode_idx": st.session_state.get("episode_idx", 1),
        "completed_turns": completed_turns,
        "max_turns": st.session_state.get("max_turns"),
        "transcript_len": len(st.session_state.get("episode_transcript", [])),
        "stop_reason": st.session_state.get("stop_reason")
    })

    # Execution diagnostics
    exec_log("episode_complete:enter", {
        "episode_idx": st.session_state.get("episode_idx", 1),
        "completed_turns": completed_turns,
        "stop_reason": st.session_state.get("stop_reason")
    })

    episode_idx = st.session_state.get("episode_idx", 1)

    # Save current episode transcript to run transcript
    st.session_state.setdefault("run_transcript", {})[episode_idx] = st.session_state["episode_transcript"].copy()

    # Run judge evaluation for this episode
    run_judge_evaluation()

    # Set completion state
    st.session_state["debate_in_progress"] = False
    st.session_state["match_completed"] = True


def next_episode():
    """
    Transition to the next episode: reset counters, clear transcript.
    """
    # Increment episode index
    st.session_state["episode_idx"] = st.session_state.get("episode_idx", 1) + 1

    # Reset turn counters for new episode
    st.session_state["turn_idx"] = 0
    st.session_state["completed_turn_pairs"] = 0
    st.session_state["spreader_msgs_count"] = 0
    st.session_state["debunker_msgs_count"] = 0

    # Clear current episode transcript (fresh start)
    st.session_state["episode_transcript"] = []

    # Reset structured turns for judge
    st.session_state["turns"] = []

    # Reset debate state
    st.session_state["match_in_progress"] = True
    st.session_state["early_stop_reason"] = None
    st.session_state["judge_decision"] = None


def run_judge_evaluation():
    """
    Run judge evaluation after debate completion.
    """
    # Debug instrumentation
    ("run_judge_evaluation:enter", {
        "episode_idx": st.session_state.get("episode_idx", 1),
        "turns_count": len(st.session_state.get("turns", [])),
        "transcript_len": len(st.session_state.get("episode_transcript", [])),
        "max_turns": st.session_state.get("max_turns", 5),
        "topic": _preview_text(st.session_state.get("topic", ""), 100)
    })

    # Execution diagnostics
    exec_log("run_judge_evaluation:enter", {
        "episode_idx": st.session_state.get("episode_idx", 1),
        "turns_count": len(st.session_state.get("turns", [])),
        "transcript_len": len(st.session_state.get("episode_transcript", []))
    })

    judge_turns = _convert_transcript_for_judge(st.session_state["episode_transcript"])
    config = DebateConfig(
        max_turns=st.session_state.get("max_turns", 5),
        topic=st.session_state["topic"],
        judge_weights=st.session_state["judge"].weights
    )

    try:
        judge_decision = st.session_state["judge"].evaluate_match(judge_turns, config)
    except Exception as e:
        if DEBUG_DIAG:
            print(f"JUDGE_ERROR: {str(e)}")
        # Create a default draw decision on judge failure
        judge_decision = JudgeDecision(
            winner="draw",
            confidence=0.5,
            reason=f"Judge evaluation failed: {str(e)}",
            total_score_spreader=5.0,
            total_score_debunker=5.0,
            scorecard=[]
        )

    st.session_state["judge_decision"] = judge_decision

    # Note: Insights generation moved to generate_episode_insights_if_ready()
    # to ensure it only happens AFTER debate is fully finished




if __name__ == "__main__":
    main()