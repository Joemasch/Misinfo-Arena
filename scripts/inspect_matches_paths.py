#!/usr/bin/env python3
"""
Inspection script for Arena-to-Replay data pipeline paths.
Captures absolute paths, file existence, and filesystem stats.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
script_dir = Path(__file__).resolve().parent.parent
src_dir = script_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

def inspect_matches_paths():
    """Inspect all potential matches.jsonl paths and their status."""

    print("=== ARENA-TO-REPLAY FEED INSPECTION ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Script location: {__file__}")
    print(f"Current working directory: {os.getcwd()}")
    print()

    # Import config to get DEFAULT_MATCHES_PATH
    try:
        from arena.app_config import DEFAULT_MATCHES_PATH
        default_path = Path(DEFAULT_MATCHES_PATH)
        print(f"DEFAULT_MATCHES_PATH: {DEFAULT_MATCHES_PATH}")
        print(f"Resolved absolute path: {default_path.resolve()}")
        print(f"Exists: {default_path.exists()}")

        if default_path.exists():
            stat = default_path.stat()
            print(f"Size: {stat.st_size} bytes")
            print(f"Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat()}")

            # Count lines and show last 3
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"Line count: {len(lines)}")

                    if lines:
                        print("Last 3 lines (truncated to 200 chars each):")
                        for i, line in enumerate(lines[-3:], len(lines)-2):
                            truncated = line.strip()[:200]
                            if len(line.strip()) > 200:
                                truncated += "..."
                            print(f"  Line {i}: {truncated}")
                    else:
                        print("File is empty")
            except Exception as e:
                print(f"Error reading file: {e}")
        else:
            print("File does not exist")

        print()
    except ImportError as e:
        print(f"ERROR: Could not import DEFAULT_MATCHES_PATH: {e}")
        print()

    # Search for all matches.jsonl files in the repo
    print("=== SEARCHING FOR ALL matches.jsonl FILES IN REPO ===")

    repo_root = script_dir
    matches_files = []

    for root, dirs, files in os.walk(repo_root):
        # Skip common directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', '.git']]

        for file in files:
            if file == 'matches.jsonl':
                full_path = Path(root) / file
                matches_files.append(full_path)

    if matches_files:
        print(f"Found {len(matches_files)} matches.jsonl file(s):")
        for i, path in enumerate(matches_files, 1):
            abs_path = path.resolve()
            print(f"\n{i}. {abs_path}")
            print(f"   Relative: {path.relative_to(repo_root)}")
            print(f"   Exists: {path.exists()}")

            if path.exists():
                stat = path.stat()
                print(f"   Size: {stat.st_size} bytes")
                print(f"   Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat()}")

                # Count lines
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        print(f"   Line count: {len(lines)}")

                        if lines and len(lines) > 0:
                            last_line = lines[-1].strip()[:200]
                            if len(lines[-1].strip()) > 200:
                                last_line += "..."
                            print(f"   Last line: {last_line}")
                except Exception as e:
                    print(f"   Error reading: {e}")
    else:
        print("No matches.jsonl files found in repository")

    print()

    # Check analytics storage path (if we can infer it)
    print("=== ANALYTICS STORAGE PATH ANALYSIS ===")

    try:
        # Try to import and inspect analytics/storage setup
        from arena.state import initialize_session_state
        from arena.factories import create_match_storage

        # Create a storage instance to see what path it uses
        storage = create_match_storage()
        storage_path = Path(storage.full_path)

        print("Analytics storage configuration:")
        print(f"Storage dir: {storage.storage_dir}")
        print(f"Filename: {storage.filename}")
        print(f"Full path: {storage.full_path}")
        print(f"Resolved: {storage_path.resolve()}")
        print(f"Exists: {storage_path.exists()}")

        if storage_path.exists():
            stat = storage_path.stat()
            print(f"Size: {stat.st_size} bytes")
            print(f"Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat()}")

            try:
                with open(storage_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"Line count: {len(lines)}")
            except Exception as e:
                print(f"Error reading: {e}")

    except Exception as e:
        print(f"Could not inspect analytics storage: {e}")

if __name__ == "__main__":
    inspect_matches_paths()

