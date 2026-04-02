"""Tests for transcript conversion (to_paired_turns_for_judge)."""

import pytest
from arena.utils.transcript_conversion import (
    to_paired_turns_for_judge,
    _extract_speaker,
    _extract_turn_index,
    _extract_content,
)


def test_flat_stored_turns():
    """Flat stored turns input produces paired format."""
    input_turns = [
        {"name": "spreader", "content": "a", "turn_index": 0},
        {"name": "debunker", "content": "b", "turn_index": 0},
    ]
    result = to_paired_turns_for_judge(input_turns)
    assert len(result) == 1
    assert result[0]["turn_index"] == 0
    assert result[0]["spreader_message"]["content"] == "a"
    assert result[0]["debunker_message"]["content"] == "b"


def test_episode_transcript_single_message_mode():
    """episode_transcript with role user/assistant but name spreader/debunker works."""
    input_turns = [
        {"role": "user", "name": "spreader", "content": "claim", "turn_index": 0},
        {"role": "assistant", "name": "debunker", "content": "response", "turn_index": 0},
    ]
    result = to_paired_turns_for_judge(input_turns)
    assert len(result) == 1
    assert result[0]["spreader_message"]["content"] == "claim"
    assert result[0]["debunker_message"]["content"] == "response"


def test_missing_debunker_message():
    """Missing debunker for a turn yields empty content for debunker side."""
    input_turns = [
        {"name": "spreader", "content": "a", "turn_index": 0},
        # no debunker for turn 0
    ]
    result = to_paired_turns_for_judge(input_turns)
    assert len(result) == 1
    assert result[0]["spreader_message"]["content"] == "a"
    assert result[0]["debunker_message"]["content"] == ""


def test_mixed_schema_keys_speaker_turn():
    """Accept speaker and turn as synonyms for name and turn_index."""
    input_turns = [
        {"speaker": "spreader", "content": "x", "turn": 0},
        {"speaker": "debunker", "content": "y", "turn": 0},
    ]
    result = to_paired_turns_for_judge(input_turns)
    assert len(result) == 1
    assert result[0]["spreader_message"]["content"] == "x"
    assert result[0]["debunker_message"]["content"] == "y"


def test_empty_input_returns_empty():
    """Empty input returns empty list."""
    assert to_paired_turns_for_judge([]) == []


def test_extract_speaker():
    """Helper extracts spreader/debunker from name or speaker."""
    assert _extract_speaker({"name": "spreader"}) == "spreader"
    assert _extract_speaker({"name": "debunker"}) == "debunker"
    assert _extract_speaker({"speaker": "spreader"}) == "spreader"
    assert _extract_speaker({"role": "user", "name": "spreader"}) == "spreader"
    assert _extract_speaker({"role": "assistant"}) is None
    assert _extract_speaker({}) is None


def test_extract_turn_index():
    """Helper extracts turn_index or turn."""
    assert _extract_turn_index({"turn_index": 0}) == 0
    assert _extract_turn_index({"turn": 1}) == 1
    assert _extract_turn_index({"turn_index": 2}) == 2
    assert _extract_turn_index({}) is None


def test_extract_content():
    """Helper extracts content from content, text, or message."""
    assert _extract_content({"content": "hi"}) == "hi"
    assert _extract_content({"text": "there"}) == "there"
    assert _extract_content({"message": "msg"}) == "msg"
    assert _extract_content({}) == ""
    assert _extract_content(None) == ""
