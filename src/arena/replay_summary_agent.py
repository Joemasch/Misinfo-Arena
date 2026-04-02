"""
ReplaySummaryAgent: generates "Strategic Observer Insight" summaries for the
Episode Replay tab. Causal persuasion insight only; not a recap.
Isolated from Arena flow; used only by Replay UI with session-state cache.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class ReplaySummary:
    full_text: str
    model: str
    version: str
    generated_at: str
    quality_warnings: list[str]


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse a JSON object from model output. Tolerates markdown fences and surrounding text."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("No JSON object found in response")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Replay summary JSON parse failed: {e}") from e


def _format_transcript(transcript: list[dict]) -> str:
    """Format transcript for the LLM prompt."""
    lines = []
    turns: dict[int, list[dict]] = {}
    for msg in transcript:
        idx = msg.get("turn_index", 0)
        if idx not in turns:
            turns[idx] = []
        turns[idx].append(msg)
    for idx in sorted(turns.keys()):
        for msg in turns[idx]:
            name = (msg.get("name") or "Unknown").title()
            content = (msg.get("content") or "").strip()
            if content:
                lines.append(f"Turn {idx + 1} ({name}): {content}")
    return "\n".join(lines)


class ReplaySummaryAgent:
    """
    Generates strategic observer summaries for a single episode.
    Optimized for causal persuasion insight; grounded in transcript + judge verdict.
    """

    VERSION = "replay_summary_v1"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 900,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        self._timeout_kwarg_supported: str | None = None  # "timeout", "request_timeout", or "none"
        try:
            from openai import OpenAI
            from arena.utils.openai_config import get_openai_api_key

            api_key = get_openai_api_key()
            if api_key:
                self.client = OpenAI(api_key=api_key)
        except (ImportError, Exception):
            pass

    def generate(
        self,
        claim: str,
        transcript: list[dict],
        judge_verdict: dict[str, Any],
    ) -> ReplaySummary:
        """
        Generate a strategic observer summary. Raises on parse failure or if client unavailable.
        """
        if not self.client:
            raise RuntimeError("OpenAI client not available - check API key configuration")

        verdict = judge_verdict
        if hasattr(verdict, "__dict__"):
            verdict = vars(verdict)
        elif hasattr(verdict, "model_dump"):
            verdict = verdict.model_dump()

        formatted_transcript = _format_transcript(transcript)
        system_prompt = self._system_prompt()
        user_prompt = f"""CLAIM:
{claim}

TRANSCRIPT:
{formatted_transcript}

JUDGE VERDICT (JSON):
{json.dumps(verdict, indent=2)}

Return strict JSON only, no markdown:
{{ "full_text": "<3–5 paragraphs, 250–350 words>", "quality_warnings": ["...optional..."] }}"""

        response = self._call_llm(system_prompt, user_prompt)
        content = (response.choices[0].message.content or "").strip()
        data = self._parse_response(content)
        full_text = data.get("full_text") or ""
        quality_warnings = list(data.get("quality_warnings") or [])

        self._add_validation_warnings(full_text, quality_warnings)
        generated_at = datetime.now(timezone.utc).isoformat()
        return ReplaySummary(
            full_text=full_text,
            model=self.model,
            version=self.VERSION,
            generated_at=generated_at,
            quality_warnings=quality_warnings,
        )

    def _system_prompt(self) -> str:
        return """You are a research assistant analyzing persuasion dynamics in a misinformation vs correction debate.

Audience: A "strategic observer" learning how misinformation persuades and why corrections succeed or fail.

Your output MUST:
- Be 3–5 paragraphs, each 3–5 sentences max; total 250–350 words.
- Use NO bullet lists, no headings, no numbered lists.
- NOT be a recap or play-by-play of the debate.

You MUST address these four points (in flowing prose):
1) What persuasive tactics did the spreader use?
2) What counter-strategy did the debunker use?
3) Why did the outcome happen behaviorally (persuasion, cognition, rhetoric)?
4) How do the judge metrics qualitatively reflect those dynamics? Interpret them in human terms; do not dump raw numbers.

Grounding:
- Ground every statement in the provided transcript and judge verdict.
- Use phrases like "the spreader framed…" / "the debunker relied on…".
- Do not introduce new medical or factual claims beyond the transcript.
- Do not give medical advice; focus on rhetoric and reasoning patterns.

Output strict JSON only: { "full_text": "<your 3–5 paragraphs>", "quality_warnings": [] }."""

    def _call_llm(self, system_prompt: str, user_prompt: str):  # noqa: ANN201
        base_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        timeout_candidates = [("timeout", 60.0), ("request_timeout", 60.0), (None, None)]
        if self._timeout_kwarg_supported is not None:
            if self._timeout_kwarg_supported == "timeout":
                timeout_candidates = [("timeout", 60.0), ("request_timeout", 60.0), (None, None)]
            elif self._timeout_kwarg_supported == "request_timeout":
                timeout_candidates = [("request_timeout", 60.0), ("timeout", 60.0), (None, None)]
            else:
                timeout_candidates = [(None, None), ("timeout", 60.0), ("request_timeout", 60.0)]

        max_attempts = 3
        base_delay = 1.0
        last_exception = None
        for attempt in range(max_attempts):
            try:
                last_type_error = None
                for name, val in timeout_candidates:
                    kwargs = dict(base_kwargs)
                    if name is not None:
                        kwargs[name] = val
                    try:
                        response = self.client.chat.completions.create(**kwargs)
                        if self._timeout_kwarg_supported is None:
                            self._timeout_kwarg_supported = name if name else "none"
                        return response
                    except TypeError as e:
                        msg = str(e)
                        if name is not None and "unexpected keyword argument" in msg and name in msg:
                            last_type_error = e
                            continue
                        raise
                if last_type_error is not None:
                    raise last_type_error
                raise RuntimeError("OpenAI create() failed with incompatible timeout kwargs")
            except Exception as e:
                last_exception = e
                is_rate_limit = "rate limit" in str(e).lower() or "RateLimitError" in str(type(e))
                if attempt < max_attempts - 1 and is_rate_limit:
                    time.sleep(base_delay * (2**attempt))
                    continue
                raise e
        raise RuntimeError(f"Rate limit exceeded after {max_attempts} attempts: {last_exception}") from last_exception

    def _parse_response(self, content: str) -> dict[str, Any]:
        data = _extract_json(content.strip())
        if not isinstance(data, dict):
            raise RuntimeError("Replay summary response is not a JSON object")
        return data

    def _add_validation_warnings(self, full_text: str, quality_warnings: list[str]) -> None:
        words = len(full_text.split())
        if words < 230:
            quality_warnings.append(f"word_count_low ({words} < 230)")
        elif words > 380:
            quality_warnings.append(f"word_count_high ({words} > 380)")
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        if paragraphs and (len(paragraphs) < 3 or len(paragraphs) > 5):
            quality_warnings.append(f"paragraph_count ({len(paragraphs)}, expected 3–5)")
        for i, para in enumerate(paragraphs):
            sentences = re.split(r"[.?!]+", para)
            sentences = [s.strip() for s in sentences if s.strip()]
            if sentences and (len(sentences) < 3 or len(sentences) > 6):
                quality_warnings.append(f"paragraph_{i + 1}_sentences ({len(sentences)}, expected 3–6)")


_replay_summary_agent: ReplaySummaryAgent | None = None


def get_replay_summary_agent() -> ReplaySummaryAgent:
    """Get or create the global ReplaySummaryAgent instance."""
    global _replay_summary_agent
    if _replay_summary_agent is None:
        _replay_summary_agent = ReplaySummaryAgent()
    return _replay_summary_agent
