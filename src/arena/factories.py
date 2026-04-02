"""
FACTORY CENTRALIZATION MODULE - The Single Source of Truth for Arena Factories

WHY CENTRALIZE FACTORIES?
========================
1. PREVENTS NAMEERROR ISSUES:
   - One import point eliminates "function not defined" errors
   - Clear API boundary prevents accidental direct imports
   - Wiring problems caught at import time, not runtime

2. REDUCES COUPLING:
   - App code depends only on this stable factory interface
   - Implementation details can change without affecting app.py
   - Future refactoring (new agent types, judge algorithms) won't break imports

3. IMPROVES MAINTAINABILITY:
   - Single file to audit for factory-related changes
   - Clear documentation of available factories
   - Easy to add new factories or deprecate old ones

4. ENHANCES TESTING:
   - Factories can be easily mocked for unit tests
   - Consistent interface across all factory functions
   - Easy to inject test doubles

ARCHITECTURAL PATTERN:
- This module acts as an ADAPTER between app needs and implementation details
- App.py sees only the stable factory API
- Implementation modules (agents.py, judge.py, engine.py) contain the actual logic
- Changes to implementations don't require app.py changes

IMPORT STRATEGY:
- Import concrete implementations from implementation modules
- Re-export only the stable factory functions
- Keep implementation details hidden from app.py
"""

# ===================================================================
# IMPORTS FROM IMPLEMENTATION MODULES
# ===================================================================
# These imports bring in the actual implementations via compat layer
# App.py never needs to know about these modules directly

from arena.compat import (
    create_agent as _create_agent_impl,
    create_judge as _create_judge_impl,
    create_debate_engine as _create_debate_engine_impl,
    create_match_storage as _create_match_storage_impl,
    create_analytics as _create_analytics_impl,
    create_default_setup as _create_default_setup_impl,
)
from arena.types import MatchConfig as DebateConfig, MatchState, AgentRole, Message, Turn, MatchResult

# ===================================================================
# STABLE FACTORY API - What app.py imports and uses
# ===================================================================

def create_agent(role: str, agent_type: str, model: str | None = None, temperature: float = 0.7, name: str | None = None):
    """
    Factory for creating debate agents (spreader or debunker).

    STABLE API: This signature should rarely change.
    Implementation can evolve without affecting callers.

    Args:
        role: "spreader" or "debunker"
        agent_type: "Dummy" or "OpenAI"
        model: OpenAI model name (ignored for Dummy)
        temperature: Sampling temperature (ignored for Dummy)
        name: Optional agent name

    Returns:
        Agent instance ready for debate
    """
    return _create_agent_impl(role=role, agent_type=agent_type, model=model, temperature=temperature, name=name)


def create_judge(weights: dict[str, float] | None = None) -> object:
    """
    Factory for creating debate judges.

    STABLE API: Simple creation interface.
    Implementation can switch between heuristic/LLM judges.

    Args:
        weights: Optional custom weights for scoring metrics

    Returns:
        Judge instance for evaluating debates
    """
    return _create_judge_impl(weights)


def create_debate_engine(spreader_agent, debunker_agent, judge) -> object:
    """
    Factory for creating debate engines.

    STABLE API: Takes agents and judge, returns configured engine.
    Implementation can evolve orchestration logic.

    Args:
        spreader_agent: Agent playing spreader role
        debunker_agent: Agent playing debunker role
        judge: Judge for evaluating outcomes

    Returns:
        Configured debate engine ready to run matches
    """
    return _create_debate_engine_impl(spreader_agent, debunker_agent, judge)


def create_match_storage() -> object:
    """
    Factory for creating match storage instances.

    Args:
        None (uses defaults)

    Returns:
        Storage instance for persisting match results
    """
    return _create_match_storage_impl()


def create_analytics(storage) -> object:
    """
    Factory for creating analytics instances.

    Args:
        storage: Storage instance to analyze

    Returns:
        Analytics instance for performance analysis
    """
    return _create_analytics_impl(storage)


def create_default_setup():
    """
    Factory for creating a default debate setup.

    Returns:
        Tuple of (engine, storage, analytics) with default configuration
    """
    return _create_default_setup_impl()


# ===================================================================
# RE-EXPORTED TYPES - For convenience, so app.py doesn't need separate imports
# ===================================================================

def fetch_openai_models():
    """
    Fetch available OpenAI models from the API.

    WHY THIS HELPER EXISTS:
    - Provides dynamic model discovery for better UX
    - Allows users to see what models are actually available to them
    - Handles API errors gracefully (falls back to curated list)
    - Caches results to avoid repeated API calls

    Returns:
        List of model IDs (strings) or empty list on error
    """
    try:
        # Lazy import to avoid issues when OpenAI not installed
        from openai import OpenAI
        from arena.utils.openai_config import get_openai_api_key

        api_key = get_openai_api_key()
        if not api_key:
            return []  # No API key, can't fetch

        client = OpenAI(api_key=api_key)
        models = client.models.list()

        # Extract model IDs, filter to chat models only
        chat_models = [
            model.id for model in models.data
            if model.id.startswith(('gpt-', 'chatgpt-'))  # Focus on chat models
        ]

        return sorted(chat_models)  # Sort for consistent UI

    except Exception as e:
        # Any error (API issues, network, etc.) - return empty list
        # UI will fall back to curated list
        print(f"Warning: Could not fetch OpenAI models: {e}")
        return []


__all__ = [
    "create_agent",
    "create_judge",
    "create_debate_engine",
    "create_match_storage",
    "create_analytics",
    "create_default_setup",
    "fetch_openai_models",
    "DebateConfig",
    "MatchState",
    "AgentRole",
    "Message",
    "Turn",
    "MatchResult"
]
