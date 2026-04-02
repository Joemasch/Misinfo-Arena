#!/usr/bin/env python3
"""
Quick test to verify judge debug logging works.
"""

# Simulate the debug flag
DEBUG_SANITY = True

# Test judge creation and evaluation
from arena.factories import create_judge
from arena.types import MatchConfig as DebateConfig, Message, Turn, AgentRole

print("Testing judge debug logging...")

# Create judge
judge = create_judge()
print(f"Created judge: {type(judge).__name__}")

# Create mock turns for testing
config = DebateConfig(max_turns=10, topic="Test topic")

spreader_msg = Message(role=AgentRole.SPREADER, content="This is a test claim from spreader")
debunker_msg = Message(role=AgentRole.DEBUNKER, content="I disagree with your claim")

test_turns = [
    Turn(turn_index=0, spreader_message=spreader_msg, debunker_message=debunker_msg)
]

# Test judge evaluation with debug logging
if DEBUG_SANITY:
    print(f"JUDGE_CALLED match_id=test_match turns={len(test_turns)} topic='{config.topic[:30]}...'")

try:
    decision = judge.evaluate_match(test_turns, config)
    if DEBUG_SANITY:
        judge_fields = list(vars(decision).keys()) if hasattr(decision, '__dict__') else ['unknown']
        print(f"JUDGE_OK verdict={getattr(decision, 'winner', 'unknown')} conf={getattr(decision, 'confidence', 'unknown')} fields={judge_fields}")
    print(f"Judge result: winner={decision.winner}, confidence={decision.confidence}")
except Exception as e:
    if DEBUG_SANITY:
        print(f"JUDGE_ERROR match_id=test_match err={str(e)}")
    print(f"Judge error: {e}")

print("Judge debug logging test complete!")
