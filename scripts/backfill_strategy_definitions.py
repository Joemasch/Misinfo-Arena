"""
Backfill one-line definitions for open-coded strategy labels.

Scans every episode in runs/, extracts each unique tactic label that's
NOT already in the Atlas catalogue, samples 2-3 transcript sentences
where that tactic was tagged, asks the LLM for a one-line definition,
and caches the result to:

    src/arena/data/strategy_definitions.json

The Atlas then reads from this cache when a label isn't in the catalogue.

Re-run safely: existing entries are kept; only NEW labels get an API call.
Pass --force to regenerate everything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from arena.presentation.streamlit.pages.atlas_page import _STRATEGY_CATALOG  # noqa: E402

RUNS_DIR = REPO_ROOT / "runs"
OUT_PATH = REPO_ROOT / "src" / "arena" / "data" / "strategy_definitions.json"

MODEL = os.getenv("BACKFILL_MODEL", "gpt-4o-mini")


def _plain_from_raw(raw: str) -> str:
    """Mirror the Atlas's plain-name derivation for un-catalogued labels."""
    return (raw or "").replace("_", " ").title()


def _normalize_label(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "_")


def _catalogue_keys() -> set[str]:
    """Set of normalized raw labels + their plain names — these are skipped."""
    keys = set()
    for raw, (plain, _desc, _side) in _STRATEGY_CATALOG.items():
        keys.add(_normalize_label(raw))
        keys.add(_normalize_label(plain))
    return keys


def _sentences_from(text: str) -> list[str]:
    """Split into reasonable sentences. Filter out very short fragments."""
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) >= 30]


def _collect_labels_and_examples() -> dict[str, dict]:
    """
    Walk runs/ and build:

        {
            normalized_label: {
                "plain": "Title Case Name",
                "raw":   "snake_case_label",
                "examples": [
                    {"text": "...", "side": "spreader", "turn": 2,
                     "claim": "...", "run_id": "..."},
                    ...
                ],
                "spreader_count": int,
                "debunker_count": int,
            }
        }
    """
    out: dict[str, dict] = defaultdict(lambda: {
        "plain": "", "raw": "", "examples": [],
        "spreader_count": 0, "debunker_count": 0,
    })

    if not RUNS_DIR.exists():
        return out

    for run_dir in sorted(RUNS_DIR.iterdir()):
        ep_file = run_dir / "episodes.jsonl"
        if not ep_file.exists():
            continue
        for line in ep_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ep = json.loads(line)
            except json.JSONDecodeError:
                continue

            claim = ep.get("claim", "") or ""
            pts = ep.get("per_turn_strategies") or []
            if not pts:
                continue

            # Build per-turn text lookup. The stored turns array has one
            # entry per side per turn (flattened): {name, content, turn_index}
            # with 0-based turn_index per side. We collapse them into
            # {turn_num: {spreader, debunker}}.
            turn_texts: dict[int, dict[str, str]] = {}
            for i, t in enumerate(ep.get("turns") or []):
                name = (t.get("name") or t.get("role") or "").lower()
                content = t.get("content") or ""
                ti = t.get("turn_index")
                if ti is None:
                    ti = i // 2
                tnum = int(ti) + 1
                rec = turn_texts.setdefault(tnum, {"spreader": "", "debunker": ""})
                if "spread" in name:
                    rec["spreader"] = content
                elif "debunk" in name or "fact" in name:
                    rec["debunker"] = content
                # Legacy structured format
                if "spreader_message" in t:
                    sm = t.get("spreader_message") or {}
                    rec["spreader"] = sm.get("content", "") if isinstance(sm, dict) else ""
                if "debunker_message" in t:
                    dm = t.get("debunker_message") or {}
                    rec["debunker"] = dm.get("content", "") if isinstance(dm, dict) else ""

            for entry in pts:
                tnum = entry.get("turn") or entry.get("turn_index") or 0
                try:
                    tnum = int(tnum)
                except (TypeError, ValueError):
                    continue
                for side_key, label_key in [
                    ("spreader", "spreader_strategies"),
                    ("debunker", "debunker_strategies"),
                ]:
                    for raw_label in entry.get(label_key) or []:
                        norm = _normalize_label(raw_label)
                        if not norm:
                            continue
                        rec = out[norm]
                        rec["plain"] = rec["plain"] or _plain_from_raw(raw_label)
                        rec["raw"] = rec["raw"] or norm
                        if side_key == "spreader":
                            rec["spreader_count"] += 1
                        else:
                            rec["debunker_count"] += 1
                        # Collect example sentences from this turn for this side
                        if len(rec["examples"]) < 3:
                            text = (turn_texts.get(tnum) or {}).get(side_key, "")
                            for s in _sentences_from(text)[:2]:
                                if len(rec["examples"]) >= 3:
                                    break
                                rec["examples"].append({
                                    "text": s, "side": side_key, "turn": tnum,
                                    "claim": claim, "run_id": run_dir.name,
                                })
    return out


def _load_cache() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _generate_definition(client, plain: str, raw: str, examples: list[dict],
                          spreader_count: int, debunker_count: int) -> str:
    """Ask the LLM for a single-sentence definition of this open-coded tactic."""
    role_hint = (
        "more often by the spreader" if spreader_count > debunker_count else
        "more often by the fact-checker" if debunker_count > spreader_count else
        "by both sides roughly equally"
    )
    example_block = ""
    for i, ex in enumerate(examples[:3], 1):
        side = "spreader" if ex["side"] == "spreader" else "fact-checker"
        example_block += f"  {i}. ({side}, on \"{ex['claim'][:60]}\"): \"{ex['text']}\"\n"
    if not example_block:
        example_block = "  (no transcript examples captured)\n"

    system = (
        "You write concise glossary entries for rhetorical tactics used in AI-vs-AI "
        "misinformation debates. You produce a single sentence (40-65 words) that "
        "explains what the tactic is — its mechanism and why someone would use it. "
        "Plain English. No hedging, no preamble, no quotation marks. Do not start "
        "with the tactic name. Write declaratively, like a glossary."
    )
    user = (
        f"Tactic name: {plain}\n"
        f"Raw label: {raw}\n"
        f"Usage: {role_hint} (spreader={spreader_count}, fact-checker={debunker_count})\n"
        f"Examples from real debates:\n{example_block}\n"
        "Write one declarative sentence (40-65 words) defining this tactic."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=180,
    )
    text = (response.choices[0].message.content or "").strip()
    # Strip trailing quotes / leading bullet markers if the model adds them
    text = text.strip(' "*-').strip()
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Regenerate definitions for labels already in the cache")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without calling the API")
    args = parser.parse_args()

    catalogue_keys = _catalogue_keys()
    print(f"Catalogue has {len(_STRATEGY_CATALOG)} entries — these are skipped.\n")

    labels = _collect_labels_and_examples()
    print(f"Scanned runs/. Found {len(labels)} unique tactic labels across all episodes.")

    needs_def = []
    for norm, rec in labels.items():
        if norm in catalogue_keys:
            continue
        needs_def.append((norm, rec))
    print(f"  {len(needs_def)} are open-coded (not catalogued).\n")

    cache = _load_cache()
    print(f"Existing cache has {len(cache)} definitions.")

    todo = []
    for norm, rec in needs_def:
        if not args.force and norm in cache:
            continue
        todo.append((norm, rec))
    print(f"Will generate {len(todo)} new definitions.\n")

    if args.dry_run:
        for norm, rec in todo[:10]:
            print(f"  would define: {rec['plain']} ({norm}) — {len(rec['examples'])} examples")
        return

    if not todo:
        print("Nothing to do.")
        return

    # Init LLM client
    try:
        from openai import OpenAI
        from arena.utils.openai_config import get_openai_api_key
        api_key = get_openai_api_key()
        if not api_key:
            print("ERROR: OPENAI_API_KEY not set.")
            sys.exit(1)
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"ERROR: OpenAI client init failed: {e}")
        sys.exit(1)

    for i, (norm, rec) in enumerate(todo, 1):
        try:
            definition = _generate_definition(
                client, rec["plain"], rec["raw"], rec["examples"],
                rec["spreader_count"], rec["debunker_count"],
            )
        except Exception as e:
            print(f"  [{i:>2}/{len(todo)}] FAILED  {rec['plain']:30s} — {e}")
            continue
        cache[norm] = {
            "plain":           rec["plain"],
            "raw":             rec["raw"],
            "definition":      definition,
            "spreader_count":  rec["spreader_count"],
            "debunker_count":  rec["debunker_count"],
            "model":           MODEL,
        }
        print(f"  [{i:>2}/{len(todo)}]  {rec['plain']:30s} → {definition[:80]}")
        # Persist incrementally so a crash doesn't lose progress
        _save_cache(cache)

    print(f"\nDone. {OUT_PATH} now has {len(cache)} definitions.")


if __name__ == "__main__":
    main()
