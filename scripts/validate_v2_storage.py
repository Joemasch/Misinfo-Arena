#!/usr/bin/env python3
"""
Validate JSON v2 storage structure.

Scans runs/*/run.json and runs/*/episodes.jsonl files to verify:
- Required keys exist
- Episode counts per run
- Latest created_at timestamps
- Basic schema compliance
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List


def validate_run_json(run_path: Path) -> Dict[str, Any]:
    """Validate a run.json file and return summary."""
    try:
        with open(run_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check required keys
        required_keys = ["schema_version", "run_id", "created_at", "arena_type", "run_config"]
        missing = [k for k in required_keys if k not in data]

        return {
            "valid": len(missing) == 0,
            "missing_keys": missing,
            "run_id": data.get("run_id", "unknown"),
            "arena_type": data.get("arena_type", "unknown"),
            "created_at": data.get("created_at", "unknown"),
            "episode_count": data.get("run_config", {}).get("episode_count", 0)
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "run_id": run_path.parent.name
        }


def validate_episodes_jsonl(episodes_path: Path) -> Dict[str, Any]:
    """Validate an episodes.jsonl file and return summary."""
    if not episodes_path.exists():
        return {"valid": False, "error": "File does not exist", "episode_count": 0}

    episodes = []
    try:
        with open(episodes_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        episode = json.loads(line)
                        episodes.append(episode)
                    except json.JSONDecodeError as e:
                        return {
                            "valid": False,
                            "error": f"JSON error at line {line_num}: {e}",
                            "episode_count": len(episodes)
                        }

        # Check required keys in first episode
        if episodes:
            required_keys = ["schema_version", "run_id", "episode_id", "created_at", "claim"]
            first_episode = episodes[0]
            missing = [k for k in required_keys if k not in first_episode]

            # Find latest created_at
            latest_created = max((ep.get("created_at", "") for ep in episodes), default="")

            return {
                "valid": len(missing) == 0,
                "missing_keys": missing,
                "episode_count": len(episodes),
                "latest_created": latest_created,
                "run_id": first_episode.get("run_id", "unknown")
            }
        else:
            return {"valid": True, "episode_count": 0, "run_id": "unknown"}

    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "episode_count": len(episodes)
        }


def main():
    """Main validation function."""
    runs_dir = Path("runs")

    if not runs_dir.exists():
        print("❌ runs/ directory does not exist")
        return

    print("🔍 Validating JSON v2 storage structure...\n")

    total_runs = 0
    valid_runs = 0
    total_episodes = 0

    # Find all run directories
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue

        run_id = run_dir.name
        total_runs += 1

        print(f"📁 Run: {run_id}")

        # Validate run.json
        run_path = run_dir / "run.json"
        if run_path.exists():
            run_validation = validate_run_json(run_path)
            if run_validation["valid"]:
                print(f"  ✅ run.json: {run_validation['arena_type']} arena, created {run_validation['created_at']}")
                valid_runs += 1
            else:
                print(f"  ❌ run.json: Invalid - missing keys: {run_validation['missing_keys']}")
                if "error" in run_validation:
                    print(f"      Error: {run_validation['error']}")
        else:
            print("  ❌ run.json: Missing")

        # Validate episodes.jsonl
        episodes_path = run_dir / "episodes.jsonl"
        episodes_validation = validate_episodes_jsonl(episodes_path)
        if episodes_validation["valid"]:
            episode_count = episodes_validation["episode_count"]
            total_episodes += episode_count
            if episode_count > 0:
                print(f"  ✅ episodes.jsonl: {episode_count} episodes, latest {episodes_validation.get('latest_created', 'unknown')}")
            else:
                print("  ✅ episodes.jsonl: Empty (no episodes yet)")
        else:
            print(f"  ❌ episodes.jsonl: Invalid - {episodes_validation.get('error', 'unknown error')}")

        print()

    # Summary
    print("📊 Summary:")
    print(f"  Total runs: {total_runs}")
    print(f"  Valid runs: {valid_runs}")
    print(f"  Total episodes: {total_episodes}")

    if valid_runs == total_runs and total_runs > 0:
        print("🎉 All runs are valid!")
    elif total_runs == 0:
        print("ℹ️  No runs found - run some debates first")
    else:
        print(f"⚠️  {total_runs - valid_runs} runs have validation issues")


if __name__ == "__main__":
    main()

