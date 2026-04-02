#!/usr/bin/env python3
"""
Read-only audit script for runs/ folder.
Collects stats for RUNS_FOLDER_AND_EPISODE_SCHEMA_AUDIT.md.
Run from repo root: python tools/runs_audit_script.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
CANONICAL_METRICS = {"truthfulness_proxy", "evidence_quality", "reasoning_quality", "responsiveness", "persuasion", "civility"}


def main() -> dict:
    runs_path = RUNS_DIR
    if not runs_path.exists():
        return {"error": "runs/ not found"}

    run_dirs = [d for d in runs_path.iterdir() if d.is_dir()]
    run_count = len(run_dirs)

    # Per-run overview
    overview = []
    all_episodes: list[dict] = []
    run_episode_map: dict[str, list[dict]] = defaultdict(list)

    for run_dir in sorted(run_dirs):
        run_id = run_dir.name
        run_json_path = run_dir / "run.json"
        episodes_path = run_dir / "episodes.jsonl"
        matches_path = run_dir / "matches.jsonl"

        has_run_json = run_json_path.exists()
        has_episodes = episodes_path.exists()
        has_matches = matches_path.exists()

        episode_count = 0
        if has_episodes:
            with open(episodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ep = json.loads(line)
                        episode_count += 1
                        all_episodes.append(ep)
                        run_episode_map[run_id].append(ep)
                    except json.JSONDecodeError:
                        pass

        overview.append({
            "run_id": run_id,
            "has_run_json": has_run_json,
            "episode_count": episode_count,
            "has_matches_jsonl": has_matches,
        })

    # Episode schema integrity
    total_episodes = len(all_episodes)
    missing_results = sum(1 for ep in all_episodes if ep.get("results") is None)
    missing_scorecard = sum(1 for ep in all_episodes if (ep.get("results") or {}).get("scorecard") is None)
    missing_totals = sum(1 for ep in all_episodes if (ep.get("results") or {}).get("totals") is None)
    missing_winner = sum(1 for ep in all_episodes if (ep.get("results") or {}).get("winner") is None)
    missing_judge_confidence = sum(1 for ep in all_episodes if (ep.get("results") or {}).get("judge_confidence") is None)
    missing_judge_audit = sum(1 for ep in all_episodes if ep.get("judge_audit") is None)

    error_flag_count = 0
    for ep in all_episodes:
        ja = ep.get("judge_audit") or {}
        status = ja.get("status")
        mode = ja.get("mode")
        error_msg = ja.get("error_message")
        is_error = (status != "success") or (mode != "agent" and mode != "heuristic") or bool(error_msg)
        if is_error:
            error_flag_count += 1

    # Metric consistency
    all_metrics: Counter[str] = Counter()
    episodes_with_scorecard = 0
    for ep in all_episodes:
        scorecard = (ep.get("results") or {}).get("scorecard") or []
        if not isinstance(scorecard, list):
            continue
        episodes_with_scorecard += 1
        for item in scorecard:
            if isinstance(item, dict) and item.get("metric"):
                all_metrics[item["metric"]] += 1

    missing_metrics = CANONICAL_METRICS - set(all_metrics.keys())
    extra_metrics = set(all_metrics.keys()) - CANONICAL_METRICS

    # Judge mode
    mode_counts: Counter[str] = Counter()
    config_vs_audit_mismatch = 0
    for ep in all_episodes:
        ja = ep.get("judge_audit") or {}
        mode = ja.get("mode")
        mode_counts[mode if mode else "(missing)"] += 1

        config_judge = ((ep.get("config_snapshot") or {}).get("agents") or {}).get("judge") or {}
        config_type = config_judge.get("type") if isinstance(config_judge, dict) else None
        if mode and config_type and mode != config_type:
            config_vs_audit_mismatch += 1

    # Model metadata
    spreader_models: Counter[str] = Counter()
    debunker_models: Counter[str] = Counter()
    judge_models: Counter[str] = Counter()
    missing_spreader = 0
    missing_debunker = 0
    missing_judge_model = 0
    for ep in all_episodes:
        agents = (ep.get("config_snapshot") or {}).get("agents") or {}
        sp = (agents.get("spreader") or {})
        db = (agents.get("debunker") or {})
        jg = (agents.get("judge") or {})
        sp_model = sp.get("model") if isinstance(sp, dict) else None
        db_model = db.get("model") if isinstance(db, dict) else None
        jg_model = jg.get("model") if isinstance(jg, dict) else None

        if sp_model:
            spreader_models[sp_model] += 1
        else:
            missing_spreader += 1
        if db_model:
            debunker_models[db_model] += 1
        else:
            missing_debunker += 1
        if jg_model:
            judge_models[jg_model] += 1
        else:
            missing_judge_model += 1

    # Run-level metadata (run.json)
    run_jsons: list[dict] = []
    arena_type_values: Counter[str] = Counter()
    runs_missing_arena_type = 0
    run_json_keys: dict[str, int] = defaultdict(int)
    run_config_keys: dict[str, int] = defaultdict(int)
    run_agents_keys: dict[str, int] = defaultdict(int)
    run_judge_weights_keys: dict[str, int] = defaultdict(int)

    for run_dir in sorted(run_dirs):
        run_json_path = run_dir / "run.json"
        if not run_json_path.exists():
            continue
        try:
            with open(run_json_path, "r", encoding="utf-8") as f:
                rj = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        run_jsons.append(rj)
        arena = rj.get("arena_type")
        if arena:
            arena_type_values[arena] += 1
        else:
            runs_missing_arena_type += 1
        for k in rj.keys():
            run_json_keys[k] += 1
        rc = rj.get("run_config") or {}
        for k in rc.keys():
            run_config_keys[k] += 1
        ag = rc.get("agents") or {}
        for k in ag.keys():
            run_agents_keys[k] += 1
        jw = rc.get("judge_weights") or {}
        for k in jw.keys():
            run_judge_weights_keys[k] += 1

    # Schema drift - episode fields
    ep_field_counts: dict[str, int] = defaultdict(int)
    for ep in all_episodes:
        for k in ep.keys():
            ep_field_counts[k] += 1
    ep_field_pct = {k: (v / total_episodes * 100) if total_episodes else 0 for k, v in ep_field_counts.items()}

    # Schema drift - run.json fields
    rj_count = len(run_jsons)
    run_field_pct = {k: (v / rj_count * 100) if rj_count else 0 for k, v in run_json_keys.items()}

    return {
        "overview": overview,
        "total_runs": run_count,
        "total_episodes": total_episodes,
        "episode_integrity": {
            "missing_results": missing_results,
            "missing_scorecard": missing_scorecard,
            "missing_totals": missing_totals,
            "missing_winner": missing_winner,
            "missing_judge_confidence": missing_judge_confidence,
            "missing_judge_audit": missing_judge_audit,
            "error_flag_count": error_flag_count,
        },
        "metrics": {
            "all_metrics": dict(all_metrics),
            "missing_from_canonical": list(missing_metrics),
            "extra_unexpected": list(extra_metrics),
            "episodes_with_scorecard": episodes_with_scorecard,
        },
        "judge_mode": {
            "mode_counts": dict(mode_counts),
            "config_vs_audit_mismatch": config_vs_audit_mismatch,
        },
        "models": {
            "spreader": dict(spreader_models),
            "debunker": dict(debunker_models),
            "judge": dict(judge_models),
            "missing_spreader": missing_spreader,
            "missing_debunker": missing_debunker,
            "missing_judge_model": missing_judge_model,
        },
        "run_json": {
            "count": rj_count,
            "arena_type_values": dict(arena_type_values),
            "runs_missing_arena_type": runs_missing_arena_type,
            "run_field_pct": dict(run_field_pct),
            "run_config_field_pct": {k: (v / rj_count * 100) if rj_count else 0 for k, v in run_config_keys.items()},
            "has_arena_type": "arena_type" in run_json_keys,
            "has_run_config": "run_config" in run_json_keys,
            "has_run_config_agents": sum(1 for r in run_jsons if (r.get("run_config") or {}).get("agents")),
            "has_run_config_judge_weights": sum(1 for r in run_jsons if (r.get("run_config") or {}).get("judge_weights")),
        },
        "episode_field_pct": ep_field_pct,
        "run_episode_map": {k: len(v) for k, v in run_episode_map.items()},
    }


if __name__ == "__main__":
    d = main()
    if "error" in d:
        print(d["error"])
    else:
        print(json.dumps(d, indent=2, default=str))
