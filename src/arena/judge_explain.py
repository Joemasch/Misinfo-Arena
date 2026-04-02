"""Deprecated -- explanations handled in judge.py directly.

The explain_judge_decision() function is kept as a thin shim for
backward compatibility with app.py's legacy analytics expander,
which still imports it inside a try/except block.
"""

from typing import Dict, Any, Optional


def explain_judge_decision(judge_output: Any) -> Dict[str, Any]:
    """Minimal shim kept for backward compatibility."""
    if not judge_output or not isinstance(judge_output, dict):
        return {
            "winner": None,
            "confidence": None,
            "summary": "No judge explanation available.",
            "criteria_breakdown": {},
            "evidence_used": [],
        }

    winner = judge_output.get("winner")
    confidence = judge_output.get("confidence")
    reason = judge_output.get("reason", "")
    scorecard = judge_output.get("scorecard", [])

    if reason:
        summary = reason
    elif winner:
        summary = f"The {winner} won the debate."
    else:
        summary = "Debate outcome determined."

    criteria_breakdown = {}
    if scorecard:
        for metric in scorecard:
            metric_name = metric.get("metric", "unknown")
            criteria_breakdown[metric_name] = {
                "spreader_score": metric.get("spreader", 0.0),
                "debunker_score": metric.get("debunker", 0.0),
                "difference": metric.get("debunker", 0.0) - metric.get("spreader", 0.0),
            }

    return {
        "winner": winner,
        "confidence": confidence,
        "summary": summary,
        "criteria_breakdown": criteria_breakdown,
        "evidence_used": judge_output.get("evidence_used", []),
    }


def extract_judge_explanation_from_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Minimal shim kept for backward compatibility."""
    if "judge_explanation" in record and record["judge_explanation"]:
        return record["judge_explanation"]
    judge_decision = record.get("judge_decision")
    if judge_decision:
        return explain_judge_decision(judge_decision)
    return None
