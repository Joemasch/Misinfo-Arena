"""
Prompt library for Misinfo Arena v2.

Manages saved prompt entries per agent type (spreader, debunker, judge).
Supports save, load, activate, and backward-safe initialization.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from arena.app_config import PROMPT_LIBRARY_PATH, PROMPTS_PATH
except ImportError:
    # Fallback when app_config lacks PROMPT_LIBRARY_PATH (e.g. older install)
    _root = Path(__file__).resolve().parent.parent.parent.parent
    PROMPTS_PATH = _root / "prompts.json"
    PROMPT_LIBRARY_PATH = _root / "prompt_library.json"

AGENT_TYPES = ("spreader", "debunker", "judge")

BASE_VERSIONS = {
    "spreader": "spreader_v1",
    "debunker": "debunker_v1",
    "judge": "judge_static_v1",
}


def _load_json(path: Path, default: dict) -> dict:
    """Load JSON file; return default if missing or invalid."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: dict) -> None:
    """Save dict as JSON."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_prompt_library() -> dict:
    """Load prompt library; returns {spreader: [...], debunker: [...], judge: [...]}."""
    data = _load_json(PROMPT_LIBRARY_PATH, {})
    for agent in AGENT_TYPES:
        if agent not in data or not isinstance(data[agent], list):
            data[agent] = []
    return data


def save_prompt_library(data: dict) -> None:
    """Save prompt library."""
    out = {agent: data.get(agent, []) for agent in AGENT_TYPES}
    _save_json(PROMPT_LIBRARY_PATH, out)


def get_agent_prompt_entries(agent_type: str) -> list[dict]:
    """Return list of saved entries for an agent type."""
    lib = load_prompt_library()
    return lib.get(agent_type, [])


def _generate_id(agent_type: str) -> str:
    """Generate a stable local prompt id."""
    prefix = {"spreader": "spr", "debunker": "deb", "judge": "jud"}[agent_type]
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def add_prompt_entry(
    agent_type: str,
    name: str,
    prompt_text: str,
    notes: str = "",
    base_version: str | None = None,
) -> dict:
    """Add a new prompt entry; returns the created entry."""
    lib = load_prompt_library()
    if agent_type not in lib:
        lib[agent_type] = []

    if base_version is None:
        base_version = BASE_VERSIONS.get(agent_type, "custom")

    entry = {
        "id": _generate_id(agent_type),
        "name": name.strip() or "Unnamed",
        "prompt_text": prompt_text,
        "notes": (notes or "").strip(),
        "base_version": base_version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
    lib[agent_type].append(entry)
    save_prompt_library(lib)
    return entry


def add_blank_prompt_entry(agent_type: str) -> dict:
    """Add a new blank prompt entry for experimentation; returns the created entry."""
    return add_prompt_entry(
        agent_type,
        name="Untitled",
        prompt_text="",
        notes="",
        base_version=BASE_VERSIONS.get(agent_type, "custom"),
    )


def get_prompt_entry(agent_type: str, prompt_id: str) -> dict | None:
    """Return entry by id, or None."""
    entries = get_agent_prompt_entries(agent_type)
    for e in entries:
        if e.get("id") == prompt_id:
            return e
    return None


def update_prompt_entry(
    agent_type: str,
    prompt_id: str,
    updates: dict[str, Any],
) -> dict | None:
    """Update an entry; returns updated entry or None."""
    lib = load_prompt_library()
    entries = lib.get(agent_type, [])
    for i, e in enumerate(entries):
        if e.get("id") == prompt_id:
            entries[i] = {**e, **updates, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}
            save_prompt_library(lib)
            return entries[i]
    return None


def delete_prompt_entry(agent_type: str, prompt_id: str) -> bool:
    """Delete an entry; returns True if deleted."""
    lib = load_prompt_library()
    entries = lib.get(agent_type, [])
    new_entries = [e for e in entries if e.get("id") != prompt_id]
    if len(new_entries) == len(entries):
        return False
    lib[agent_type] = new_entries
    save_prompt_library(lib)
    return True


def get_active_prompt_id(agent_type: str) -> str | None:
    """Return active prompt id for agent from prompts.json."""
    data = _load_json(PROMPTS_PATH, {})
    key = f"active_{agent_type}_id"
    val = data.get(key)
    return val if isinstance(val, str) and val.strip() else None


def set_active_prompt_id(agent_type: str, prompt_id: str | None, prompt_text: str) -> None:
    """
    Set active prompt id and update the active prompt text in prompts.json.
    If prompt_id is None, clears active id but keeps prompt_text.
    """
    data = _load_json(PROMPTS_PATH, {})
    prompt_key = {"spreader": "spreader_prompt", "debunker": "debunker_prompt", "judge": "judge_static_prompt"}[agent_type]
    data[prompt_key] = prompt_text
    data[f"active_{agent_type}_id"] = prompt_id if prompt_id else ""
    _save_json(PROMPTS_PATH, data)


def update_prompts_file_merge(updates: dict) -> None:
    """Merge updates into prompts.json without losing other keys (e.g. active_*_id)."""
    data = _load_json(PROMPTS_PATH, {})
    data.update(updates)
    _save_json(PROMPTS_PATH, data)


def auto_activate_research_defaults() -> None:
    """
    On first run (or when no active prompt is set), automatically activate the
    first research_default entry for each agent type. Safe to call repeatedly —
    skips agents that already have an active ID set.
    """
    data = _load_json(PROMPTS_PATH, {})
    lib = load_prompt_library()
    changed = False
    for agent_type in AGENT_TYPES:
        active_key = f"active_{agent_type}_id"
        if data.get(active_key, "").strip():
            continue  # already has an active prompt — don't override
        entries = lib.get(agent_type, [])
        default_entry = next((e for e in entries if e.get("research_default")), None)
        if default_entry:
            prompt_key = {
                "spreader": "spreader_prompt",
                "debunker": "debunker_prompt",
                "judge": "judge_static_prompt",
            }[agent_type]
            data[active_key] = default_entry["id"]
            data[prompt_key] = default_entry.get("prompt_text", "")
            changed = True
    if changed:
        _save_json(PROMPTS_PATH, data)


def resolve_active_prompt(
    agent_type: str,
    default_text: str,
    prompts_data: dict | None = None,
) -> tuple[str, str | None, bool]:
    """
    Resolve the active prompt text for an agent.
    Returns (prompt_text, prompt_id, prompt_customized).
    """
    prompts_data = prompts_data or _load_json(PROMPTS_PATH, {})
    active_id = prompts_data.get(f"active_{agent_type}_id") or ""
    if isinstance(active_id, str) and active_id.strip():
        lib = load_prompt_library()
        for e in lib.get(agent_type, []):
            if e.get("id") == active_id:
                text = e.get("prompt_text", "")
                if text:
                    return (text, active_id, text.strip() != default_text.strip())
    # Fallback to stored prompt text
    prompt_key = {"spreader": "spreader_prompt", "debunker": "debunker_prompt", "judge": "judge_static_prompt"}[agent_type]
    text = prompts_data.get(prompt_key) or default_text
    customized = (text or "").strip() != (default_text or "").strip()
    return (text or default_text, active_id if active_id else None, customized)
