"""
Run store utilities for Misinformation Arena v2.

Provides centralized functions for persisting and loading match results to/from JSONL files.
"""

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Iterator

from arena.app_config import DEFAULT_MATCHES_PATH

# JSON v2 storage constants
DEFAULT_RUNS_DIR = Path("runs")


def ensure_run_dir(run_id: str) -> Path:
    """Ensure run directory exists and return its path."""
    run_dir = DEFAULT_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_meta_path(run_id: str) -> Path:
    """Return path to run.json for given run_id."""
    return ensure_run_dir(run_id) / "run.json"


def episodes_path(run_id: str) -> Path:
    """Return path to episodes.jsonl for given run_id."""
    return ensure_run_dir(run_id) / "episodes.jsonl"


def make_run_id(now: datetime | None = None) -> str:
    """Generate a unique run ID with timestamp and random suffix."""
    if now is None:
        now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)  # 4 hex chars
    return f"{timestamp}_{suffix}"


def write_run_json(run_id: str, run_obj: Dict[str, Any], overwrite: bool = False) -> None:
    """Write run metadata to run.json (idempotent unless overwrite=True)."""
    run_path = run_meta_path(run_id)

    # Don't overwrite existing run.json unless explicitly requested
    if run_path.exists() and not overwrite:
        return

    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run_obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def append_episode_jsonl(run_id: str, episode_obj: Dict[str, Any]) -> None:
    """Append an episode to episodes.jsonl."""
    episodes_file = episodes_path(run_id)

    with open(episodes_file, "a", encoding="utf-8") as f:
        json.dump(episode_obj, f, ensure_ascii=False, default=str)
        f.write("\n")


def _is_jsonable(x) -> bool:
    """Test if an object is JSON serializable."""
    try:
        json.dumps(x, ensure_ascii=False, default=str)
        return True
    except Exception:
        return False


def append_match_jsonl(path: str, match_obj: Dict[str, Any]) -> None:
    """
    Append a match result to a JSONL file.

    Args:
        path: Path to the JSONL file
        match_obj: Match result dictionary to append
    """
    # Ensure directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # Append to JSONL file
    with open(path, "a", encoding="utf-8") as f:
        try:
            json.dump(match_obj, f, ensure_ascii=False, default=str)
        except TypeError as e:
            # JSON serialization failed - identify problematic fields
            bad_fields = []
            for k, v in match_obj.items():
                try:
                    json.dumps(v, ensure_ascii=False, default=str)
                except Exception:
                    # Truncate value preview for logging
                    value_preview = str(v)[:200] + "..." if len(str(v)) > 200 else str(v)
                    bad_fields.append((k, type(v).__name__, value_preview))
            raise TypeError(f"json_dumps_failed bad_fields={bad_fields}") from e
        f.write("\n")


def iter_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    """
    Iterate over records in a JSONL file.

    Args:
        path: Path to the JSONL file

    Yields:
        Parsed JSON objects from each line (skips malformed lines)
    """
    if not Path(path).exists():
        return

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines but could log if needed
                    continue


def load_matches_jsonl(path: str) -> List[Dict[str, Any]]:
    """
    Load all matches from a JSONL file.

    Args:
        path: Path to the JSONL file

    Returns:
        List of match dictionaries
    """
    return list(iter_jsonl(path))
