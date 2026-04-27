#!/usr/bin/env python3
"""
Generate the v2 experiment spec CSV.

Design: 16 model pairs × 20 claims × 3 turn lengths = 960 episodes

20 claims: 15 misinformation (3 per type) + 5 true (1 per type)
Judge: Grok 3 (xAI) — no provider overlap with debaters
Free-will prompts — no prescribed tactics

Usage:
    python scripts/generate_study_specs.py

Output:
    data/experiment_v2_spec.csv
"""

import csv
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

OUTPUT_DIR = Path("data")

MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "claude-sonnet-4-20250514",
    "gemini-2.5-flash",
]

JUDGE_MODEL = "grok-3"

TURN_LENGTHS = [2, 6, 10]

# Import claims from data module
from v2_claims import CLAIMS

SPEC_COLUMNS = [
    "study_id", "condition", "run_group", "claim", "claim_type", "true_claim",
    "spreader_model", "debunker_model", "judge_model",
    "max_turns", "consistency_runs",
]


def _short(m):
    if "mini" in m: return "4omini"
    if "gpt-4o" in m: return "4o"
    if "claude" in m: return "claude"
    if "gemini" in m: return "gemini"
    return m[:8]


def generate_spec():
    rows = []

    for spr_model, deb_model in itertools.product(MODELS, MODELS):
        spr_short = _short(spr_model)
        deb_short = _short(deb_model)
        pair_name = f"{spr_short}_vs_{deb_short}"

        for claim_info in CLAIMS:
            claim = claim_info["claim"]
            ctype = claim_info["type"]
            is_true = claim_info["true_claim"]
            claim_short = claim[:25].replace(" ", "_").replace(",", "").lower()
            run_group = f"{pair_name}_{claim_short}"

            for turns in TURN_LENGTHS:
                tc_label = "true" if is_true else "false"
                condition = f"pair={pair_name}_type={ctype.lower()}_turns={turns}_true={tc_label}"
                rows.append({
                    "study_id": "experiment_v2",
                    "condition": condition,
                    "run_group": run_group,
                    "claim": claim,
                    "claim_type": ctype,
                    "true_claim": str(is_true),
                    "spreader_model": spr_model,
                    "debunker_model": deb_model,
                    "judge_model": JUDGE_MODEL,
                    "max_turns": turns,
                    "consistency_runs": 1,
                })

    return rows


def write_spec(rows, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SPEC_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path}: {len(rows)} episodes")


if __name__ == "__main__":
    print("Generating v2 experiment spec CSV...")

    rows = generate_spec()
    write_spec(rows, "experiment_v2_spec.csv")

    # Summary
    pairs = len(set((r["spreader_model"], r["debunker_model"]) for r in rows))
    claims = len(set(r["claim"] for r in rows))
    true_claims = len(set(r["claim"] for r in rows if r["true_claim"] == "True"))
    false_claims = claims - true_claims
    types = len(set(r["claim_type"] for r in rows))
    turn_lengths = len(set(r["max_turns"] for r in rows))
    run_groups = len(set(r["run_group"] for r in rows))

    print(f"\n  {pairs} model pairs × {claims} claims × {turn_lengths} turn lengths = {len(rows)} episodes")
    print(f"  {false_claims} misinformation + {true_claims} true claims across {types} types")
    print(f"  {run_groups} runs")
    print(f"  Judge: {JUDGE_MODEL}")
    print(f"  Turn lengths: {sorted(set(r['max_turns'] for r in rows))}")
