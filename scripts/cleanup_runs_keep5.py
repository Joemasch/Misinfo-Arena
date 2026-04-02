#!/usr/bin/env python3
"""
Runs cleanup: keep 5 baseline runs, archive the rest to runs_archive/.
Idempotent: skips if already archived. Copy first, validate, then remove.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

KEEP_RUN_IDS = frozenset({
    "20260226_130331_1a70",
    "20260225_174748_6341",
    "20260225_162125_c82c",
    "20260225_160536_881b",
    "golden_v1_20260223_210258",
})

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
ARCHIVE_ROOT = ROOT / "runs_archive"
ARCHIVE_GOLDEN = ARCHIVE_ROOT / "golden"
ARCHIVE_DEV = ARCHIVE_ROOT / "dev"
ARCHIVE_ERROR = ARCHIVE_ROOT / "error"
ARCHIVE_LEGACY = ARCHIVE_ROOT / "legacy"


def _load_run_json(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_episodes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    episodes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return episodes


def classify_run(run_dir: Path) -> str:
    """Return archive bucket: golden, dev, or error."""
    run_id = run_dir.name
    if "golden" in run_id.lower():
        return "golden"

    run_json = _load_run_json(run_dir / "run.json")
    arena_type = (run_json or {}).get("arena_type", "")
    if "golden" in arena_type.lower():
        return "golden"

    episodes = _load_episodes(run_dir / "episodes.jsonl")
    incomplete = 0
    error_count = 0

    for ep in episodes:
        results = ep.get("results") or {}
        scorecard = results.get("scorecard")
        has_scorecard = isinstance(scorecard, list) and len(scorecard) > 0
        if not has_scorecard:
            incomplete += 1

        judge_audit = ep.get("judge_audit") or {}
        status = judge_audit.get("status")
        mode = judge_audit.get("mode")
        err_msg = judge_audit.get("error_message")
        is_error = (
            status not in (None, "success", "ok")
            or bool(err_msg)
            or mode in (None, "", "(missing)", "missing")
        )
        if is_error:
            error_count += 1

    if incomplete > 0 or error_count > 0:
        return "error"
    return "dev"


def main() -> int:
    if not RUNS_DIR.exists():
        print("runs/ not found")
        return 0

    for d in (ARCHIVE_GOLDEN, ARCHIVE_DEV, ARCHIVE_ERROR, ARCHIVE_LEGACY):
        d.mkdir(parents=True, exist_ok=True)

    matches_copied = False
    matches_src = RUNS_DIR / "matches.jsonl"
    matches_dest = ARCHIVE_LEGACY / "matches.jsonl"
    if matches_src.exists() and (not matches_dest.exists() or matches_dest.stat().st_size < matches_src.stat().st_size):
        shutil.copy2(matches_src, matches_dest)
        matches_copied = True

    kept = []
    archived = []
    by_bucket = {"golden": 0, "dev": 0, "error": 0}

    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name

        if run_id in KEEP_RUN_IDS:
            kept.append(run_id)
            continue

        bucket = classify_run(run_dir)
        dest_dir = ARCHIVE_ROOT / bucket / run_id

        if dest_dir.exists():
            # Already archived; ensure runs/ is clean (idempotent)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            continue

        # Copy first
        try:
            shutil.copytree(run_dir, dest_dir)
        except Exception as e:
            print(f"ERROR: Failed to copy {run_id}: {e}", file=sys.stderr)
            return 1

        # Validate: key files exist in copy
        if not (dest_dir / "episodes.jsonl").exists():
            print(f"ERROR: Copy invalid for {run_id} (no episodes.jsonl)", file=sys.stderr)
            shutil.rmtree(dest_dir, ignore_errors=True)
            return 1

        # Remove from runs/
        shutil.rmtree(run_dir)
        archived.append(run_id)
        by_bucket[bucket] += 1

    print("=== Cleanup Summary ===")
    print(f"Kept: {len(kept)} runs")
    for r in kept:
        print(f"  - {r}")
    print(f"Archived: {len(archived)} runs")
    print(f"  golden: {by_bucket['golden']}")
    print(f"  dev:    {by_bucket['dev']}")
    print(f"  error:  {by_bucket['error']}")
    if archived:
        print("Moved run_ids:", archived)
    if matches_copied:
        print("matches.jsonl copied to runs_archive/legacy/matches.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
