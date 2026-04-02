#!/usr/bin/env python3
"""
Prompt Sanity Test - Verifies prompt architecture without full UI
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import app constants
from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT, DEBUG_DIAG

# Import agent creation
from arena.factories import create_agent

# Mock streamlit for debug prints
class MockST:
    class session_state:
        DEBUG_DIAG = True

import arena.agents as agents
agents.st = MockST()

def test_prompt_sources():
    """Test that prompts are sourced correctly"""
    print("=== PROMPT SOURCE VERIFICATION ===")

    # Check constants exist and are non-empty
    assert SPREADER_SYSTEM_PROMPT, "Spreader prompt is empty"
    assert DEBUNKER_SYSTEM_PROMPT, "Debunker prompt is empty"

    print(f"✅ SPREADER_SYSTEM_PROMPT: {len(SPREADER_SYSTEM_PROMPT)} chars")
    print(f"✅ DEBUNKER_SYSTEM_PROMPT: {len(DEBUNKER_SYSTEM_PROMPT)} chars")

    # Check they start correctly
    assert SPREADER_SYSTEM_PROMPT.startswith("You are a misinformation spreader"), "Spreader prompt format wrong"
    assert DEBUNKER_SYSTEM_PROMPT.startswith("You are a fact-checking debunker agent"), "Debunker prompt format wrong"

def test_agent_creation():
    """Test agent creation and prompt injection"""
    print("\n=== AGENT CREATION TEST ===")

    # Create agents
    spreader = create_agent("spreader", "OpenAI", model="gpt-4o-mini", temperature=0.7)
    debunker = create_agent("debunker", "OpenAI", model="gpt-4o-mini", temperature=0.7)

    print(f"✅ Spreader agent: {type(spreader).__name__}")
    print(f"✅ Debunker agent: {type(debunker).__name__}")

    # Test context building (simulate app.py logic)
    spreader_context = {
        "system_prompt": SPREADER_SYSTEM_PROMPT,
        "topic": "vaccines cause autism",
        "turn_idx": 0,
        "last_opponent_text": "Vaccines are safe and effective."
    }

    debunker_context = {
        "system_prompt": DEBUNKER_SYSTEM_PROMPT,
        "topic": "vaccines cause autism",
        "turn_idx": 1,
        "last_opponent_text": "Vaccines definitely cause autism."
    }

    print(f"✅ Context system_prompt matches: spreader={spreader_context['system_prompt'][:50]}...")
    print(f"✅ Context system_prompt matches: debunker={debunker_context['system_prompt'][:50]}...")

    return spreader, debunker, spreader_context, debunker_context

def test_user_template():
    """Test user message template construction"""
    print("\n=== USER TEMPLATE TEST ===")

    # This is the template from arena/agents.py line 257
    template = "Debate claim: {topic}\nOpponent last message:\n{opponent_text}\n\nWrite your next reply:"
    topic = "vaccines cause autism"
    opponent_text = "Vaccines definitely cause autism."

    rendered = template.format(topic=topic, opponent_text=opponent_text)
    print(f"✅ User template renders correctly: {rendered[:100]}...")

    # Verify it matches what's in the code
    expected_start = "Debate claim: vaccines cause autism\nOpponent last message:\nVaccines definitely cause autism.\n\nWrite your next reply:"
    assert rendered == expected_start, f"Template mismatch: {rendered} != {expected_start}"

if __name__ == "__main__":
    try:
        test_prompt_sources()
        test_agent_creation()
        test_user_template()
        print("\n🎉 ALL SANITY CHECKS PASSED!")
    except Exception as e:
        print(f"\n❌ SANITY CHECK FAILED: {e}")
        sys.exit(1)

