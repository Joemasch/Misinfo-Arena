"""
Core type definitions for the Misinformation Arena v2.

This module defines all the data structures used throughout the application.
We use dataclasses for clean, immutable data structures with automatic
__init__, __repr__, and other methods.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class AgentRole(Enum):
    """Enumeration for the two types of agents in the debate."""
    SPREADER = "spreader"
    DEBUNKER = "debunker"


@dataclass
class Citation:
    """
    Represents a structured citation/reference in a debate message.

    This data structure enables agents to provide verifiable evidence
    alongside their textual arguments. Citations can come from web search,
    academic databases, or other evidence sources.

    WHY THIS DESIGN EARLY?
    - Prevents massive refactors when implementing real retrieval
    - Allows UI to render citations consistently
    - Enables judge to score evidence quality objectively
    - Supports future evidence pipeline integration
    """
    title: str           # Title/headline of the cited source
    publisher: str       # Source organization (e.g., "NASA", "BBC", "CDC")
    date: Optional[str]  # Publication date (ISO format preferred)
    url: Optional[str]   # Direct link to the source
    snippet: str         # Relevant excerpt/quote from the source


@dataclass
class Message:
    """
    Represents a single message from one agent in the debate.

    This is the atomic unit of communication between agents. Enhanced with
    structured citations to support evidence-based argumentation.

    WHY THIS DESIGN EARLY?
    - Citations field allows future evidence retrieval without code changes
    - UI can render citations consistently regardless of retrieval method
    - Judge can score evidence quality based on citation presence/structure
    - Storage format remains flexible for different citation sources
    - Backward compatibility maintained through empty citations list
    """
    role: AgentRole                           # Who sent this message (spreader or debunker)
    content: str                              # The actual text content of the message
    citations: List[Citation] = field(default_factory=list)  # Structured evidence references
    timestamp: datetime = field(default_factory=datetime.now)  # When message was created


@dataclass
class Turn:
    turn_index: int
    spreader_message: Optional[Any] = None
    debunker_message: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class MatchConfig:
    """
    Configuration settings for a debate match.

    This defines the rules and constraints for how a match should be run.
    """
    max_turns: int = 10  # Maximum number of turns before forcing a conclusion
    topic: str = "General misinformation debate"  # The topic/claim being debated
    concession_phrases: List[str] = field(default_factory=lambda: [
        "i agree", "you're right", "i retract", "i concede",
        "you are correct", "i was wrong", "i apologize", "i surrender",
        "point taken", "fair enough", "you win", "i give up"
    ])  # Phrases that indicate concession (case-insensitive)
    judge_weights: Dict[str, float] = field(default_factory=lambda: {
        # Equal weights per Wachsmuth et al. (2017) — quality is context-dependent
        "factuality": 0.167,            # D2D: factual grounding
        "source_credibility": 0.167,    # D2D: source reliability
        "reasoning_quality": 0.167,     # Wachsmuth: cogency
        "responsiveness": 0.167,        # Wachsmuth: reasonableness
        "persuasion": 0.167,            # Wachsmuth: effectiveness
        "manipulation_awareness": 0.167, # Inoculation theory
    })


@dataclass
class MetricScore:
    """
    Individual metric score for both debaters.

    One row of the judge scorecard — metric name, per-side scores, and weight.
    """
    metric: str      # Name of the metric (e.g., "evidence_quality")
    spreader: float  # Score for spreader (0-10)
    debunker: float  # Score for debunker (0-10)
    weight: float    # Weight of this metric in final scoring


@dataclass
class JudgeDecision:
    """
    Complete judge decision with all evaluation results.

    Canonical definition used by HeuristicJudge and AgentJudge.
    """
    winner: str                    # "spreader", "debunker", or "draw"
    confidence: float              # 0.0 to 1.0 confidence in decision
    reason: str                    # Short explanation of decision
    totals: Dict[str, float]       # Total scores: {"spreader": X.X, "debunker": Y.Y}
    scorecard: List["MetricScore"]   # Detailed scores for each metric


# Backward compatibility alias
JudgeScorecard = MetricScore


@dataclass
class DebateInsights:
    """
    AI-generated insights for a completed debate episode.

    Provides strategic analysis for users learning about misinformation persuasion tactics.
    Generated once per episode and cached to avoid repeated API calls.
    """
    title: str = "Debate Insights"
    tldr: str = ""
    core_conflict: str = ""
    strategic_dynamics: str = ""
    outcome_driver: str = ""
    counterfactual: str = ""
    pattern_note: Optional[str] = None
    turning_points_explained: str = ""  # 1-2 sentences explaining why key_turns mattered
    key_turns: List[int] = field(default_factory=list)
    generated_at: str = ""
    model: str = ""
    quality_warnings: List[str] = field(default_factory=list)  # SOFT validation warnings


@dataclass
class MatchResult:
    """
    The complete outcome of a finished debate match.

    This includes all the turns, configuration, and the judge's detailed decision.
    This is what gets persisted to storage for later analysis.
    """
    match_id: str                    # Unique identifier for this match
    config: MatchConfig              # Configuration used for this match
    turns: List[Dict[str, Any]]       # All messages that occurred in sequence (legacy compatibility)
    judge_decision: JudgeDecision    # Complete judge evaluation with scoring
    early_stop: bool = False         # Whether the match ended early due to concession
    created_at: datetime = field(default_factory=datetime.now)  # When match was completed
    prompt_snapshot: Dict[str, Any] | None = None  # Complete prompt and generation parameters snapshot
    insights: Optional[DebateInsights] = None  # AI-generated strategic insights
    insights_error: Optional[str] = None  # Error message if insights generation failed

    # Convenience properties for backward compatibility
    @property
    def winner(self) -> str:
        """Convenience property for winner access."""
        return self.judge_decision.winner

    @property
    def confidence(self) -> float:
        """Convenience property for confidence access."""
        return self.judge_decision.confidence

    @property
    def reason(self) -> str:
        """Convenience property for reason access."""
        return self.judge_decision.reason


@dataclass
class MatchState:
    """
    Current state of an ongoing match.

    This tracks the progress of a debate that's still in progress.
    Used for managing the current conversation in the Streamlit session.
    """
    config: MatchConfig              # Current match configuration
    turns: List[Dict[str, Any]] = field(default_factory=list)  # Messages completed so far (legacy compatibility)
    current_turn: int = 1            # Next turn number to execute
    is_active: bool = False          # Whether a match is currently running
    last_message: Optional[Message] = None  # Most recent message in the debate


@dataclass
class AgentConfig:
    """
    Configuration for creating debate agents.

    This encapsulates all the parameters needed to create an agent,
    providing a clean interface for agent factory functions.
    """
    role: str                    # Agent role: 'spreader', 'debunker', or 'judge'
    agent_type: str = "Dummy"    # Agent implementation: 'Dummy' or 'OpenAI'
    model: str | None = None     # OpenAI model name (ignored for Dummy)
    temperature: float = 0.7     # Sampling temperature (ignored for Dummy)
    name: str | None = None      # Optional agent name


# Type aliases for clarity in other modules
MessageList = List[Message]
