"""
Concession evaluation module for Misinformation Arena v2.

This module provides evidence-driven concession logic that analyzes judge scoring,
evidence signals, and conversation state to recommend when a debate participant
should concede. Includes fallback to keyword-based concession detection.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from arena.types import JudgeDecision, Turn
from arena.factories import DebateConfig

# Configuration constants
CONSECUTIVE_REQUIRED = 2
STRENGTH_THRESHOLD = 0.75
GAP_THRESHOLD_TOTALS = 2.0  # For when we have actual judge totals
GAP_THRESHOLD_CONF = 0.70   # For when we only have winner + confidence


@dataclass
class ConcessionRecommendation:
    """Recommendation for whether a participant should concede."""
    recommend: bool
    conceder: Optional[str]  # "spreader" or "debunker"
    strength: float          # 0.0 to 1.0
    reason: str
    method: str              # "model" or "keyword"
    at_turn_idx: Optional[int]


def _get_message_content(msg_or_dict, content_key: str = "content") -> str:
    """Get content from Turn message or dict (paired format)."""
    if msg_or_dict is None:
        return ""
    if isinstance(msg_or_dict, dict):
        return str(msg_or_dict.get(content_key) or msg_or_dict.get("text") or "")
    return getattr(getattr(msg_or_dict, "content", None) or msg_or_dict, "content", str(msg_or_dict))


def extract_evidence_signals(turns: List) -> Dict[str, Any]:
    """
    Extract evidence signals from debate turns.

    Accepts either Turn objects or paired dicts (spreader_message/debunker_message).
    Analyzes URLs and evidence-related phrases to quantify
    the strength of arguments presented by each side.

    Args:
        turns: List of debate turns (Turn objects or paired dicts)

    Returns:
        Dictionary with evidence metrics for each side
    """
    spreader_evidence = 0.0
    debunker_evidence = 0.0
    spreader_urls = 0
    debunker_urls = 0

    # Evidence phrases to look for (minimal set)
    evidence_phrases = [
        r'\baccording to\b', r'\bstudy\b', r'\bresearch\b', r'\bCDC\b', r'\bWHO\b',
        r'\bIPCC\b', r'\bNASA\b', r'\bscientists?\b', r'\bexperts?\b', r'\bevidence\b'
    ]
    evidence_pattern = re.compile('|'.join(evidence_phrases), re.IGNORECASE)

    # URL pattern
    url_pattern = re.compile(r'https?://[^\s]+', re.IGNORECASE)

    for turn in turns:
        spreader_msg = turn.get("spreader_message") if isinstance(turn, dict) else getattr(turn, "spreader_message", None)
        debunker_msg = turn.get("debunker_message") if isinstance(turn, dict) else getattr(turn, "debunker_message", None)

        if spreader_msg:
            text = _get_message_content(spreader_msg)
            evidence_count = min(len(evidence_pattern.findall(text)), 3)
            spreader_evidence += evidence_count
            spreader_urls += len(url_pattern.findall(text))

        if debunker_msg:
            text = _get_message_content(debunker_msg)
            evidence_count = min(len(evidence_pattern.findall(text)), 3)
            debunker_evidence += evidence_count
            debunker_urls += len(url_pattern.findall(text))

    # Normalize evidence scores (simple approach: scale by number of turns)
    num_turns = len(turns)
    if num_turns > 0:
        spreader_evidence = min(spreader_evidence / num_turns, 5.0)  # Cap at 5
        debunker_evidence = min(debunker_evidence / num_turns, 5.0)  # Cap at 5

    return {
        "spreader_evidence": spreader_evidence,
        "debunker_evidence": debunker_evidence,
        "spreader_urls": spreader_urls,
        "debunker_urls": debunker_urls
    }


def compute_score_gap(judge, turns: List[Turn], config: DebateConfig) -> Tuple[float, Optional[str], Dict[str, Any]]:
    """
    Compute the scoring gap between debunker and spreader.

    Uses judge evaluation to determine which side has the advantage and by how much.

    Args:
        judge: The judge instance to evaluate
        turns: Debate turns to evaluate
        config: Debate configuration

    Returns:
        Tuple of (gap, advantaged_side, debug_info)
        gap: Positive means debunker advantage, negative means spreader advantage
        advantaged: "debunker", "spreader", or None
    """
    debug = {"method": "unknown", "raw_gap": 0.0}

    try:
        # Get judge evaluation
        decision = judge.evaluate_match(turns, config)
        debug["decision_winner"] = decision.winner
        debug["decision_confidence"] = decision.confidence

        # Try to use actual totals if available
        if hasattr(decision, 'totals') and decision.totals:
            debunker_total = decision.totals.get('debunker', 0.0)
            spreader_total = decision.totals.get('spreader', 0.0)
            gap = debunker_total - spreader_total
            debug["method"] = "totals"
            debug["debunker_total"] = debunker_total
            debug["spreader_total"] = spreader_total
        else:
            # Fallback to winner + confidence approximation
            confidence = decision.confidence
            if decision.winner == "debunker":
                gap = confidence * 2.0  # Scale confidence to gap-like range
            elif decision.winner == "spreader":
                gap = -(confidence * 2.0)
            else:
                gap = 0.0
            debug["method"] = "confidence_fallback"

        debug["raw_gap"] = gap

        # Determine advantaged side
        if gap > 0.5:
            advantaged = "debunker"
        elif gap < -0.5:
            advantaged = "spreader"
        else:
            advantaged = None

        debug["advantaged"] = advantaged

    except Exception as e:
        debug["error"] = str(e)
        gap = 0.0
        advantaged = None

    return gap, advantaged, debug


def should_concede(judge, turns: List[Turn], config: DebateConfig, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine if a participant should concede based on evidence and scoring analysis.

    Args:
        judge: Judge instance for evaluation
        turns: Current debate turns
        config: Debate configuration
        state: Rolling state dict with:
            - "consecutive": int (consecutive turns with same advantage)
            - "last_advantaged": Optional[str] (last advantaged side)

    Returns:
        Dict with concession evaluation results:
        {
            "recommend": bool,
            "conceder": Optional[str] ("spreader" or "debunker"),
            "strength": float (0.0 to 1.0),
            "reason": str,
            "advantaged": Optional[str],
            "gap_debug": dict
        }
    """
    # Compute score gap and advantage
    gap, advantaged, gap_debug = compute_score_gap(judge, turns, config)

    # Extract evidence signals
    evidence = extract_evidence_signals(turns)

    # Compute strength score (0.0 to 1.0)
    gap_abs = abs(gap)

    # Choose threshold based on gap computation method
    if gap_debug["method"] == "totals":
        gap_threshold = GAP_THRESHOLD_TOTALS
        # Strength based on sigmoid-like normalization of gap
        strength_base = min(gap_abs / 5.0, 1.0)  # Normalize assuming max gap ~5
    else:
        gap_threshold = GAP_THRESHOLD_CONF
        # Strength based on confidence (already 0-1 range)
        strength_base = min(gap_debug.get("decision_confidence", 0.0), 1.0)

    # Evidence bonuses/penalties
    evidence_bonus = 0.0
    if advantaged:
        adv_urls = evidence[f"{advantaged}_urls"]
        opp_urls = evidence[f"{'debunker' if advantaged == 'spreader' else 'spreader'}_urls"]

        if adv_urls >= 1 and opp_urls == 0:
            evidence_bonus += 0.10  # Bonus for having URLs when opponent doesn't

        # Penalty for no evidence signals
        adv_evidence = evidence[f"{advantaged}_evidence"]
        if adv_evidence < 0.5:  # Less than 0.5 evidence phrases per turn on average
            strength_base = min(strength_base, 0.60)  # Cap at 0.60

    strength = min(strength_base + evidence_bonus, 1.0)

    # Update consecutive state for concession rules
    if advantaged == state.get("last_advantaged"):
        state["consecutive"] = state.get("consecutive", 0) + 1
    else:
        state["consecutive"] = 1
        state["last_advantaged"] = advantaged

    # Concession rule: trigger only when consecutive >= 2 and other conditions met
    recommend = (
        gap_abs >= gap_threshold and
        strength >= STRENGTH_THRESHOLD and
        state.get("consecutive", 0) >= CONSECUTIVE_REQUIRED and
        advantaged is not None
    )

    if recommend:
        conceder = "spreader" if advantaged == "debunker" else "debunker"
        reason_parts = [
            f"Strong {advantaged} advantage (gap={gap:.2f})",
            f"High confidence (strength={strength:.2f})",
            f"Consistent for {state['consecutive']} turns"
        ]
        if evidence_bonus > 0:
            reason_parts.append("Evidence advantage")
        reason = "; ".join(reason_parts)
    else:
        conceder = None
        reason = f"Gap {gap:.2f} below threshold or inconsistent advantage"

    return {
        "recommend": recommend,
        "conceder": conceder,
        "strength": strength,
        "reason": reason,
        "advantaged": advantaged,
        "gap_debug": gap_debug
    }


def check_keyword_concession(text: str) -> bool:
    """
    Check if text contains keyword-based concession phrases.

    Args:
        text: The text to check for concession keywords

    Returns:
        True if concession keywords are found, False otherwise
    """
    if not text:
        return False

    # Convert to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Common concession phrases
    concession_keywords = [
        "i concede", "you win", "you are right", "i was wrong",
        "i agree with you", "you've convinced me", "i stand corrected",
        "you are correct", "i admit defeat", "you win this debate",
        "i bow to your superior argument", "you have bested me",
        "i yield", "i surrender", "i give up", "you win",
        "congratulations", "well done", "good job", "impressive argument",
        "i'm convinced", "you convinced me", "i'm persuaded",
        "you persuaded me", "i accept your point", "you make a good point",
        "i see your point", "that's a good point", "fair enough",
        "point taken", "touché", "i stand corrected", "my mistake",
        "i was mistaken", "i apologize", "i'm sorry", "i retract",
        "i take back", "i withdraw my statement", "i was wrong about that"
    ]

    # Check if any concession keyword is in the text
    for keyword in concession_keywords:
        if keyword in text_lower:
            return True

    return False
