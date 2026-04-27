"""
Episode and run object builders for persistence.

Extracted from execute_next_turn.py to reduce module size.
Builds the JSON v2 episode and run metadata objects from session state.
"""

import os
from datetime import datetime

from arena.prompts.judge_static_prompt import JUDGE_STATIC_PROMPT_VERSION
from arena.prompts.prompt_library import get_active_prompt_id
from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT
from arena.claim_metadata import infer_claim_metadata_from_text
from arena.strategy_analyst import analyze_episode_strategies

from arena.application.use_cases.judge_helpers import (
    _jd_get,
    _ensure_non_empty_scorecard,
)


def _extract_claim_metadata(ss) -> dict:
    """Return optional claim metadata from session state. Only includes non-empty values."""
    out = {}
    for key in (
        "claim_id",
        "claim_type",
        "claim_complexity",
        "claim_verifiability",
        "claim_structure",
        "claim_label_source",
    ):
        val = ss.get(key)
        if val is not None and str(val).strip():
            out[key] = val
    return out


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
        "study_id": ss.get("study_id"),
        "condition": ss.get("condition"),
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
                    "model": (ss.get("judge_model_select") or os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")) if ss.get("judge_mode") == "agent" else "heuristic",
                    "temperature": ss.get("judge_temperature", None),
                    "prompt_version": JUDGE_STATIC_PROMPT_VERSION,
                    "prompt_customized": ss.get("judge_prompt_customized", False),
                    "static_prompt": ss.get("judge_static_prompt_used") if ss.get("judge_mode") == "agent" else None,
                    "consistency_n": ss.get("judge_consistency_n", 1),
                    "consistency_std": ss.get("judge_consistency_std"),
                },
            },
            "judge_weights": {
                "factuality": 0.125, "source_reputability": 0.125,
                "hallucination_index": 0.125, "reasoning_quality": 0.125,
                "responsiveness": 0.125, "persuasion": 0.125,
                "manipulation_awareness": 0.125, "adaptability": 0.125,
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

    # Merge claim metadata: heuristic base -> curated -> session state override
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
                "judge": {"model": ss.get("judge_model_select") or os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini"), "temperature": ss.get("judge_temperature", None)},
            },
            "judge_weights": {
                "factuality": 0.125, "source_reputability": 0.125,
                "hallucination_index": 0.125, "reasoning_quality": 0.125,
                "responsiveness": 0.125, "persuasion": 0.125,
                "manipulation_awareness": 0.125, "adaptability": 0.125,
            },
        },
        "storage": {"episodes_file": "episodes.jsonl"},
    }
