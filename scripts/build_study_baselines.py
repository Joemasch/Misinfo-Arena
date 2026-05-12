"""
Build per-(domain, falsifiability) baseline statistics from the archived
960-episode experiment_v2 dataset.

Output: src/arena/data/study_baselines.json

Each baseline entry contains:
  - n: episode count
  - fc_win_rate, sp_win_rate, draw_rate
  - avg_confidence, avg_margin
  - turn_breakdown: {2: {...}, 6: {...}, 10: {...}}

Re-run this when the archive changes. The output JSON is committed and
loaded at runtime by src/arena/study_baselines.py.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from arena.claim_metadata import classify_falsifiability  # noqa: E402

ARCHIVE = REPO_ROOT / "runs_archive" / "experiment_v2_archived_20260511_171256"
OUT_PATH = REPO_ROOT / "src" / "arena" / "data" / "study_baselines.json"


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _load_episodes() -> list[dict]:
    episodes: list[dict] = []
    for run_dir in sorted(ARCHIVE.iterdir()):
        if not run_dir.is_dir():
            continue
        jsonl = run_dir / "episodes.jsonl"
        if not jsonl.exists():
            continue
        for line in jsonl.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ep = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ep.get("study_id") != "experiment_v2":
                continue
            if ep.get("results", {}).get("winner") not in ("spreader", "debunker", "draw"):
                continue
            episodes.append(ep)
    return episodes


def _bucket_key(ep: dict) -> tuple[str, str] | None:
    domain = (ep.get("claim_type") or "").strip()
    if not domain:
        return None
    claim = ep.get("claim", "")
    fals_label, _ = classify_falsifiability(claim)
    if fals_label == "unknown":
        return None
    return (domain, fals_label)


def _summarize(eps: list[dict]) -> dict:
    n = len(eps)
    if n == 0:
        return {}
    fc = sum(1 for e in eps if e.get("results", {}).get("winner") == "debunker")
    sp = sum(1 for e in eps if e.get("results", {}).get("winner") == "spreader")
    dr = sum(1 for e in eps if e.get("results", {}).get("winner") == "draw")
    confs = [
        _safe_float(e.get("results", {}).get("judge_confidence"))
        for e in eps
        if e.get("results", {}).get("judge_confidence") is not None
    ]
    margins = []
    for e in eps:
        totals = e.get("results", {}).get("totals", {}) or {}
        margins.append(abs(_safe_float(totals.get("debunker")) - _safe_float(totals.get("spreader"))))
    return {
        "n": n,
        "fc_win_rate": round(fc / n, 3),
        "sp_win_rate": round(sp / n, 3),
        "draw_rate": round(dr / n, 3),
        "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
        "avg_margin": round(sum(margins) / len(margins), 3) if margins else 0.0,
    }


def _turn_breakdown(eps: list[dict]) -> dict[str, dict]:
    by_turns: dict[int, list[dict]] = defaultdict(list)
    for e in eps:
        planned = e.get("config_snapshot", {}).get("planned_max_turns")
        if planned is None:
            continue
        by_turns[int(planned)].append(e)
    return {str(k): _summarize(v) for k, v in sorted(by_turns.items())}


def main() -> None:
    print(f"Loading from {ARCHIVE}")
    episodes = _load_episodes()
    print(f"Loaded {len(episodes)} experiment_v2 episodes")

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ep in episodes:
        key = _bucket_key(ep)
        if key is None:
            continue
        buckets[key].append(ep)

    out: dict = {
        "metadata": {
            "source": "experiment_v2_archived_20260511_171256",
            "total_episodes": len(episodes),
            "judge_model": "grok-3",
        },
        "overall": _summarize(episodes),
        "by_domain_falsifiability": {},
    }

    for (domain, fals), eps in sorted(buckets.items()):
        cell_key = f"{domain}|{fals}"
        out["by_domain_falsifiability"][cell_key] = {
            **_summarize(eps),
            "turn_breakdown": _turn_breakdown(eps),
        }
        s = out["by_domain_falsifiability"][cell_key]
        print(f"  ({domain}, {fals}) n={s['n']}: FC {s['fc_win_rate']:.0%} | conf {s['avg_confidence']:.2f} | margin {s['avg_margin']:.2f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
