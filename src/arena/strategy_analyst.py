"""
Strategy Analyst: Post-judge agent that annotates completed debates with structured strategy labels.

Runs after the judge, before episode persistence. Outputs taxonomy-based strategy labels
for spreader and debunker. Never blocks persistence on failure.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from arena.strategy_taxonomy import (
    STRATEGY_ANALYSIS_VERSION,
    STRATEGY_TAXONOMY_VERSION,
    get_debunker_strategy_labels,
    get_spreader_strategy_labels,
)

STRATEGY_ANALYST_MODEL = os.getenv("STRATEGY_ANALYST_MODEL", "gpt-4o-mini")
MAX_NOTES_LENGTH = 500


def _extract_json_from_response(text: str) -> dict[str, Any]:
    """Extract JSON object from LLM response. Tolerates markdown fences."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"Strategy analysis JSON parse failed: {e}") from e


def _format_transcript_for_analyst(turns: list[dict]) -> str:
    """Format transcript turns for the strategy analyst prompt.

    Handles both formats:
    - Flat: [{"name": "spreader", "content": "...", "turn_index": 0}, ...]
    - Paired: [{"spreader_message": {"content": "..."}, "debunker_message": {"content": "..."}}, ...]
    """
    if not turns:
        return "(No transcript)"
    lines = []

    for i, t in enumerate(turns):
        # Paired format (from experiment engine)
        if "spreader_message" in t or "debunker_message" in t:
            s_msg = t.get("spreader_message") or {}
            d_msg = t.get("debunker_message") or {}
            s_text = (s_msg.get("content", "") if isinstance(s_msg, dict) else str(s_msg)).strip()
            d_text = (d_msg.get("content", "") if isinstance(d_msg, dict) else str(d_msg)).strip()
            if s_text:
                lines.append(f"Turn {i + 1} (Spreader): {s_text}")
            if d_text:
                lines.append(f"Turn {i + 1} (Debunker): {d_text}")
        # Flat format (from arena live debate)
        elif "name" in t and "content" in t:
            name = (t.get("name") or "Unknown").title()
            content = (t.get("content") or "").strip()
            tidx = t.get("turn_index", i)
            if content:
                lines.append(f"Turn {tidx + 1} ({name}): {content}")

    return "\n".join(lines) if lines else "(Empty transcript)"


def _normalize_strategy_output(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw analyst output: remove unknown labels, deduplicate, ensure schema.
    """
    spreader_labels = set(get_spreader_strategy_labels())
    debunker_labels = set(get_debunker_strategy_labels())

    def filter_list(lst: list, valid: set[str]) -> list[str]:
        if not isinstance(lst, list):
            return []
        seen = set()
        out = []
        for x in lst:
            s = str(x).strip() if x is not None else ""
            if s and s in valid and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def filter_primary(val: Any, valid: set[str]) -> str | None:
        if val is None:
            return None
        s = str(val).strip()
        return s if s and s in valid else None

    spreader_strategies = filter_list(raw.get("spreader_strategies") or [], spreader_labels)
    debunker_strategies = filter_list(raw.get("debunker_strategies") or [], debunker_labels)
    spreader_primary = filter_primary(raw.get("spreader_primary"), spreader_labels)
    debunker_primary = filter_primary(raw.get("debunker_primary"), debunker_labels)

    if not spreader_primary and spreader_strategies:
        spreader_primary = spreader_strategies[0]
    if not debunker_primary and debunker_strategies:
        debunker_primary = debunker_strategies[0]

    # Emergent strategies: pass through unfiltered (not constrained to taxonomy).
    # Each entry is expected to be {"side": str, "label": str, "description": str}.
    emergent_raw = raw.get("emergent_strategies") or []
    emergent_strategies: list[dict] = []
    if isinstance(emergent_raw, list):
        for entry in emergent_raw[:5]:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "").strip().lower().replace(" ", "_")
            side = str(entry.get("side") or "").strip().lower()
            desc = str(entry.get("description") or "").strip()[:200]
            if label and side in ("spreader", "debunker"):
                emergent_strategies.append({"side": side, "label": label, "description": desc})

    notes = (raw.get("notes") or "")
    if isinstance(notes, str):
        notes = notes.strip()[:MAX_NOTES_LENGTH]
    else:
        notes = ""

    return {
        "version": STRATEGY_ANALYSIS_VERSION,
        "taxonomy_version": STRATEGY_TAXONOMY_VERSION,
        "status": "ok",
        "analyst_type": "agent",
        "model": STRATEGY_ANALYST_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spreader_primary": spreader_primary,
        "debunker_primary": debunker_primary,
        "spreader_strategies": spreader_strategies,
        "debunker_strategies": debunker_strategies,
        "emergent_strategies": emergent_strategies,
        "notes": notes,
    }


def build_error_stub(error_msg: str) -> dict[str, Any]:
    """Build strategy_analysis stub for failure case. Public alias for external callers."""
    return _build_error_stub(error_msg)


def _build_error_stub(error_msg: str) -> dict[str, Any]:
    """Build strategy_analysis stub for failure case."""
    return {
        "version": STRATEGY_ANALYSIS_VERSION,
        "taxonomy_version": STRATEGY_TAXONOMY_VERSION,
        "status": "error",
        "analyst_type": "agent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spreader_primary": None,
        "debunker_primary": None,
        "spreader_strategies": [],
        "debunker_strategies": [],
        "emergent_strategies": [],
        "notes": "",
        "error": (error_msg or "Unknown error")[:200],
    }


def _judge_verdict_to_dict(verdict: Any) -> dict[str, Any]:
    """Convert judge decision to serializable dict."""
    if verdict is None:
        return {}
    if isinstance(verdict, dict):
        return verdict
    if hasattr(verdict, "model_dump"):
        return verdict.model_dump()
    if hasattr(verdict, "__dict__"):
        return dict(verdict.__dict__)
    return {}


def analyze_episode_strategies(
    claim: str,
    transcript_turns: list[dict],
    judge_result: Any,
    claim_metadata: dict[str, Any] | None = None,
    arena_mode: str = "single_claim",
) -> dict[str, Any]:
    """
    Analyze debate transcript and return structured strategy labels.

    Inputs:
        claim: The debate claim/topic.
        transcript_turns: List of {name, content, turn_index} (from _convert_transcript_for_judge).
        judge_result: Judge decision (dict or object).
        claim_metadata: Optional dict with claim_id, claim_type, etc.
        arena_mode: "single_claim" or "multi_claim".

    Returns:
        Normalized strategy_analysis dict (status "ok") or error stub (status "error").
        Never raises; failures return error stub.
    """
    if not transcript_turns:
        return _build_error_stub("Empty transcript")

    try:
        from openai import OpenAI
        from arena.utils.openai_config import get_openai_api_key

        api_key = get_openai_api_key()
        if not api_key:
            return _build_error_stub("OpenAI API key not configured")
        client = OpenAI(api_key=api_key)
    except ImportError:
        return _build_error_stub("OpenAI library not available")
    except Exception as e:
        return _build_error_stub(f"OpenAI client init failed: {e}")

    spreader_labels = get_spreader_strategy_labels()
    debunker_labels = get_debunker_strategy_labels()
    verdict = _judge_verdict_to_dict(judge_result)
    formatted_transcript = _format_transcript_for_analyst(transcript_turns)

    system_prompt = f"""You are a debate strategy analyst. Your task is to identify the rhetorical strategies used by the spreader (misinformation promoter) and debunker (fact-checker) in a completed debate.

Choose labels ONLY from these exact taxonomies for the primary outputs.

SPREADER strategies (pick the primary and any additional that apply):
{', '.join(spreader_labels)}

DEBUNKER strategies (pick the primary and any additional that apply):
{', '.join(debunker_labels)}

Rules:
- spreader_primary: exactly one label from the spreader list; the main strategy used.
- debunker_primary: exactly one label from the debunker list; the main strategy used.
- spreader_strategies: list of all applicable spreader labels (primary first).
- debunker_strategies: list of all applicable debunker labels (primary first).
- emergent_strategies: list of notable tactics observed that do NOT fit any taxonomy label above.
  Use short snake_case names (e.g. "gish_gallop", "appeal_to_tradition"). Max 5 entries total across both sides.
  Each entry: {{"side": "spreader"|"debunker", "label": "...", "description": "1-sentence explanation"}}.
  If nothing notable, use an empty list [].
- notes: optional 1-2 sentence summary (max 200 chars).

Return strict JSON only. No markdown fences. No extra text."""

    user_prompt = f"""CLAIM:
{claim}

TRANSCRIPT:
{formatted_transcript}

JUDGE VERDICT:
{json.dumps(verdict, indent=2)}

Return JSON: {{"spreader_primary": "...", "debunker_primary": "...", "spreader_strategies": [...], "debunker_strategies": [...], "emergent_strategies": [...], "notes": "..."}}"""

    try:
        response = client.chat.completions.create(
            model=STRATEGY_ANALYST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return _build_error_stub("Empty model response")
        raw = _extract_json_from_response(content)
        return _normalize_strategy_output(raw)
    except Exception as e:
        return _build_error_stub(str(e))


def analyze_per_turn_strategies(
    claim: str,
    transcript_turns: list[dict],
) -> list[dict]:
    """
    Analyze each turn pair individually, returning per-turn strategy labels.

    Returns a list of dicts, one per turn:
    [
        {
            "turn": 1,
            "spreader_strategies": ["emotional_appeal", "anecdotal_evidence"],
            "debunker_strategies": ["evidence_citation", "logical_refutation"],
            "spreader_adapted": false,  # true if tactics changed from previous turn
            "debunker_adapted": false,
        },
        ...
    ]

    Never raises — returns empty list on failure.
    """
    if not transcript_turns:
        return []

    try:
        from openai import OpenAI
        from arena.utils.openai_config import get_openai_api_key

        api_key = get_openai_api_key()
        if not api_key:
            return []
        client = OpenAI(api_key=api_key)
    except Exception:
        return []

    spreader_labels = get_spreader_strategy_labels()
    debunker_labels = get_debunker_strategy_labels()

    # Build turn pairs
    pairs = []
    for i, t in enumerate(transcript_turns):
        if "spreader_message" in t or "debunker_message" in t:
            s_msg = t.get("spreader_message") or {}
            d_msg = t.get("debunker_message") or {}
            s_text = s_msg.get("content", "") if isinstance(s_msg, dict) else str(s_msg or "")
            d_text = d_msg.get("content", "") if isinstance(d_msg, dict) else str(d_msg or "")
            pairs.append({"turn": i + 1, "spreader": s_text.strip(), "debunker": d_text.strip()})
        elif t.get("name") and t.get("content"):
            tidx = t.get("turn_index", i // 2)
            if t["name"] == "spreader":
                if not pairs or "spreader" in pairs[-1]:
                    pairs.append({"turn": tidx + 1, "spreader": "", "debunker": ""})
                pairs[-1]["spreader"] = t["content"].strip()
            else:
                if not pairs:
                    pairs.append({"turn": tidx + 1, "spreader": "", "debunker": ""})
                pairs[-1]["debunker"] = t["content"].strip()

    if not pairs:
        return []

    # Build the full transcript context for the LLM (it needs to see the whole debate
    # to understand adaptation, but we ask it to label each turn)
    transcript_text = ""
    for p in pairs:
        transcript_text += f"--- Turn {p['turn']} ---\n"
        transcript_text += f"[SPREADER]: {p['spreader'][:1000]}\n"
        transcript_text += f"[DEBUNKER]: {p['debunker'][:1000]}\n\n"

    system_prompt = f"""You are a debate strategy analyst. Analyze each turn of this debate individually.

For each turn, identify the strategies used by the spreader and debunker.
Also note whether each side ADAPTED their approach from the previous turn
(changed tactics, introduced new arguments, or shifted strategy in response to the opponent).

SPREADER strategy labels: {', '.join(spreader_labels)}
DEBUNKER strategy labels: {', '.join(debunker_labels)}

Return strict JSON only — an array with one object per turn:
[
  {{
    "turn": 1,
    "spreader_strategies": ["label1", "label2"],
    "debunker_strategies": ["label1", "label2"],
    "spreader_adapted": false,
    "debunker_adapted": false
  }},
  ...
]

For turn 1, adapted is always false (no previous turn to compare to).
JSON ONLY — no markdown, no explanation."""

    user_prompt = f"""CLAIM: {claim}

TRANSCRIPT:
{transcript_text}

Analyze each of the {len(pairs)} turns. Return a JSON array with {len(pairs)} objects."""

    try:
        response = client.chat.completions.create(
            model=STRATEGY_ANALYST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=200 * len(pairs),
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return []

        # Parse JSON array
        text = content
        if text.startswith("```"):
            import re
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        result = json.loads(text)
        if not isinstance(result, list):
            return []

        # Normalize labels
        spr_valid = set(spreader_labels)
        deb_valid = set(debunker_labels)
        normalized = []
        for entry in result:
            if not isinstance(entry, dict):
                continue
            spr_strats = [s for s in (entry.get("spreader_strategies") or []) if s in spr_valid]
            deb_strats = [s for s in (entry.get("debunker_strategies") or []) if s in deb_valid]
            normalized.append({
                "turn": entry.get("turn", len(normalized) + 1),
                "spreader_strategies": spr_strats,
                "debunker_strategies": deb_strats,
                "spreader_adapted": bool(entry.get("spreader_adapted", False)),
                "debunker_adapted": bool(entry.get("debunker_adapted", False)),
            })
        return normalized

    except Exception as e:
        print(f"[PER_TURN_STRATEGY] failed: {e}")
        return []
