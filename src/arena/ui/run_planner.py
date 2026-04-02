"""
Run plan utilities: parse turn-plan CSV, apply per-episode max_turns, reset episode state for chaining.

Used for multi-episode runs with per-episode turn schedules (e.g. 4,6,8).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# Valid range for turn count per episode (inclusive)
MIN_TURNS = 1
MAX_TURNS = 20


def parse_turn_plan_csv(
    csv: str,
    num_episodes: int,
    default_turns: int,
) -> Tuple[List[int], Optional[str]]:
    """
    Parse a comma-separated turn plan.

    Accepts:
    - "4,6,8" where len must equal num_episodes
    - "6" (single value) replicated to length num_episodes
    - Strips whitespace; trailing commas are ignored (empty segments yield validation error unless single int)

    Valid turn range: 1..MAX_TURNS (20).

    Returns:
        (plan, None) on success; ([], "error message") on error.
    """
    if num_episodes < 1:
        return ([], "num_episodes must be at least 1")

    raw = (csv or "").strip().strip(",")
    if not raw:
        # Replicate default to full length
        return ([default_turns] * num_episodes, None)

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return ([], "Enter at least one value (e.g. 6 or 4,6,8)")

    # Single value: replicate to num_episodes
    if len(parts) == 1:
        try:
            v = int(parts[0])
        except ValueError:
            return ([], "Turn plan must be integers (e.g. 6 or 4,6,8)")
        if not (MIN_TURNS <= v <= MAX_TURNS):
            return ([], f"Turn count must be between {MIN_TURNS} and {MAX_TURNS}")
        return ([v] * num_episodes, None)

    # Multiple values: length must match num_episodes
    if len(parts) != num_episodes:
        return (
            [],
            f"Turn plan has {len(parts)} value(s) but num_episodes is {num_episodes}. "
            "Use one value (e.g. 6) to apply to all, or one per episode (e.g. 4,6,8).",
        )

    plan = []
    for i, p in enumerate(parts):
        try:
            v = int(p)
        except ValueError:
            return ([], f"Invalid integer at position {i + 1}: {p!r}")
        if not (MIN_TURNS <= v <= MAX_TURNS):
            return ([], f"Turn count at position {i + 1} must be between {MIN_TURNS} and {MAX_TURNS}")
        plan.append(v)

    return (plan, None)


def apply_turn_plan_to_episode(ss: dict, episode_idx_1_based: int) -> None:
    """
    Set ss["max_turns"] for the given episode (1-based) from ss["turn_plan"].

    If no plan exists, leaves ss["max_turns"] unchanged (or uses ss.get("max_turns", 5) as fallback).
    """
    plan = ss.get("turn_plan")
    if not plan or not isinstance(plan, list):
        # Leave max_turns as-is (already set elsewhere or default)
        return
    idx = max(0, episode_idx_1_based - 1)
    if idx < len(plan):
        ss["max_turns"] = plan[idx]
    else:
        ss["max_turns"] = ss.get("max_turns", 5)


# Canonical empty concession structure (must match app.py / execute_next_turn usage)
EMPTY_CONCESSION_DATA = {
    "early_stop_reason": None,
    "concession_method": None,
    "conceded_by": None,
    "concession_turn": None,
    "concession_strength": None,
    "concession_reason": None,
}


def reset_episode_state_for_chaining(ss: dict) -> None:
    """
    Reset only episode-local keys for a clean next episode (chat, transcript, counters, verdicts).

    Does NOT touch: run_id, spreader_agent, debunker_agent, judge, analytics, storage,
    num_episodes, turn_plan, turn_plan_csv.
    """
    ss["debate_messages"] = []
    ss["episode_transcript"] = []
    ss["messages"] = []
    ss["turns"] = []
    ss["turn_idx"] = 0
    ss["completed_turn_pairs"] = 0
    ss["spreader_msgs_count"] = 0
    ss["debunker_msgs_count"] = 0
    ss["debate_phase"] = "spreader"
    ss["debate_turn_idx"] = 1
    ss["judge_decision"] = None
    ss["judge_status"] = None
    ss["judge_error"] = None
    ss["early_stop_reason"] = None
    ss["stop_reason"] = None
    ss["match_in_progress"] = True

    if "last_openai_error" in ss:
        ss["last_openai_error"] = None
    ss["concession_data"] = dict(EMPTY_CONCESSION_DATA)


def check_debate_invariants(ss: dict) -> None:
    """
    Optional debug-only invariant checks. No exceptions; emits st.warning when gated.

    - If debate_running and match_in_progress: completed_turn_pairs should not exceed max_turns.
    - If debate_messages non-empty, episode_transcript should be in sync (both non-empty or both empty).
    """
    try:
        import streamlit as st
    except ImportError:
        return

    if not ss.get("debate_running") or not ss.get("match_in_progress"):
        return

    pairs = ss.get("completed_turn_pairs", 0)
    max_t = ss.get("max_turns", 5)
    if pairs > max_t:
        st.warning(f"[Run planner] Invariant: completed_turn_pairs ({pairs}) > max_turns ({max_t})")

    dm = ss.get("debate_messages") or []
    et = ss.get("episode_transcript") or []
    if dm and not et:
        st.warning("[Run planner] Invariant: debate_messages non-empty but episode_transcript empty")
    if et and not dm:
        st.warning("[Run planner] Invariant: episode_transcript non-empty but debate_messages empty")
