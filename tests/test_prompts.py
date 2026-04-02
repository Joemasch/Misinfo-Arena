#!/usr/bin/env python3
"""
Test prompts.json load/save functionality
"""

import sys
import os
import json
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions we want to test
from arena.io.prompts_store import load_prompts_file, save_prompts_file
from arena.app_config import PROMPTS_PATH, SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT

def test_load_empty():
    """Test loading when file doesn't exist"""
    print("=== Testing load_prompts_file (no file) ===")

    # Ensure file doesn't exist
    if PROMPTS_PATH.exists():
        PROMPTS_PATH.unlink()

    result = load_prompts_file()
    print(f"Result: {result}")
    assert result == {}, f"Expected empty dict, got {result}"
    print("✅ Returns empty dict when file doesn't exist")

def test_save_and_load():
    """Test saving and loading prompts"""
    print("\n=== Testing save_prompts_file and load_prompts_file ===")

    test_data = {
        "spreader_prompt": "Test spreader prompt",
        "debunker_prompt": "Test debunker prompt"
    }

    # Save data
    save_prompts_file(test_data)
    print(f"✅ Saved test data to {PROMPTS_PATH}")

    # Load data back
    loaded_data = load_prompts_file()
    print(f"Loaded data: {loaded_data}")

    assert loaded_data == test_data, f"Data mismatch: {loaded_data} != {test_data}"
    print("✅ Save and load round-trip works")

def test_load_malformed():
    """Test loading malformed JSON"""
    print("\n=== Testing load_prompts_file (malformed JSON) ===")

    # Write malformed JSON
    PROMPTS_PATH.write_text("{invalid json", encoding="utf-8")

    result = load_prompts_file()
    print(f"Result with malformed JSON: {result}")
    assert result == {}, f"Expected empty dict for malformed JSON, got {result}"
    print("✅ Gracefully handles malformed JSON")

def test_integration():
    """Test the full integration flow"""
    print("\n=== Testing integration with defaults ===")

    # Clean up first
    if PROMPTS_PATH.exists():
        PROMPTS_PATH.unlink()

    # Simulate what happens in initialize_session_state
    data = load_prompts_file()
    spreader_init = data.get("spreader_prompt", SPREADER_SYSTEM_PROMPT)
    debunker_init = data.get("debunker_prompt", DEBUNKER_SYSTEM_PROMPT)

    assert spreader_init == SPREADER_SYSTEM_PROMPT, "Should fallback to default"
    assert debunker_init == DEBUNKER_SYSTEM_PROMPT, "Should fallback to default"
    print("✅ Fallback to defaults works when no file exists")

    # Now save custom prompts
    custom_spreader = "Custom spreader prompt for testing"
    custom_debunker = "Custom debunker prompt for testing"

    save_prompts_file({
        "spreader_prompt": custom_spreader,
        "debunker_prompt": custom_debunker,
    })

    # Load them back
    data = load_prompts_file()
    loaded_spreader = data.get("spreader_prompt", SPREADER_SYSTEM_PROMPT)
    loaded_debunker = data.get("debunker_prompt", DEBUNKER_SYSTEM_PROMPT)

    assert loaded_spreader == custom_spreader, "Should load custom spreader"
    assert loaded_debunker == custom_debunker, "Should load custom debunker"
    print("✅ Custom prompts persist correctly")

def cleanup():
    """Clean up test file"""
    if PROMPTS_PATH.exists():
        PROMPTS_PATH.unlink()
        print(f"\n🧹 Cleaned up {PROMPTS_PATH}")

if __name__ == "__main__":
    try:
        test_load_empty()
        test_save_and_load()
        test_load_malformed()
        test_integration()
        print("\n🎉 ALL PROMPT PERSISTENCE TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()

