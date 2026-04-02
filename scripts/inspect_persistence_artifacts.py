#!/usr/bin/env python3
"""
Inspection script for Arena persistence artifacts.

Captures filesystem state of runs/matches.jsonl for forensic analysis.
"""

import os
import json
from pathlib import Path
from datetime import datetime

def inspect_matches_file():
    """Inspect the current state of matches.jsonl"""

    print("=== PERSISTENCE ARTIFACTS INSPECTION ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Current working directory: {os.getcwd()}")
    print()

    # Import just the config to get DEFAULT_MATCHES_PATH
    try:
        # Add src to path temporarily
        import sys
        src_path = Path(__file__).resolve().parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from arena.app_config import DEFAULT_MATCHES_PATH

        matches_path = Path(DEFAULT_MATCHES_PATH)
        resolved_path = matches_path.resolve()

        print("DEFAULT_MATCHES_PATH configuration:")
        print(f"  Raw path: {DEFAULT_MATCHES_PATH}")
        print(f"  Resolved absolute: {resolved_path}")
        print(f"  Exists: {matches_path.exists()}")
        print()

        if matches_path.exists():
            stat = matches_path.stat()
            print("File metadata:")
            print(f"  Size: {stat.st_size} bytes")
            print(f"  Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat()}")
            print(f"  Permissions: {oct(stat.st_mode)[-3:]}")
            print()

            # Count lines and show sample
            try:
                with open(matches_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    print(f"Content analysis:")
                    print(f"  Total lines: {line_count}")

                    if lines:
                        # Show last 2 lines (truncated)
                        print("  Last 2 lines (truncated to 200 chars each):")
                        for i, line in enumerate(lines[-2:], max(1, line_count-1)):
                            truncated = line.strip()[:200]
                            if len(line.strip()) > 200:
                                truncated += "..."
                            print(f"    Line {i}: {truncated}")
                        print()

                        # Try to parse the last line as JSON to show structure
                        try:
                            last_obj = json.loads(lines[-1].strip())
                            print("  Last line JSON structure:")
                            print(f"    Top-level keys: {list(last_obj.keys())}")
                            for key in ['match_id', 'timestamp', 'topic', 'winner', 'judge_decision']:
                                if key in last_obj:
                                    value = last_obj[key]
                                    if isinstance(value, (list, dict)):
                                        print(f"    {key}: {type(value).__name__} with {len(value)} items")
                                    else:
                                        print(f"    {key}: {repr(str(value)[:50])}...")
                            print()
                        except json.JSONDecodeError as e:
                            print(f"  Last line JSON parsing failed: {e}")
                            print()
                    else:
                        print("  File is empty")
                        print()

            except Exception as e:
                print(f"Error reading file: {e}")
                print()
        else:
            print("File does not exist - no matches have been persisted yet")
            print()

    except ImportError as e:
        print(f"ERROR: Could not import configuration: {e}")
        print("This suggests the arena modules are not properly set up.")
        print()

    # Check for any other JSONL files in runs/
    runs_dir = Path("runs")
    if runs_dir.exists():
        jsonl_files = list(runs_dir.glob("*.jsonl"))
        if jsonl_files:
            print("Other JSONL files in runs/ directory:")
            for jsonl_file in jsonl_files:
                if jsonl_file.name != "matches.jsonl":
                    stat = jsonl_file.stat()
                    print(f"  {jsonl_file.name}: {stat.st_size} bytes, modified {datetime.fromtimestamp(stat.st_mtime).isoformat()}")
            print()

    print("=== END INSPECTION ===")

if __name__ == "__main__":
    inspect_matches_file()

