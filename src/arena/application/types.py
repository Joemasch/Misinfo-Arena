"""
Application layer types for Misinformation Arena v2.

Contains result objects and data transfer objects for use cases.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class TurnPairResult:
    """
    Result of executing a turn pair (spreader + debunker response).

    This provides a clean contract between the application layer and presentation layer,
    enabling better debugging, analytics, and future extensibility without changing behavior.
    """
    ok: bool
    turn_idx: Optional[int] = None

    spreader_text: Optional[str] = None
    debunker_text: Optional[str] = None

    spreader_conceded: Optional[bool] = None
    debunker_conceded: Optional[bool] = None

    completion_reason: Optional[str] = None
    match_completed: bool = False
    judge_ran: bool = False

    early_stop_reason: Optional[str] = None
    last_openai_error: Optional[str] = None

    # Free-form debug fields; keep small + JSON-safe
    debug: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        # ensure debug is at least a dict when present
        if d.get("debug") is None:
            d["debug"] = {}
        return d

