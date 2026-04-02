#!/usr/bin/env python3
"""
Smoke test for Wave 5 Run Store integration.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from arena.io.run_store import append_match_jsonl, load_matches_jsonl

def test_run_store():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "matches.jsonl")

        # Test appending matches
        append_match_jsonl(p, {"hello": "world", "n": 1})
        append_match_jsonl(p, {"hello": "again", "n": 2})

        # Test loading matches
        rows = load_matches_jsonl(p)
        assert len(rows) == 2
        assert rows[0]["n"] == 1
        assert rows[1]["n"] == 2

        print("OK: run_store append/load works")

if __name__ == "__main__":
    import sys
    test_run_store()
