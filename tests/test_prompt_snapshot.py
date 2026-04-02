#!/usr/bin/env python3
"""
Test Prompt Snapshot Implementation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Test the constant
from arena.agents import SPREADER_USER_PROMPT_TEMPLATE, DEBUNKER_USER_PROMPT_TEMPLATE, DEFAULT_USER_PROMPT_TEMPLATE

# Test the types
from arena.types import MatchResult, AgentConfig

# Test the build function
from app import build_prompt_snapshot
from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT

def test_constants():
    """Test that constants are properly exposed"""
    print("=== TESTING CONSTANTS ===")

    # Test role-specific user prompt templates
    assert "IN FAVOR" in SPREADER_USER_PROMPT_TEMPLATE, "Spreader template must say IN FAVOR"
    assert "AGAINST" in DEBUNKER_USER_PROMPT_TEMPLATE, "Debunker template must say AGAINST"
    assert "{topic}" in SPREADER_USER_PROMPT_TEMPLATE, "Spreader template must have {topic}"
    assert "{topic}" in DEBUNKER_USER_PROMPT_TEMPLATE, "Debunker template must have {topic}"
    print("✅ Role-specific user prompt templates are correct")

    # Test system prompts exist
    assert SPREADER_SYSTEM_PROMPT.startswith("You are a misinformation spreader"), "Spreader prompt format wrong"
    assert DEBUNKER_SYSTEM_PROMPT.startswith("You are a fact-checking debunker agent"), "Debunker prompt format wrong"
    print("✅ System prompts have correct format")

def test_template_formatting():
    """Test that template formatting works"""
    print("\n=== TESTING TEMPLATE FORMATTING ===")

    topic = "vaccines cause autism"
    opponent_text = "Vaccines are safe."

    spr_formatted = SPREADER_USER_PROMPT_TEMPLATE.format(topic=topic, opponent_text=opponent_text)
    deb_formatted = DEBUNKER_USER_PROMPT_TEMPLATE.format(topic=topic, opponent_text=opponent_text)

    assert "IN FAVOR" in spr_formatted and topic in spr_formatted, f"Spreader format failed: {spr_formatted}"
    assert "AGAINST" in deb_formatted and topic in deb_formatted, f"Debunker format failed: {deb_formatted}"
    print("✅ Template formatting works correctly for both roles")

def test_build_snapshot():
    """Test the build_prompt_snapshot function"""
    print("\n=== TESTING BUILD SNAPSHOT ===")

    # Create mock configs
    spreader_cfg = AgentConfig(
        role="spreader",
        agent_type="OpenAI",
        model="gpt-4o-mini",
        temperature=0.7
    )
    debunker_cfg = AgentConfig(
        role="debunker",
        agent_type="OpenAI",
        model="gpt-4o-mini",
        temperature=0.8
    )
    judge_weights = {"truthfulness_proxy": 0.2, "evidence_quality": 0.2}

    # Build snapshot
    snapshot = build_prompt_snapshot(spreader_cfg, debunker_cfg, judge_weights)

    # Verify structure
    assert "system_prompts" in snapshot
    assert "user_prompt_template" in snapshot
    assert "generation" in snapshot
    assert "judge" in snapshot

    assert snapshot["system_prompts"]["spreader"] == SPREADER_SYSTEM_PROMPT
    assert snapshot["system_prompts"]["debunker"] == DEBUNKER_SYSTEM_PROMPT
    assert snapshot["user_prompt_template"] == DEFAULT_USER_PROMPT_TEMPLATE
    assert snapshot["generation"]["spreader"]["temperature"] == 0.7
    assert snapshot["generation"]["debunker"]["temperature"] == 0.8
    assert snapshot["judge"]["weights"] == judge_weights

    print("✅ build_prompt_snapshot creates correct structure")

def test_matchresult_field():
    """Test that MatchResult accepts the new field"""
    print("\n=== TESTING MATCHRESULT FIELD ===")

    # Test that we can create a MatchResult with prompt_snapshot=None (backward compatibility)
    result = MatchResult(
        match_id="test_match",
        config=None,
        turns=[],
        judge_decision=None,
        prompt_snapshot=None  # Should work
    )
    assert result.prompt_snapshot is None
    print("✅ MatchResult accepts prompt_snapshot=None")

    # Test with actual snapshot
    test_snapshot = {"test": "data"}
    result2 = MatchResult(
        match_id="test_match2",
        config=None,
        turns=[],
        judge_decision=None,
        prompt_snapshot=test_snapshot
    )
    assert result2.prompt_snapshot == test_snapshot
    print("✅ MatchResult accepts prompt_snapshot data")

if __name__ == "__main__":
    try:
        test_constants()
        test_template_formatting()
        test_build_snapshot()
        test_matchresult_field()
        print("\n🎉 ALL PROMPT SNAPSHOT TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

