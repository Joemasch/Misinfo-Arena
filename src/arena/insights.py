"""
AI-generated debate insights for the Misinformation Arena v2.

This module provides intelligent analysis of completed debates to help users
understand misinformation persuasion tactics and why corrections succeed or fail.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
import streamlit as st

from arena.types import DebateInsights, Message, Turn
from arena.agents import BaseAgent, AgentRole

# ===================================================================
# TARGET PERSONA FOR INSIGHTS
# ===================================================================
# Strategic observer learning how misinformation persuasion works
TARGET_PERSONA = """You are an expert analyst helping non-technical but curious users understand misinformation debates. Focus on:
- Persuasive tactics used by each side
- Why the outcome occurred (causality)
- Turning points and strategic decisions
- What could realistically have changed the result
- Patterns in misinformation vs. correction approaches

Keep explanations accessible, interpretive, and focused on learning outcomes."""


class InsightsAgent(BaseAgent):
    """
    AI agent that generates strategic insights for completed debates.

    Produces persona-driven analysis of misinformation persuasion tactics,
    focusing on learning outcomes for users studying debate dynamics.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3, max_tokens: int = 700):
        """Initialize the insights agent."""
        super().__init__(AgentRole.DEBUNKER, "Insights Analyzer")  # Role doesn't matter for insights

        # Check for OpenAI client availability
        self.client = None
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Try to get OpenAI client
        try:
            from openai import OpenAI
            from arena.utils.openai_config import get_openai_api_key

            api_key = get_openai_api_key()
            if api_key:
                self.client = OpenAI(api_key=api_key)
            else:
                if st.session_state.get("DEV_MODE"):
                    print("INSIGHTS_AGENT: No OpenAI API key available - insights will be skipped")

        except ImportError:
            if st.session_state.get("DEV_MODE"):
                print("INSIGHTS_AGENT: OpenAI library not available - insights will be skipped")

    def is_available(self) -> bool:
        """Check if the insights agent can generate insights."""
        return self.client is not None

    def generate_insights(self, claim: str, transcript: List[Dict], judge_verdict: Dict[str, Any], diagnostics: Optional[Dict] = None) -> Optional[DebateInsights]:
        """
        Generate strategic insights for a completed debate.

        Args:
            claim: The debate claim text
            transcript: List of message dicts with turn_index, role, name, content
            judge_verdict: Judge decision dict (should be JSON-serializable)
            diagnostics: Optional diagnostics dict to populate

        Returns:
            DebateInsights object or raises exception if generation fails
        """
        # Ensure diagnostics is always a dict for safe mutation
        if diagnostics is None:
            diagnostics = {}

        if not self.is_available():
            diagnostics["llm_call_attempted"] = False
            diagnostics["returned_none_reason"] = "client not available"
            diagnostics["client_present"] = False
            raise RuntimeError("OpenAI client not available - check API key configuration")

        # Ensure judge_verdict is JSON-serializable
        if hasattr(judge_verdict, '__dict__'):
            judge_verdict = vars(judge_verdict)
        elif hasattr(judge_verdict, 'model_dump'):
            judge_verdict = judge_verdict.model_dump()
        # If it's already serializable, leave it as-is

        diagnostics["llm_call_attempted"] = True
        diagnostics["summary_model"] = self.model
        diagnostics["temperature"] = self.temperature
        diagnostics["max_tokens"] = self.max_tokens
        diagnostics["client_type"] = type(self.client).__name__
        diagnostics["client_present"] = True
        diagnostics["api_key_present"] = hasattr(self.client, '_api_key') and self.client._api_key is not None

        try:
            # Format transcript for the LLM
            formatted_transcript = self._format_transcript(transcript)

            diagnostics["transcript_formatted_len"] = len(formatted_transcript)

            # Build the prompt with persona-aligned rubric
            system_prompt = """You write "Debate Insights" for a curious, non-technical user learning how misinformation persuasion works.
Your goal is to explain strategy and causality, not to recap the transcript.
You must remain neutral and educational; do not endorse misinformation.
Write clearly and concisely with concrete, debate-specific details.

Output format rules:
- Output VALID JSON ONLY. No markdown. No extra keys.
- Write 3-5 short paragraphs total, each 3-5 sentences minimum (except TL;DR).
- Total output ~250-350 words.
- Avoid quoting the transcript; paraphrase specific actions and tactics.
- Use at least THREE tactic labels from the provided vocabulary in "strategic_dynamics".
- Every paragraph must contain at least one concrete debate-specific detail.
- Do not write generic statements like "emotional appeal vs science" unless you name at least two additional tactics and describe how they appeared in this specific debate."""

            user_prompt = f"""Return JSON matching this schema exactly:
{{
  "title": "Debate Insights",
  "tldr": "...",
  "core_conflict": "...",
  "strategic_dynamics": "...",
  "outcome_driver": "...",
  "counterfactual": "...",
  "pattern_note": "... (optional)",
  "turning_points_explained": "...",
  "key_turns": [1,2,3],
  "generated_at": "ISO-8601 string",
  "model": "model name"
}}

Tactic vocabulary (use labels verbatim when relevant):
emotional appeal; moral framing; anecdotal evidence; uncertainty amplification; authority/credibility attack;
conspiracy framing; shifting burden of proof; cherry-picking; mechanistic explanation; source citation;
empathy + reframing; narrowing the claim / falsifiability request.

Task:
Write concise, strategy-focused insights that help the user understand what happened and why.

Constraints (strict):
- 250-350 words total.
- Each paragraph field: 3-5 sentences minimum (except TL;DR which is 1 sentence).
- No bullet lists.
- Do not quote the transcript; paraphrase concrete actions (e.g., "the spreader leaned on parental anecdotes and motive questioning").
- Mention at least THREE tactic labels in strategic_dynamics from the vocabulary above.
- Every section must contain at least one concrete debate-specific detail.
- outcome_driver must reference at least TWO judge criteria (evidence quality, correctness, clarity, persuasiveness) and explicitly connect them to what happened in the debate.
- turning_points_explained: 1-2 sentences explaining why each key turn mattered, referencing the specific key_turns list.
- counterfactual must include BOTH parts clearly separated:
  (a) how the spreader could have been more persuasive (without endorsing misinformation; focus on specificity, falsifiability, credible sourcing)
  (b) how the debunker could have been more effective (empathy, clarity, narrowing the claim, better citations, mechanistic explanations)

Inputs:
CLAIM:
{claim}

TRANSCRIPT (numbered turns):
{formatted_transcript}

JUDGE VERDICT (JSON-safe):
{json.dumps(judge_verdict, indent=2)}"""

            diagnostics["system_prompt_len"] = len(system_prompt)
            diagnostics["user_prompt_len"] = len(user_prompt)

            # Make the API call with rate limit retry
            import time
            max_attempts = 3
            base_delay = 1.0  # seconds

            diagnostics["rate_limit_max_attempts"] = max_attempts
            diagnostics["rate_limit_base_delay"] = base_delay

            response = None
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    diagnostics[f"llm_call_attempt_{attempt + 1}_started"] = datetime.now().isoformat()

                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )

                    diagnostics[f"llm_call_attempt_{attempt + 1}_completed"] = datetime.now().isoformat()
                    diagnostics["rate_limit_success_attempt"] = attempt + 1

                    break  # Success, exit retry loop

                except Exception as e:
                    last_exception = e

                    # Check if it's a rate limit error
                    is_rate_limit = "rate limit" in str(e).lower() or "RateLimitError" in str(type(e))

                    diagnostics[f"llm_call_attempt_{attempt + 1}_exception"] = f"{type(e).__name__}: {str(e)}"
                    diagnostics[f"llm_call_attempt_{attempt + 1}_is_rate_limit"] = is_rate_limit

                    if attempt < max_attempts - 1 and is_rate_limit:
                        # Exponential backoff for rate limits
                        delay = base_delay * (2 ** attempt)
                        diagnostics[f"rate_limit_retry_delay_{attempt + 1}"] = delay
                        time.sleep(delay)
                        continue
                    else:
                        # Not a rate limit or final attempt, re-raise
                        raise e

            if not response:
                # All attempts failed
                diagnostics["rate_limit_all_attempts_failed"] = True
                diagnostics["rate_limit_final_exception"] = f"{type(last_exception).__name__}: {str(last_exception)}"
                raise RuntimeError(f"Rate limit exceeded after {max_attempts} attempts. Last error: {last_exception}") from last_exception

            diagnostics["llm_call_completed"] = datetime.now().isoformat()

            # Extract and validate JSON
            content = response.choices[0].message.content
            if content:
                content = content.strip()

            diagnostics["llm_raw_text_len"] = len(content) if content else 0
            diagnostics["llm_raw_text_preview"] = content[:800] if content else ""

            if not content:
                raise RuntimeError("OpenAI API returned empty response")

            # Try to parse JSON
            try:
                insights_data = json.loads(content)

                diagnostics["json_parse_ok"] = True
                diagnostics["parsed_fields"] = list(insights_data.keys())

                # HARD VALIDATION: Required fields (must pass or fail)
                required_fields = ["tldr", "core_conflict", "strategic_dynamics", "outcome_driver", "counterfactual", "key_turns"]
                missing_fields = []
                for field in required_fields:
                    if field not in insights_data:
                        missing_fields.append(field)

                if missing_fields:
                    diagnostics["schema_validate_ok"] = False
                    diagnostics["schema_validate_error"] = f"Missing required fields: {missing_fields}"
                    raise ValueError(f"Missing required fields: {missing_fields}")

                diagnostics["schema_validate_ok"] = True

                # SOFT VALIDATION: Content quality (warnings, but still proceed)
                quality_warnings = []

                # Check strategic_dynamics has at least 3 tactic labels
                strategic_text = insights_data.get("strategic_dynamics", "").lower()
                tactic_vocabulary = [
                    "emotional appeal", "moral framing", "anecdotal evidence", "uncertainty amplification",
                    "authority/credibility attack", "conspiracy framing", "shifting burden of proof",
                    "cherry-picking", "mechanistic explanation", "source citation",
                    "empathy + reframing", "narrowing the claim / falsifiability request"
                ]
                tactic_count = sum(1 for tactic in tactic_vocabulary if tactic in strategic_text)
                if tactic_count < 3:
                    quality_warnings.append(f"Only {tactic_count} tactic labels found in strategic_dynamics (recommended: at least 3)")

                # Check turning_points_explained references key turns (more robust regex)
                key_turns = insights_data.get("key_turns", [])
                turning_explained = insights_data.get("turning_points_explained", "")
                if not turning_explained:
                    quality_warnings.append("turning_points_explained is empty")
                else:
                    # Check if explanation mentions at least one of the key turns using word boundaries
                    mentioned_turns = []
                    import re
                    for turn in key_turns:
                        # Match "turn 1", "turn1", or just "1" as a word
                        if re.search(rf"\b{turn}\b", turning_explained.lower()) or \
                           re.search(rf"\bturn {turn}\b", turning_explained.lower()) or \
                           re.search(rf"\bturn{turn}\b", turning_explained.lower()):
                            mentioned_turns.append(turn)
                    if not mentioned_turns:
                        quality_warnings.append(f"turning_points_explained does not mention any of the key_turns {key_turns}")

                # Store quality warnings in diagnostics
                diagnostics["content_validate_warnings"] = quality_warnings
                diagnostics["tactic_count_found"] = tactic_count

                # Create and return the insights object with quality warnings (SOFT validation never blocks)
                insights_obj = DebateInsights(
                    title=insights_data.get("title", "Debate Insights"),
                    tldr=insights_data["tldr"],
                    core_conflict=insights_data["core_conflict"],
                    strategic_dynamics=insights_data["strategic_dynamics"],
                    outcome_driver=insights_data["outcome_driver"],
                    counterfactual=insights_data["counterfactual"],
                    pattern_note=insights_data.get("pattern_note"),
                    turning_points_explained=insights_data.get("turning_points_explained", ""),
                    key_turns=insights_data["key_turns"],
                    generated_at=datetime.now().isoformat(),
                    model=self.model,
                    quality_warnings=quality_warnings  # Include SOFT validation warnings
                )

                diagnostics["insights_created"] = True
                diagnostics["returned_valid_object"] = True
                diagnostics["quality_warnings_count"] = len(quality_warnings)

                # SUCCESS: Return immediately (SOFT validation never blocks)
                return insights_obj

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                diagnostics["json_parse_ok"] = False
                diagnostics["json_parse_error"] = str(e)

                # HARD validation failure - attempt repair once
                if st.session_state.get("DEV_MODE"):
                    print(f"INSIGHTS_ERROR: HARD validation failed (JSON/schema): {str(e)}")
                    print(f"INSIGHTS_ERROR: Raw response: {content[:200]}...")

                diagnostics["repair_attempted"] = True

                # Attempt repair with rate limit retry
                repair_response = None
                repair_last_exception = None

                for repair_attempt in range(max_attempts):
                    try:
                        diagnostics[f"repair_llm_call_attempt_{repair_attempt + 1}_started"] = datetime.now().isoformat()

                        repair_response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                                {"role": "assistant", "content": content},  # Previous invalid response
                                {"role": "user", "content": "Your previous output was invalid or did not meet quality requirements. Output VALID JSON ONLY matching the schema exactly. Include at least 3 tactic labels in strategic_dynamics from the vocabulary provided. Explain turning points in turning_points_explained, referencing the key_turns list. No markdown. No extra keys. Keep 250-350 words total."}
                            ],
                            temperature=self.temperature,
                            max_tokens=self.max_tokens
                        )

                        diagnostics[f"repair_llm_call_attempt_{repair_attempt + 1}_completed"] = datetime.now().isoformat()
                        diagnostics["repair_rate_limit_success_attempt"] = repair_attempt + 1

                        break  # Success, exit retry loop

                    except Exception as e:
                        repair_last_exception = e

                        # Check if it's a rate limit error
                        is_rate_limit = "rate limit" in str(e).lower() or "RateLimitError" in str(type(e))

                        diagnostics[f"repair_llm_call_attempt_{repair_attempt + 1}_exception"] = f"{type(e).__name__}: {str(e)}"
                        diagnostics[f"repair_llm_call_attempt_{repair_attempt + 1}_is_rate_limit"] = is_rate_limit

                        if repair_attempt < max_attempts - 1 and is_rate_limit:
                            # Exponential backoff for rate limits
                            delay = base_delay * (2 ** repair_attempt)
                            diagnostics[f"repair_rate_limit_retry_delay_{repair_attempt + 1}"] = delay
                            time.sleep(delay)
                            continue
                        else:
                            # Not a rate limit or final attempt, re-raise
                            raise e

                if not repair_response:
                    # All repair attempts failed
                    diagnostics["repair_rate_limit_all_attempts_failed"] = True
                    diagnostics["repair_rate_limit_final_exception"] = f"{type(repair_last_exception).__name__}: {str(repair_last_exception)}"
                    raise RuntimeError(f"Rate limit exceeded during repair after {max_attempts} attempts. Last error: {repair_last_exception}") from repair_last_exception

                repair_content = repair_response.choices[0].message.content
                if repair_content:
                    repair_content = repair_content.strip()

                diagnostics["repair_raw_text_len"] = len(repair_content) if repair_content else 0
                diagnostics["repair_raw_text_preview"] = repair_content[:800] if repair_content else ""

                if not repair_content:
                    raise RuntimeError("OpenAI API repair call returned empty response")

                try:
                    insights_data = json.loads(repair_content)

                    diagnostics["repair_json_parse_ok"] = True

                    # HARD VALIDATION for repair: Required fields only
                    missing_fields = []
                    for field in required_fields:
                        if field not in insights_data:
                            missing_fields.append(field)

                    if missing_fields:
                        diagnostics["repair_schema_validate_ok"] = False
                        diagnostics["repair_schema_validate_error"] = f"Repair also missing fields: {missing_fields}"
                        raise ValueError(f"Repair response missing required fields: {missing_fields}")

                    diagnostics["repair_schema_validate_ok"] = True

                    # SOFT VALIDATION for repair: Content quality (warnings, but still proceed)
                    repair_quality_warnings = []

                    # Check strategic_dynamics has at least 3 tactic labels
                    repair_strategic_text = insights_data.get("strategic_dynamics", "").lower()
                    repair_tactic_count = sum(1 for tactic in tactic_vocabulary if tactic in repair_strategic_text)
                    if repair_tactic_count < 3:
                        repair_quality_warnings.append(f"Repair: Only {repair_tactic_count} tactic labels found in strategic_dynamics (recommended: at least 3)")

                    # Check turning_points_explained references key turns (more robust regex)
                    repair_key_turns = insights_data.get("key_turns", [])
                    repair_turning_explained = insights_data.get("turning_points_explained", "")
                    if not repair_turning_explained:
                        repair_quality_warnings.append("Repair: turning_points_explained is empty")
                    else:
                        # Check if explanation mentions at least one of the key turns using word boundaries
                        repair_mentioned_turns = []
                        import re
                        for turn in repair_key_turns:
                            if re.search(rf"\b{turn}\b", repair_turning_explained.lower()) or \
                               re.search(rf"\bturn {turn}\b", repair_turning_explained.lower()) or \
                               re.search(rf"\bturn{turn}\b", repair_turning_explained.lower()):
                                repair_mentioned_turns.append(turn)
                        if not repair_mentioned_turns:
                            repair_quality_warnings.append(f"Repair: turning_points_explained does not mention any of the key_turns {repair_key_turns}")

                    # Store repair quality warnings in diagnostics
                    diagnostics["repair_content_validate_warnings"] = repair_quality_warnings
                    diagnostics["repair_tactic_count_found"] = repair_tactic_count

                    # Create insights object with repair quality warnings
                    insights_obj = DebateInsights(
                        title=insights_data.get("title", "Debate Insights"),
                        tldr=insights_data["tldr"],
                        core_conflict=insights_data["core_conflict"],
                        strategic_dynamics=insights_data["strategic_dynamics"],
                        outcome_driver=insights_data["outcome_driver"],
                        counterfactual=insights_data["counterfactual"],
                        pattern_note=insights_data.get("pattern_note"),
                        turning_points_explained=insights_data.get("turning_points_explained", ""),
                        key_turns=insights_data["key_turns"],
                        generated_at=datetime.now().isoformat(),
                        model=self.model,
                        quality_warnings=repair_quality_warnings  # Include repair SOFT validation warnings
                    )

                    diagnostics["insights_created_via_repair"] = True
                    diagnostics["repair_quality_warnings_count"] = len(repair_quality_warnings)

                    return insights_obj

                except Exception as repair_error:
                    diagnostics["repair_json_parse_ok"] = False
                    diagnostics["repair_parse_error"] = str(repair_error)
                    diagnostics["returned_none_reason"] = f"Both initial and repair parsing failed: {str(repair_error)}"
                    raise RuntimeError(f"Both initial and repair JSON parsing failed: {str(repair_error)}")

        except Exception as e:
            diagnostics["llm_call_exception"] = f"{type(e).__name__}: {str(e)}"
            diagnostics["returned_none_reason"] = f"Exception during generation: {str(e)}"
            raise RuntimeError(f"Insights generation failed: {str(e)}") from e

    def _format_transcript(self, transcript: List[Dict]) -> str:
        """Format transcript for the LLM prompt."""
        formatted_lines = []

        # Group by turns
        turns = {}
        for msg in transcript:
            turn_idx = msg.get("turn_index", 0) + 1  # Convert to 1-based for display
            if turn_idx not in turns:
                turns[turn_idx] = []
            turns[turn_idx].append(msg)

        # Format each turn
        for turn_idx in sorted(turns.keys()):
            messages = turns[turn_idx]
            for msg in messages:
                role = msg.get("name", "Unknown").title()
                content = msg.get("content", "").strip()
                if content:
                    formatted_lines.append(f"Turn {turn_idx} ({role}): {content}")

        return "\n".join(formatted_lines)


# Global insights agent instance
_insights_agent = None

def get_insights_agent() -> InsightsAgent:
    """Get or create the global insights agent instance."""
    global _insights_agent
    if _insights_agent is None:
        _insights_agent = InsightsAgent()
    return _insights_agent
