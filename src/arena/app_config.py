"""
Application configuration constants for Misinformation Arena v2.

Centralized location for constants that were previously defined in app.py.
This prevents circular dependencies and maintains clean architecture.
"""

from pathlib import Path

# Debug constants (False for production experimentation; set True for development)
DEBUG_SANITY = False
DEBUG_DIAG = False

# Prompt configuration
PROMPTS_PATH = Path("prompts.json")  # Stored at repo root
PROMPT_LIBRARY_PATH = Path("prompt_library.json")  # Saved prompt entries by agent type

# Match persistence
DEFAULT_MATCHES_PATH = Path("runs_archive/legacy/matches.jsonl")  # Archived; was runs/matches.jsonl

# System prompts for agents — canonical versions defined in config.py
from arena.config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT  # noqa: F401, E402
