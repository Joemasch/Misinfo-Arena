"""
Centralized runs_refresh_token handling.

Bump this token when runs/episodes are written so Analytics and Replay
invalidates cached data and shows newly completed runs.
"""

import streamlit as st


def bump_runs_refresh_token(reason: str | None = None) -> int:
    """
    Increment runs_refresh_token to invalidate cached run data.
    Safe to call multiple times.
    Returns new token value.
    """
    cur = st.session_state.get("runs_refresh_token", 0)
    try:
        cur = int(cur)
    except (TypeError, ValueError):
        cur = 0
    new = cur + 1
    st.session_state["runs_refresh_token"] = new

    if reason:
        st.session_state["runs_refresh_reason"] = reason

    return new


def get_auto_run_ids(runs_dir: str, refresh_token: int = 0, limit: int | None = None) -> list[str]:
    """
    Returns newest-first run_ids for valid/completed runs.
    Uses existing list_runs filtering and ordering.
    By default returns all runs; pass limit=N to cap.
    """
    from arena.io.run_store_v2_read import list_runs

    runs_list = list_runs(runs_dir, refresh_token=float(refresh_token) if refresh_token is not None else 0.0)
    run_ids = [r["run_id"] for r in runs_list]
    return run_ids[:limit] if limit is not None else run_ids
