"""
Session state management for Misinformation Arena.

This module handles initialization and migration of Streamlit session state.
Separated from UI to avoid circular imports and enable testing.
"""

import streamlit as st
from pathlib import Path

# Import required components
from .config import (
    AVAILABLE_MODELS, get_default_model,
    DEFAULT_SPREADER_TEMPERATURE, DEFAULT_DEBUNKER_TEMPERATURE
)

# Local imports (avoid circular imports)
def load_prompts_file():
    """Load saved prompts from prompts.json"""
    prompts_path = Path("prompts.json")
    if not prompts_path.exists():
        return {}
    try:
        import json
        return json.loads(prompts_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def get_system_prompts():
    """Get default system prompts"""
    # Import here to avoid circular imports
    from .config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
    return SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT


def ss_init(key: str, default_value):
    """
    Initialize a session state variable if it doesn't exist.

    Args:
        key: Session state key
        default_value: Default value if key doesn't exist
    """
    if key not in st.session_state:
        st.session_state[key] = default_value
    return st.session_state[key]


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
    ss_init("topic", "Climate change is completely made up by scientists for grant money")

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

    ss_init("spreader_temperature", DEFAULT_SPREADER_TEMPERATURE)
    ss_init("debunker_temperature", DEFAULT_DEBUNKER_TEMPERATURE)

    # ===================================================================
    # PHASE 1.5: PROMPTS (depend on constants but needed before agents)
    # ===================================================================
    # Load saved prompts from disk; resolve active prompt from library if active_*_id set
    data = load_prompts_file()
    spreader_default, debunker_default = get_system_prompts()
    from arena.prompts.judge_static_prompt import get_judge_static_prompt
    from arena.prompts.prompt_library import resolve_active_prompt, auto_activate_research_defaults
    auto_activate_research_defaults()
    data = load_prompts_file()  # reload after auto-activation may have written prompts.json
    spreader_text, _, _ = resolve_active_prompt("spreader", spreader_default, data)
    debunker_text, _, _ = resolve_active_prompt("debunker", debunker_default, data)
    judge_text, _, _ = resolve_active_prompt("judge", get_judge_static_prompt(), data)
    # Always enforce research prompts — prompts are fixed for experimental control.
    # ss_init would preserve stale custom prompts from prior sessions.
    st.session_state["spreader_prompt"] = spreader_text
    st.session_state["debunker_prompt"] = debunker_text
    st.session_state["judge_static_prompt"] = judge_text

    # ===================================================================
    # PHASE 2: AGENTS (depend on config above)
    # ===================================================================
    # Import here to avoid circular imports
    from arena.factories import create_agent

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
    # Import here to avoid circular imports
    from arena.factories import create_judge
    ss_init("judge", create_judge())

    # ===================================================================
    # PHASE 4: OTHER COMPONENTS (depend on storage)
    # ===================================================================
    # Import here to avoid circular imports
    from arena.factories import create_match_storage, create_analytics
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


def is_concession(text: str) -> bool:
    """
    Check if a message contains concession language.

    WHY THIS IS A LOCAL HELPER:
    - Simple string matching for early debate termination
    - No need for complex NLP - just keyword detection
    - Fast and reliable for UI responsiveness

    Args:
        text: The message text to check

    Returns:
        True if any concession phrases are detected (case-insensitive)
    """
    if not text:
        return False

    phrases = ["i agree", "you're right", "i retract", "i concede"]
    text_lower = text.lower()

    for phrase in phrases:
        if phrase in text_lower:
            return True

    return False
