"""
Compatibility layer for arena factories.

This module provides backward-compatible create_* functions that forward
to the actual implementations in other arena modules. This centralizes
all factory function imports and prevents ImportErrors when modules
are reorganized.

WHY THIS COMPAT LAYER EXISTS:
- Centralizes factory function imports
- Prevents ImportErrors from missing functions
- Provides stable API surface for factories.py
- Allows implementation modules to evolve independently
"""

# ===================================================================
# AGENT FACTORIES
# ===================================================================

def create_agent(role: str, agent_type: str, model: str | None = None, temperature: float = 0.7, name: str | None = None):
    """
    Create an agent instance.

    Forwards to: arena.agents.create_agent
    Accepts legacy signature and adapts to AgentConfig-based implementation.
    """
    # Try to use AgentConfig if available, otherwise fall back to SimpleNamespace
    try:
        from arena.types import AgentConfig
        config = AgentConfig(
            role=role,
            agent_type=agent_type,
            model=model,
            temperature=temperature,
            name=name
        )
    except ImportError:
        # Fallback if AgentConfig is not available
        from types import SimpleNamespace
        config = SimpleNamespace(
            role=role,
            agent_type=agent_type,
            model=model,
            temperature=temperature,
            name=name
        )

    from arena.agents import create_agent as impl
    return impl(config)


# ===================================================================
# JUDGE FACTORIES
# ===================================================================

def create_judge(weights: dict[str, float] | None = None):
    """
    Create a judge instance.

    Forwards to: arena.judge.create_judge
    """
    from arena.judge import create_judge as impl
    return impl(weights)


# ===================================================================
# ENGINE FACTORIES
# ===================================================================

def create_debate_engine(spreader_agent, debunker_agent, judge):
    """
    Create a debate engine instance.

    Deprecated: arena.engine no longer exists. Debate execution is now
    handled by arena.application.use_cases.execute_next_turn.
    """
    raise NotImplementedError(
        "create_debate_engine() is no longer available. "
        "Debate execution has moved to arena.application.use_cases.execute_next_turn. "
        "Remove calls to create_debate_engine() and use execute_next_turn() instead."
    )


# ===================================================================
# STORAGE FACTORIES
# ===================================================================

def create_match_storage(storage_dir: str = "runs", filename: str = "matches.jsonl"):
    """
    Create a match storage instance.

    Forwards to: arena.storage.create_match_storage
    """
    from arena.storage import create_match_storage as impl
    return impl(storage_dir, filename)


# ===================================================================
# ANALYTICS FACTORIES
# ===================================================================

def create_analytics(storage):
    """
    Create an analytics instance.

    Forwards to: arena.analytics.create_analytics
    """
    from arena.analytics import create_analytics as impl
    return impl(storage)


# ===================================================================
# SETUP FACTORIES
# ===================================================================

def create_default_setup():
    """
    Create a default debate setup.

    Returns a tuple of (engine, storage, analytics) with default agents and configuration.
    This creates a complete, ready-to-use debate system with dummy agents.
    """
    # Create default storage
    storage = create_match_storage()

    # Create default analytics
    analytics = create_analytics(storage)

    # Create default agents (dummy agents for testing)
    spreader_agent = create_agent(role="spreader", agent_type="Dummy", name="DefaultSpreader")
    debunker_agent = create_agent(role="debunker", agent_type="Dummy", name="DefaultDebunker")

    # Create default judge
    judge = create_judge()

    # Create default engine
    engine = create_debate_engine(spreader_agent, debunker_agent, judge)

    return engine, storage, analytics
