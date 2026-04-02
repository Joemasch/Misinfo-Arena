#!/usr/bin/env python3
"""
Test if DEFAULT_USER_PROMPT_TEMPLATE constant is accessible
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to read the constant directly from the file
try:
    with open('arena/agents.py', 'r') as f:
        content = f.read()

    # Look for the constant definition
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('DEFAULT_USER_PROMPT_TEMPLATE ='):
            print("✅ Found constant definition in arena/agents.py")
            # Extract the constant value
            constant_line = line
            # Handle multi-line strings
            if '"""' in line or "'''" in line:
                # Multi-line string
                quote_type = '"""' if '"""' in line else "'''"
                start_idx = line.find(quote_type)
                if start_idx != -1:
                    # Find the end of the multi-line string
                    remaining = line[start_idx + 3:]
                    if quote_type in remaining:
                        # Single line
                        value = remaining.split(quote_type)[0]
                    else:
                        # Multi-line - this is a simple case, assume it's on one line
                        value = remaining.rstrip(quote_type).rstrip()
                else:
                    value = line.split('=')[1].strip().strip('"\'')
            else:
                # Single line string
                value = line.split('=', 1)[1].strip().strip('"\'')
            print(f"Constant value: {repr(value[:80])}...")
            break
    else:
        print("❌ DEFAULT_USER_PROMPT_TEMPLATE constant not found in arena/agents.py")

except Exception as e:
    print(f"❌ Error reading file: {e}")

# Try importing with fallback
print("\n=== Testing app.py import logic ===")
try:
    from arena.agents import DEFAULT_USER_PROMPT_TEMPLATE
    print("✅ Direct import successful")
    print(f"Value: {repr(DEFAULT_USER_PROMPT_TEMPLATE[:50])}...")
except ImportError as e:
    print(f"❌ Direct import failed: {e}")
    # Test fallback
    fallback = "Debate claim: {topic}\nOpponent last message:\n{opponent_text}\n\nWrite your next reply:"
    print(f"✅ Using fallback: {repr(fallback[:50])}...")

print("\n=== Testing app.py build_prompt_snapshot logic ===")
try:
    # Simulate the try/except logic from app.py
    try:
        from arena.agents import DEFAULT_USER_PROMPT_TEMPLATE
        print("✅ Try block succeeded")
    except ImportError:
        DEFAULT_USER_PROMPT_TEMPLATE = "Debate claim: {topic}\nOpponent last message:\n{opponent_text}\n\nWrite your next reply:"
        print("✅ Fallback used in except block")

    print(f"Final constant value: {repr(DEFAULT_USER_PROMPT_TEMPLATE[:50])}...")

except Exception as e:
    print(f"❌ Unexpected error: {e}")


