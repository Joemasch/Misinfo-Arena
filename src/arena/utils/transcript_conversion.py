"""
Canonical transcript conversion for judge and concession logic.

Converts episode_transcript or flat stored turns into paired-turn format
expected by HeuristicJudge and AgentJudge.

Storage format (unchanged): flat list of {name, content, turn_index}
Judge format: paired list of {turn_index, spreader_message, debunker_message}
"""

from __future__ import annotations


def _extract_speaker(msg: dict) -> str | None:
    """
    Extract speaker role from message dict.
    Prefer "name", fallback to "speaker". Do NOT rely on "role" (single-message uses user/assistant).
    Returns "spreader", "debunker", or None if unrecognized.
    """
    if not isinstance(msg, dict):
        return None
    raw = (msg.get("name") or msg.get("speaker") or "").strip().lower()
    if raw in ("spreader", "debunker"):
        return raw
    return None


def _extract_turn_index(msg: dict) -> int | None:
    """Extract turn index from message dict. Accepts turn_index or turn."""
    if not isinstance(msg, dict):
        return None
    val = msg.get("turn_index")
    if val is None:
        val = msg.get("turn")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _extract_content(msg: dict) -> str:
    """Extract content from message dict."""
    if not isinstance(msg, dict):
        return ""
    raw = msg.get("content") or msg.get("text") or msg.get("message") or ""
    return str(raw).strip() if raw is not None else ""


def to_paired_turns_for_judge(messages: list[dict]) -> list[dict]:
    """
    Convert flat or mixed message list to paired-turn format for judge.

    Accepts:
    - episode_transcript (role user/assistant, name spreader/debunker)
    - flat stored turns ({name, content, turn_index})
    - debate_messages ({speaker, content, turn})

    Returns:
        [
            {
                "turn_index": int,
                "spreader_message": {"content": str},
                "debunker_message": {"content": str}
            },
            ...
        ]
    Order: ascending by turn_index. Missing side gets content="".
    """
    if not messages:
        return []

    # Group by turn_index
    grouped: dict[int, list[dict]] = {}
    has_any_turn_index = False

    for m in messages:
        if not isinstance(m, dict):
            continue
        tidx = _extract_turn_index(m)
        if tidx is not None:
            has_any_turn_index = True
        else:
            tidx = 0  # Placeholder; will use fallback below
        grouped.setdefault(tidx, []).append(m)

    # Fallback: if no turn_index anywhere, infer sequentially
    if not has_any_turn_index and grouped:
        inferred: dict[int, list[dict]] = {}
        cur_turn = 0
        for m in messages:
            if not isinstance(m, dict):
                continue
            sp = _extract_speaker(m)
            if sp is None:
                continue
            inferred.setdefault(cur_turn, []).append(m)
            if sp == "debunker":
                cur_turn += 1
        grouped = inferred

    out = []
    for turn_idx in sorted(grouped.keys()):
        msgs = grouped[turn_idx]
        spreader_content = ""
        debunker_content = ""
        for m in msgs:
            sp = _extract_speaker(m)
            if sp == "spreader":
                spreader_content = _extract_content(m)
            elif sp == "debunker":
                debunker_content = _extract_content(m)

        out.append({
            "turn_index": turn_idx,
            "spreader_message": {"content": spreader_content},
            "debunker_message": {"content": debunker_content},
        })

    return out
