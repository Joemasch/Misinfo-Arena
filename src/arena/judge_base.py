"""
Base judge interface for the Misinformation Arena v2.

This module defines the abstract interface that all judge implementations
must follow, enabling easy swapping between different judge types.
"""

from abc import ABC, abstractmethod
from typing import List, Any
from arena.types import JudgeDecision
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.judge import Turn


class BaseJudge(ABC):
    """
    Abstract base class for all judge implementations.

    WHY AN ABSTRACT BASE CLASS?
    - Defines the standard interface for judge evaluation
    - Enables polymorphism between different judge types
    - Ensures all judges provide the same evaluation contract
    - Supports future judge implementations (LLM-based, etc.)
    """

    @property
    @abstractmethod
    def judge_type(self) -> str:
        """
        The type identifier for this judge implementation.

        Returns:
            String identifier (e.g., "heuristic", "llm", "hybrid")
        """
        pass

    @abstractmethod
    def evaluate_match(self, judge_turns: List["Turn"], config: Any) -> JudgeDecision:
        """
        Evaluate a completed debate match and return a judge decision.

        Args:
            judge_turns: List of Turn objects containing the debate messages
            config: Debate configuration (may be ignored by some judge types)

        Returns:
            JudgeDecision with winner, confidence, reason, totals, and scorecard
        """
        pass
