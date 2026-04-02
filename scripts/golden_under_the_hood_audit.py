#!/usr/bin/env python3
"""
Under-the-hood audit for Golden runs: reads episodes.jsonl and writes
runs/<run_id>/golden_under_the_hood_audit.md for diagnosis (style injection,
temps, regeneration, diversity gate, judge mode).

Usage:
  python scripts/golden_under_the_hood_audit.py --latest
  python scripts/golden_under_the_hood_audit.py --run-id <id>
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def load_episodes(path: Path) -> list[dict]:
    episodes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return episodes


def resolve_run(run_id: str | None, latest: bool) -> tuple[str, Path]:
    runs_dir = Path("runs")
    if run_id:
        p = runs_dir / run_id / "episodes.jsonl"
        if not p.exists():
            sys.exit(2)
        return run_id, p
    if latest:
        files = sorted(runs_dir.glob("*/episodes.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            sys.exit(2)
        return files[0].parent.name, files[0]
    sys.exit(2)


def expected_regime(ep: dict) -> str:
    cfg = ep.get("config_snapshot") or {}
    gd = cfg.get("golden_meta") or cfg.get("golden_debug") or {}
    r = (gd.get("expected_regime") or "").strip()
    if r:
        return r
    tag = (ep.get("scenario_tag") or "").strip().lower()
    if tag == "mixed_truth":
        return "mixed_truth"
    if tag == "both_bad":
        return "both_bad"
    return "debunker_win"


def build_audit_md(run_id: str, ep_path: Path, episodes: list[dict]) -> str:
    out = []
    # 1) Run header
    gen_at = ""
    for ep in episodes:
        if ep.get("created_at"):
            gen_at = ep["created_at"]
            break
    out.append("# Golden Under-the-Hood Audit")
    out.append("")
    out.append("## 1. Run Header")
    out.append(f"- **run_id**: {run_id}")
    out.append(f"- **path**: {ep_path}")
    out.append(f"- **episode_count**: {len(episodes)}")
    out.append(f"- **generated_at**: {gen_at or 'N/A'}")
    out.append("")

    # 2) Per-episode table
    out.append("## 2. Per-Episode Table")
    out.append("")
    headers = [
        "episode_id", "golden_set_id", "scenario_tag", "expected_regime",
        "temps_spreader", "temps_debunker", "styles_spreader", "styles_debunker",
        "style_prefix_injected", "prompt_fp_spreader", "prompt_fp_debunker",
        "generation_attempts", "judge_mode", "final_winner", "final_confidence",
    ]
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["--------"] * len(headers)) + "|")
    for ep in episodes:
        cfg = ep.get("config_snapshot") or {}
        gd = cfg.get("golden_debug") or {}
        res = ep.get("results") or {}
        judge_mode = (ep.get("judge_audit") or {}).get("mode", "")
        row = [
            str(ep.get("episode_id", "")),
            str(ep.get("golden_set_id", "")),
            str(ep.get("scenario_tag", "")),
            expected_regime(ep),
            str(gd.get("temps", {}).get("spreader", "")),
            str(gd.get("temps", {}).get("debunker", "")),
            str(gd.get("styles", {}).get("spreader_style", "")),
            str(gd.get("styles", {}).get("debunker_style", "")),
            "true" if gd.get("style_prefix_injected") else "false",
            str((gd.get("prompt_fingerprint") or {}).get("spreader", "")),
            str((gd.get("prompt_fingerprint") or {}).get("debunker", "")),
            str(gd.get("generation_attempts", "")),
            str(judge_mode),
            str(res.get("winner", "")),
            str(res.get("judge_confidence", "")),
        ]
        out.append("| " + " | ".join(row) + " |")
    out.append("")

    # 3) Regeneration summary
    out.append("## 3. Regeneration Summary")
    multi = [ep for ep in episodes if (ep.get("config_snapshot") or {}).get("golden_debug", {}).get("generation_attempts", 1) > 1]
    out.append(f"- Episodes with generation_attempts > 1: **{len(multi)}**")
    out.append("")
    for ep in multi:
        gd = (ep.get("config_snapshot") or {}).get("golden_debug") or {}
        hist = gd.get("attempt_history") or []
        out.append(f"- **Episode {ep.get('episode_id')}** ({ep.get('golden_set_id')}): {len(hist)} attempts")
        for h in hist:
            out.append(f"  - attempt {h.get('attempt')}: spreader_temp={h.get('spreader_temp')} debunker_temp={h.get('debunker_temp')} -> winner={h.get('winner')} confidence={h.get('confidence')}")
    out.append("")

    # 4) Outcome summary
    winners = [ep.get("results", {}).get("winner", "draw") for ep in episodes if ep.get("results")]
    winners_set = set(winners)
    out.append("## 4. Outcome Summary")
    out.append("- **Winner distribution (overall):** " + str(dict(Counter(winners))))
    non_debunker = {"spreader_win_possible", "mixed_truth", "both_bad"}
    w_bcd = [ep.get("results", {}).get("winner", "draw") for ep in episodes if expected_regime(ep) in non_debunker and ep.get("results")]
    out.append("- **Winner distribution (non-debunker regimes B/C/D):** " + str(dict(Counter(w_bcd)) if w_bcd else "N/A"))
    out.append("")

    # 5) What likely happened (heuristics)
    out.append("## 5. What Likely Happened (Heuristics)")
    issues = []
    has_false_injected = any(
        not (ep.get("config_snapshot") or {}).get("golden_debug", {}).get("style_prefix_injected", True)
        for ep in episodes
    )
    if has_false_injected:
        issues.append("- **Primary bug:** At least one episode has `style_prefix_injected=false` -> style hints may not be reaching agent prompts.")

    temps_s = [((ep.get("config_snapshot") or {}).get("golden_debug") or {}).get("temps", {}).get("spreader") for ep in episodes]
    temps_d = [((ep.get("config_snapshot") or {}).get("golden_debug") or {}).get("temps", {}).get("debunker") for ep in episodes]
    if len(set(temps_s)) <= 1 and len(set(temps_d)) <= 1 and len(episodes) > 1:
        issues.append("- **Temps:** All episodes have identical temps -> regime/CLI overrides may not be applied.")

    if len(multi) == 0 and len(episodes) >= 1 and len(winners_set) < 2:
        issues.append("- **Regeneration:** Regeneration never triggered (no episodes with attempts > 1) -> diversity gate may not be reached or thresholds wrong.")

    if multi and len(winners_set) < 2:
        same_temps_after_regen = True
        for ep in multi:
            hist = (ep.get("config_snapshot") or {}).get("golden_debug", {}).get("attempt_history") or []
            if len(hist) >= 2 and hist[0].get("spreader_temp") != hist[-1].get("spreader_temp"):
                same_temps_after_regen = False
                break
        if same_temps_after_regen:
            issues.append("- **Regen mutation:** Regeneration ran but temps did not change across attempts -> regen mutation bug.")

    if not issues:
        out.append("- No obvious heuristics triggered; review table and judge_audit.mode for agent vs heuristic_fallback.")
    else:
        for i in issues:
            out.append(i)
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Golden under-the-hood audit")
    ap.add_argument("--run-id", type=str, default=None, help="Run ID")
    ap.add_argument("--latest", action="store_true", default=True, help="Use latest run (default True if no run-id)")
    args = ap.parse_args()
    if not args.run_id:
        args.latest = True
    run_id, ep_path = resolve_run(args.run_id, args.latest)
    episodes = load_episodes(ep_path)
    if not episodes:
        sys.exit(2)
    md = build_audit_md(run_id, ep_path, episodes)
    out_dir = Path("runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "golden_under_the_hood_audit.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md)
    print("Audit written to " + str(out_file))


if __name__ == "__main__":
    main()
