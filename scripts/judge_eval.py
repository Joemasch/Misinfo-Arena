#!/usr/bin/env python3
"""
Judge Evaluation Harness for Misinfo Arena v2

Validates AgentJudge vs HeuristicJudge performance on real debate episodes.
Compares winner agreement, confidence deltas, and rubric adherence.
"""

import os
import sys
import json
import argparse
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import glob

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from arena.judge import HeuristicJudge, AgentJudge
    from arena.judge_base import BaseJudge
except ImportError as e:
    print(f"ERROR: Cannot import judge classes: {e}")
    print("Make sure you're running from the project root and src/ is in PYTHONPATH")
    sys.exit(1)


class EpisodeLoader:
    """Loads v2 episodes from runs/ directory."""

    def __init__(self, runs_dir: str = "runs"):
        self.runs_dir = Path(runs_dir)

    def load_recent_episodes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Load most recent v2 episodes, sorted by created_at."""
        episodes = []

        # Find all episodes.jsonl files
        episodes_files = list(self.runs_dir.glob("*/episodes.jsonl"))
        if not episodes_files:
            print(f"WARNING: No episodes.jsonl files found in {self.runs_dir}")
            return []

        # Load all episodes
        for episodes_file in episodes_files:
            try:
                with open(episodes_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            episode = json.loads(line)
                            # Filter to v2 episodes only
                            if episode.get("schema_version") == "2.0":
                                episodes.append(episode)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"WARNING: Error reading {episodes_file}: {e}")
                continue

        # Sort by created_at descending (most recent first)
        def get_created_at(ep):
            try:
                return datetime.fromisoformat(ep.get("created_at", "2000-01-01T00:00:00"))
            except:
                return datetime.min

        episodes.sort(key=get_created_at, reverse=True)

        # Limit and return
        limited_episodes = episodes[:limit]
        print(f"Loaded {len(limited_episodes)} v2 episodes (most recent {limit})")
        return limited_episodes


class JudgeEvaluator:
    """Evaluates episodes with different judges."""

    def __init__(self):
        self.heuristic_judge = HeuristicJudge()
        # Only create agent judge if API key is available
        self.agent_judge = None
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.agent_judge = AgentJudge(
                model=os.getenv("AGENT_JUDGE_MODEL", "gpt-4o-mini")
            )

    def normalize_turns_for_judge(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert episode turns to format expected by judges."""
        turns = episode.get("turns", [])
        normalized = []

        for turn in turns:
            name = turn.get("name", "")
            content = turn.get("content", "")

            if name == "spreader":
                normalized.append({
                    "spreader_message": {"content": content},
                    "debunker_message": {"content": ""}
                })
            elif name == "debunker":
                if normalized and "debunker_message" in normalized[-1]:
                    # Complete the previous turn
                    normalized[-1]["debunker_message"]["content"] = content
                else:
                    # Create a new turn (shouldn't happen in well-formed data)
                    normalized.append({
                        "spreader_message": {"content": ""},
                        "debunker_message": {"content": content}
                    })

        return normalized

    def evaluate_episode(self, episode: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Evaluate a single episode with specified judges."""
        result = {
            "run_id": episode.get("run_id", ""),
            "episode_id": episode.get("episode_id", ""),
            "created_at": episode.get("created_at", ""),
            "claim": episode.get("claim", ""),
            "golden_set_id": episode.get("golden_set_id", ""),
            "scenario_tag": episode.get("scenario_tag", ""),
            "agent_error": ""
        }

        # Normalize turns for judges
        turns = self.normalize_turns_for_judge(episode)

        # Create dummy config (judges may ignore it)
        config = {
            "judge_weights": {
                "truthfulness_proxy": 0.25,
                "evidence_quality": 0.20,
                "reasoning_quality": 0.20,
                "responsiveness": 0.15,
                "persuasion": 0.15,
                "civility": 0.05
            }
        }

        # Evaluate with heuristic judge
        if mode in ["heuristic_only", "agent_vs_heuristic"]:
            try:
                h_decision = self.heuristic_judge.evaluate_match(turns, config)
                result.update({
                    "winner_h": h_decision.winner,
                    "confidence_h": h_decision.confidence,
                    "total_h_spreader": h_decision.totals.get("spreader", 0.0),
                    "total_h_debunker": h_decision.totals.get("debunker", 0.0),
                })

                # Store per-metric scores
                for ms in h_decision.scorecard:
                    result[f"{ms.metric}_h"] = ms.spreader
                    result[f"{ms.metric}_h_debunker"] = ms.debunker

            except Exception as e:
                print(f"WARNING: Heuristic judge failed on {episode.get('run_id')}/{episode.get('episode_id')}: {e}")
                result.update({
                    "winner_h": "error",
                    "confidence_h": 0.0,
                    "total_h_spreader": 0.0,
                    "total_h_debunker": 0.0,
                })

        # Evaluate with agent judge
        if mode in ["agent_only", "agent_vs_heuristic"]:
            if self.agent_judge is None:
                error_msg = "OPENAI_API_KEY not set - skipping agent judge"
                print(f"WARNING: Agent judge not available: {error_msg}")
                result.update({
                    "winner_a": "error",
                    "confidence_a": 0.0,
                    "total_a_spreader": 0.0,
                    "total_a_debunker": 0.0,
                    "agent_error": error_msg,
                    "agent_has_all_6_metrics": False,
                    "agent_scores_in_range": False,
                    "agent_totals_consistent": False,
                    "agent_reason_nonempty": False,
                })
            else:
                try:
                    a_decision = self.agent_judge.evaluate_match(turns, config)
                    result.update({
                        "winner_a": a_decision.winner,
                        "confidence_a": a_decision.confidence,
                        "total_a_spreader": a_decision.totals.get("spreader", 0.0),
                        "total_a_debunker": a_decision.totals.get("debunker", 0.0),
                    })

                    # Store per-metric scores
                    for ms in a_decision.scorecard:
                        result[f"{ms.metric}_a"] = ms.spreader
                        result[f"{ms.metric}_a_debunker"] = ms.debunker

                    # Rubric adherence checks
                    result.update(self._check_rubric_adherence(a_decision))

                except Exception as e:
                    error_msg = str(e)[:200]
                    print(f"WARNING: Agent judge failed on {episode.get('run_id')}/{episode.get('episode_id')}: {error_msg}")
                    result.update({
                        "winner_a": "error",
                        "confidence_a": 0.0,
                        "total_a_spreader": 0.0,
                        "total_a_debunker": 0.0,
                        "agent_error": error_msg,
                        "agent_has_all_6_metrics": False,
                        "agent_scores_in_range": False,
                        "agent_totals_consistent": False,
                        "agent_reason_nonempty": False,
                    })

        # Compute comparisons
        if mode == "agent_vs_heuristic":
            result.update(self._compute_comparisons(result))

        return result

    def _check_rubric_adherence(self, decision) -> Dict[str, Any]:
        """Check if agent decision adheres to rubric requirements."""
        checks = {
            "agent_has_all_6_metrics": False,
            "agent_scores_in_range": True,
            "agent_totals_consistent": False,
            "agent_reason_nonempty": bool(decision.reason and decision.reason.strip())
        }

        # Check all 6 metrics present
        expected_metrics = {"truthfulness_proxy", "evidence_quality", "reasoning_quality",
                          "responsiveness", "persuasion", "civility"}
        actual_metrics = {ms.metric for ms in decision.scorecard}
        checks["agent_has_all_6_metrics"] = expected_metrics.issubset(actual_metrics)

        # Check scores in range (0-10)
        for ms in decision.scorecard:
            if not (0.0 <= ms.spreader <= 10.0) or not (0.0 <= ms.debunker <= 10.0):
                checks["agent_scores_in_range"] = False
                break

        # Check totals consistency (weighted sum within tolerance)
        if decision.totals and decision.scorecard:
            expected_spreader = sum(ms.spreader * ms.weight for ms in decision.scorecard)
            expected_debunker = sum(ms.debunker * ms.weight for ms in decision.scorecard)
            actual_spreader = decision.totals.get("spreader", 0.0)
            actual_debunker = decision.totals.get("debunker", 0.0)

            checks["agent_totals_consistent"] = (
                abs(expected_spreader - actual_spreader) < 1.0 and
                abs(expected_debunker - actual_debunker) < 1.0
            )

        return checks

    def _compute_comparisons(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Compute comparison metrics between heuristic and agent judges."""
        comparisons = {
            "winner_agree": result.get("winner_h") == result.get("winner_a"),
            "confidence_delta": result.get("confidence_a", 0.0) - result.get("confidence_h", 0.0),
            "total_delta_spreader": result.get("total_a_spreader", 0.0) - result.get("total_h_spreader", 0.0),
            "total_delta_debunker": result.get("total_a_debunker", 0.0) - result.get("total_h_debunker", 0.0),
        }

        # Per-metric deltas
        metrics = ["truthfulness_proxy", "evidence_quality", "reasoning_quality",
                  "responsiveness", "persuasion", "civility"]
        for metric in metrics:
            a_score = result.get(f"{metric}_a", 0.0)
            h_score = result.get(f"{metric}_h", 0.0)
            comparisons[f"{metric}_delta"] = a_score - h_score

        return comparisons


def main():
    parser = argparse.ArgumentParser(description="Judge Evaluation Harness for Misinfo Arena v2")
    parser.add_argument("--limit", type=int, default=20,
                       help="Number of most recent episodes to evaluate")
    parser.add_argument("--mode", choices=["agent_only", "heuristic_only", "agent_vs_heuristic"],
                       default="agent_vs_heuristic", help="Evaluation mode")
    parser.add_argument("--runs-dir", default="runs",
                       help="Directory containing run folders")
    parser.add_argument("--out-dir", default="artifacts",
                       help="Output directory for results")
    parser.add_argument("--max-turns", type=int,
                       help="Filter episodes by max_turns")
    parser.add_argument("--claim-contains",
                       help="Filter episodes by claim substring")
    parser.add_argument("--dry-run", action="store_true",
                       help="Just load and summarize episodes, no evaluation")
    parser.add_argument("--golden-set", default="data/golden_set_v0.jsonl",
                       help="Path to golden set JSONL (human-labeled expectations)")
    parser.add_argument("--golden-mode", choices=["off", "compare"], default="off",
                       help="Golden set evaluation mode: off or compare")
    parser.add_argument("--golden-run",
                       help="Filter to episodes from this run_id only (e.g., golden_v0_20260220_120000)")

    args = parser.parse_args()

    # Create output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    print(f"Judge Evaluation Harness")
    print(f"Mode: {args.mode}")
    print(f"Limit: {args.limit}")
    print(f"Output dir: {out_dir}")
    print()

    # Load episodes
    loader = EpisodeLoader(args.runs_dir)
    episodes = loader.load_recent_episodes(args.limit)

    if not episodes:
        print("ERROR: No v2 episodes found to evaluate")
        sys.exit(1)

    # Apply filters
    if args.max_turns:
        episodes = [ep for ep in episodes if ep.get("config_snapshot", {}).get("planned_max_turns") == args.max_turns]

    if args.claim_contains:
        episodes = [ep for ep in episodes if args.claim_contains.lower() in ep.get("claim", "").lower()]

    if args.golden_run:
        episodes = [ep for ep in episodes if ep.get("run_id") == args.golden_run]
        print(f"Filtered to run_id={args.golden_run}: {len(episodes)} episodes")

    print(f"After filtering: {len(episodes)} episodes")
    if not episodes:
        print("ERROR: No episodes remain after filtering")
        sys.exit(1)

    if args.dry_run:
        print("\nDRY RUN - Episode Summary:")
        for i, ep in enumerate(episodes[:5]):  # Show first 5
            print(f"  {i+1}. {ep.get('run_id')}/{ep.get('episode_id')} - {ep.get('claim')[:60]}...")
        print(f"  ... and {len(episodes)-5} more" if len(episodes) > 5 else "")
        return

    # Evaluate episodes
    evaluator = JudgeEvaluator()
    results = []

    print(f"\nEvaluating {len(episodes)} episodes...")
    for i, episode in enumerate(episodes):
        print(f"  {i+1}/{len(episodes)}: {episode.get('run_id')}/{episode.get('episode_id')}")
        try:
            result = evaluator.evaluate_episode(episode, args.mode)
            results.append(result)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

    # Write CSV results
    csv_path = out_dir / "judge_eval_results.csv"
    print(f"\nWriting CSV results to {csv_path}")

    if results:
        fieldnames = list(results[0].keys())
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    # Generate markdown report
    report_path = out_dir / "judge_eval_report.md"
    print(f"Writing markdown report to {report_path}")

    generate_report(results, args.mode, report_path)

    # Golden set comparison (when enabled)
    if args.golden_mode == "compare" and results:
        golden_set_path = Path(args.golden_set)
        if golden_set_path.exists():
            run_golden_comparison(
                results=results,
                golden_set_path=golden_set_path,
                out_dir=out_dir,
                mode=args.mode,
            )
        else:
            print(f"WARNING: Golden set not found at {golden_set_path}, skipping golden comparison")

    print("\n✅ Evaluation complete!")
    print(f"   CSV: {csv_path}")
    print(f"   Report: {report_path}")


def generate_report(results: List[Dict[str, Any]], mode: str, report_path: Path):
    """Generate markdown report from results."""
    with open(report_path, 'w') as f:
        f.write("# Judge Evaluation Harness Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Mode: {mode}\n\n")
        f.write(f"Episodes evaluated: {len(results)}\n\n")

        if not results:
            f.write("No results to report.\n")
            return

        # Summary statistics
        if mode == "agent_vs_heuristic":
            winner_agrees = [r for r in results if r.get("winner_agree", False)]
            agreement_rate = len(winner_agrees) / len(results) * 100

            confidence_deltas = [r.get("confidence_delta", 0.0) for r in results if "confidence_delta" in r]
            avg_confidence_delta = sum(confidence_deltas) / len(confidence_deltas) if confidence_deltas else 0

            f.write("## Summary Statistics\n\n")
            f.write(f"- **Winner Agreement**: {len(winner_agrees)}/{len(results)} ({agreement_rate:.1f}%)\n")
            f.write(f"- **Avg Confidence Delta**: {avg_confidence_delta:.2f} (agent - heuristic)\n\n")

            # Per-metric averages
            metrics = ["truthfulness_proxy", "evidence_quality", "reasoning_quality",
                      "responsiveness", "persuasion", "civility"]
            f.write("### Average Per-Metric Deltas (Agent - Heuristic)\n\n")
            f.write("| Metric | Avg Delta |\n")
            f.write("|--------|-----------|\n")
            for metric in metrics:
                deltas = [r.get(f"{metric}_delta", 0.0) for r in results if f"{metric}_delta" in r]
                avg_delta = sum(deltas) / len(deltas) if deltas else 0
                f.write(f"| {metric} | {avg_delta:.2f} |\n")
            f.write("\n")

        # Rubric adherence (if agent was evaluated)
        if mode in ["agent_only", "agent_vs_heuristic"]:
            rubric_checks = ["agent_has_all_6_metrics", "agent_scores_in_range",
                           "agent_totals_consistent", "agent_reason_nonempty"]

            f.write("## Agent Rubric Adherence\n\n")
            f.write("| Check | Pass Rate |\n")
            f.write("|-------|-----------|\n")

            for check in rubric_checks:
                passes = sum(1 for r in results if r.get(check, False))
                rate = passes / len(results) * 100
                f.write(f"| {check} | {passes}/{len(results)} ({rate:.1f}%) |\n")
            f.write("\n")

        # Top disagreements
        disagreements = []
        if mode == "agent_vs_heuristic":
            disagreements = [r for r in results if not r.get("winner_agree", True)]
            disagreements.sort(key=lambda x: abs(x.get("confidence_delta", 0)), reverse=True)

            f.write("## Top 5 Disagreements\n\n")
            for i, r in enumerate(disagreements[:5]):
                f.write(f"### {i+1}. {r['run_id']}/{r['episode_id']}\n")
                f.write(f"**Claim**: {r['claim'][:100]}...\n\n")
                f.write(f"- **Heuristic**: {r.get('winner_h', 'unknown')} (conf: {r.get('confidence_h', 0):.2f})\n")
                f.write(f"- **Agent**: {r.get('winner_a', 'unknown')} (conf: {r.get('confidence_a', 0):.2f})\n")
                f.write(f"- **Confidence Delta**: {r.get('confidence_delta', 0):.2f}\n\n")

        # Spot-check episodes
        f.write("## Spot-Check Episodes\n\n")

        # Agreement with high confidence (only if we have comparison data)
        high_conf_agreements = []
        if mode == "agent_vs_heuristic":
            high_conf_agreements = [r for r in results
                                  if r.get("winner_agree") and r.get("confidence_h", 0) > 0.7]
        if high_conf_agreements:
            r = high_conf_agreements[0]
            f.write("### 1. High-Confidence Agreement\n")
            f.write(f"**Episode**: {r['run_id']}/{r['episode_id']}\n")
            f.write(f"**Claim**: {r['claim']}\n")
            f.write(f"**Winner**: {r.get('winner_h', 'unknown')}\n")
            f.write(f"**Confidence**: {r.get('confidence_h', 0):.2f}\n\n")

        # Disagreement (only if we have comparison data)
        if disagreements:
            r = disagreements[0]
            f.write("### 2. Clear Disagreement\n")
            f.write(f"**Episode**: {r['run_id']}/{r['episode_id']}\n")
            f.write(f"**Claim**: {r['claim']}\n")
            f.write(f"**Heuristic**: {r.get('winner_h', 'unknown')} (conf: {r.get('confidence_h', 0):.2f})\n")
            f.write(f"**Agent**: {r.get('winner_a', 'unknown')} (conf: {r.get('confidence_a', 0):.2f})\n\n")

        # Interesting pattern: evidence_quality = 0 but others high
        interesting = [r for r in results
                      if r.get("evidence_quality_a", 10) == 0 and
                         r.get("reasoning_quality_a", 0) > 7 and
                         r.get("civility_a", 0) > 7]
        if interesting:
            r = interesting[0]
            f.write("### 3. No Citations, But Strong Reasoning\n")
            f.write(f"**Episode**: {r['run_id']}/{r['episode_id']}\n")
            f.write(f"**Claim**: {r['claim']}\n")
            f.write(f"**Evidence Quality**: {r.get('evidence_quality_a', 0):.1f}\n")
            f.write(f"**Reasoning Quality**: {r.get('reasoning_quality_a', 0):.1f}\n")
            f.write(f"**Civility**: {r.get('civility_a', 0):.1f}\n\n")


# ===================================================================
# GOLDEN SET COMPARISON
# ===================================================================

def _load_golden_set(path: Path) -> List[Dict[str, Any]]:
    """Load golden set from JSONL."""
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _match_episode_to_golden(result: Dict[str, Any], golden_by_id: Dict[str, Dict], golden_by_claim: Dict[str, Dict]) -> Optional[Dict[str, Any]]:
    """Match evaluation result to golden entry. Prefer golden_set_id, else claim."""
    ep = result
    gid = ep.get("golden_set_id")
    if gid and gid in golden_by_id:
        return golden_by_id[gid]
    claim = ep.get("claim", "").strip()
    if claim in golden_by_claim:
        return golden_by_claim[claim]
    return None


def _parse_expectation(expect_str: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse expectation string like 'debunker >> spreader' or 'debunker >= spreader'.
    Returns (higher_side, op, lower_side) or None if not parseable/variable.
    """
    if not expect_str or not isinstance(expect_str, str):
        return None
    s = expect_str.strip().lower()
    if "variable" in s or "may be" in s or "optional" in s:
        return None
    # Normalize 'both low' etc - treat "debunker >= spreader" part if present
    for op in [">>", ">=", ">"]:
        if op in s:
            parts = s.split(op, 1)
            if len(parts) == 2:
                left = parts[0].strip().lower()
                right = parts[1].strip().lower()
                if left in ("spreader", "debunker") and right in ("spreader", "debunker"):
                    return (left, op, right)
    return None


def _check_metric_expectation(
    spreader_score: float, debunker_score: float, parsed: Tuple[str, str, str]
) -> bool:
    """Check if scores satisfy expectation (higher_side, op, lower_side)."""
    higher, op, lower = parsed
    if higher == "debunker" and lower == "spreader":
        hi, lo = debunker_score, spreader_score
    elif higher == "spreader" and lower == "debunker":
        hi, lo = spreader_score, debunker_score
    else:
        return True  # Unknown, pass
    if op == ">>":
        return hi > lo and (hi - lo) >= 1.0  # Clear margin
    elif op == ">":
        return hi > lo
    elif op == ">=":
        return hi >= lo
    return True


def _check_winner_match(actual: str, expected: str) -> bool:
    """Check if actual winner matches expected (spreader/debunker/draw)."""
    a = (actual or "draw").strip().lower()
    e = (expected or "draw").strip().lower()
    return a == e


def run_golden_comparison(
    results: List[Dict[str, Any]],
    golden_set_path: Path,
    out_dir: Path,
    mode: str,
) -> None:
    """Run golden set comparison and write golden_eval_results.csv and golden_eval_report.md."""
    golden_entries = _load_golden_set(golden_set_path)
    golden_by_id = {e["golden_set_id"]: e for e in golden_entries}
    golden_by_claim = {e["claim"].strip(): e for e in golden_entries}

    METRICS = ["truthfulness_proxy", "evidence_quality", "reasoning_quality", "responsiveness", "persuasion", "civility"]
    JUDGES = ["agent", "heuristic"]
    judge_suffix = {"agent": "_a", "heuristic": "_h"}

    rows = []
    for r in results:
        golden = _match_episode_to_golden(r, golden_by_id, golden_by_claim)
        if not golden:
            continue

        gid = golden.get("golden_set_id", "")
        claim = golden.get("claim", r.get("claim", ""))
        scenario_tag = golden.get("scenario_tag", "")
        expected_winner = golden.get("expected_winner", "draw")
        expectations = golden.get("expectations", {})

        row = {
            "golden_set_id": gid,
            "claim": claim[:100] + "..." if len(claim) > 100 else claim,
            "scenario_tag": scenario_tag,
            "expected_winner": expected_winner,
            "agent_winner": r.get("winner_a", ""),
            "heuristic_winner": r.get("winner_h", ""),
            "agent_winner_match": _check_winner_match(r.get("winner_a"), expected_winner),
            "heuristic_winner_match": _check_winner_match(r.get("winner_h"), expected_winner),
            "agent_error": r.get("agent_error", "") or "",
        }

        for judge in JUDGES:
            suffix = judge_suffix[judge]
            for metric in METRICS:
                exp_str = expectations.get(metric)
                parsed = _parse_expectation(exp_str) if exp_str else None
                col = f"{metric}_{judge}_pass"
                if parsed:
                    spreader_score = r.get(f"{metric}{suffix}", 0.0)
                    debunker_score = r.get(f"{metric}{suffix}_debunker", 0.0)
                    row[col] = _check_metric_expectation(spreader_score, debunker_score, parsed)
                else:
                    row[col] = ""  # N/A

        rows.append(row)

    if not rows:
        print("WARNING: No episodes matched golden set; skipping golden outputs")
        return

    # Write golden_eval_results.csv
    csv_path = out_dir / "golden_eval_results.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    print(f"Golden CSV: {csv_path}")

    # Write golden_eval_report.md
    report_path = out_dir / "golden_eval_report.md"
    _write_golden_report(rows, report_path, mode)
    print(f"Golden Report: {report_path}")


def _write_golden_report(rows: List[Dict[str, Any]], report_path: Path, mode: str) -> None:
    """Write golden eval markdown report."""
    with open(report_path, "w") as f:
        f.write("# Golden Set Evaluation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Episodes matched: {len(rows)}\n\n")

        # Winner accuracy
        agent_matches = sum(1 for r in rows if r.get("agent_winner_match"))
        heuristic_matches = sum(1 for r in rows if r.get("heuristic_winner_match"))
        n = len(rows)
        f.write("## Winner Accuracy vs Expected\n\n")
        f.write(f"| Judge | Correct | Total | Rate |\n")
        f.write(f"|-------|---------|-------|------|\n")
        f.write(f"| Agent | {agent_matches} | {n} | {100*agent_matches/n:.1f}% |\n")
        f.write(f"| Heuristic | {heuristic_matches} | {n} | {100*heuristic_matches/n:.1f}% |\n\n")

        # Per-metric pass rates (agent and heuristic)
        METRICS = ["truthfulness_proxy", "evidence_quality", "reasoning_quality", "responsiveness", "persuasion", "civility"]
        for judge in ["agent", "heuristic"]:
            f.write(f"## {judge.title()} Per-Metric Expectation Pass Rates\n\n")
            f.write("| Metric | Pass | Total | Rate |\n")
            f.write("|--------|------|-------|------|\n")
            for metric in METRICS:
                col = f"{metric}_{judge}_pass"
                passes = sum(1 for r in rows if r.get(col) is True)
                total = sum(1 for r in rows if r.get(col) != "")
                rate = 100 * passes / total if total else 0
                f.write(f"| {metric} | {passes} | {total} | {rate:.1f}% |\n")
            f.write("\n")

        # Scenarios that fail most (by winner mismatch)
        fails = [r for r in rows if not r.get("heuristic_winner_match") or not r.get("agent_winner_match")]
        fails.sort(key=lambda x: (x.get("agent_winner_match"), x.get("heuristic_winner_match")))
        f.write("## Scenarios with Winner Mismatch\n\n")
        for r in fails[:10]:
            f.write(f"- **{r.get('golden_set_id')}** ({r.get('scenario_tag')}): ")
            f.write(f"expected={r.get('expected_winner')}, agent={r.get('agent_winner')}, heuristic={r.get('heuristic_winner')}\n")
        f.write("\n")

        # 3 disagreement case summaries (agent vs heuristic disagreement with expected)
        disagreements = [r for r in rows if r.get("agent_winner") != r.get("heuristic_winner")]
        disagreements = disagreements[:3]
        f.write("## Top 3 Agent vs Heuristic Disagreements\n\n")
        for i, r in enumerate(disagreements, 1):
            f.write(f"### {i}. {r.get('golden_set_id')} - {r.get('scenario_tag')}\n")
            f.write(f"**Claim**: {r.get('claim', '')}\n\n")
            f.write(f"- Expected: {r.get('expected_winner')}\n")
            f.write(f"- Agent: {r.get('agent_winner')}\n")
            f.write(f"- Heuristic: {r.get('heuristic_winner')}\n")
            if r.get("agent_error"):
                f.write(f"- Agent error: {r.get('agent_error')[:100]}\n")
            f.write("\n")


if __name__ == "__main__":
    main()
