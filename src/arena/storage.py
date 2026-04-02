"""
Match storage implementation for Misinformation Arena.

Provides persistent storage for debate match results in JSONL format.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from .types import MatchResult


class MatchStorage:
    """
    Handles persistence of debate match results.

    Saves match results to JSONL format (one JSON object per line) for
    efficient storage and analysis. Automatically creates the runs/ directory.
    """

    def __init__(self, storage_dir: str = "runs", filename: str = "matches.jsonl"):
        """
        Initialize the storage handler.

        Args:
            storage_dir: Directory to store match results (default: "runs")
            filename: Name of the JSONL file (default: "matches.jsonl")
        """
        # Make storage path deterministic based on repo root
        # Since we're now in src/arena/storage.py, we need to go up two levels
        repo_root = Path(__file__).resolve().parents[2]  # src/arena/ -> repo root
        runs_dir = repo_root / storage_dir

        self.storage_dir = str(runs_dir)
        self.filename = filename
        self.full_path = runs_dir / filename

        # Ensure storage directory exists
        self._ensure_storage_directory()

    def _ensure_storage_directory(self) -> None:
        """Create the storage directory if it doesn't exist."""
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_match(self, match_result: MatchResult, judge=None, concession_data: Dict[str, Any] = None) -> None:
        """
        Save a match result to the JSONL file.

        Args:
            match_result: The match result to save
            judge: Optional judge object (for compatibility)
            concession_data: Optional concession data
        """
        # Convert match result to dictionary
        record = self._match_result_to_dict(match_result, concession_data)

        # Append to JSONL file
        with open(self.full_path, "a", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, default=str)
            f.write("\n")

    def _match_result_to_dict(self, match_result: MatchResult, concession_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Convert a MatchResult to a dictionary suitable for JSON serialization.

        Args:
            match_result: The match result to convert
            concession_data: Optional concession data

        Returns:
            Dictionary representation of the match result
        """
        # Get the base record from the MatchResult
        record = {
            "match_id": getattr(match_result, 'match_id', None),
            "timestamp": getattr(match_result, 'timestamp', datetime.now().isoformat()),
            "topic": getattr(match_result, 'topic', ''),
            "transcript": getattr(match_result, 'transcript', []),
            "winner": getattr(match_result, 'winner', None),
            "judge_decision": getattr(match_result, 'judge_decision', {}),
            "judge_explanation": getattr(match_result, 'judge_explanation', ''),
            "episode_idx": getattr(match_result, 'episode_idx', 0),
            "turn_count": getattr(match_result, 'turn_count', 0),
            "concession_data": concession_data or {},
        }

        # Add prompt snapshot if available
        if hasattr(match_result, 'prompt_snapshot') and match_result.prompt_snapshot:
            record["prompt_snapshot"] = match_result.prompt_snapshot

        return record


def create_match_storage(storage_dir: str = "runs", filename: str = "matches.jsonl") -> MatchStorage:
    """
    Factory function to create a match storage instance.

    Args:
        storage_dir: Directory for storing matches
        filename: Name of the JSONL file

    Returns:
        A new MatchStorage instance
    """
    return MatchStorage(storage_dir, filename)


