"""
OpenAI API key configuration — backward compatibility shim.

All logic now lives in arena.utils.api_keys. This module re-exports
get_openai_api_key() and mask_key() so existing imports continue to work.
"""

from arena.utils.api_keys import get_openai_api_key, mask_key  # noqa: F401
