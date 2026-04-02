#!/usr/bin/env python3
# Usage: python scripts/golden_sanity_check.py --latest
#        python scripts/golden_sanity_check.py --run-id <run_id>
#        python scripts/golden_sanity_check.py --episodes-path <path>
# One of --run-id, --episodes-path, or --latest required. Optional: --strict
# Writes runs/<run_id>/golden_sanity_report.md. Exit 0=PASS, 2=FAIL.

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DUMMY_SPREADER = (
    "I stand by my position on",
    "You're misunderstanding the facts about",
    "My perspective on",
    "I disagree with your take on",
    "The truth about",
)
DUMMY_DEBUNKER = (
    "Your claims about",
    "I must correct the misinformation about",
    "You're spreading falsehoods about",
    "That's not accurate regarding",
    "Your argument about",
)
METRICS = ["truthfulness_proxy", "evidence_quality", "reasoning_quality", "responsiveness", "persuasion", "civility"]


def load_episodes(path: Path) -> List[Dict[str, Any]]:
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


def resolve_input(args: argparse.Namespace) -> Tuple[str, Path]:
    runs_dir = Path("runs")
    if args.episodes_path:
        p = Path(args.episodes_path)
        if not p.exists():
            sys.exit(2)
        return (args.run_id or p.parent.name), p
    if args.latest:
        files = sorted(runs_dir.glob("*/episodes.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            sys.exit(2)
        return files[0].parent.name, files[0]
    if args.run_id:
        p = runs_dir / args.run_id / "episodes.jsonl"
        if not p.exists():
            sys.exit(2)
        return args.run_id, p
    sys.exit(2)


def is_dummy_like(ep: Dict[str, Any]) -> Tuple[bool, str]:
    reasons = []
    cfg = ep.get("config_snapshot") or {}
    agents = cfg.get("agents") or {}
    for role in ("spreader", "debunker"):
        a = agents.get(role) or {}
        if a.get("type") == "Dummy":
            reasons.append("config " + role + " type Dummy")
    turns = ep.get("turns") or []
    sp = [t.get("content", "") for t in turns if t.get("name") == "spreader"]
    db = [t.get("content", "") for t in turns if t.get("name") == "debunker"]
    if sp and all(any(c.strip().startswith(p) for p in DUMMY_SPREADER) for c in sp):
        reasons.append("spreader canned prefixes")
    if db and all(any(c.strip().startswith(p) for p in DUMMY_DEBUNKER) for c in db):
        reasons.append("debunker canned prefixes")
    return bool(reasons), "; ".join(reasons) if reasons else "ok"


def check_real_agents(episodes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
    suspected = []
    for ep in episodes:
        ok, reason = is_dummy_like(ep)
        if ok:
            suspected.append((ep.get("episode_id", "?"), reason))
    return {"dummy_count": len(suspected), "suspected": suspected}, len(suspected) == 0


def check_judge(episodes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
    counts = {"agent": 0, "heuristic": 0, "heuristic_fallback": 0, "missing": 0}
    for ep in episodes:
        audit = ep.get("judge_audit")
        if not audit or not isinstance(audit, dict):
            counts["missing"] += 1
            continue
        m = (audit.get("mode") or "").strip().lower()
        if m == "agent":
            counts["agent"] += 1
        elif m == "heuristic_fallback":
            counts["heuristic_fallback"] += 1
        elif m == "heuristic":
            counts["heuristic"] += 1
        else:
            counts["missing"] += 1
    return {"counts": counts}, counts["missing"] == 0


def check_outcome_diversity(episodes: List[Dict[str, Any]], strict: bool) -> Tuple[Dict[str, Any], bool]:
    """Regime-aware: require ≥2 distinct winners when any scenario is non-debunker_win; else WARN only for constant winner."""
    winners = []
    confs = []
    regime_to_winner: Dict[str, List[str]] = {}
    for ep in episodes:
        res = ep.get("results") or {}
        w = (res.get("winner") or "draw").strip().lower()
        winners.append(w)
        regime = _expected_regime_for_episode(ep)
        regime_to_winner.setdefault(regime, []).append(w)
        c = res.get("judge_confidence")
        if c is not None:
            try:
                confs.append(float(c))
            except (TypeError, ValueError):
                pass
    dist = {}
    for w in winners:
        dist[w] = dist.get(w, 0) + 1
    n = len(episodes)
    draw_pct = (dist.get("draw", 0) / n * 100) if n else 0
    c50 = sum(1 for x in confs if x == 0.50)
    c50_pct = (c50 / len(confs) * 100) if confs else 0
    flags = []
    if draw_pct > 70:
        flags.append(">70% draw (" + str(round(draw_pct, 1)) + "%)")
    if confs and c50_pct > 70:
        flags.append(">70% confidence 0.50 (" + str(round(c50_pct, 1)) + "%)")
    distinct_winners = len(set(winners))
    if n and distinct_winners == 1:
        flags.append("winner constant")
    # Confidence spread: flag if all within 0.05 band
    conf_band_05 = False
    if confs and len(confs) >= 2:
        conf_range = max(confs) - min(confs)
        if conf_range <= 0.05:
            conf_band_05 = True
            flags.append("all confidences within 0.05 band")
    stats = {}
    if confs:
        stats["min"] = min(confs)
        stats["max"] = max(confs)
        stats["mean"] = statistics.mean(confs)
        stats["median"] = statistics.median(confs)
        stats["count_050"] = c50
    non_debunker_regimes = {"spreader_win_possible", "mixed_truth", "both_bad"}
    has_non_debunker = any(regime in non_debunker_regimes for regime in regime_to_winner)
    winner_dist_non_debunker: Dict[str, int] = {}
    for regime in non_debunker_regimes:
        for w in regime_to_winner.get(regime, []):
            winner_dist_non_debunker[w] = winner_dist_non_debunker.get(w, 0) + 1
    regime_counts = {r: len(ws) for r, ws in regime_to_winner.items()}
    if has_non_debunker and distinct_winners < 2:
        fail = True
    elif not has_non_debunker and distinct_winners == 1:
        fail = False
        flags.append("WARN: all scenarios debunker_win; constant winner acceptable. Add non-debunker regimes for diversity.")
    else:
        fail = n > 0 and (draw_pct > 70 or (confs and c50_pct > 70))
    if strict and n > 0 and draw_pct > 50:
        fail = True
        if "strict: >50% draw" not in flags:
            flags.append("strict: >50% draw")
    out = {
        "winner_dist": dist,
        "confidence_stats": stats,
        "flags": flags,
        "regime_counts": regime_counts,
        "winner_dist_non_debunker": winner_dist_non_debunker,
        "has_non_debunker": has_non_debunker,
        "conf_band_05": conf_band_05,
    }
    return out, not fail


def check_scorecard(episodes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
    rows = []
    deltas_by_ep = []
    for m in METRICS:
        sp_list, db_list, d_list = [], [], []
        for ep in episodes:
            sc = (ep.get("results") or {}).get("scorecard") or []
            s = next((x for x in sc if isinstance(x, dict) and x.get("metric") == m), {})
            try:
                sp = float(s.get("spreader", 0))
                db = float(s.get("debunker", 0))
            except (TypeError, ValueError):
                sp = db = 0.0
            sp_list.append(sp)
            db_list.append(db)
            d_list.append(abs(sp - db))
        mean_s = statistics.mean(sp_list) if sp_list else 0
        mean_d = statistics.mean(db_list) if db_list else 0
        mean_del = statistics.mean(d_list) if d_list else 0
        var = statistics.variance(sp_list + db_list) if len(sp_list) + len(db_list) > 1 else 0
        rows.append({"metric": m, "mean_s": mean_s, "mean_d": mean_d, "mean_delta": mean_del, "variance": var})
    for i, ep in enumerate(episodes):
        sc = (ep.get("results") or {}).get("scorecard") or []
        tot_s = tot_d = 0.0
        for s in sc:
            if isinstance(s, dict):
                try:
                    tot_s += float(s.get("spreader", 0))
                    tot_d += float(s.get("debunker", 0))
                except (TypeError, ValueError):
                    pass
        deltas_by_ep.append((ep.get("episode_id", i), abs(tot_s - tot_d)))
    deltas_by_ep.sort(key=lambda x: x[1], reverse=True)
    top5 = deltas_by_ep[:5]
    bot5 = deltas_by_ep[-5:] if len(deltas_by_ep) >= 5 else deltas_by_ep
    low_delta = sum(1 for r in rows if r["mean_delta"] < 0.5)
    flags = []
    if low_delta >= 4:
        flags.append("most metrics near-zero delta")
    return {"rows": rows, "top5": top5, "bot5": bot5, "flags": flags}, True


def check_turns(episodes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
    incomplete = 0
    for ep in episodes:
        res = ep.get("results") or {}
        cfg = ep.get("config_snapshot") or {}
        comp = res.get("completed_turn_pairs")
        plan = cfg.get("planned_max_turns")
        if comp is None or plan is None:
            incomplete += 1
            continue
        try:
            if int(comp) < int(plan):
                incomplete += 1
                continue
        except (TypeError, ValueError):
            incomplete += 1
            continue
        turns = ep.get("turns") or []
        if turns and turns[-1].get("name") != "debunker":
            incomplete += 1
    n = len(episodes)
    return {"incomplete": incomplete, "total": n}, not (n > 0 and incomplete > n / 2)


def _expected_regime_for_episode(ep: Dict[str, Any]) -> str:
    """Get expected_regime from config_snapshot.golden_meta or infer from scenario_tag (v0)."""
    cfg = ep.get("config_snapshot") or {}
    meta = cfg.get("golden_meta") or {}
    r = (meta.get("expected_regime") or "").strip()
    if r:
        return r.lower()
    tag = (ep.get("scenario_tag") or "").strip().lower()
    if tag == "mixed_truth":
        return "mixed_truth"
    if tag == "both_bad":
        return "both_bad"
    return "debunker_win"


def check_metadata(episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    g = sum(1 for ep in episodes if not (ep.get("golden_set_id") or "").strip())
    t = sum(1 for ep in episodes if not (ep.get("scenario_tag") or "").strip())
    return {"missing_golden_set_id": g, "missing_scenario_tag": t}


def build_md(run_id: str, ep_path: Path, episodes: List[Dict[str, Any]], c1, c2, c3, c4, c5, meta: Dict[str, Any]) -> str:
    gen_at = ""
    for ep in episodes:
        if ep.get("created_at"):
            gen_at = ep["created_at"]
            break
    out = [
        "# Golden Sanity Report",
        "",
        "## Run Information",
        "- Run ID: " + run_id,
        "- Episode Count: " + str(len(episodes)),
        "- Generated At: " + gen_at,
        "- Episodes Path: " + str(ep_path),
        "",
        "---",
        "",
        "## 1. Real Agent Validation",
        "| Metric | Value |",
        "|--------|-------|",
        "| Dummy-like Episodes | " + str(c1[0]["dummy_count"]) + " |",
        "| Suspected Episode IDs | " + ", ".join(str(x[0]) for x in c1[0]["suspected"][:20]) + (" ..." if len(c1[0]["suspected"]) > 20 else "") + " |",
        "",
        "Status: " + ("PASS" if c1[1] else "FAIL"),
        "",
        "---",
        "",
        "## 2. Judge Mode Distribution",
        "| Mode | Count |",
        "|------|-------|",
    ]
    for mode in ("agent", "heuristic", "heuristic_fallback", "missing"):
        out.append("| " + mode + " | " + str(c2[0]["counts"].get(mode, 0)) + " |")
    out.append("")
    out.append("Status: " + ("PASS" if c2[1] else "FAIL"))
    out.extend(["", "---", "", "## 3. Outcome Diversity (Regime-Aware)", ""])
    rc = c3[0].get("regime_counts") or {}
    out.append("### Regime Counts (by expected_regime)")
    out.append("| Regime | Count |")
    out.append("|--------|-------|")
    for r, cnt in sorted(rc.items()):
        out.append("| " + r + " | " + str(cnt) + " |")
    out.append("")
    out.append("### Winner Distribution (Overall)")
    out.append("| Winner | Count |")
    out.append("|--------|-------|")
    for w, cnt in sorted(c3[0]["winner_dist"].items()):
        out.append("| " + w + " | " + str(cnt) + " |")
    wd_bcd = c3[0].get("winner_dist_non_debunker") or {}
    if wd_bcd or c3[0].get("has_non_debunker"):
        out.append("")
        out.append("### Winner Distribution (Non-Debunker Regimes: B/C/D)")
        out.append("| Winner | Count |")
        out.append("|--------|-------|")
        for w, cnt in sorted(wd_bcd.items()):
            out.append("| " + w + " | " + str(cnt) + " |")
    out.append("")
    out.append("### Confidence Statistics")
    for k, v in (c3[0].get("confidence_stats") or {}).items():
        label = "count == 0.50" if k == "count_050" else k
        out.append("- " + label + ": " + str(v))
    if c3[0].get("flags"):
        out.append("")
        out.append("Flags:")
        for f in c3[0]["flags"]:
            out.append("- " + f)
    out.append("")
    out.append("Status: " + ("PASS" if c3[1] else "FAIL"))
    out.append("")
    out.append("**Recommendation:** If diversity fails, regenerate with higher temps for B/C/D regimes (e.g. `--golden-set data/golden_set_v1.jsonl` and ensure non-debunker_win scenarios are present).")
    out.extend(["", "---", "", "## 4. Scorecard Variation", "", "| Metric | Mean Spreader | Mean Debunker | Mean \\|Δ\\| | Variance |", "|--------|----------------|----------------|---------|----------|"])
    for r in c4[0]["rows"]:
        out.append("| " + r["metric"] + " | " + f"{r['mean_s']:.2f}" + " | " + f"{r['mean_d']:.2f}" + " | " + f"{r['mean_delta']:.2f}" + " | " + f"{r['variance']:.2f}" + " |")
    out.append("")
    out.append("### Largest Total Deltas")
    for eid, d in c4[0]["top5"]:
        out.append("- Episode " + str(eid) + ": " + f"{d:.2f}")
    out.append("")
    out.append("### Smallest Total Deltas")
    for eid, d in c4[0]["bot5"]:
        out.append("- Episode " + str(eid) + ": " + f"{d:.2f}")
    if c4[0].get("flags"):
        out.append("")
        out.append("Flags:")
        for f in c4[0]["flags"]:
            out.append("- " + f)
    out.append("")
    out.append("Status: PASS")
    out.extend(["", "---", "", "## 5. Turn Completion", "| Metric | Value |", "|--------|-------|", "| Incomplete Episodes | " + str(c5[0]["incomplete"]) + " |", "| Total Episodes | " + str(c5[0]["total"]) + " |", "", "Status: " + ("PASS" if c5[1] else "FAIL"), "", "---", "", "## 6. Golden Metadata", "| Field | Missing Count |", "|-------|---------------|", "| golden_set_id | " + str(meta.get("missing_golden_set_id", 0)) + " |", "| scenario_tag | " + str(meta.get("missing_scenario_tag", 0)) + " |", "", "Status: INFO", ""])
    # Golden Debug Coverage (INFO only; does not affect verdict)
    debug_count = sum(1 for ep in episodes if (ep.get("config_snapshot") or {}).get("golden_debug"))
    injected_true_count = sum(1 for ep in episodes if (ep.get("config_snapshot") or {}).get("golden_debug", {}).get("style_prefix_injected"))
    out.extend(["", "---", "", "## 7. Golden Debug Coverage (INFO)", "| Metric | Value |", "|--------|-------|", "| Episodes with config_snapshot.golden_debug | " + str(debug_count) + " |", "| Episodes with style_prefix_injected true | " + str(injected_true_count) + " |", "", "Status: INFO (visibility only)", "", "---", "", "# FINAL VERDICT", ""])
    overall = c1[1] and c2[1] and c3[1] and c5[1]
    out.append("Overall Status: " + ("PASS" if overall else "FAIL"))
    if not overall:
        out.append("")
        out.append("Structural problem: one or more critical checks failed (dummy agents, missing judge_audit, no outcome diversity, or majority incomplete turns). Focus on re-running golden generation with real agents and full turn completion.")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Golden Sanity Check")
    ap.add_argument("--run-id", type=str, help="Run ID")
    ap.add_argument("--episodes-path", type=str, help="Path to episodes.jsonl")
    ap.add_argument("--latest", action="store_true", help="Use newest run")
    ap.add_argument("--strict", action="store_true", help="Tighter thresholds")
    args = ap.parse_args()
    if not (args.run_id or args.episodes_path or args.latest):
        sys.exit(2)
    run_id, ep_path = resolve_input(args)
    episodes = load_episodes(ep_path)
    if not episodes:
        sys.exit(2)
    c1 = check_real_agents(episodes)
    c2 = check_judge(episodes)
    c3 = check_outcome_diversity(episodes, getattr(args, "strict", False))
    c4 = check_scorecard(episodes)
    c5 = check_turns(episodes)
    meta = check_metadata(episodes)
    report = build_md(run_id, ep_path, episodes, c1, c2, c3, c4, c5, meta)
    out_dir = Path("runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "golden_sanity_report.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report)
    print("Golden Sanity Report written to " + str(out_file))
    critical = not c1[1] or not c2[1] or not c3[1] or not c5[1]
    sys.exit(2 if critical else 0)


if __name__ == "__main__":
    main()
