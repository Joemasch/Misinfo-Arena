"""
Arena package for Misinformation Arena v2.

This package provides the core functionality for running AI-powered debates
between misinformation spreaders and fact-checkers.
"""

# Re-export key components for convenience
from . import config
from .config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
# Note: factories and state modules may have dependencies, import when needed
# from . import factories, state

# Note: Other modules will be imported when they exist
# from .ui import layout, sidebar, arena_page, analytics_page, replay_page, components
# from .debate import runner, turns, judge, agents, prompts
# from .io import runs, storage
# from .util import text, time, logging

__version__ = "2.0.0"
