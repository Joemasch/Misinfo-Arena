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
    Normalize raw analyst output for open-coding (v3).

    No taxonomy filtering — all labels are accepted. Normalization only:
    - snake_case formatting
    - deduplication
    - extract labels from strategy objects (which now have label + description)
    """
    def extract_labels(lst: list) -> list[str]:
        """Extract label strings from list of dicts or strings."""
        if not isinstance(lst, list):
            return []
        seen = set()
        out = []
        for x in lst:
            if isinstance(x, dict):
                label = str(x.get("label") or "").strip().lower().replace(" ", "_")
            elif isinstance(x, str):
                label = str(x).strip().lower().replace(" ", "_")
            else:
                continue
            if label and label not in seen:
                seen.add(label)
                out.append(label)
        return out[:7]  # Max 7 per side

    def extract_strategy_objects(lst: list) -> list[dict]:
        """Extract label + description objects."""
        if not isinstance(lst, list):
            return []
        out = []
        for x in lst:
            if isinstance(x, dict):
                label = str(x.get("label") or "").strip().lower().replace(" ", "_")
                desc = str(x.get("description") or "").strip()[:200]
                if label:
                    out.append({"label": label, "description": desc})
            elif isinstance(x, str):
                label = str(x).strip().lower().replace(" ", "_")
                if label:
                    out.append({"label": label, "description": ""})
        return out[:7]

    spreader_labels = extract_labels(raw.get("spreader_strategies") or [])
    debunker_labels = extract_labels(raw.get("debunker_strategies") or [])
    spreader_details = extract_strategy_objects(raw.get("spreader_strategies") or [])
    debunker_details = extract_strategy_objects(raw.get("debunker_strategies") or [])

    # Primary: accept any label, normalize to snake_case
    spreader_primary = None
    deb_primary = None
    sp_raw = raw.get("spreader_primary")
    dp_raw = raw.get("debunker_primary")
    if sp_raw:
        spreader_primary = str(sp_raw).strip().lower().replace(" ", "_")
    if dp_raw:
        deb_primary = str(dp_raw).strip().lower().replace(" ", "_")

    if not spreader_primary and spreader_labels:
        spreader_primary = spreader_labels[0]
    if not deb_primary and debunker_labels:
        deb_primary = debunker_labels[0]

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
        "debunker_primary": deb_primary,
        "spreader_strategies": spreader_labels,
        "debunker_strategies": debunker_labels,
        "spreader_strategy_details": spreader_details,
        "debunker_strategy_details": debunker_details,
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

    verdict = _judge_verdict_to_dict(judge_result)
    formatted_transcript = _format_transcript_for_analyst(transcript_turns)

    system_prompt = """You are a debate strategy analyst using an open-coding methodology (Grounded Theory, Glaser & Strauss 1967).

Your task: identify the rhetorical strategies ACTUALLY USED by each side in this debate. Do NOT use a predefined list — describe what you observe in the transcript.

Rules for generating labels:
- Use short snake_case labels (1-3 words max). Examples: "emotional_appeal", "source_citation", "personal_anecdote", "institutional_distrust", "data_reframing"
- Be CONSISTENT: if two behaviors are essentially the same tactic, use the same label
- Each strategy gets a one-sentence description explaining what the participant did
- Identify the single PRIMARY tactic (most dominant) for each side
- List ALL tactics observed (primary first, then others in order of prominence)
- Maximum 7 tactics per side
- Do not invent tactics that aren't in the transcript — only label what you actually observe

Return strict JSON only. No markdown fences. No extra text."""

    user_prompt = f"""CLAIM:
{claim}

TRANSCRIPT:
{formatted_transcript}

Return JSON:
{{
  "spreader_primary": "snake_case_label",
  "debunker_primary": "snake_case_label",
  "spreader_strategies": [{{"label": "...", "description": "..."}}, ...],
  "debunker_strategies": [{{"label": "...", "description": "..."}}, ...],
  "notes": "optional 1-2 sentence summary"
}}"""

    try:
        response = client.chat.completions.create(
            model=STRATEGY_ANALYST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
            response_format={"type": "json_object"},
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

    system_prompt = """You are a debate strategy analyst using open-coding methodology. Analyze each turn individually.

For each turn, identify the rhetorical strategies used by each side. Use short snake_case labels (1-3 words) that describe what you observe — do NOT use a predefined list.

Also note whether each side ADAPTED their approach from the previous turn (changed tactics, introduced new arguments, or shifted strategy in response to the opponent).

Be CONSISTENT with labels across turns — if the same tactic appears in turn 1 and turn 3, use the same label.

Return strict JSON only — a single object with a "turns" array containing one object per turn:
{
  "turns": [
    {
      "turn": 1,
      "spreader_strategies": ["label1", "label2"],
      "debunker_strategies": ["label1", "label2"],
      "spreader_adapted": false,
      "debunker_adapted": false
    },
    ...
  ]
}

For turn 1, adapted is always false.
JSON ONLY — no markdown, no explanation."""

    user_prompt = f"""CLAIM: {claim}

TRANSCRIPT:
{transcript_text}

Analyze each of the {len(pairs)} turns. Return a JSON object with a "turns" array containing {len(pairs)} objects."""

    try:
        response = client.chat.completions.create(
            model=STRATEGY_ANALYST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=max(400, 250 * len(pairs)),
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return []

        # Parse JSON object (fenced response also tolerated, just in case)
        text = content
        if text.startswith("```"):
            import re
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        parsed = json.loads(text)
        # Accept either {"turns": [...]} or a bare list (older format)
        if isinstance(parsed, dict):
            result = parsed.get("turns") or parsed.get("data") or []
        elif isinstance(parsed, list):
            result = parsed
        else:
            result = []
        if not isinstance(result, list):
            return []

        # Normalize labels — open coding, accept all labels
        normalized = []
        for entry in result:
            if not isinstance(entry, dict):
                continue
            spr_strats = [str(s).strip().lower().replace(" ", "_")
                         for s in (entry.get("spreader_strategies") or []) if s]
            deb_strats = [str(s).strip().lower().replace(" ", "_")
                         for s in (entry.get("debunker_strategies") or []) if s]
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
