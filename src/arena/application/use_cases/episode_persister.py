"""
Episode persistence logic.

Extracted from execute_next_turn.py to reduce module size.
Handles converting transcripts and writing completed episodes to disk.
"""

import os

from arena.io.run_store import (
    append_match_jsonl,
    write_run_json,
    append_episode_jsonl,
    make_run_id,
)
from arena.app_config import DEFAULT_MATCHES_PATH
from arena.utils.serialization import to_jsonable
from arena.utils.transcript_conversion import to_paired_turns_for_judge

from arena.application.use_cases.judge_helpers import (
    _jd_get,
    _jd_to_dict,
    _evaluate_judge,
    _make_judge_decision_safe,
)
from arena.application.use_cases.episode_builder import (
    _extract_claim_metadata,
    _build_episode_object,
    _build_run_object,
    _run_strategy_analysis,
)


_METRIC_NAMES = [
    "factuality",
    "source_credibility",
    "reasoning_quality",
    "responsiveness",
    "persuasion",
    "manipulation_awareness",
]


def _convert_transcript_for_judge(raw: list) -> list:
    """
    Convert flat message transcript to judge-expected Turn objects.

    Handles both legacy and current transcript formats:
    - Legacy: {name, role, content, turn_index}
    - Current: {name/speaker, content/text, turn_index/turn}

    Args:
        raw: List of message dicts from episode_transcript

    Returns:
        List of Turn objects suitable for judge.evaluate_match()
    """
    out = []

    for m in raw or []:
        if not isinstance(m, dict):
            continue
        content = (m.get("content") or m.get("text") or m.get("message") or "").strip()
        name = (m.get("name") or m.get("speaker") or "").strip()
        turn = m.get("turn_index")
        if turn is None:
            turn = m.get("turn")
        if not content:
            continue
        if not name:
            continue
        if turn is None:
            continue
        out.append({
            "name": name,
            "content": content,
            "turn_index": int(turn),
        })

    return out


def _persist_completed_match(ss) -> None:
    """
    Persist a completed match: evaluate judge, run strategy analysis,
    build episode/run objects, and write to disk.

    Split into sub-functions for testability:
    - _evaluate_judge() -- judge routing and scoring
    - _run_strategy_analysis() -- optional strategy labeling
    - _build_episode_object() -- v2 episode JSON construction
    - _build_run_object() -- v2 run metadata construction
    """
    # Ensure judge evaluation has run
    if not ss.get("judge_decision"):
        raw_transcript = ss.get("episode_transcript") or ss.get("debate_messages") or []
        turns_for_judge = to_paired_turns_for_judge(raw_transcript)
        try:
            _evaluate_judge(ss, turns_for_judge)
        except Exception as e:
            ss["judge_status"] = "error"
            ss["judge_error"] = str(e)[:200]
            ss["judge_mode"] = "heuristic"
            print(f"[JUDGE] error: {str(e)[:100]}")
            try:
                error_scorecard = ss["judge"]._error_scorecard()
            except (AttributeError, TypeError):
                error_scorecard = [
                    {"metric": m, "spreader": 0.0, "debunker": 0.0, "weight": 0.0}
                    for m in _METRIC_NAMES
                ]
            ss["judge_decision"] = _make_judge_decision_safe(
                winner="draw", confidence=0.0,
                reason=f"Judge evaluation failed: {str(e)[:100]}",
                totals={"spreader": 0.0, "debunker": 0.0},
                scorecard=error_scorecard,
            )

    judge_decision = ss.get("judge_decision") or {}
    concession_data = ss.get("concession_data") or {}
    if not isinstance(ss.get("judge_decision"), dict):
        ss["judge_decision"] = judge_decision

    if not ss.get("run_id"):
        ss["run_id"] = make_run_id()
        ss["episode_counter"] = 0
    run_id = ss["run_id"]
    episode_id = ss.get("episode_idx", ss.get("episode_counter", 0))
    ss["episode_counter"] = episode_id + 1

    # Convert transcript to paired turns
    raw_transcript = ss.get("episode_transcript") or ss.get("debate_messages") or []
    turns = _convert_transcript_for_judge(raw_transcript)

    arena_mode = ss.get("arena_mode", "single_claim") or "single_claim"
    claim_metadata = _extract_claim_metadata(ss)
    judge_verdict = _jd_to_dict(judge_decision) if judge_decision else {}

    # Strategy analysis
    strategy_analysis = _run_strategy_analysis(
        claim=ss.get("topic", ""),
        claim_metadata=claim_metadata,
        turns=turns,
        judge_verdict=judge_verdict,
        arena_mode=arena_mode,
    )

    # Build v2 objects
    run_obj = _build_run_object(ss, run_id, arena_mode)
    episode_obj = _build_episode_object(
        ss, run_id, episode_id, turns, judge_decision,
        concession_data, strategy_analysis, arena_mode,
    )

    # Persist to disk
    try:
        safe_run_obj = to_jsonable(run_obj)
        write_run_json(run_id, safe_run_obj)

        # Add judge audit envelope
        judge_mode = ss.get("judge_mode", "heuristic")
        agent_model = ss.get("judge_model_select") or os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")
        if judge_mode == "agent":
            judge_version = f"agent_v1:{agent_model}"
        elif judge_mode == "heuristic_fallback":
            judge_version = "heuristic_fallback_v1"
        else:
            judge_version = "heuristic_v1"
        episode_obj["judge_audit"] = {
            "status": ss.get("judge_status", "unknown"),
            "error_message": ss.get("judge_error"),
            "version": judge_version,
            "mode": judge_mode,
        }

        safe_episode_obj = to_jsonable(episode_obj)
        append_episode_jsonl(run_id, safe_episode_obj)
        print(f"[PERSIST_V2] run_id={run_id} episode_id={episode_id}")

        # Bump cache token
        try:
            import streamlit as st
            from arena.presentation.streamlit.state.runs_refresh import bump_runs_refresh_token
            bump_runs_refresh_token("episode_appended")
            st.session_state["last_persisted_run_id"] = run_id
            st.session_state["last_persisted_episode_id"] = episode_id
        except Exception:
            pass

        # Legacy v1 (off by default)
        if os.getenv("WRITE_LEGACY_MATCHES", "0") == "1":
            match_obj = {
                "match_id": f"match_{episode_id}",
                "timestamp": ss.get("match_start_time"),
                "topic": ss.get("topic", ""),
                "transcript": ss.get("episode_transcript", []),
                "winner": _jd_get(judge_decision, "winner"),
                "judge_decision": _jd_to_dict(judge_decision),
                "episode_idx": episode_id,
                "turn_count": ss.get("completed_turn_pairs", 0),
            }
            safe_match_obj = to_jsonable(match_obj)
            append_match_jsonl(str(DEFAULT_MATCHES_PATH), safe_match_obj)

    except Exception as e:
        err = f"PERSIST_FAIL err={type(e).__name__}: {e}"
        print(err)
        ss["last_persist_error"] = err
