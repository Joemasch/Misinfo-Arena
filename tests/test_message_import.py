#!/usr/bin/env python3
"""
Test Message import and usage.
"""

from arena.factories import Message, AgentRole, Turn

# Test Message creation
msg = Message(role=AgentRole.SPREADER, content="Test message")
print(f"✅ Message created: role={msg.role}, content='{msg.content}'")

# Test Turn creation
turn = Turn(
    turn_index=0,
    spreader_message=Message(role=AgentRole.SPREADER, content="Spreader text"),
    debunker_message=Message(role=AgentRole.DEBUNKER, content="Debunker text")
)
print(f"✅ Turn created: turn_index={turn.turn_index}")
print(f"   Spreader: {turn.spreader_message.content}")
print(f"   Debunker: {turn.debunker_message.content}")

print("Message import test complete!")
