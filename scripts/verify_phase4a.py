#!/usr/bin/env python3
"""
Phase 4A verification: run metadata ingestion + long-format analytics.
Run from repo root: PYTHONPATH=src python tools/verify_phase4a.py
Exit 0 on success; exit 1 on validation failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure arena is importable
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from arena.analysis.episode_dataset import (
    CANONICAL_METRICS,
    build_episode_df,
    build_episode_long_df,
)


def discover_run_ids(runs_dir: Path) -> list[str]:
    """Discover run_ids: subdirs that have episodes.jsonl."""
    if not runs_dir.exists():
        return []
    ids = []
    for child in sorted(runs_dir.iterdir()):
        if child.is_dir() and (child / "episodes.jsonl").exists():
            ids.append(child.name)
    return ids


def count_complete_episodes(runs_dir: Path, run_ids: list[str]) -> int:
    """Count episodes with results.scorecard (list with items)."""
    total = 0
    for run_id in run_ids:
        ep_path = runs_dir / run_id / "episodes.jsonl"
        if not ep_path.exists():
            continue
        with open(ep_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ep = json.loads(line)
                    sc = (ep.get("results") or {}).get("scorecard")
                    if isinstance(sc, list) and len(sc) > 0:
                        total += 1
                except json.JSONDecodeError:
                    pass
    return total


def main() -> int:
    runs_dir = _root / "runs"
    run_ids = discover_run_ids(runs_dir)
    if not run_ids:
        print("No runs discovered (runs/ has no subdirs with episodes.jsonl)")
        return 0

    wide_df, warnings = build_episode_df(run_ids, runs_dir=str(runs_dir), refresh_token=0.0)
    long_df = build_episode_long_df(run_ids, runs_dir=str(runs_dir), refresh_token=0.0)

    n_episodes = len(wide_df)
    complete_eps = count_complete_episodes(runs_dir, run_ids)
    expected_rows = complete_eps * 6 * 2

    # Output
    lines = []
    lines.append("=== Phase 4A Verification ===\n")
    lines.append(f"Runs discovered: {len(run_ids)}")
    lines.append(f"Episodes in wide_df: {n_episodes}")
    lines.append(f"Complete episodes (with scorecard): {complete_eps}")
    lines.append(f"Expected long rows (complete_eps * 6 * 2): {expected_rows}")
    lines.append(f"Actual long_df rows: {len(long_df)}")
    lines.append("")

    # Wide columns
    wide_cols = ["arena_type", "run_spreader_model", "run_debunker_model", "run_judge_model", "judge_mode"]
    for col in wide_cols:
        present = col in wide_df.columns
        lines.append(f"wide_df has '{col}': {present}")
    lines.append("")

    # arena_type value_counts
    if "arena_type" in wide_df.columns:
        lines.append("arena_type value_counts (top 10):")
        vc = wide_df["arena_type"].value_counts()
        for val, cnt in vc.head(10).items():
            lines.append(f"  {val}: {cnt}")
    else:
        lines.append("arena_type: COLUMN MISSING")
    lines.append("")

    # Long df stats
    if not long_df.empty:
        lines.append("long_df unique metric_name (sorted):")
        metrics = sorted(long_df["metric_name"].dropna().unique().tolist())
        lines.append(f"  {metrics}")
        lines.append("")
        lines.append("long_df side value_counts:")
        for side, cnt in long_df["side"].value_counts().items():
            lines.append(f"  {side}: {cnt}")
        lines.append("")
        pct_missing = long_df["metric_value"].isna().mean() * 100
        lines.append(f"percent missing metric_value: {pct_missing:.2f}%")
        pct_null_arena = long_df["arena_type"].isna().mean() * 100
        lines.append(f"percent null arena_type: {pct_null_arena:.2f}%")
    else:
        lines.append("long_df is empty")
    lines.append("")

    output = "\n".join(lines)
    print(output)

    # Validation failures → exit 1
    def fail(msg: str) -> None:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)

    if complete_eps > 0 and long_df.empty:
        fail("long_df is empty but there are complete episodes")

    if "arena_type" not in wide_df.columns:
        fail("arena_type column missing from wide_df")

    if not long_df.empty and "arena_type" not in long_df.columns:
        fail("arena_type column missing from long_df")

    if not long_df.empty:
        long_metrics = set(long_df["metric_name"].dropna().unique())
        if not set(CANONICAL_METRICS).issubset(long_metrics):
            missing = set(CANONICAL_METRICS) - long_metrics
            fail(f"long_df metric_name missing canonical metrics: {missing}")

        sides = set(long_df["side"].dropna().unique())
        if sides != {"spreader", "debunker"}:
            fail(f"long_df sides must be exactly {{'spreader','debunker'}}, got {sides}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
