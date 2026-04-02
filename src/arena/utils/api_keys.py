"""
Centralized API key management for Misinformation Arena v2.

Resolution priority (highest → lowest):
1. Streamlit secrets (.streamlit/secrets.toml)
2. Environment variables
3. Session state (entered via sidebar UI)

All provider-specific key getters follow this same pattern.
"""

from __future__ import annotations

import os


def _from_streamlit_secrets(key_name: str) -> str | None:
    """Try to read a key from Streamlit secrets."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return None


def _from_env(key_name: str) -> str | None:
    """Try to read a key from environment variables."""
    val = os.environ.get(key_name)
    if val and val.strip():
        return val.strip()
    return None


def _from_session_state(key_name: str) -> str | None:
    """Try to read a key from Streamlit session state (UI-entered)."""
    try:
        import streamlit as st
        val = st.session_state.get(key_name)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return None


def _resolve(key_name: str) -> str | None:
    """Resolve an API key from all sources in priority order."""
    return (
        _from_streamlit_secrets(key_name)
        or _from_env(key_name)
        or _from_session_state(key_name)
    )


# ---------------------------------------------------------------------------
# Provider-specific getters
# ---------------------------------------------------------------------------

def get_openai_api_key() -> str | None:
    """Get OpenAI API key from secrets, env, or session state."""
    return _resolve("OPENAI_API_KEY")


def get_anthropic_api_key() -> str | None:
    """Get Anthropic API key from secrets, env, or session state."""
    return _resolve("ANTHROPIC_API_KEY")


def get_gemini_api_key() -> str | None:
    """Get Google Gemini API key from secrets, env, or session state."""
    return _resolve("GEMINI_API_KEY")


def get_xai_api_key() -> str | None:
    """Get xAI (Grok) API key from secrets, env, or session state."""
    return _resolve("XAI_API_KEY")


# ---------------------------------------------------------------------------
# Status helpers (for sidebar display)
# ---------------------------------------------------------------------------

def mask_key(key: str | None) -> str:
    """Mask an API key for safe display: sk-proj-Fsa...efcA"""
    if not key or not isinstance(key, str) or len(key.strip()) < 12:
        return "not set"
    k = key.strip()
    return f"{k[:7]}...{k[-4:]}"


def get_key_status() -> dict[str, dict]:
    """
    Return status of all provider keys.

    Returns dict like:
    {
        "openai": {"set": True, "source": "secrets", "masked": "sk-proj...efcA"},
        "anthropic": {"set": False, "source": None, "masked": "not set"},
    }
    """
    status = {}
    for provider, key_name in [
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("xai", "XAI_API_KEY"),
    ]:
        val = _from_streamlit_secrets(key_name)
        if val:
            status[provider] = {"set": True, "source": "secrets.toml", "masked": mask_key(val)}
            continue
        val = _from_env(key_name)
        if val:
            status[provider] = {"set": True, "source": "env var", "masked": mask_key(val)}
            continue
        val = _from_session_state(key_name)
        if val:
            status[provider] = {"set": True, "source": "sidebar", "masked": mask_key(val)}
            continue
        status[provider] = {"set": False, "source": None, "masked": "not set"}
    return status
