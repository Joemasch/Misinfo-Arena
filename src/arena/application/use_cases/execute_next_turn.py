"""
Execute Next Turn Use Case

Handles the debate turn-pair execution logic (spreader -> debunker -> completion checks).
Extracted from app.py to separate application logic from presentation concerns.
"""

import streamlit as st
import json
import math
import traceback
import os  # NOTE: os must be imported at module scope. Do not import inside functions (causes UnboundLocalError in judge routing).
from datetime import datetime
from collections import defaultdict

# Import required types and functions
from arena.factories import DebateConfig, Message, Turn, AgentRole
from arena.concession import should_concede, check_keyword_concession
from arena.state import is_concession
from arena.application.types import TurnPairResult
from arena.io.run_store import (
    append_match_jsonl,
    write_run_json,
    append_episode_jsonl,
    make_run_id,
)
from arena.app_config import DEFAULT_MATCHES_PATH, DEBUG_DIAG
from arena.prompts.judge_static_prompt import (
    JUDGE_STATIC_PROMPT_VERSION,
    get_judge_static_prompt,
)
from arena.prompts.prompt_library import get_active_prompt_id
from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
from arena.utils.serialization import to_jsonable
from arena.utils.transcript_conversion import to_paired_turns_for_judge
from arena.claim_metadata import infer_claim_metadata_from_text
from arena.strategy_analyst import analyze_episode_strategies

def _jd_get(jd, key, default=None):
    # Supports dict-like and object-like JudgeDecision
    if jd is None:
        return default
    if isinstance(jd, dict):
        return jd.get(key, default)
    # dataclass / object
    return getattr(jd, key, default)

def _jd_to_dict(jd):
    if jd is None:
        return {}
    if isinstance(jd, dict):
        return jd
    # dataclass has __dict__ but may include non-serializable types; shallow copy is fine here
    try:
        from dataclasses import asdict, is_dataclass
        if is_dataclass(jd):
            return asdict(jd)
    except Exception:
        pass
    try:
        return dict(jd.__dict__)
    except Exception:
        return {}

def _extract_claim_metadata(ss) -> dict:
    """Return optional claim metadata from session state. Only includes non-empty values."""
    out = {}
    for key in (
        "claim_id",
        "claim_type",
        "claim_complexity",
        "claim_domain",
        "claim_verifiability",
        "claim_structure",
        "claim_label_source",
    ):
        val = ss.get(key)
        if val is not None and str(val).strip():
            out[key] = val
    return out


def _ensure_non_empty_scorecard(scorecard) -> list:
    """Ensure scorecard is never empty - defensive fallback."""
    if scorecard and len(scorecard) > 0:
        return scorecard
    # Create fallback 6-metric scorecard
    return [
        {"metric": m, "spreader": 0.0, "debunker": 0.0, "weight": 0.0}
        for m in ["factuality", "source_credibility", "reasoning_quality", "responsiveness", "persuasion", "manipulation_awareness"]
    ]

def _infer_judge_status(decision) -> tuple[str, str | None]:
    """Infer judge status from returned JudgeDecision object."""
    if decision is None:
        return "error", "Judge returned None"

    # Extract fields safely
    winner = _jd_get(decision, "winner")
    confidence = _jd_get(decision, "confidence", 0.0)
    reason = _jd_get(decision, "reason", "")
    totals = _jd_get(decision, "totals", {})
    scorecard = _jd_get(decision, "scorecard", [])

    # Check for error indicators
    is_error = False
    error_msg = None

    # Check reason for failure indicators
    if reason and ("judge evaluation failed" in reason.lower() or "judge received no turns" in reason.lower()):
        is_error = True
        error_msg = reason

    # Check scorecard emptiness
    if not scorecard or len(scorecard) == 0:
        is_error = True
        error_msg = error_msg or "Empty scorecard returned"

    # Check totals structure
    if not isinstance(totals, dict) or "spreader" not in totals or "debunker" not in totals:
        is_error = True
        error_msg = error_msg or "Invalid totals structure"

    # Check for placeholder values (all zeros + draw + confidence 0.0)
    if (winner == "draw" and confidence == 0.0 and
        isinstance(totals, dict) and totals.get("spreader") == 0.0 and totals.get("debunker") == 0.0):
        # This could be either success (no debate) or error - check reason
        if reason and "placeholder" in reason.lower():
            is_error = True
            error_msg = error_msg or "Placeholder decision returned"

    return ("error", error_msg) if is_error else ("success", None)

def _make_judge_decision_safe(**kwargs):
    # Import the actual JudgeDecision type
    from arena.judge import JudgeDecision, MetricScore
    # If it's a dataclass:
    try:
        allowed = set(getattr(JudgeDecision, "__dataclass_fields__", {}).keys())
        if allowed:
            filtered = {k: v for k, v in kwargs.items() if k in allowed}
            return JudgeDecision(**filtered)
    except Exception:
        pass
    # If it's a normal class / TypedDict-like, fall back to passing only common keys
    common = {}
    for k in ("winner", "confidence", "judge_confidence", "reason", "rationale", "explanation", "scorecard", "scores", "metrics"):
        if k in kwargs:
            common[k] = kwargs[k]
    return JudgeDecision(**common)


def _evaluate_judge(ss, turns_for_judge) -> None:
    """Run judge evaluation and store results in session state."""
    from arena.factories import DebateConfig
    config = DebateConfig(
        max_turns=ss.get("max_turns", 5),
        topic=ss.get("topic", ""),
        judge_weights={
            "factuality": 0.167, "source_credibility": 0.167,
            "reasoning_quality": 0.167, "responsiveness": 0.167,
            "persuasion": 0.167, "manipulation_awareness": 0.167,
        },
    )
    judge_mode = os.getenv("JUDGE_MODE", "agent").lower()
    agent_model = os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")

    if judge_mode == "agent":
        try:
            from arena.judge import AgentJudge
            current_judge_prompt = (
                (ss.get("judge_static_prompt") or "").strip()
                or get_judge_static_prompt()
            )
            ss["judge_static_prompt_used"] = current_judge_prompt
            ss["judge_prompt_customized"] = current_judge_prompt.strip() != get_judge_static_prompt().strip()
            _consistency_runs = int(ss.get("judge_consistency_runs", 1) or 1)
            agent_judge = AgentJudge(
                model=agent_model,
                static_prompt_template=current_judge_prompt or None,
                consistency_runs=_consistency_runs,
            )
            decision = agent_judge.evaluate_match(turns_for_judge, config)
            ss["judge_decision"] = decision
            ss["judge_status"] = "success"
            ss["judge_error"] = None
            ss["judge_mode"] = "agent"
            ss["judge_consistency_n"] = agent_judge.last_consistency_n
            ss["judge_consistency_std"] = agent_judge.last_consistency_std
            print("[JUDGE] success (agent)")
        except Exception as agent_error:
            print(f"[JUDGE] agent failed: {str(agent_error)[:100]}, falling back to heuristic")
            decision = ss["judge"].evaluate_match(turns_for_judge, config)
            ss["judge_decision"] = decision
            ss["judge_status"] = "success"
            ss["judge_error"] = str(agent_error)[:200]
            ss["judge_mode"] = "heuristic_fallback"
            print("[JUDGE] success (heuristic_fallback)")
    else:
        decision = ss["judge"].evaluate_match(turns_for_judge, config)
        ss["judge_decision"] = decision
        status, error_msg = _infer_judge_status(decision)
        ss["judge_status"] = status
        ss["judge_error"] = error_msg
        ss["judge_mode"] = "heuristic"
        print(f"[JUDGE] {status} (heuristic)")


def _run_strategy_analysis(claim, claim_metadata, turns, judge_verdict, arena_mode):
    """Run optional strategy analysis. Returns result dict or None."""
    if os.getenv("ENABLE_STRATEGY_ANALYST", "1").lower() not in ("1", "true", "yes"):
        return None
    if not turns:
        return None
    try:
        result = analyze_episode_strategies(
            claim=claim,
            claim_metadata=claim_metadata or None,
            transcript_turns=turns,
            judge_result=judge_verdict,
            arena_mode=arena_mode,
        )
        print("[STRATEGY] success")
        return result
    except Exception as e:
        from arena.strategy_analyst import build_error_stub
        print(f"[STRATEGY] failed: {e}")
        return build_error_stub(str(e))


def _build_episode_object(ss, run_id, episode_id, turns, judge_decision, concession_data, strategy_analysis, arena_mode) -> dict:
    """Build the v2 episode JSON object from session state."""
    claim_idx = ss.get("current_claim_index", 0) if arena_mode == "multi_claim" else (episode_id - 1 if isinstance(episode_id, int) else 0)
    total_cl = ss.get("total_claims", 1) if arena_mode == "multi_claim" else 1

    episode_obj = {
        "schema_version": "2.0",
        "run_id": run_id,
        "episode_id": episode_id,
        "created_at": datetime.now().isoformat(),
        "claim": ss.get("topic", ""),
        "claim_index": claim_idx,
        "total_claims": total_cl,
        "config_snapshot": {
            "planned_max_turns": ss.get("max_turns", 5),
            "agents": {
                "spreader": {
                    "model": ss.get("spreader_model"),
                    "temperature": ss.get("spreader_temperature"),
                    "prompt_id": get_active_prompt_id("spreader"),
                    "prompt_version": "spreader_v1",
                    "prompt_customized": (ss.get("spreader_prompt") or "").strip() != (SPREADER_SYSTEM_PROMPT or "").strip(),
                    "static_prompt": ss.get("spreader_prompt"),
                },
                "debunker": {
                    "model": ss.get("debunker_model"),
                    "temperature": ss.get("debunker_temperature"),
                    "prompt_id": get_active_prompt_id("debunker"),
                    "prompt_version": "debunker_v1",
                    "prompt_customized": (ss.get("debunker_prompt") or "").strip() != (DEBUNKER_SYSTEM_PROMPT or "").strip(),
                    "static_prompt": ss.get("debunker_prompt"),
                },
                "judge": {
                    "type": "agent" if ss.get("judge_mode") == "agent" else "heuristic",
                    "model": os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini") if ss.get("judge_mode") == "agent" else "heuristic",
                    "temperature": ss.get("judge_temperature", None),
                    "prompt_version": JUDGE_STATIC_PROMPT_VERSION,
                    "prompt_customized": ss.get("judge_prompt_customized", False),
                    "static_prompt": ss.get("judge_static_prompt_used") if ss.get("judge_mode") == "agent" else None,
                    "consistency_n": ss.get("judge_consistency_n", 1),
                    "consistency_std": ss.get("judge_consistency_std"),
                },
            },
            "judge_weights": {
                "truthfulness_proxy": 0.2, "evidence_quality": 0.2,
                "reasoning_quality": 0.2, "responsiveness": 0.15,
                "persuasion": 0.15, "civility": 0.1,
            },
            "judge_prompt_static_version": JUDGE_STATIC_PROMPT_VERSION,
        },
        "results": {
            "completed_turn_pairs": ss.get("completed_turn_pairs", 0),
            "winner": _jd_get(judge_decision, "winner"),
            "judge_confidence": _jd_get(judge_decision, "confidence"),
            "reason": _jd_get(judge_decision, "reason"),
            "totals": _jd_get(judge_decision, "totals"),
            "scorecard": _ensure_non_empty_scorecard(_jd_get(judge_decision, "scorecard", [])),
        },
        "concession": {
            "early_stop": ss.get("early_stop_reason") is not None,
            "trigger": ss.get("stop_reason", "max_turns"),
            "conceded_by": concession_data.get("conceded_by"),
            "concession_turn": concession_data.get("turn"),
        },
        "summaries": {"abridged": "", "full": "", "model": "", "version": "v0"},
        "turns": turns,
    }

    if strategy_analysis is not None:
        episode_obj["strategy_analysis"] = strategy_analysis

    # Merge claim metadata: heuristic base → curated → session state override
    existing = _extract_claim_metadata(ss)
    inferred = infer_claim_metadata_from_text(ss.get("topic", ""))
    curated = {}
    meta_list = ss.get("claim_metadata_list") or []
    if 0 <= claim_idx < len(meta_list) and meta_list[claim_idx]:
        curated = {k: v for k, v in (meta_list[claim_idx] or {}).items() if v is not None and str(v).strip()}
    merged = dict(inferred)
    merged.update(curated)
    merged.update({k: v for k, v in existing.items() if v is not None and str(v).strip()})
    episode_obj.update(merged)

    return episode_obj


def _build_run_object(ss, run_id, arena_mode) -> dict:
    """Build the v2 run.json metadata object."""
    return {
        "schema_version": "2.0",
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "arena_type": "multi_claim" if arena_mode == "multi_claim" else "single_claim",
        "input": {
            "single_claim": ss.get("topic", "") if arena_mode != "multi_claim" else "",
            "claims": ss.get("claims_list", []) if arena_mode == "multi_claim" else [],
            "claim_metadata": ss.get("claim_metadata_list") or [],
        },
        "run_config": {
            "episode_count": ss.get("total_claims", ss.get("num_episodes", 1)) if arena_mode == "multi_claim" else ss.get("num_episodes", 1),
            "turn_schedule": {"type": "fixed", "values": []},
            "agents": {
                "spreader": {"model": ss.get("spreader_model"), "temperature": ss.get("spreader_temperature")},
                "debunker": {"model": ss.get("debunker_model"), "temperature": ss.get("debunker_temperature")},
                "judge": {"model": ss.get("judge_model", "heuristic"), "temperature": ss.get("judge_temperature", None)},
            },
            "judge_weights": {
                "truthfulness_proxy": 0.2, "evidence_quality": 0.2,
                "reasoning_quality": 0.2, "responsiveness": 0.15,
                "persuasion": 0.15, "civility": 0.1,
            },
        },
        "storage": {"episodes_file": "episodes.jsonl"},
    }


def _persist_completed_match(ss) -> None:
    """
    Persist a completed match: evaluate judge, run strategy analysis,
    build episode/run objects, and write to disk.

    Split into sub-functions for testability:
    - _evaluate_judge() — judge routing and scoring
    - _run_strategy_analysis() — optional strategy labeling
    - _build_episode_object() — v2 episode JSON construction
    - _build_run_object() — v2 run metadata construction
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
                    for m in ["factuality", "source_credibility", "reasoning_quality", "responsiveness", "persuasion", "manipulation_awareness"]
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
        agent_model = os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")
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


def _convert_transcript_for_judge(raw: list[dict]) -> list[dict]:
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
    # V2_CONVERT_ENTRY
    if hasattr(st.session_state, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("V2_CONVERT_ENTRY", raw_len=len(raw) if raw else 0,
                     sample_keys=list(raw[-1].keys()) if raw and isinstance(raw[-1], dict) else None)
        except ImportError:
            pass

    out = []
    bad_not_dict = bad_missing_content = bad_missing_name = bad_missing_turn = 0

    for m in raw or []:
        if not isinstance(m, dict):
            bad_not_dict += 1
            continue
        content = (m.get("content") or m.get("text") or m.get("message") or "").strip()
        name = (m.get("name") or m.get("speaker") or "").strip()
        turn = m.get("turn_index")
        if turn is None:
            turn = m.get("turn")
        if not content:
            bad_missing_content += 1
            continue
        if not name:
            bad_missing_name += 1
            continue
        if turn is None:
            bad_missing_turn += 1
            continue
        out.append({
            "name": name,
            "content": content,
            "turn_index": int(turn),
        })

    # V2_CONVERT_RESULT
    if hasattr(st.session_state, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("V2_CONVERT_RESULT",
                     out_len=len(out),
                     bad_not_dict=bad_not_dict,
                     bad_missing_content=bad_missing_content,
                     bad_missing_name=bad_missing_name,
                     bad_missing_turn=bad_missing_turn,
                     out_last=out[-1] if out else None)
        except ImportError:
            pass

    return out


def generate_agent_message(agent, context):
    """
    Generate a message from an agent with the given context.
    """
    return agent.generate(context)


def execute_next_turn(state=None, single_message_mode=False) -> dict:
    """
    EXECUTE NEXT TURN - Generate both spreader and debunker messages.

    CHAT TURN PATTERN:
    ==================
    1. Generate spreader message based on topic and conversation history
    2. Generate debunker message in response to spreader
    3. Add both messages to chat transcript immediately
    4. Check for completion conditions
    5. If complete, run judge evaluation

    WHY TWO MESSAGES PER TURN?
    ==========================
    - Matches real debate flow: spreader argues, debunker responds
    - Each button click advances the conversation meaningfully
    - Users see both sides of the exchange at once
    """
    # Use provided state or default to streamlit session_state
    ss = state if state is not None else st.session_state

    # ===================================================================
    # TRANSCRIPT KEY BRIDGING - Ensure UI and persistence use same transcript
    # ===================================================================
    # The Arena UI renders from debate_messages, but persistence expects episode_transcript
    # Bridge them so both keys contain the same data
    if "debate_messages" in ss and "episode_transcript" not in ss:
        ss["episode_transcript"] = ss["debate_messages"]
    elif "episode_transcript" in ss and "debate_messages" not in ss:
        ss["debate_messages"] = ss["episode_transcript"]

    # Create result object to track turn execution
    result = TurnPairResult(ok=True, debug={})

    # TEMPORARY DEBUG: Entry state (gated by DEBUG_DIAG for production experimentation)
    if DEBUG_DIAG:
        print(f"TRACE execute_next_turn ENTRY: single_mode={single_message_mode} phase={ss.get('debate_phase')} pairs={ss.get('completed_turn_pairs', 0)} max={ss.get('max_turns', 5)} match_in_progress={ss.get('match_in_progress', False)}")

    # A) STEP_ENTRY at function entry
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("STEP_ENTRY",
                     phase=ss.get('debate_phase'),
                     completed_turn_pairs=ss.get('completed_turn_pairs', 0),
                     match_in_progress=ss.get('match_in_progress', False),
                     debate_running=ss.get('debate_running', False))
        except ImportError:
            pass

    # Initialize message variables to avoid UnboundLocalError
    spreader_message = None
    debunker_message = None

    # ===================================================================
    # GUARD: Check if match is in progress
    # ===================================================================
    if not ss.get("match_in_progress", False):
        st.warning("No active match to continue - start a new match first")
        result.ok = False
        result.completion_reason = "No active match"
        return result.to_dict()

    # Completion check moved to after message generation

    turn_idx = ss["turn_idx"]
    topic = ss.get("topic", "")

    # Track turn index in result
    result.turn_idx = turn_idx

    # ===================================================================
    # PHASE 2A: CONCESSION STATE MANAGEMENT
    # ===================================================================
    # Initialize or get rolling concession state for evidence-driven concessions
    if "concession_state" not in ss:
        ss["concession_state"] = {"consecutive": 0, "last_advantaged": None}

    if single_message_mode:
        # ===================================================================
        # SINGLE MESSAGE MODE - Generate one message per call (for UI rolling chat)
        # ===================================================================
        # Determine current speaker from debate_phase (default to spreader for first message)
        current_phase = ss.get("debate_phase", "spreader")
        debate_messages = ss.get("debate_messages", [])

        # Get context from debate_messages instead of messages
        last_spreader_content = ""
        last_debunker_content = ""
        for msg in reversed(debate_messages):
            if msg.get("status") == "final":  # Only consider finalized messages
                if msg.get("speaker") == "spreader":
                    last_spreader_content = msg.get("content", "")
                    break
                elif msg.get("speaker") == "debunker":
                    last_debunker_content = msg.get("content", "")
                    break

        # Build context for current speaker
        if current_phase == "spreader":
            context = {
                "topic": topic,
                "turn_idx": turn_idx,
                "last_opponent_text": last_debunker_content,
                "system_prompt": ss.get("spreader_prompt", ""),
            }
            agent = ss["spreader_agent"]
            speaker_name = "spreader"
            result.spreader_text = None  # Will be set after generation
        else:  # debunker
            context = {
                "topic": topic,
                "turn_idx": turn_idx,
                "last_opponent_text": last_spreader_content,
                "system_prompt": ss.get("debunker_prompt", ""),
            }
            agent = ss["debunker_agent"]
            speaker_name = "debunker"
            result.debunker_text = None  # Will be set after generation

        try:
            message_content = generate_agent_message(agent, context)
        except Exception as e:
            error_msg = f"{speaker_name.title()} generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = f"{speaker_name} generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # Add message to debate_messages (UI transcript)
        import time
        message_record = {
            "id": f"turn_{turn_idx}_{speaker_name}_{time.time()}",
            "turn": turn_idx,
            "speaker": speaker_name,
            "content": message_content,
            "status": "final",
            "ts": time.time(),
        }
        debate_messages.append(message_record)

        # APPEND: Track message append (transcript duplication detection)
        if hasattr(ss, 'arena_dbg'):  # Import debug function if available
            try:
                from app import arena_dbg
                arena_dbg("APPEND", speaker=speaker_name, turn=turn_idx,
                         debate_msgs_count=len(debate_messages),
                         episode_transcript_count=len(episode_transcript),
                         message_id=message_record.get("id", ""),
                         content_len=len(message_content))
            except ImportError:
                pass

        # Also add to episode_transcript for persistence (bridge the keys)
        episode_transcript = ss.get("episode_transcript", [])
        transcript_record = {
            "message_id": message_record["id"],
            "episode_index": ss.get("episode_idx", 1),
            "turn_index": turn_idx,
            "role": "user" if speaker_name == "spreader" else "assistant",
            "name": speaker_name,
            "content": message_content,
            "timestamp": message_record["ts"],
        }
        episode_transcript.append(transcript_record)

        # D) MSG_GENERATED immediately after message creation but before completion logic
        if hasattr(ss, 'arena_dbg'):
            try:
                from app import arena_dbg
                arena_dbg("MSG_GENERATED",
                         phase=ss.get('debate_phase'),
                         speaker=message_record.get("speaker"),
                         turn=message_record.get("turn"),
                         debate_messages_len=len(debate_messages),
                         episode_transcript_len=len(episode_transcript),
                         completed_turn_pairs=ss.get('completed_turn_pairs', 0))
            except ImportError:
                pass

        # Update result
        if speaker_name == "spreader":
            result.spreader_text = message_content
        else:
            result.debunker_text = message_content

        # Count full pair only after debunker responds
        if current_phase == "debunker":
            before = ss.get("completed_turn_pairs", 0)
            ss["completed_turn_pairs"] = before + 1
            if hasattr(ss, 'arena_dbg'):
                try:
                    from app import arena_dbg
                    arena_dbg(
                        "PAIRS_INC_AFTER_DEBUNK",
                        before=before,
                        after=ss["completed_turn_pairs"],
                        turn=transcript_record.get("turn_index"),
                        name=transcript_record.get("name"),
                    )
                except ImportError:
                    pass

        # Advance phase for next call
        if current_phase == "spreader":
            ss["debate_phase"] = "debunker"
        else:
            ss["debate_phase"] = "spreader"

    else:
        # ===================================================================
        # PAIR MODE - Generate both messages (original logic for backward compatibility)
        # ===================================================================
        # Find the last message from each debater for context
        messages = ss["messages"]

        # Find the last spreader message (for debunker context)
        last_spreader_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user" or msg.get("name") == "spreader":
                last_spreader_content = msg.get("content", "")
                break

        # Find the last debunker message (for spreader context)
        last_debunker_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" or msg.get("name") == "debunker":
                last_debunker_content = msg.get("content", "")
                break

        # ===================================================================
        # GENERATE SPREADER MESSAGE
        # ===================================================================
        spreader_context = {
            "topic": topic,
            "turn_idx": turn_idx,
            "last_opponent_text": last_debunker_content,
            "system_prompt": ss.get("spreader_prompt", ""),
        }

        try:
            spreader_message = generate_agent_message(ss["spreader_agent"], spreader_context)
        except Exception as e:
            error_msg = f"Spreader generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = "Spreader generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # ===================================================================
        # GENERATE DEBUNKER MESSAGE
        # ===================================================================
        debunker_context = {
            "topic": topic,
            "turn_idx": turn_idx,
            "last_opponent_text": spreader_message,
            "system_prompt": ss.get("debunker_prompt", ""),
        }

        try:
            debunker_message = generate_agent_message(ss["debunker_agent"], debunker_context)
        except Exception as e:
            error_msg = f"Debunker generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = "Debunker generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # Set result fields for pair mode
        result.spreader_text = str(spreader_message) if spreader_message is not None else ""
        result.debunker_text = str(debunker_message) if debunker_message is not None else ""

    # For single message mode, result fields are already set in the respective branches

    if not single_message_mode:
        # ===================================================================
        # PAIR MODE - Add both messages to transcripts
        # ===================================================================

        # Add to episode transcript (structured for judge/analysis)
        import datetime
        message_records = [
            {
                "message_id": f"ep{ss.get('episode_idx', 1)}_turn{turn_idx}_spreader",
                "episode_index": ss.get("episode_idx", 1),
                "turn_index": turn_idx,
                "role": "spreader",
                "name": "spreader",
                "content": str(spreader_message),
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "message_id": f"ep{ss.get('episode_idx', 1)}_turn{turn_idx}_debunker",
                "episode_index": ss.get("episode_idx", 1),
                "turn_index": turn_idx,
                "role": "debunker",
                "name": "debunker",
                "content": str(debunker_message),
                "created_at": datetime.datetime.now().isoformat()
            }
        ]

        if "episode_transcript" not in ss:
            ss["episode_transcript"] = []
        ss["episode_transcript"].extend(message_records)

        # Add to flat messages (for UI compatibility)
        ss["messages"].extend([
            {
                "role": "user",
                "name": "spreader",
                "content": spreader_message
            },
            {
                "role": "assistant",
                "name": "debunker",
                "content": debunker_message
            }
        ])

    if single_message_mode:
        # In single message mode, counters are updated incrementally above
        # Only increment turn_idx when completing a full pair (debunker turn)
        if current_phase == "debunker":  # Just completed a full turn
            ss["turn_idx"] += 1
    else:
        # ===================================================================
        # PAIR MODE - Update structured turns and counters (original logic)
        # ===================================================================
        if "turns" not in ss:
            ss["turns"] = []

        ss["turns"].append({
            "turn_idx": turn_idx,
            "spreader_text": spreader_message,
            "debunker_text": debunker_message
        })

        # ===================================================================
        # UPDATE COUNTERS
        # ===================================================================
        ss["turn_idx"] += 1
        ss["completed_turn_pairs"] = min(
            ss.get("spreader_msgs_count", 0) + 1,
            ss.get("debunker_msgs_count", 0) + 1
        )
        ss["spreader_msgs_count"] = ss.get("spreader_msgs_count", 0) + 1
        ss["debunker_msgs_count"] = ss.get("debunker_msgs_count", 0) + 1
        ss["current_turn_idx"] = ss["completed_turn_pairs"]

    # ===================================================================
    # CHECK COMPLETION CONDITIONS
    # ===================================================================
    max_turns = ss.get("max_turns", 5)

    # TURN_STATE: Track completion check
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("TURN_STATE", completed_turn_pairs=ss.get('completed_turn_pairs', 0),
                     max_turns=max_turns,
                     match_in_progress=ss.get('match_in_progress', False),
                     will_complete=(ss.get('completed_turn_pairs', 0) >= max_turns))
        except ImportError:
            pass
    else:
        # Fallback to existing logging (gated by DEBUG_DIAG for production experimentation)
        if DEBUG_DIAG:
            print(f"TRACE execute_next_turn CHECK_COMPLETION: pairs={ss.get('completed_turn_pairs', 0)} >= max={max_turns} ? {ss.get('completed_turn_pairs', 0) >= max_turns}")

    # CHECK_COMPLETION_POST_APPEND immediately before completion logic
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg(
                "CHECK_COMPLETION_POST_APPEND",
                phase=ss.get('debate_phase'),
                pairs=ss.get("completed_turn_pairs", 0),
                max_turns=max_turns,
                debate_messages_len=len(debate_messages),
                transcript_len=len(episode_transcript),
            )
        except ImportError:
            pass

    # Check for completion after phase advancement (ensures final debunker generates)
    if ss.get("completed_turn_pairs", 0) >= max_turns:
        ss["match_in_progress"] = False
        if hasattr(ss, 'arena_dbg'):
            try:
                from app import arena_dbg
                arena_dbg(
                    "COMPLETION_TRIGGERED",
                    pairs=ss["completed_turn_pairs"],
                    max_turns=max_turns,
                )
            except ImportError:
                pass
        elif DEBUG_DIAG:
            print(f"TRACE execute_next_turn COMPLETING: setting match_in_progress=False")
        ss["early_stop_reason"] = f"Reached maximum turn pairs ({max_turns})"
        ss["stop_reason"] = "max_turns"
        _persist_completed_match(ss)
        st.success(f"✅ Debate completed: Reached maximum turns ({max_turns})")
        result.completion_reason = "Max turns reached"
        result.match_completed = True
        result.early_stop_reason = ss["early_stop_reason"]
        result.debug["persisted"] = True
        result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
        return result.to_dict()

    if single_message_mode:
        # ===================================================================
        # SINGLE MESSAGE MODE - Check concession on the message just generated
        # ===================================================================
        just_generated_message = message_content
        speaker_who_spoke = speaker_name

        # Check if the message just generated contains a concession
        conceded = is_concession(just_generated_message)

        if conceded:
            # Set up concession data
            ss["concession_data"] = {
                "early_stop_reason": "concession_keyword",
                "conceded_by": speaker_who_spoke,
                "concession_method": "keyword",
                "concession_turn": turn_idx,
                "concession_strength": 1.0,
                "concession_reason": f"Keyword concession detected: '{just_generated_message[:50]}...'"
            }

            ss["match_in_progress"] = False
            ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
            ss["stop_reason"] = "concession_keyword"

            _persist_completed_match(ss)

            st.success(f"🎉 **{speaker_who_spoke.title()} conceded!** Debate completed via keyword concession.")

            result.completion_reason = "Keyword concession"
            result.match_completed = True
            result.early_stop_reason = ss["early_stop_reason"]
            if speaker_who_spoke == "spreader":
                result.spreader_conceded = True
            else:
                result.debunker_conceded = True
            result.debug["persisted"] = True
            result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
            return result.to_dict()
    else:
        # ===================================================================
        # PAIR MODE - Check concessions on both messages (original logic)
        # ===================================================================
        # Check for keyword concessions
        spreader_conceded = is_concession(spreader_message)
        debunker_conceded = is_concession(debunker_message)

        # Add concession results to result
        result.spreader_conceded = spreader_conceded
        result.debunker_conceded = debunker_conceded

        if spreader_conceded or debunker_conceded:
            # Set up concession data
            conceder = "spreader" if spreader_conceded else "debunker"
            concession_text = spreader_message if spreader_conceded else debunker_message

            ss["concession_data"] = {
                "early_stop_reason": "concession_keyword",
                "conceded_by": conceder,
                "concession_method": "keyword",
                "concession_turn": turn_idx,
                "concession_strength": 1.0,
                "concession_reason": f"Keyword concession detected: '{concession_text[:50]}...'"
            }

            ss["match_in_progress"] = False
            ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
            ss["stop_reason"] = "concession_keyword"

            _persist_completed_match(ss)

            st.success(f"🎉 **{conceder.title()} conceded!** Debate completed via keyword concession.")

            result.completion_reason = "Keyword concession"
            result.match_completed = True
            result.early_stop_reason = ss["early_stop_reason"]
            result.debug["persisted"] = True
            result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
            return result.to_dict()

    # Check for model-based concessions (evidence-driven)
    if len(ss.get("turns", [])) >= 2:  # Need at least 1 full exchange for meaningful evaluation
        try:
            raw_for_concession = ss.get("episode_transcript") or ss.get("debate_messages") or []
            paired_for_concession = to_paired_turns_for_judge(raw_for_concession)
            config = DebateConfig(max_turns=max_turns, topic=topic)
            result.judge_ran = True
            model_concession = should_concede(
                ss["judge"],
                paired_for_concession,
                config,
                ss["concession_state"]
            )

            if model_concession and model_concession["recommend"]:
                conceder = model_concession["conceder"]
                ss["concession_data"] = {
                    "early_stop_reason": "concession_model",
                    "conceded_by": conceder,
                    "concession_method": "model",
                    "concession_turn": turn_idx,
                    "concession_strength": model_concession["strength"],
                    "concession_reason": model_concession["reason"]
                }

                ss["match_in_progress"] = False
                ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
                ss["stop_reason"] = "concession_model"

                _persist_completed_match(ss)

                st.success(f"🎯 **{conceder.title()} conceded!** Debate completed via evidence-driven concession.")

                result.completion_reason = "Model concession"
                result.match_completed = True
                result.judge_ran = True
                result.early_stop_reason = ss["early_stop_reason"]
                result.debug["persisted"] = True
                result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
                return result.to_dict()

        except Exception as e:
            if DEBUG_DIAG:
                print(f"CONCESSION_ERROR: {str(e)}")
            # Continue without model concession check

    # ===================================================================
    # CONTINUE DEBATE
    # ===================================================================
    st.success(f"✅ Turn {turn_idx + 1} completed. Ready for next turn.")

    return result.to_dict()
