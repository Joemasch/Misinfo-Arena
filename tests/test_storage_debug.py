#!/usr/bin/env python3
"""
Test storage path debugging.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set debug flag
DEBUG_SANITY = True

# Test storage path computation
from arena.storage import MatchStorage

print("Testing storage path computation...")

storage = MatchStorage()
print(f"Storage dir: {storage.storage_dir}")
print(f"Storage file: {storage.filename}")
print(f"Full path: {storage.full_path}")
print(f"Directory exists: {os.path.exists(storage.storage_dir)}")
print(f"File exists: {os.path.exists(storage.full_path)}")

# Test repo root calculation
repo_root = Path(__file__).resolve().parents[1]
runs_dir = repo_root / "runs"
print(f"Computed repo root: {repo_root}")
print(f"Computed runs dir: {runs_dir}")
print(f"Repo root exists: {repo_root.exists()}")
print(f"Parent of arena: {(Path(__file__).resolve().parents[1])}")

print("Storage path test complete!")


