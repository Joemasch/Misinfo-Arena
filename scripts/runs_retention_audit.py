#!/usr/bin/env python3
"""
Runs retention audit: inventory all runs for RUNS_RETENTION_AND_ARCHIVE_PLAN.md.
Run from repo root: python tools/runs_retention_audit.py
Outputs JSON for downstream MD generation.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))


def load_run_json(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_episodes(path: Path) -> list[dict]:
    episodes = []
    if not path.exists():
        return episodes
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


def main() -> dict:
    runs_dir = _root / "runs"
    if not runs_dir.exists():
        return {"runs": [], "error": "runs/ not found"}

    inventory = []
    for child in sorted(runs_dir.iterdir()):
        if not child.is_dir():
            continue
        run_id = child.name
        run_json_path = child / "run.json"
        episodes_path = child / "episodes.jsonl"

        if not episodes_path.exists():
            continue

        run_json = load_run_json(run_json_path) if run_json_path.exists() else None
        episodes = load_episodes(episodes_path)

        created_at = (run_json or {}).get("created_at", "")
        arena_type = (run_json or {}).get("arena_type", "")
        run_config = (run_json or {}).get("run_config") or {}
        agents = run_config.get("agents") or {}

        def _model(role: str) -> str:
            a = agents.get(role) or {}
            m = a.get("model") if isinstance(a, dict) else None
            return str(m) if m else ""

        models_str = f"spreader={_model('spreader')} debunker={_model('debunker')} judge={_model('judge')}"

        episode_count = len(episodes)
        complete_count = 0
        incomplete_count = 0
        error_count = 0
        judge_mode_counts: Counter[str] = Counter()
        claims: list[str] = []

        for ep in episodes:
            results = ep.get("results") or {}
            scorecard = results.get("scorecard")
            judge_audit = ep.get("judge_audit") or {}

            has_scorecard = isinstance(scorecard, list) and len(scorecard) > 0
            if has_scorecard:
                complete_count += 1
            else:
                incomplete_count += 1

            status = judge_audit.get("status")
            mode = judge_audit.get("mode") or "(missing)"
            err_msg = judge_audit.get("error_message")

            is_error = (
                status not in (None, "success", "ok")
                or bool(err_msg)
                or mode in ("(missing)", "missing")
            )
            if is_error:
                error_count += 1

            judge_mode_counts[mode] += 1

            c = (ep.get("claim") or "").strip()
            if c and c not in claims:
                claims.append(c)

        claim_preview = claims[0][:60] + "..." if len(claims) == 1 and len(claims[0]) > 60 else (claims[0][:40] if claims else "(none)")
        if len(claims) > 1:
            claim_preview = f"multi ({len(claims)} claims)"

        tags = []
        if arena_type == "single_claim" and complete_count == episode_count and error_count == 0 and episode_count >= 2:
            tags.append("baseline_candidate")
        if "golden" in arena_type.lower() or "golden" in run_id.lower():
            tags.append("golden_run")
        if incomplete_count > 0 or episode_count < 2:
            tags.append("dev_partial")
        if error_count > 0:
            tags.append("error_heavy")

        inventory.append({
            "run_id": run_id,
            "created_at": created_at,
            "arena_type": arena_type,
            "episode_count": episode_count,
            "complete_episode_count": complete_count,
            "incomplete_episode_count": incomplete_count,
            "error_episode_count": error_count,
            "judge_mode_counts": dict(judge_mode_counts),
            "models": models_str,
            "claim_preview": claim_preview,
            "tags": tags,
            "run_json_exists": run_json_path.exists(),
        })

    # Sort newest first (by created_at, then by run_id as tiebreaker)
    def sort_key(r):
        return (r["created_at"] or "", r["run_id"] or "")

    inventory.sort(key=sort_key, reverse=True)

    return {"runs": inventory, "total_runs": len(inventory)}


if __name__ == "__main__":
    out = main()
    print(json.dumps(out, indent=2, default=str))
