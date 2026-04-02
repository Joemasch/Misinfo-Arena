# Replay Summary Helper: on-demand generation for Episode Replay tab (Option B).
# Uses ReplaySummaryAgent; caches in session_state AND on disk inside the run directory.
# Disk cache means repeat visits to the same episode never re-call the LLM.
# Failures are recorded in session_state for diagnostics; app never crashes.

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

import streamlit as st

from arena.utils.openai_config import get_openai_api_key

RUNS_DIR = "runs"


def _disk_cache_path(run_id: str, episode_id: Any) -> Path:
    return Path(RUNS_DIR) / run_id / f"summary_ep{episode_id}.json"


def _load_disk_cache(run_id: str, episode_id: Any) -> dict | None:
    p = _disk_cache_path(run_id, episode_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_disk_cache(run_id: str, episode_id: Any, payload: dict) -> None:
    p = _disk_cache_path(run_id, episode_id)
    try:
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # Disk write failure is non-fatal


def _err_key(run_id: str, episode_id: Any) -> str:
    return f"replay_summary_error::{run_id}::{episode_id}"


def _set_last_error(run_id: str, episode_id: Any, stage: str, exc: Exception) -> None:
    tb = traceback.format_exc().splitlines()
    st.session_state[_err_key(run_id, episode_id)] = {
        "stage": stage,
        "exc_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "\n".join(tb[-25:]),
        "ts": time.time(),
    }


def _clear_last_error(run_id: str, episode_id: Any) -> None:
    k = _err_key(run_id, episode_id)
    if k in st.session_state:
        del st.session_state[k]


def get_or_generate_replay_summary(run_id: str, episode: dict) -> dict | None:
    """
    Return a generated summary payload for the episode, or None if unavailable.
    Cached in st.session_state by (run_id, episode_id). Never raises.
    On failure, records a diagnostic envelope keyed by (run_id, episode_id).
    """
    episode_id = episode.get("episode_id")
    if episode_id is None:
        return None

    claim = episode.get("claim")
    turns = episode.get("turns")
    results = episode.get("results")

    missing = [n for n, v in [("claim", claim), ("turns", turns), ("results", results)] if v is None]
    if missing:
        _set_last_error(
            run_id,
            episode_id,
            stage="missing_fields",
            exc=ValueError(f"missing: {', '.join(missing)}"),
        )
        return None

    api_key = get_openai_api_key()
    if not api_key:
        _set_last_error(
            run_id,
            episode_id,
            stage="missing_api_key",
            exc=RuntimeError("OPENAI_API_KEY not found in st.secrets or env"),
        )
        return None

    cache_name = "replay_summary_cache_v1"
    if cache_name not in st.session_state:
        st.session_state[cache_name] = {}

    key = (run_id, episode_id)

    # 1. Check session-state cache
    if key in st.session_state[cache_name]:
        return st.session_state[cache_name][key]

    # 2. Check disk cache — load and populate session cache so future reads are free
    disk = _load_disk_cache(run_id, episode_id)
    if disk:
        st.session_state[cache_name][key] = disk
        return disk

    try:
        from arena.replay_summary_agent import get_replay_summary_agent
    except Exception as e:
        _set_last_error(run_id, episode_id, stage="import_agent", exc=e)
        return None

    try:
        agent = get_replay_summary_agent()
    except Exception as e:
        _set_last_error(run_id, episode_id, stage="agent_init", exc=e)
        return None

    try:
        rs = agent.generate(claim, turns, results)
    except Exception as e:
        _set_last_error(run_id, episode_id, stage="llm_or_parse", exc=e)
        return None

    payload = {
        "full_text": rs.full_text,
        "model": rs.model,
        "version": rs.version,
        "generated_at": rs.generated_at,
        "quality_warnings": rs.quality_warnings,
    }
    # 3. Persist to disk so future sessions don't re-call the LLM
    _save_disk_cache(run_id, episode_id, payload)
    st.session_state[cache_name][key] = payload
    _clear_last_error(run_id, episode_id)
    return payload
