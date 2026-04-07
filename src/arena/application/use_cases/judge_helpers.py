"""
Judge helper utilities for execute_next_turn.

Extracted from execute_next_turn.py to reduce module size.
Contains judge decision accessors, validation, and evaluation routing.
"""

import os


def _jd_get(jd, key, default=None):
    """Supports dict-like and object-like JudgeDecision."""
    if jd is None:
        return default
    if isinstance(jd, dict):
        return jd.get(key, default)
    return getattr(jd, key, default)


def _jd_to_dict(jd):
    """Convert a JudgeDecision (dict, dataclass, or object) to a plain dict."""
    if jd is None:
        return {}
    if isinstance(jd, dict):
        return jd
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


_METRIC_NAMES = [
    "factuality",
    "source_credibility",
    "reasoning_quality",
    "responsiveness",
    "persuasion",
    "manipulation_awareness",
]


def _ensure_non_empty_scorecard(scorecard) -> list:
    """Ensure scorecard is never empty - defensive fallback."""
    if scorecard and len(scorecard) > 0:
        return scorecard
    return [
        {"metric": m, "spreader": 0.0, "debunker": 0.0, "weight": 0.0}
        for m in _METRIC_NAMES
    ]


def _infer_judge_status(decision) -> tuple:
    """Infer judge status from returned JudgeDecision object.

    Returns:
        Tuple of (status_str, error_msg_or_none).
    """
    if decision is None:
        return "error", "Judge returned None"

    winner = _jd_get(decision, "winner")
    confidence = _jd_get(decision, "confidence", 0.0)
    reason = _jd_get(decision, "reason", "")
    totals = _jd_get(decision, "totals", {})
    scorecard = _jd_get(decision, "scorecard", [])

    is_error = False
    error_msg = None

    if reason and ("judge evaluation failed" in reason.lower() or "judge received no turns" in reason.lower()):
        is_error = True
        error_msg = reason

    if not scorecard or len(scorecard) == 0:
        is_error = True
        error_msg = error_msg or "Empty scorecard returned"

    if not isinstance(totals, dict) or "spreader" not in totals or "debunker" not in totals:
        is_error = True
        error_msg = error_msg or "Invalid totals structure"

    if (winner == "draw" and confidence == 0.0 and
        isinstance(totals, dict) and totals.get("spreader") == 0.0 and totals.get("debunker") == 0.0):
        if reason and "placeholder" in reason.lower():
            is_error = True
            error_msg = error_msg or "Placeholder decision returned"

    return ("error", error_msg) if is_error else ("success", None)


def _make_judge_decision_safe(**kwargs):
    """Construct a JudgeDecision, filtering kwargs to known fields."""
    from arena.judge import JudgeDecision, MetricScore  # noqa: F811
    try:
        allowed = set(getattr(JudgeDecision, "__dataclass_fields__", {}).keys())
        if allowed:
            filtered = {k: v for k, v in kwargs.items() if k in allowed}
            return JudgeDecision(**filtered)
    except Exception:
        pass
    common = {}
    for k in ("winner", "confidence", "judge_confidence", "reason", "rationale",
              "explanation", "scorecard", "scores", "metrics"):
        if k in kwargs:
            common[k] = kwargs[k]
    return JudgeDecision(**common)


def _evaluate_judge(ss, turns_for_judge) -> None:
    """Run judge evaluation and store results in session state."""
    from arena.factories import DebateConfig
    from arena.judge import AgentJudge
    from arena.prompts.judge_static_prompt import get_judge_static_prompt

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
    # Read judge model from session state (sidebar selector) or env var fallback
    agent_model = ss.get("judge_model_select") or os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")

    if judge_mode == "agent":
        try:
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
