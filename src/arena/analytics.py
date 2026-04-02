"""
Analytics engine for debate performance analysis.

Provides methods to load match data, compute statistics, and generate
insights from completed debate matches. Works with the storage system
to access historical match results.

Required interface based on app.py usage:
- get_basic_stats() -> Dict[str, Any]
- load_matches_df() -> pd.DataFrame (returns pandas DataFrame directly)
- compute_rolling_metrics(data, window_size) -> pd.DataFrame (returns pandas DataFrame)
"""

import pandas as pd

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import statistics


class Analytics:
    """
    Analytics engine for debate performance analysis.

    Provides methods to load match data, compute statistics, and generate
    insights from completed debate matches. Works with the storage system
    to access historical match results.
    """

    def __init__(self, storage):
        """
        Initialize analytics with a storage backend.

        Args:
            storage: Storage instance that provides access to match data
        """
        self.storage = storage

    def get_basic_stats(self) -> Dict[str, Any]:
        """
        Get basic statistics about stored matches.

        Returns:
            Dictionary with basic statistics
        """
        matches = self._load_all_matches()

        if not matches:
            return {
                "total_matches": 0,
                "total_episodes": 0,
                "avg_turns_per_episode": 0,
                "spreader_wins": 0,
                "debunker_wins": 0,
                "win_rate_spreader": 0.0,
                "win_rate_debunker": 0.0,
                "avg_judge_confidence": 0.0,
            }

        total_matches = len(matches)
        total_episodes = sum(match.get("episode_idx", 0) + 1 for match in matches)
        total_turns = sum(match.get("turn_count", 0) for match in matches)

        spreader_wins = sum(1 for match in matches if match.get("winner") == "spreader")
        debunker_wins = sum(1 for match in matches if match.get("winner") == "debunker")

        # Calculate win rates
        win_rate_spreader = spreader_wins / total_matches if total_matches > 0 else 0.0
        win_rate_debunker = debunker_wins / total_matches if total_matches > 0 else 0.0

        # Calculate average judge confidence (if available in judge_decision)
        confidences = []
        for match in matches:
            judge_decision = match.get("judge_decision", {})
            if isinstance(judge_decision, dict) and "confidence" in judge_decision:
                try:
                    conf = float(judge_decision["confidence"])
                    confidences.append(conf)
                except (ValueError, TypeError):
                    pass

        avg_confidence = statistics.mean(confidences) if confidences else 0.0

        return {
            "total_matches": total_matches,
            "total_episodes": total_episodes,
            "avg_turns_per_episode": total_turns / total_episodes if total_episodes > 0 else 0,
            "spreader_wins": spreader_wins,
            "debunker_wins": debunker_wins,
            "win_rate_spreader": win_rate_spreader,
            "win_rate_debunker": win_rate_debunker,
            "avg_judge_confidence": avg_confidence,
        }

    def load_matches_df(self) -> pd.DataFrame:
        """
        Load all matches as a pandas DataFrame.

        Returns:
            pandas DataFrame with flattened match data
        """
        matches = self._load_all_matches()

        if not matches:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=[
                "match_id", "timestamp", "topic", "winner", "episode_idx",
                "turn_count", "judge_explanation", "judge_confidence",
                "judge_primary_factor", "concession_reason", "concession_turn"
            ])

        # Flatten the data for DataFrame compatibility
        flattened = []
        for match in matches:
            flat_match = {
                "match_id": match.get("match_id", ""),
                "timestamp": match.get("timestamp", ""),
                "topic": match.get("topic", ""),
                "winner": match.get("winner", ""),
                "episode_idx": match.get("episode_idx", 0),
                "turn_count": match.get("turn_count", 0),
                "judge_explanation": match.get("judge_explanation", ""),
            }

            # Add judge decision fields if available
            judge_decision = match.get("judge_decision", {})
            if isinstance(judge_decision, dict):
                flat_match["judge_confidence"] = judge_decision.get("confidence", 0.0)
                flat_match["judge_primary_factor"] = judge_decision.get("primary_factor", "")

                # Extract total scores for analytics compatibility
                # Handle both old schema (total_score_spreader/total_score_debunker)
                # and new schema (totals dict)
                totals = judge_decision.get("totals", {})
                if isinstance(totals, dict):
                    flat_match["total_score_spreader"] = totals.get("spreader", 0.0)
                    flat_match["total_score_debunker"] = totals.get("debunker", 0.0)
                else:
                    # Fallback to old direct fields if totals dict not available
                    flat_match["total_score_spreader"] = judge_decision.get("total_score_spreader", 0.0)
                    flat_match["total_score_debunker"] = judge_decision.get("total_score_debunker", 0.0)
            else:
                flat_match["judge_confidence"] = 0.0
                flat_match["judge_primary_factor"] = ""
                flat_match["total_score_spreader"] = 0.0
                flat_match["total_score_debunker"] = 0.0

            # Add concession data if available
            concession_data = match.get("concession_data", {})
            if isinstance(concession_data, dict):
                flat_match["concession_reason"] = concession_data.get("reason", "")
                flat_match["concession_turn"] = concession_data.get("turn", 0)
            else:
                flat_match["concession_reason"] = ""
                flat_match["concession_turn"] = 0

            flattened.append(flat_match)

        df = pd.DataFrame(flattened)

        # Normalize confidence column for consistent UI access
        self._normalize_confidence_column(df)

        # Apply full schema normalization
        df = normalize_analytics_df(df)

        return df

    def compute_rolling_metrics(self, data: pd.DataFrame, window_size: int) -> pd.DataFrame:
        """
        Compute rolling window metrics from match data.

        Args:
            data: pandas DataFrame of match data (from load_matches_df)
            window_size: Size of the rolling window

        Returns:
            pandas DataFrame with rolling metrics
        """
        if data.empty or window_size <= 0:
            return pd.DataFrame(columns=[
                "match_index", "window_end_timestamp", "window_size", "rolling_spreader_wins",
                "rolling_debunker_wins", "rolling_win_rate_spreader",
                "rolling_debunker_win_rate", "rolling_avg_confidence"
            ])

        # Sort by timestamp (assuming data is already sorted chronologically)
        sorted_data = data.sort_values("timestamp")

        rolling_results = []

        for i in range(len(sorted_data)):
            window_start = max(0, i - window_size + 1)
            window_data = sorted_data.iloc[window_start:i+1]

            # Calculate rolling metrics
            spreader_wins = (window_data["winner"] == "spreader").sum()
            debunker_wins = (window_data["winner"] == "debunker").sum()
            total_matches = len(window_data)

            # Safely resolve confidence column (robust to schema variations)
            conf_col = None
            for c in ("judge_confidence", "confidence", "judge_decision_confidence", "judge_score_confidence"):
                if c in window_data.columns:
                    conf_col = c
                    break

            if conf_col is None:
                # No confidence available in this dataset/window
                avg_conf = 0.0
                # Debug warning for schema compatibility (only in debug mode)
                try:
                    from arena.app_config import DEBUG_DIAG
                    if DEBUG_DIAG:
                        print(f"ANALYTICS: No confidence column found in window {i}, using 0.0")
                except ImportError:
                    pass
            else:
                # Coerce to numeric; ignore non-numeric/NaN
                avg_conf = pd.to_numeric(window_data[conf_col], errors="coerce").mean()
                if pd.isna(avg_conf):
                    avg_conf = 0.0

            rolling_result = {
                "match_index": i,  # Use row index as match_index
                "window_end_timestamp": sorted_data.iloc[i]["timestamp"],
                "window_size": total_matches,
                "rolling_spreader_wins": spreader_wins,
                "rolling_debunker_wins": debunker_wins,
                "rolling_win_rate_spreader": spreader_wins / total_matches if total_matches > 0 else 0.0,
                "rolling_debunker_win_rate": debunker_wins / total_matches if total_matches > 0 else 0.0,
                "rolling_avg_confidence": avg_conf,
            }

            rolling_results.append(rolling_result)

        return pd.DataFrame(rolling_results)

    def _normalize_confidence_column(self, df: pd.DataFrame) -> None:
        """
        Ensure the DataFrame has a standardized 'confidence' column.

        This normalizes various confidence-like columns into a single 'confidence' column
        that the UI can reliably access.

        Args:
            df: DataFrame to normalize (modified in-place)
        """
        CONFIDENCE_CANDIDATES = [
            "confidence",
            "judge_confidence",
            "winner_confidence",
            "verdict_confidence",
            "confidence_score",
        ]

        # If we already have a confidence column, ensure it's numeric
        if "confidence" in df.columns:
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
            return

        # Look for alternative confidence columns
        for candidate in CONFIDENCE_CANDIDATES[1:]:  # Skip "confidence" since we checked it
            if candidate in df.columns:
                df["confidence"] = pd.to_numeric(df[candidate], errors="coerce")
                return

        # If no confidence-like column found, try to derive from other data
        # For example, use a default confidence based on winner determination
        if "winner" in df.columns:
            # Simple heuristic: higher confidence for decisive wins
            df["confidence"] = 0.5  # Default moderate confidence
            # Could be improved with more sophisticated logic based on available data

        # If still no confidence, leave it as NaN (UI will handle gracefully)

    def _load_all_matches(self) -> List[Dict[str, Any]]:
        """
        Load all matches from storage.

        Returns:
            List of match dictionaries
        """
        matches = []

        try:
            # Read the JSONL file
            if Path(self.storage.full_path).exists():
                with open(self.storage.full_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                match = json.loads(line)
                                matches.append(match)
                            except json.JSONDecodeError:
                                # Skip malformed lines
                                continue
        except (FileNotFoundError, IOError):
            # If file doesn't exist or can't be read, return empty list
            pass

        return matches


def normalize_analytics_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize analytics DataFrame to ensure consistent column names.

    This function maps alternative column names to canonical names expected by
    the UI, ensuring the analytics page can access data reliably even when
    the underlying schema varies.

    Args:
        df: DataFrame to normalize (modified in-place)

    Returns:
        The same DataFrame with normalized column names
    """
    # Normalize confidence column (already done in _normalize_confidence_column)
    # but ensure it's called here for consistency
    analytics = Analytics(None)  # Create instance just to call the method
    analytics._normalize_confidence_column(df)

    # Normalize score columns
    SPREADER_SCORE_CANDIDATES = [
        "total_score_spreader",
        "total_spreader_score",
        "spreader_total_score",
        "spreader_score",
        "judge_score_spreader",
        "score_spreader",
        "avg_spreader_score",
    ]

    DEBUNKER_SCORE_CANDIDATES = [
        "total_score_debunker",
        "total_debunker_score",
        "debunker_total_score",
        "debunker_score",
        "judge_score_debunker",
        "score_debunker",
        "avg_debunker_score",
    ]

    # Ensure total_score_spreader column exists
    if "total_score_spreader" not in df.columns:
        spreader_src = next((c for c in SPREADER_SCORE_CANDIDATES if c in df.columns), None)
        if spreader_src:
            df["total_score_spreader"] = pd.to_numeric(df[spreader_src], errors="coerce")
        else:
            # No spreader score data available, leave as NaN
            df["total_score_spreader"] = pd.NA

    # Ensure total_score_debunker column exists
    if "total_score_debunker" not in df.columns:
        debunker_src = next((c for c in DEBUNKER_SCORE_CANDIDATES if c in df.columns), None)
        if debunker_src:
            df["total_score_debunker"] = pd.to_numeric(df[debunker_src], errors="coerce")
        else:
            # No debunker score data available, leave as NaN
            df["total_score_debunker"] = pd.NA

    # Normalize early_stop column
    EARLY_STOP_CANDIDATES = [
        "early_stop",
        "stopped_early",
        "is_early_stop",
        "early_termination",
    ]

    if "early_stop" not in df.columns:
        early_stop_src = next((c for c in EARLY_STOP_CANDIDATES if c in df.columns), None)
        if early_stop_src:
            df["early_stop"] = pd.to_numeric(df[early_stop_src], errors="coerce").fillna(0)
        else:
            # No early stop data, assume all completed normally
            df["early_stop"] = 0

    # Normalize timestamp columns to created_at
    TS_CANDIDATES = ["created_at", "timestamp", "time", "started_at", "saved_at", "event_time", "datetime"]

    if "created_at" not in df.columns:
        ts_src = next((c for c in TS_CANDIDATES if c in df.columns), None)
        if ts_src:
            # Copy the timestamp column to created_at
            df["created_at"] = df[ts_src]
            # Try to convert to datetime if it looks like a timestamp
            try:
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            except:
                pass  # Keep as-is if conversion fails
        else:
            # No timestamp data available, create a stable sort key from index
            df = df.reset_index(drop=False).rename(columns={"index": "created_at_index"})
            df["created_at"] = df["created_at_index"]

    return df


def create_analytics(storage) -> Analytics:
    """
    Create an analytics instance.

    This function provides a stable API for creating analytics instances.
    It forwards to the Analytics constructor.

    Args:
        storage: Storage instance that provides access to match data

    Returns:
        A new Analytics instance
    """
    return Analytics(storage)
