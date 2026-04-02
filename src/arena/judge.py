"""
Judge module for evaluating debate outcomes in Misinformation Arena v2.

This module implements a heuristic-based judge that evaluates debate quality
across multiple dimensions using simple regex patterns and rule-based scoring.
The judge analyzes debate transcripts to determine winners based on argument quality.

WHY HEURISTIC JUDGE?
- No LLM dependency: Works without OpenAI API keys
- Fast and deterministic: Consistent results for testing
- Interpretable: Clear rules explain scoring decisions
- Research-ready: Provides structured evaluation metrics
"""

import re
import math
import json
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from arena.types import Message, MetricScore, JudgeDecision
from arena.judge_base import BaseJudge


@dataclass
class Turn:
    """
    Represents one complete exchange in the debate.

    A turn consists of exactly one message from the spreader followed by
    exactly one message from the debunker. This is the fundamental unit
    of debate progression.
    """
    turn_id: int               # Sequential turn ID (1-based for display)
    spreader_message: Message   # Message from the misinformation spreader
    debunker_message: Message   # Message from the fact-checker debunker
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class HeuristicJudge(BaseJudge):
    """
    Evaluates the outcome of a completed debate match using heuristic scoring.

    The judge analyzes debate transcripts across six key dimensions:
    - truthfulness_proxy: Evidence reference and factual consistency
    - evidence_quality: Citations, specificity, and factual grounding
    - reasoning_quality: Logical structure and fallacy avoidance
    - responsiveness: Addressing opponent's arguments directly
    - persuasion: Rhetorical strength and argumentative skill
    - civility: Professional discourse and avoidance of attacks

    Uses regex patterns and rule-based heuristics for automated evaluation.
    """

    # Default weights for scoring dimensions (equal, per Wachsmuth 2017)
    DEFAULT_WEIGHTS = {
        "factuality": 0.167,            # D2D: factual grounding / narrative consistency
        "source_credibility": 0.167,    # D2D: source reliability
        "reasoning_quality": 0.167,     # Wachsmuth: cogency
        "responsiveness": 0.167,        # Wachsmuth: reasonableness
        "persuasion": 0.167,            # Wachsmuth: effectiveness
        "manipulation_awareness": 0.167, # Inoculation theory
    }

    # Backward compatibility: map old metric names to new
    _METRIC_ALIASES = {
        "truthfulness_proxy": "factuality",
        "evidence_quality": "source_credibility",
        "civility": "manipulation_awareness",
    }

    @property
    def judge_type(self) -> str:
        """Return the judge type identifier."""
        return "heuristic"

    def __init__(self, weights: Dict[str, float] | None = None):
        """
        Initialize judge with scoring weights.

        Args:
            weights: Custom weights for metrics, uses defaults if None
        """
        self.weights = weights if weights else HeuristicJudge.DEFAULT_WEIGHTS.copy()

        # ===================================================================
        # SCORING PATTERNS - Simple regex rules for each metric
        # ===================================================================

        # EVIDENCE QUALITY: Reward factual grounding indicators
        self.evidence_patterns = [
            re.compile(r'\baccording to|research shows|citation|source\b', re.IGNORECASE),
            re.compile(r'https?://[^\s]+'),  # URLs
            re.compile(r'\b\d{2,}\b'),       # Numbers (2+ digits)
            re.compile(r'\b(19|20)\d{2}\b'), # Years
            re.compile(r'\[\d+\]|\(source\)'), # Citation markers
        ]

        # CIVILITY: Penalize insults and attacks
        self.civility_penalties = [
            re.compile(r'\b(idiot|moron|stupid|dumb|fool|sheeple|brainwashed)\b', re.IGNORECASE),
            re.compile(r'\byou.*\b(are|is)\b.*\bwrong|stupid\b', re.IGNORECASE),
        ]

        # REASONING QUALITY: Penalize overconfidence and fallacies
        self.reasoning_penalties = [
            re.compile(r'\beveryone knows|wake up|obviously|clearly\b', re.IGNORECASE),
            re.compile(r'\bno proof needed|trust me|believe me\b', re.IGNORECASE),
        ]

        # RESPONSIVENESS: Reward engagement with opponent
        self.responsiveness_indicators = [
            re.compile(r'\byou said|you claim|your argument|you argue|you suggest\b', re.IGNORECASE),
            re.compile(r'\bbut|however|although|despite|in contrast\b', re.IGNORECASE),
            re.compile(r'\bthis claim|that claim|this argument|counter\b', re.IGNORECASE),
        ]

        # PERSUASION: Reward structured argumentation (role-neutral)
        # Includes both academic connectors (debunker style) AND rhetorical
        # narrative markers that the IME507 spreader uses.
        self.persuasion_indicators = [
            re.compile(r'\btherefore|thus|hence|consequently\b', re.IGNORECASE),
            re.compile(r'\bfirst|second|third|finally|in conclusion\b', re.IGNORECASE),
            re.compile(r'\bthe key point|most importantly|critically\b', re.IGNORECASE),
            # IME507 spreader rhetorical markers
            re.compile(r'\bfollow the money|they don.t want|media won.t|cover.?up\b', re.IGNORECASE),
            re.compile(r'\breal patriots|people who care|wake up and\b', re.IGNORECASE),
            re.compile(r'\bfact.?checkers|establishment|mainstream media\b', re.IGNORECASE),
        ]

        # TRUTHFULNESS PROXY: Penalize internal contradiction, not rhetorical style.
        # Absolutist language like "always/never" is part of the spreader's toolkit
        # (per IME507); penalizing it structurally biases the judge against the spreader.
        # Only penalize genuine logical contradictions detectable by pattern.
        self.truthfulness_penalties = [
            re.compile(r'\bno doubt|undeniably|facts prove\b', re.IGNORECASE),
            re.compile(r'\bI never said.*but I said\b', re.IGNORECASE),
        ]

        # EVIDENCE: Spreader-style evidence markers (fake expert appeals, anecdote)
        # These are valid rhetorical moves per IME507 and should score on evidence_quality.
        self.spreader_evidence_patterns = [
            re.compile(r'\bscientists? (in|at|from)\b', re.IGNORECASE),
            re.compile(r'\ba doctor who|experts? say|studies? (have|show|found)\b', re.IGNORECASE),
            re.compile(r'\bmy (neighbor|friend|family|doctor)\b', re.IGNORECASE),
            re.compile(r'\bthousands of (people|patients|cases)\b', re.IGNORECASE),
        ]

    def evaluate(self, turns: List[Dict]) -> JudgeDecision:
        """
        Evaluate debate turns and return judge decision.

        WHY THIS INTERFACE?
        - Simple list of turn dictionaries (easy to call from app)
        - No MatchConfig dependency (uses internal default weights)
        - Returns complete JudgeDecision with all evaluation data

        Args:
            turns: List of turn dicts with 'spreader_message' and 'debunker_message'

        Returns:
            Complete judge decision with winner, confidence, and scorecard
        """
        if not turns:
            return JudgeDecision(
                winner="draw",
                confidence=0.0,
                reason="No debate content to evaluate",
                totals={"spreader": 0.0, "debunker": 0.0},
                scorecard=self._error_scorecard()
            )

        # Extract messages for each side
        spreader_texts = [turn['spreader_message']['content'] for turn in turns]
        debunker_texts = [turn['debunker_message']['content'] for turn in turns]

        # Score each metric for both sides
        scorecard = []
        spreader_total = 0.0
        debunker_total = 0.0

        for metric_name in self.weights.keys():
            spreader_score = self._score_metric(metric_name, spreader_texts, debunker_texts, is_spreader=True)
            debunker_score = self._score_metric(metric_name, debunker_texts, spreader_texts, is_spreader=False)

            weight = self.weights[metric_name]
            spreader_total += spreader_score * weight
            debunker_total += debunker_score * weight

            scorecard.append(MetricScore(
                metric=metric_name,
                spreader=spreader_score,
                debunker=debunker_score,
                weight=weight
            ))

        # Determine winner and confidence
        winner, confidence = self._calculate_winner_and_confidence(spreader_total, debunker_total)

        # Generate reasoning
        reason = self._generate_reason(winner, scorecard)

        return JudgeDecision(
            winner=winner,
            confidence=confidence,
            reason=reason,
            totals={"spreader": spreader_total, "debunker": debunker_total},
            scorecard=scorecard
        )

    def _extract_messages(self, turns: List[Turn], is_spreader: bool) -> List[Message]:
        """
        Extract all messages from one side of the debate.

        WHY MESSAGE OBJECTS INSTEAD OF STRINGS?
        - Citations data is preserved for evidence quality evaluation
        - Judge can evaluate both text content and structured citations
        - Enables future citation-based scoring enhancements
        - Maintains rich message metadata for analysis

        Args:
            turns: All debate turns
            is_spreader: True to get spreader messages, False for debunker

        Returns:
            List of Message objects (with content and citations)
        """
        messages = []
        for turn in turns:
            if is_spreader:
                messages.append(turn.spreader_message)
            else:
                messages.append(turn.debunker_message)
        return messages

    def _score_metric(self, metric: str, own_texts: List[str], opponent_texts: List[str], is_spreader: bool) -> float:  # noqa: ARG002
        """
        Score a single metric for one participant.

        WHY INDIVIDUAL METRIC SCORING?
        - Modular evaluation allows easy testing and debugging
        - Each metric uses simple, interpretable heuristics
        - Enables detailed scorecard for research analysis

        Args:
            metric: Name of metric to score
            own_texts: Texts from the participant being scored
            opponent_texts: Texts from their opponent
            is_spreader: Whether scoring spreader (affects baseline)

        Returns:
            Score from 0-10 for this metric
        """
        combined_text = ' '.join(own_texts)

        if metric == "evidence_quality":
            return self._score_evidence_quality(combined_text, is_spreader=is_spreader)
        elif metric == "civility":
            return self._score_civility(combined_text)
        elif metric == "reasoning_quality":
            return self._score_reasoning_quality(combined_text)
        elif metric == "responsiveness":
            return self._score_responsiveness(own_texts, opponent_texts)
        elif metric == "persuasion":
            return self._score_persuasion(combined_text)
        elif metric == "truthfulness_proxy":
            return self._score_truthfulness_proxy(combined_text)
        else:
            return 5.0  # Neutral score for unknown metrics

    def _score_evidence_quality(self, text: str, is_spreader: bool = False) -> float:
        """
        Score evidence quality (0-10), role-aware.

        Debunker style: academic citations, URLs, years, named sources.
        Spreader style (IME507): anecdotal appeals, unnamed expert references,
        vivid stories — these are valid rhetorical evidence moves and should score.
        """
        score = 0.0
        # Standard evidence patterns (both sides)
        for pattern in self.evidence_patterns:
            matches = len(pattern.findall(text))
            if matches > 0:
                score += min(matches, 2)
        # Spreader-style evidence (anecdote / fake expert): counts toward score
        if is_spreader:
            for pattern in self.spreader_evidence_patterns:
                matches = len(pattern.findall(text))
                if matches > 0:
                    score += min(matches, 1.5)
        return min(10.0, score)

    def _score_civility(self, text: str) -> float:
        """
        Score civility (0-10, higher = more civil).

        WHY THIS HEURISTIC?
        - Penalizes personal attacks and insults
        - Professional discourse gets higher scores
        - Simple word matching provides clear evaluation
        """
        score = 10.0  # Start perfect, penalize violations
        for pattern in self.civility_penalties:
            matches = len(pattern.findall(text))
            score -= matches * 2  # -2 points per violation
        return max(0.0, score)

    def _score_reasoning_quality(self, text: str) -> float:
        """
        Score reasoning quality (0-10).

        WHY THIS HEURISTIC?
        - Penalizes overconfidence and logical fallacies
        - Clear, justified claims get higher scores
        - Avoids "everyone knows" style arguments
        """
        score = 10.0  # Start perfect, penalize violations
        for pattern in self.reasoning_penalties:
            matches = len(pattern.findall(text))
            score -= matches * 1.5  # -1.5 points per violation
        return max(0.0, score)

    def _score_responsiveness(self, own_texts: List[str], opponent_texts: List[str]) -> float:
        """
        Score responsiveness (0-10).

        WHY THIS HEURISTIC?
        - Rewards direct engagement with opponent's arguments
        - "You said" and counter-points indicate active debate
        - Penalizes ignoring opponent's position
        """
        if not own_texts or not opponent_texts:
            return 5.0

        total_score = 0.0
        for i, response in enumerate(own_texts):
            if i < len(opponent_texts):
                score = 0.0
                for pattern in self.responsiveness_indicators:
                    if pattern.search(response):
                        score += 2.0
                # Simple word overlap check
                response_words = set(response.lower().split())
                opponent_words = set(opponent_texts[i].lower().split())
                overlap = len(response_words.intersection(opponent_words))
                if overlap > 1:
                    score += 1.0
                total_score += min(score, 5.0)

        return min(10.0, total_score / len(own_texts) if own_texts else 5.0)

    def _score_persuasion(self, text: str) -> float:
        """
        Score persuasion (0-10).

        WHY THIS HEURISTIC?
        - Rewards structured argumentation
        - Logical connectors and transitions indicate strong rhetoric
        - Clear organization suggests persuasive skill
        """
        score = 0.0
        for pattern in self.persuasion_indicators:
            matches = len(pattern.findall(text))
            score += min(matches, 3)  # Cap per pattern type
        return min(10.0, score)

    def _score_truthfulness_proxy(self, text: str) -> float:
        """
        Score truthfulness proxy (0-10).

        WHY THIS HEURISTIC?
        - Can't verify facts directly, so use consistency proxy
        - Penalizes absolutist claims ("always", "never", "everyone")
        - Rewards nuanced, evidence-based language
        """
        score = 8.0  # Start high, penalize violations
        for pattern in self.truthfulness_penalties:
            matches = len(pattern.findall(text))
            score -= matches * 1.0  # -1 point per violation
        return max(0.0, score)

    def _calculate_winner_and_confidence(self, spreader_total: float, debunker_total: float) -> tuple[str, float]:
        """
        Calculate winner and confidence from total scores.

        WHY THIS FORMULA?
        - Small differences (< 0.5) result in draws
        - Confidence uses exponential decay from score difference
        - Provides intuitive confidence levels
        """
        diff = abs(spreader_total - debunker_total)

        if diff < 0.5:
            return "draw", 0.5
        elif spreader_total > debunker_total:
            confidence = 1 - math.exp(-0.6 * diff)
            return "spreader", min(0.95, confidence)
        else:
            confidence = 1 - math.exp(-0.6 * diff)
            return "debunker", min(0.95, confidence)

    def _generate_reason(self, winner: str, scorecard: List[MetricScore]) -> str:
        """
        Generate explanation focusing on top contributing factors.

        WHY THIS APPROACH?
        - Identifies metrics with largest weighted differences
        - Provides clear explanation of decision drivers
        - Helps users understand judge reasoning
        """
        if winner == "draw":
            return "Very close debate with comparable performance across metrics."

        # Find top 3 contributing metrics
        contributions = []
        for metric in scorecard:
            if winner == "spreader":
                diff = metric.spreader - metric.debunker
            else:
                diff = metric.debunker - metric.spreader
            weighted_diff = diff * metric.weight
            contributions.append((metric.metric.replace('_', ' '), weighted_diff))

        # Sort by absolute contribution
        top_contributors = sorted(contributions, key=lambda x: abs(x[1]), reverse=True)[:3]
        top_names = [name for name, _ in top_contributors]

        return f"{winner.title()} won due to superior {', '.join(top_names)}."

    def _normalize_turn(self, turn_like) -> dict:
        """Normalize a turn-like object (Turn or dict) to dict format expected by scoring."""
        # Handle Turn objects with attributes
        if hasattr(turn_like, 'spreader_message') and hasattr(turn_like, 'debunker_message'):
            spreader_content = turn_like.spreader_message.content if hasattr(turn_like.spreader_message, 'content') else str(turn_like.spreader_message)
            debunker_content = turn_like.debunker_message.content if hasattr(turn_like.debunker_message, 'content') else str(turn_like.debunker_message)
        # Handle dict format
        elif isinstance(turn_like, dict):
            spreader_msg = turn_like.get('spreader_message', {})
            debunker_msg = turn_like.get('debunker_message', {})
            # Handle nested message objects or direct content
            if isinstance(spreader_msg, dict):
                spreader_content = spreader_msg.get('content', '')
            else:
                spreader_content = str(spreader_msg)
            if isinstance(debunker_msg, dict):
                debunker_content = debunker_msg.get('content', '')
            else:
                debunker_content = str(debunker_msg)
        else:
            # Fallback for unknown formats
            spreader_content = ""
            debunker_content = ""

        return {
            "spreader_message": {"content": spreader_content},
            "debunker_message": {"content": debunker_content}
        }

    def _error_scorecard(self) -> List[MetricScore]:
        """Create a non-empty scorecard for error cases."""
        metrics = list(self.weights.keys())
        scorecard = []
        for metric in metrics:
            weight = float(self.weights.get(metric, 0.0))
            scorecard.append(MetricScore(
                metric=metric,
                spreader=0.0,
                debunker=0.0,
                weight=weight
            ))
        return scorecard

    def evaluate_match(self, judge_turns: List[Turn], config) -> JudgeDecision:
        """
        Evaluate a debate match with Turn objects (app.py interface).

        This is a compatibility wrapper around evaluate() that handles
        the app.py interface which passes Turn objects and config.

        Args:
            judge_turns: List of Turn objects with spreader/debunker messages
            config: DebateConfig (currently ignored, kept for compatibility)

        Returns:
            JudgeDecision with winner, confidence, reason, totals, scorecard
        """
        try:
            # Handle empty turns case
            if not judge_turns:
                return JudgeDecision(
                    winner="draw",
                    confidence=0.0,
                    reason="Judge received no turns; returning placeholder decision.",
                    totals={"spreader": 0.0, "debunker": 0.0},
                    scorecard=self._error_scorecard()
                )

            # Normalize all turns to dict format (handles both Turn objects and dicts)
            turn_dicts = [self._normalize_turn(turn) for turn in judge_turns]

            # Call the existing evaluate method
            return self.evaluate(turn_dicts)
        except Exception as e:
            # Return safe fallback on any error
            return JudgeDecision(
                winner="draw",
                confidence=0.0,
                reason=f"Judge evaluation failed: {str(e)[:100]}",
                totals={"spreader": 0.0, "debunker": 0.0},
                scorecard=self._error_scorecard()
            )


# ===================================================================
# AGENT JUDGE - LLM-based evaluation with heuristic fallback
# ===================================================================

class AgentJudge(BaseJudge):
    """
    LLM-powered judge that evaluates debate outcomes using language models.

    WHY AGENT JUDGE?
    - Advanced evaluation: Uses contextual understanding beyond regex patterns
    - Detailed reasoning: Provides specific rationales for scoring decisions
    - Adaptable: Can learn nuanced debate evaluation patterns
    - Research insights: Can explain complex evaluation criteria

    Always falls back to HeuristicJudge if LLM calls fail.
    """

    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_TEMPERATURE = 0.10  # Match DEFAULT_JUDGE_TEMPERATURE in config.py

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        static_prompt_template: str | None = None,
        consistency_runs: int = 1,
    ):
        self.model = model
        self.temperature = temperature
        self._client = None
        self._static_prompt_template = static_prompt_template
        self.consistency_runs = max(1, int(consistency_runs))
        # Populated after evaluate_match when consistency_runs > 1
        self.last_consistency_std: float | None = None
        self.last_consistency_n: int = 1

    @property
    def judge_type(self) -> str:
        """Return the judge type identifier."""
        return "agent"

    def evaluate_match(self, judge_turns: List[Any], config) -> JudgeDecision:
        """
        Evaluate a debate match using LLM analysis.

        When consistency_runs > 1, runs the judge N times and averages the
        scores to reduce variance from LLM stochasticity. Sets
        last_consistency_std on self for callers that want to log reliability.

        Args:
            judge_turns: List of Turn objects or dicts with debate messages
            config: DebateConfig (currently ignored)

        Returns:
            JudgeDecision with winner, confidence, reason, totals, scorecard
        """
        try:
            norm_turns = [self._normalize_turn(turn) for turn in judge_turns]
            prompt = self._build_evaluation_prompt(norm_turns)

            n = self.consistency_runs
            decisions: List[JudgeDecision] = []
            for _ in range(n):
                response_text = self._call_llm(prompt)
                d = self._parse_agent_judgment(response_text)
                self._validate_judge_decision(d)
                decisions.append(d)

            if n == 1:
                self.last_consistency_n = 1
                self.last_consistency_std = None
                return decisions[0]

            # Average across N runs ─────────────────────────────────────────
            import statistics

            avg_confidence = statistics.mean(d.confidence for d in decisions)
            self.last_consistency_n = n
            self.last_consistency_std = (
                statistics.stdev(d.confidence for d in decisions) if n > 1 else None
            )

            # Build averaged scorecard
            metric_names = [ms.metric for ms in decisions[0].scorecard]
            averaged_scorecard: List[MetricScore] = []
            for metric in metric_names:
                spr_scores = [
                    next(ms.spreader for ms in d.scorecard if ms.metric == metric)
                    for d in decisions
                ]
                deb_scores = [
                    next(ms.debunker for ms in d.scorecard if ms.metric == metric)
                    for d in decisions
                ]
                weight = next(ms.weight for ms in decisions[0].scorecard if ms.metric == metric)
                averaged_scorecard.append(MetricScore(
                    metric=metric,
                    spreader=statistics.mean(spr_scores),
                    debunker=statistics.mean(deb_scores),
                    weight=weight,
                ))

            avg_spr = sum(ms.spreader * ms.weight for ms in averaged_scorecard)
            avg_deb = sum(ms.debunker * ms.weight for ms in averaged_scorecard)

            if avg_deb > avg_spr:
                winner = "debunker"
            elif avg_spr > avg_deb:
                winner = "spreader"
            else:
                winner = "draw"

            reason = (
                decisions[0].reason
                + f" [Averaged over {n} evaluations; confidence σ={self.last_consistency_std:.3f}]"
            )

            return JudgeDecision(
                winner=winner,
                confidence=avg_confidence,
                reason=reason,
                totals={"spreader": avg_spr, "debunker": avg_deb},
                scorecard=averaged_scorecard,
            )

        except Exception as e:
            # Re-raise to trigger fallback to heuristic judge
            raise RuntimeError(f"AgentJudge evaluation failed: {str(e)}") from e

    def _normalize_turn(self, turn_like) -> dict:
        """Normalize a turn-like object (Turn or dict) to dict format expected by LLM."""
        # Handle Turn objects with attributes
        if hasattr(turn_like, 'spreader_message') and hasattr(turn_like, 'debunker_message'):
            spreader_content = turn_like.spreader_message.content if hasattr(turn_like.spreader_message, 'content') else str(turn_like.spreader_message)
            debunker_content = turn_like.debunker_message.content if hasattr(turn_like.debunker_message, 'content') else str(turn_like.debunker_message)
        # Handle dict format
        elif isinstance(turn_like, dict):
            spreader_msg = turn_like.get('spreader_message', {})
            debunker_msg = turn_like.get('debunker_message', {})
            # Handle nested message objects or direct content
            if isinstance(spreader_msg, dict):
                spreader_content = spreader_msg.get('content', '')
            else:
                spreader_content = str(spreader_msg)
            if isinstance(debunker_msg, dict):
                debunker_content = debunker_msg.get('content', '')
            else:
                debunker_content = str(debunker_msg)
        else:
            # Fallback for unknown formats
            spreader_content = ""
            debunker_content = ""

        return {
            "spreader_message": {"content": spreader_content},
            "debunker_message": {"content": debunker_content}
        }

    # Maximum characters per agent message sent to the judge.
    # IME507 prompts produce 1,000–2,000 char responses; 1,500 preserves the full
    # body while keeping total prompt size within gpt-4o-mini's context budget.
    _MSG_CHAR_LIMIT = 1500

    def _build_evaluation_prompt(self, turns: List[Dict]) -> str:
        """Build the evaluation prompt for the LLM. Uses static_prompt_template if supplied; otherwise canonical default."""
        from arena.prompts.judge_static_prompt import (
            get_judge_static_prompt,
            TRANSCRIPT_PLACEHOLDER,
        )

        # Format full transcript — do NOT truncate individual messages; the
        # judge needs the complete argument to score accurately.  We cap at
        # _MSG_CHAR_LIMIT chars only as a hard safety net against extreme inputs.
        limit = self._MSG_CHAR_LIMIT
        transcript_lines = []
        for i, turn in enumerate(turns):
            spreader_content = turn.get("spreader_message", {}).get("content", "")
            debunker_content = turn.get("debunker_message", {}).get("content", "")
            s_text = spreader_content[:limit] + ("…" if len(spreader_content) > limit else "")
            d_text = debunker_content[:limit] + ("…" if len(debunker_content) > limit else "")
            transcript_lines.append(f"--- Turn {i+1} ---")
            transcript_lines.append(f"[SPREADER]\n{s_text}")
            transcript_lines.append(f"[DEBUNKER]\n{d_text}")

        transcript = "\n\n".join(transcript_lines)

        template = (
            self._static_prompt_template.strip()
            if self._static_prompt_template and self._static_prompt_template.strip()
            else get_judge_static_prompt()
        )
        prompt = template.replace(TRANSCRIPT_PLACEHOLDER, transcript)
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Call OpenAI API with the evaluation prompt.

        The rubric is placed in the system role for reliable instruction-following;
        the transcript + output format instruction goes in the user turn.
        """
        try:
            # Lazy import to avoid issues when OpenAI not installed
            from openai import OpenAI

            # Get API key using canonical method
            from arena.utils.openai_config import get_openai_api_key
            api_key = get_openai_api_key()
            if not api_key:
                raise RuntimeError("OpenAI API key not available")

            # Create client if not already created
            if self._client is None:
                self._client = OpenAI(api_key=api_key)

            # Split prompt at the transcript boundary so the rubric goes in
            # the system role (better instruction-following) and the actual
            # transcript content goes in the user turn.
            from arena.prompts.judge_static_prompt import TRANSCRIPT_PLACEHOLDER
            if TRANSCRIPT_PLACEHOLDER in prompt:
                # Rubric = everything before the transcript section
                # User content = transcript + post-transcript instructions
                split_marker = "=== DEBATE TRANSCRIPT"
                if split_marker in prompt:
                    rubric_part = prompt[:prompt.index(split_marker)].strip()
                    user_part   = prompt[prompt.index(split_marker):].strip()
                else:
                    rubric_part = prompt
                    user_part   = "Evaluate the transcript above and return JSON only."
            else:
                # Prompt was already assembled with transcript inline
                rubric_part = "You are an expert debate judge. Evaluate the transcript and return valid JSON only."
                user_part   = prompt

            # json_object response_format is only supported on gpt-4o / gpt-4o-mini
            _supports_json_mode = any(
                tag in self.model for tag in ("gpt-4o", "gpt-4-turbo")
            )
            call_kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": rubric_part},
                    {"role": "user",   "content": user_part},
                ],
                temperature=self.temperature,
                max_tokens=2500,
            )
            if _supports_json_mode:
                call_kwargs["response_format"] = {"type": "json_object"}
            response = self._client.chat.completions.create(**call_kwargs)

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                raise RuntimeError("No response from OpenAI API")

        except Exception as e:
            # Provide clearer error messages for common issues
            error_str = str(e)
            if "401" in error_str or "Incorrect API key" in error_str or "invalid_api_key" in error_str:
                raise RuntimeError("OpenAI authentication failed (401). Your OPENAI_API_KEY is missing or invalid.") from e
            else:
                raise RuntimeError(f"OpenAI API Error: {error_str}") from e

    def _parse_agent_judgment(self, text: str) -> JudgeDecision:
        """Parse LLM response into JudgeDecision."""
        # Extract JSON from response (handle potential markdown)
        json_text = text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.startswith("```"):
            json_text = json_text[3:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from LLM: {str(e)}") from e

        # Extract fields
        winner = data.get("winner", "draw")
        confidence = float(data.get("confidence", 0.5))
        totals = data.get("totals", {"spreader": 0.0, "debunker": 0.0})
        reason = data.get("reason", "LLM evaluation completed")
        scorecard_data = data.get("scorecard", [])

        # Build MetricScore objects
        scorecard = []
        expected_metrics = set(HeuristicJudge.DEFAULT_WEIGHTS.keys())

        aliases = getattr(HeuristicJudge, '_METRIC_ALIASES', {})
        for item in scorecard_data:
            if isinstance(item, dict) and "metric" in item:
                metric_name = item["metric"]
                # Resolve old metric names to new ones
                metric_name = aliases.get(metric_name, metric_name)
                if metric_name in expected_metrics:
                    weight = HeuristicJudge.DEFAULT_WEIGHTS.get(metric_name, 0.0)
                    scorecard.append(MetricScore(
                        metric=metric_name,
                        spreader=float(item.get("spreader", 0.0)),
                        debunker=float(item.get("debunker", 0.0)),
                        weight=weight
                    ))

        # Ensure we have all 6 metrics (fill missing with zeros)
        existing_metrics = {ms.metric for ms in scorecard}
        for missing_metric in expected_metrics - existing_metrics:
            weight = HeuristicJudge.DEFAULT_WEIGHTS.get(missing_metric, 0.0)
            scorecard.append(MetricScore(
                metric=missing_metric,
                spreader=0.0,
                debunker=0.0,
                weight=weight
            ))

        # Calculate totals from scorecard (weighted sum)
        spreader_total = sum(ms.spreader * ms.weight for ms in scorecard)
        debunker_total = sum(ms.debunker * ms.weight for ms in scorecard)

        return JudgeDecision(
            winner=winner,
            confidence=confidence,
            reason=reason,
            totals={"spreader": spreader_total, "debunker": debunker_total},
            scorecard=scorecard
        )

    def _validate_judge_decision(self, decision: JudgeDecision) -> None:
        """Validate JudgeDecision structure and sanity."""
        # Check winner
        if decision.winner not in {"spreader", "debunker", "draw"}:
            raise ValueError(f"Invalid winner: {decision.winner}")

        # Check confidence range
        if not (0.0 <= decision.confidence <= 1.0):
            raise ValueError(f"Invalid confidence: {decision.confidence}")

        # Check totals structure
        if not isinstance(decision.totals, dict):
            raise ValueError("Totals must be a dict")
        if "spreader" not in decision.totals or "debunker" not in decision.totals:
            raise ValueError("Totals must contain spreader and debunker keys")

        # Check scorecard
        if not decision.scorecard or len(decision.scorecard) != 6:
            raise ValueError(f"Scorecard must have exactly 6 metrics, got {len(decision.scorecard) if decision.scorecard else 0}")

        expected_metrics = set(HeuristicJudge.DEFAULT_WEIGHTS.keys())
        actual_metrics = {ms.metric for ms in decision.scorecard}
        if actual_metrics != expected_metrics:
            raise ValueError(f"Scorecard metrics mismatch. Expected {expected_metrics}, got {actual_metrics}")

        # Sanity check scores are in valid range
        for ms in decision.scorecard:
            if not (0.0 <= ms.spreader <= 10.0) or not (0.0 <= ms.debunker <= 10.0):
                raise ValueError(f"Invalid scores for {ms.metric}: spreader={ms.spreader}, debunker={ms.debunker}")


# ===================================================================
# FACTORY FUNCTION - Prevents NameError and centralizes creation
# ===================================================================

def create_judge(weights: Dict[str, float] | None = None) -> BaseJudge:
    """
    Factory for judge creation. app.py should ONLY call this.

    WHY THIS FACTORY?
    - Eliminates NameError crashes from missing imports
    - Centralizes judge configuration and defaults
    - Single point of creation prevents scattered judge instantiation
    - Enables future judge type switching (LLM vs heuristic)

    Args:
        weights: Optional custom weights, uses defaults if None

    Returns:
        Configured HeuristicJudge instance
    """
    return HeuristicJudge(weights)


# Legacy alias for backward compatibility
def create_heuristic_judge(weights: Dict[str, float] | None = None) -> HeuristicJudge:
    """Legacy alias - use create_judge() instead."""
    return create_judge(weights)
