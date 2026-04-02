"""
UI components for Misinformation Arena.

This package contains all Streamlit UI components and page renderers.
Separated from core logic to avoid circular imports.
"""

from .debate_chat import (
    inject_debate_chat_css,
    init_debate_chat_state,
    render_debate_chat,
    render_debate_controls,
    run_debate_step,
)

