#!/usr/bin/env python3
"""
URL Hallucination Checker — post-processing script.

Extracts all URLs from completed episode transcripts, checks if they resolve
via HTTP HEAD requests, and outputs a hallucination report.

Usage:
    python scripts/check_url_hallucinations.py

Output:
    data/url_hallucination_report.csv
"""

import csv
import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

RUNS_DIR = Path("runs")
OUTPUT_FILE = Path("data/url_hallucination_report.csv")

URL_PATTERN = re.compile(r'https?://[^\s<>")\]]+')


def extract_urls_from_episode(ep: dict) -> list[dict]:
    """Extract all URLs from an episode's transcript with metadata."""
    urls = []
    run_id = ep.get("run_id", "")
    episode_id = ep.get("episode_id", "")
    claim = ep.get("claim", "")

    for t_idx, t in enumerate(ep.get("turns", [])):
        for side_key, role in [("spreader_message", "spreader"), ("debunker_message", "debunker")]:
            msg = t.get(side_key, {})
            text = msg.get("content", "") if isinstance(msg, dict) else str(msg or "")
            found = URL_PATTERN.findall(text)
            for url in found:
                # Clean trailing punctuation
                url = url.rstrip(".,;:!?)")
                urls.append({
                    "run_id": run_id,
                    "episode_id": episode_id,
                    "claim": claim[:50],
                    "turn": t_idx + 1,
                    "role": role,
                    "model": ep.get("config_snapshot", {}).get("agents", {}).get(role, {}).get("model", ""),
                    "url": url,
                })
    return urls


def check_url(url: str, timeout: int = 10) -> dict:
    """Check if a URL resolves. Returns status info."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (MisinfoArena URL Checker)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": resp.status, "valid": True, "error": None}
    except urllib.error.HTTPError as e:
        # 403/404/etc — URL exists but access denied or not found
        return {"status": e.code, "valid": e.code < 500, "error": str(e.reason)}
    except urllib.error.URLError as e:
        return {"status": None, "valid": False, "error": str(e.reason)[:100]}
    except Exception as e:
        return {"status": None, "valid": False, "error": str(e)[:100]}


def main():
    # Load all episodes
    all_urls = []
    for run_dir in sorted(RUNS_DIR.iterdir()):
        ep_file = run_dir / "episodes.jsonl"
        if not ep_file.exists():
            continue
        with open(ep_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ep = json.loads(line)
                except:
                    continue
                if ep.get("results", {}).get("winner") == "error":
                    continue
                all_urls.extend(extract_urls_from_episode(ep))

    if not all_urls:
        print("No URLs found in transcripts.")
        return

    print(f"Found {len(all_urls)} URLs across all episodes.")
    unique_urls = list(set(u["url"] for u in all_urls))
    print(f"Unique URLs: {len(unique_urls)}")

    # Check URLs in parallel
    print("Checking URLs (this may take a few minutes)...")
    url_results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(futures)):
            url = futures[future]
            try:
                result = future.result()
                url_results[url] = result
            except Exception as e:
                url_results[url] = {"status": None, "valid": False, "error": str(e)[:100]}
            if (i + 1) % 50 == 0:
                print(f"  Checked {i + 1}/{len(unique_urls)}...")

    # Build report
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "run_id", "episode_id", "claim", "turn", "role", "model",
            "url", "status", "valid", "error",
        ])
        writer.writeheader()
        for entry in all_urls:
            result = url_results.get(entry["url"], {})
            writer.writerow({
                **entry,
                "status": result.get("status"),
                "valid": result.get("valid", False),
                "error": result.get("error", ""),
            })

    # Summary
    total = len(all_urls)
    valid = sum(1 for u in all_urls if url_results.get(u["url"], {}).get("valid", False))
    invalid = total - valid
    print(f"\nResults saved to {OUTPUT_FILE}")
    print(f"Total URLs: {total}")
    print(f"Valid: {valid} ({valid/total*100:.0f}%)")
    print(f"Invalid/hallucinated: {invalid} ({invalid/total*100:.0f}%)")

    # Per-model breakdown
    from collections import Counter
    model_valid = Counter()
    model_total = Counter()
    for u in all_urls:
        model = u["model"]
        model_total[model] += 1
        if url_results.get(u["url"], {}).get("valid", False):
            model_valid[model] += 1

    print("\nPer-model URL validity:")
    for model in sorted(model_total.keys()):
        v = model_valid[model]
        t = model_total[model]
        print(f"  {model[:25]:25s} {v}/{t} valid ({v/t*100:.0f}%)")


if __name__ == "__main__":
    main()
