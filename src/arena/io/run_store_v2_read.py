"""
Read-only loader for JSON v2 episodes at runs/<run_id>/episodes.jsonl.

No writing. Used by Run Replay (Stored) page only.
"""

import json
from pathlib import Path
from typing import Any

MAX_EPISODES_FOR_CLAIMS = 20


def load_run_metadata(runs_dir: str | Path, run_id: str) -> dict | None:
    """
    Read runs/<run_id>/run.json and return parsed dict.
    Return None if file missing or invalid.
    """
    try:
        path = Path(runs_dir) / run_id / "run.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_run_metadata_fields(run_meta: dict | None) -> dict[str, Any]:
    """
    Flatten selected run-level metadata for analytics.
    """
    if not run_meta:
        return {
            "arena_type": "single_claim",
            "run_spreader_model": None,
            "run_debunker_model": None,
            "run_judge_model": None,
            "run_created_at": None,
        }

    run_config = run_meta.get("run_config") or {}
    agents = run_config.get("agents") or {}

    def _model(role: str) -> Any:
        a = agents.get(role) or {}
        return a.get("model") if isinstance(a, dict) else None

    return {
        "arena_type": run_meta.get("arena_type") or "single_claim",
        "run_spreader_model": _model("spreader"),
        "run_debunker_model": _model("debunker"),
        "run_judge_model": _model("judge"),
        "run_created_at": run_meta.get("created_at"),
    }


def list_runs(runs_dir: str | Path = "runs", refresh_token: float = 0.0) -> list[dict[str, Any]]:
    """
    List run folders that contain episodes.jsonl and are valid.

    refresh_token: optional; when changed, invalidates callers' caches (e.g. st.cache_data).
    Returns only valid runs (>= 1 parsable episode, >= 1 with judge_audit.status == "success").
    One dict per run: run_id, path, mtime, episode_count, is_valid, claim_preview,
    claim_variants_count, claim_variants. Sorted descending by mtime (newest first).
    """
    base = Path(runs_dir)
    if not base.exists():
        return []

    out: list[dict[str, Any]] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        ep_path = child / "episodes.jsonl"
        if not ep_path.exists():
            continue

        try:
            mtime = ep_path.stat().st_mtime
        except OSError:
            mtime = 0.0

        episode_count = 0
        has_success_judge = False
        claim_list: list[str] = []
        with open(ep_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    episode_count += 1
                    ja = obj.get("judge_audit") or {}
                    if ja.get("status") == "success":
                        has_success_judge = True
                    c = (obj.get("claim") or "").strip()
                    if c:
                        claim_list.append(c)
                except json.JSONDecodeError:
                    continue
                if episode_count >= MAX_EPISODES_FOR_CLAIMS:
                    break
                if (
                    episode_count >= 3
                    and has_success_judge
                    and len(claim_list) >= 1
                ):
                    break

        unique_ordered: list[str] = list(dict.fromkeys(claim_list))
        claim_variants_count = len(unique_ordered)
        if not unique_ordered:
            claim_preview = "(missing claim)"
        elif claim_variants_count == 1:
            claim_preview = unique_ordered[0]
        else:
            most_common = max(set(unique_ordered), key=claim_list.count)
            claim_preview = f"{most_common} (+{claim_variants_count - 1} variants)"
        claim_variants = unique_ordered[:3]

        out.append({
            "run_id": child.name,
            "path": str(ep_path),
            "mtime": mtime,
            "episode_count": episode_count,
            "is_valid": episode_count >= 1 and has_success_judge,
            "claim_preview": claim_preview,
            "claim_variants_count": claim_variants_count,
            "claim_variants": claim_variants,
        })

    out.sort(key=lambda x: x["mtime"], reverse=True)
    return [r for r in out if r.get("is_valid")]


def load_episodes(run_id: str, runs_dir: str | Path = "runs", refresh_token: float = 0.0) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Parse runs/<run_id>/episodes.jsonl. Skips blank lines; on JSONDecodeError per line,
    continues and appends a warning. refresh_token: optional, for cache invalidation.
    Returns (episodes_list, warnings).
    """
    if isinstance(runs_dir, str):
        runs_dir = Path(runs_dir)
    ep_path = runs_dir / run_id / "episodes.jsonl"
    episodes: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not ep_path.exists():
        warnings.append(f"File not found: {ep_path}")
        return episodes, warnings

    with open(ep_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError as e:
                warnings.append(f"Line {line_num}: JSON decode error — {e!s}")
                continue

    return episodes, warnings
