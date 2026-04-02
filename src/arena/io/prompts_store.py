"""
Prompt storage I/O utilities for Misinformation Arena v2.

Handles loading and saving of custom system prompts to/from the prompts.json file.
"""

import json
from pathlib import Path

# Import from app_config to avoid duplication
from arena.app_config import PROMPTS_PATH


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

