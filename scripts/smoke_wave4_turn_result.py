#!/usr/bin/env python3
"""
Smoke test for Wave 4 Turn Result contract.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from arena.application.types import TurnPairResult

# Test basic functionality
r = TurnPairResult(ok=True, turn_idx=1, spreader_text="a", debunker_text="b").to_dict()
assert r["ok"] is True
assert r["turn_idx"] == 1
assert r["spreader_text"] == "a"
assert r["debunker_text"] == "b"
assert isinstance(r["debug"], dict)

# Test with concessions
r2 = TurnPairResult(
    ok=True,
    spreader_conceded=True,
    debunker_conceded=False,
    completion_reason="Test concession",
    match_completed=True
).to_dict()
assert r2["spreader_conceded"] is True
assert r2["debunker_conceded"] is False
assert r2["completion_reason"] == "Test concession"
assert r2["match_completed"] is True

print("OK: TurnPairResult.to_dict() works correctly")
