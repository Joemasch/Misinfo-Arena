#!/usr/bin/env python3
"""
Context Pack Generator for Misinformation Arena v2

Generates a comprehensive context pack (docs/CONTEXT_PACK.md) containing:
- __init__.py coverage under src/arena
- Streamlit routing block from app.py
- Debate execution loop snippet from app.py
- Example JSONL schema from runs/

Usage: python scripts/generate_context_pack.py
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import re


def truncate_string(text: str, max_length: int = 300) -> str:
    """Truncate string if longer than max_length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "…TRUNCATED…"


def truncate_list(items: list, max_items: int = 20, keep_first: int = 5, keep_last: int = 2) -> list:
    """Truncate list if longer than max_items."""
    if len(items) <= max_items:
        return items
    return items[:keep_first] + ["…TRUNCATED…"] + items[-keep_last:]


def truncate_dict(data: dict, max_keys: int = 50, keep_first: int = 30) -> dict:
    """Truncate dict if it has more than max_keys."""
    if len(data) <= max_keys:
        return data

    keys = sorted(data.keys())
    result = {k: data[k] for k in keys[:keep_first]}
    result["…TRUNCATED…"] = f"{len(data) - keep_first} more keys"
    return result


def process_json_value(value: Any) -> Any:
    """Recursively process JSON values for truncation."""
    if isinstance(value, str):
        return truncate_string(value)
    elif isinstance(value, list):
        return [process_json_value(item) for item in truncate_list(value)]
    elif isinstance(value, dict):
        return {k: process_json_value(v) for k, v in truncate_dict(value).items()}
    else:
        return value


def analyze_init_coverage() -> Dict[str, Any]:
    """Analyze __init__.py coverage under src/arena."""
    arena_path = Path("src/arena")
    if not arena_path.exists():
        return {"error": "src/arena directory not found"}

    coverage = {}
    total_dirs = 0
    missing_init = []

    # Walk through all directories under src/arena
    for root, dirs, files in os.walk(arena_path):
        if root == str(arena_path):
            continue  # Skip the root arena directory itself

        total_dirs += 1
        rel_path = Path(root).relative_to(arena_path)
        has_init = "__init__.py" in files
        coverage[str(rel_path)] = has_init

        if not has_init:
            missing_init.append(str(rel_path))

    return {
        "total_directories": total_dirs,
        "missing_init_count": len(missing_init),
        "missing_init_dirs": missing_init,
        "coverage": coverage
    }


def find_streamlit_routing(app_content: str, lines: List[str]) -> Dict[str, Any]:
    """Find and extract Streamlit page routing/dispatch block from app.py."""

    # PASS 1: Look for sidebar selectbox/radio with page options
    page_options = ["arena", "analytics", "replay", "prompts", "guide"]
    for i, line in enumerate(lines):
        if re.search(r'st\.sidebar\.(selectbox|radio)\s*\(', line, re.IGNORECASE):
            # Check if line contains page options
            line_lower = line.lower()
            if any(option in line_lower for option in page_options):
                # Found sidebar widget with page options - capture routing block
                start_line = max(0, i - 40)
                end_line = min(len(lines), i + 220)

                # Try to find natural end (indentation returns to baseline)
                base_indent = len(lines[i]) - len(lines[i].lstrip())
                for j in range(i, min(len(lines), i + 220)):
                    current_indent = len(lines[j]) - len(lines[j].lstrip())
                    if current_indent <= base_indent and re.search(r'^(def |class |if __name__|# ===)', lines[j]):
                        end_line = j
                        break

                snippet_lines = [f"{k+1:4d}|{lines[k]}" for k in range(start_line, end_line)]
                return {
                    "found": True,
                    "pass": 1,
                    "start_line": start_line + 1,
                    "end_line": end_line,
                    "snippet": '\n'.join(snippet_lines)
                }

    # PASS 2: Find variable assigned from sidebar widget, then look for dispatch
    for i, line in enumerate(lines):
        match = re.search(r'(\w+)\s*=\s*st\.sidebar\.(selectbox|radio)\s*\(', line)
        if match:
            var_name = match.group(1)
            # Look forward for dispatch using this variable
            for j in range(i, min(len(lines), i + 260)):
                line_j = lines[j]
                if re.search(r'\b(if|elif|match)\s+' + re.escape(var_name) + r'\b', line_j):
                    # Found dispatch - capture from assignment to end of dispatch
                    start_line = max(0, i - 20)
                    end_line = min(len(lines), j + 200)

                    # Find end of dispatch block
                    for k in range(j, min(len(lines), j + 200)):
                        if re.search(r'^(def |class |# ===|\s*$)', lines[k]) and k > j + 5:
                            end_line = k
                            break

                    snippet_lines = [f"{k+1:4d}|{lines[k]}" for k in range(start_line, end_line)]
                    return {
                        "found": True,
                        "pass": 2,
                        "variable": var_name,
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "snippet": '\n'.join(snippet_lines)
                    }

    # PASS 3: Search for render_ function calls
    render_functions = ['render_arena', 'render_analytics', 'render_replay', 'render_prompts', 'render_episode_replay', 'render_guide']
    render_hits = []
    for func in render_functions:
        for i, line in enumerate(lines):
            if func in line:
                render_hits.append((i, line.strip(), func))

    if render_hits:
        # Group nearby hits and capture clusters
        clusters = []
        current_cluster = [render_hits[0]]

        for hit in render_hits[1:]:
            if hit[0] - current_cluster[-1][0] < 50:  # Within 50 lines
                current_cluster.append(hit)
            else:
                clusters.append(current_cluster)
                current_cluster = [hit]
        clusters.append(current_cluster)

        # Use the largest cluster
        best_cluster = max(clusters, key=len) if clusters else [render_hits[0]]
        start_line = max(0, best_cluster[0][0] - 15)
        end_line = min(len(lines), best_cluster[-1][0] + 15)

        snippet_lines = [f"{i+1:4d}|{lines[i]}" for i in range(start_line, end_line)]
        return {
            "found": True,
            "pass": 3,
            "functions_found": [hit[2] for hit in best_cluster],
            "start_line": start_line + 1,
            "end_line": end_line,
            "snippet": '\n'.join(snippet_lines)
        }

    # If all passes fail, return top search hits
    search_terms = ["arena", "analytics", "replay", "prompts", "guide", "tab1", "tab2", "tab3", "tab4", "tab5"]
    all_hits = []
    for term in search_terms:
        for i, line in enumerate(lines):
            if term.lower() in line.lower():
                all_hits.append((i, line.strip(), term))

    return {
        "found": False,
        "passes_failed": [1, 2, 3],
        "top_hits": sorted(all_hits, key=lambda x: x[0])[:30],
        "error": "Could not find page routing/dispatch block. Here are top search hits:"
    }


def find_debate_execution_loop(app_content: str, lines: List[str]) -> Dict[str, Any]:
    """Find and extract debate execution/orchestration loop from app.py."""

    # PASS 1: Find execution-related function definitions with loops containing spreader/debunker
    execution_functions = ['run_debate', 'execute_debate', 'start_debate', 'run_episode', 'execute_episode', 'run_single_claim', 'run_arena']
    for func_pattern in execution_functions:
        for i, line in enumerate(lines):
            if re.search(rf'def\s+{re.escape(func_pattern)}\b', line, re.IGNORECASE):
                # Check if this function contains spreader, debunker, and a loop
                func_end = len(lines)
                for j in range(i + 1, len(lines)):
                    if re.search(r'^def |^class ', lines[j]):
                        func_end = j
                        break

                func_content = '\n'.join(lines[i:func_end]).lower()

                # Check for spreader + debunker + loop
                has_spreader = 'spreader' in func_content
                has_debunker = 'debunker' in func_content
                has_loop = 'for ' in func_content and ('range(' in func_content or 'turn' in func_content)

                if has_spreader and has_debunker and has_loop:
                    # Capture the full function
                    start_line = i
                    end_line = min(len(lines), func_end)
                    end_line = min(end_line, start_line + 320)  # Cap at 320 lines

                    snippet_lines = [f"{k+1:4d}|{lines[k]}" for k in range(start_line, end_line)]
                    return {
                        "found": True,
                        "pass": 1,
                        "function": func_pattern,
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "snippet": '\n'.join(snippet_lines)
                    }

    # PASS 2: Find densest window with multiple spreader/debunker/judge occurrences
    window_size = 220
    best_window = None
    best_score = 0
    best_start = 0

    for i in range(len(lines) - window_size):
        window_content = '\n'.join(lines[i:i + window_size]).lower()
        spreader_count = window_content.count('spreader')
        debunker_count = window_content.count('debunker')
        judge_count = sum(1 for term in ['judge', 'verdict', 'winner'] if term in window_content)

        # Score: spreader + debunker + judge weight
        score = spreader_count + debunker_count + (judge_count * 3)

        if score > best_score and spreader_count >= 6 and debunker_count >= 6:
            best_score = score
            best_start = i
            best_window = (i, i + window_size)

    if best_window:
        start_line, end_line = best_window
        snippet_lines = [f"{i+1:4d}|{lines[i]}" for i in range(start_line, end_line)]
        return {
            "found": True,
            "pass": 2,
            "score": best_score,
            "start_line": start_line + 1,
            "end_line": end_line,
            "snippet": '\n'.join(snippet_lines)
        }

    # PASS 3: Return top search hits for key terms
    search_terms = ['spreader', 'debunker', 'judge', 'verdict', 'winner', 'turn']
    all_hits = []
    for term in search_terms:
        for i, line in enumerate(lines):
            if term.lower() in line.lower():
                all_hits.append((i, line.strip(), term))

    # Group by line to avoid duplicates, sort by line number
    unique_hits = []
    seen_lines = set()
    for hit in sorted(all_hits, key=lambda x: x[0]):
        if hit[0] not in seen_lines:
            unique_hits.append(hit)
            seen_lines.add(hit[0])

    return {
        "found": False,
        "passes_failed": [1, 2],
        "top_hits": unique_hits[:50],  # Top 50 unique hits
        "error": "Could not find debate execution/orchestration loop. Here are top search hits:"
    }


def extract_jsonl_schema() -> Dict[str, Any]:
    """Extract example JSONL record schema from runs/."""

    # Find the newest .jsonl file
    jsonl_files = []
    runs_dir = Path("runs")

    if runs_dir.exists():
        jsonl_files = list(runs_dir.glob("*.jsonl"))

    if not jsonl_files:
        # Fallback to any .jsonl in repo
        jsonl_files = list(Path(".").glob("**/*.jsonl"))

    if not jsonl_files:
        return {"error": "No .jsonl files found in runs/ or anywhere in repo"}

    # Get the newest file by modification time
    newest_file = max(jsonl_files, key=lambda p: p.stat().st_mtime)
    mod_time = datetime.fromtimestamp(newest_file.stat().st_mtime)

    # Read the file
    try:
        with open(newest_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return {"error": f"File {newest_file} is empty"}

        # Parse first line
        first_record = json.loads(lines[0])

        # Try to get a middle record if file has enough lines
        middle_record = None
        if len(lines) > 50:
            middle_line = lines[49]  # 50th line (0-indexed)
            try:
                middle_record = json.loads(middle_line)
            except:
                pass

        # Process records for truncation
        processed_first = process_json_value(first_record)
        processed_middle = process_json_value(middle_record) if middle_record else None

        # Generate schema summary
        def get_schema(obj: Any, path: str = "", depth: int = 0) -> List[str]:
            """Recursively extract schema paths."""
            if depth > 2:  # Limit depth
                return [f"{path}... (nested)"]

            paths = []
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    paths.append(new_path)
                    if isinstance(value, (dict, list)):
                        paths.extend(get_schema(value, new_path, depth + 1))
            elif isinstance(obj, list) and obj:
                paths.append(f"{path}[] (array)")
                if obj and isinstance(obj[0], (dict, list)):
                    paths.extend(get_schema(obj[0], f"{path}[0]", depth + 1))
            return paths

        schema_paths = get_schema(first_record)

        # Identify special fields
        special_fields = {}
        if 'turns' in first_record and isinstance(first_record['turns'], list):
            special_fields['turns'] = f"List of {len(first_record['turns'])} turn objects"
        if 'judge_decision' in first_record and isinstance(first_record['judge_decision'], dict):
            special_fields['judge_decision'] = "Judge evaluation result with winner/confidence/reason"
        if 'config' in first_record and isinstance(first_record['config'], dict):
            special_fields['config'] = "Debate configuration (max_turns, topic, etc.)"

        return {
            "file": str(newest_file),
            "modified_time": mod_time.isoformat(),
            "total_lines": len(lines),
            "first_record": processed_first,
            "middle_record": processed_middle,
            "schema_paths": schema_paths,
            "special_fields": special_fields
        }

    except Exception as e:
        return {"error": f"Failed to process {newest_file}: {e}"}


def generate_context_pack():
    """Generate the complete context pack."""

    print("🔍 Analyzing codebase for context pack...")

    # Get file tree summary
    repo_root = Path(".")
    top_level_dirs = [d.name for d in repo_root.iterdir() if d.is_dir() and not d.name.startswith('.')]

    # Analyze __init__.py coverage
    print("📁 Analyzing __init__.py coverage...")
    init_coverage = analyze_init_coverage()

    # Read app.py for analysis
    app_path = Path("app.py")
    if not app_path.exists():
        print("❌ app.py not found!")
        return

    print("📖 Reading app.py...")
    with open(app_path, 'r', encoding='utf-8') as f:
        app_content = f.read()
    lines = app_content.splitlines()

    # Find routing block
    print("🔀 Finding Streamlit routing block...")
    routing_info = find_streamlit_routing(app_content, lines)

    # Find debate execution loop
    print("⚔️ Finding debate execution loop...")
    debate_info = find_debate_execution_loop(app_content, lines)

    # Extract JSONL schema
    print("📊 Extracting JSONL schema...")
    jsonl_info = extract_jsonl_schema()

    # Generate markdown
    print("📝 Generating context pack...")

    md_content = f"""# Misinformation Arena v2 - Context Pack

Generated on: {datetime.now().isoformat()}
Repository: {Path(".").resolve()}

## Project Execution

**Run command:** `streamlit run app.py`

**Entry point:** `app.py` (main Streamlit application)

## File Tree Summary

Top-level directories:
{chr(10).join(f"- {d}/" for d in sorted(top_level_dirs))}

## __init__.py Coverage Report

**Total directories under src/arena:** {init_coverage.get('total_directories', 'N/A')}
**Missing __init__.py:** {init_coverage.get('missing_init_count', 'N/A')}

### Missing __init__.py directories:
{chr(10).join(f"- src/arena/{d}" for d in init_coverage.get('missing_init_dirs', []))}

### Full coverage map:
{chr(10).join(f"- src/arena/{path}: {'✅' if has_init else '❌'}" for path, has_init in init_coverage.get('coverage', {}).items())}

## Streamlit Page Routing / Dispatch (best match)

"""

    if routing_info.get('found'):
        md_content += f"""**Location:** app.py lines {routing_info['start_line']}-{routing_info['end_line']}
**Found via pass {routing_info['pass']}:** """
        if routing_info['pass'] == 1:
            md_content += "Sidebar widget with page options"
        elif routing_info['pass'] == 2:
            md_content += f"Variable '{routing_info.get('variable', 'unknown')}' dispatch"
        elif routing_info['pass'] == 3:
            md_content += f"Render functions: {', '.join(routing_info.get('functions_found', []))}"

        md_content += f"""

```python
{routing_info['snippet']}
```
"""
    else:
        md_content += f"""**Not found:** {routing_info.get('error', 'Unknown error')}

### Top search hits:
{chr(10).join(f"- Line {line_num+1}: {line_text} ({term})" for line_num, line_text, term in routing_info.get('top_hits', []))}
"""

    md_content += "\n## Debate Execution / Orchestration (best match)\n\n"

    if debate_info.get('found'):
        md_content += f"""**Location:** app.py lines {debate_info['start_line']}-{debate_info['end_line']}
**Found via pass {debate_info['pass']}:** """
        if debate_info['pass'] == 1:
            md_content += f"Function '{debate_info.get('function', 'unknown')}' with spreader/debunker loop"
        elif debate_info['pass'] == 2:
            md_content += f"Densest window (score: {debate_info.get('score', 'unknown')})"

        md_content += f"""

```python
{debate_info['snippet']}
```
"""
    else:
        md_content += f"""**Not found:** {debate_info.get('error', 'Unknown error')}

### Top search hits:
{chr(10).join(f"- Line {line_num+1}: {line_text} ({term})" for line_num, line_text, term in debate_info.get('top_hits', []))}
"""

    md_content += "\n## Runs JSONL Schema\n\n"

    if 'error' in jsonl_info:
        md_content += f"**Error:** {jsonl_info['error']}\n"
    else:
        md_content += f"""**File:** {jsonl_info['file']}
**Modified:** {jsonl_info['modified_time']}
**Total records:** {jsonl_info['total_lines']}

### Schema Summary

**Top-level keys:**
{chr(10).join(f"- {key}" for key in jsonl_info.get('first_record', {}).keys())}

**Schema paths (2 levels deep):**
{chr(10).join(f"- {path}" for path in jsonl_info.get('schema_paths', [])[:50])}

**Special fields:**
{chr(10).join(f"- `{field}`: {desc}" for field, desc in jsonl_info.get('special_fields', {}).items())}

### Sample Record (First)

```json
{json.dumps(jsonl_info.get('first_record', {}), indent=2)}
```

"""

        if jsonl_info.get('middle_record'):
            md_content += f"""
### Sample Record (Middle)

```json
{json.dumps(jsonl_info['middle_record'], indent=2)}
```
"""

    # Add "What's missing?" footer
    missing_info = []

    if not routing_info.get('found'):
        missing_info.append(f"**Page routing:** Passes {routing_info.get('passes_failed', [])} failed")

    if not debate_info.get('found'):
        missing_info.append(f"**Debate execution:** Passes {debate_info.get('passes_failed', [])} failed")

    if missing_info:
        md_content += "\n## What's Missing?\n\n"
        md_content += "The following sections could not be confidently located:\n\n"
        for info in missing_info:
            md_content += f"- {info}\n"

        # Add top hits for missing sections
        if not routing_info.get('found') and routing_info.get('top_hits'):
            md_content += "\n**Top routing search hits (first 20):**\n"
            for i, (line_num, line_text, term) in enumerate(routing_info['top_hits'][:20]):
                md_content += f"{i+1:2d}. Line {line_num+1}: `{line_text}` ({term})\n"

        if not debate_info.get('found') and debate_info.get('top_hits'):
            md_content += "\n**Top debate execution search hits (first 20):**\n"
            for i, (line_num, line_text, term) in enumerate(debate_info['top_hits'][:20]):
                md_content += f"{i+1:2d}. Line {line_num+1}: `{line_text}` ({term})\n"

    # Write the context pack
    output_path = Path("docs/CONTEXT_PACK.md")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"✅ Context pack generated: {output_path}")
    print(f"📏 File size: {len(md_content)} characters")

    # Create outputs directory if needed
    outputs_dir = Path("scripts/_context_pack_outputs")
    outputs_dir.mkdir(exist_ok=True)

    # Save raw samples if available
    if 'first_record' in jsonl_info:
        with open(outputs_dir / "sample_record_first.json", 'w', encoding='utf-8') as f:
            json.dump(jsonl_info['first_record'], f, indent=2)

    if jsonl_info.get('middle_record'):
        with open(outputs_dir / "sample_record_middle.json", 'w', encoding='utf-8') as f:
            json.dump(jsonl_info['middle_record'], f, indent=2)

    print(f"💾 Raw samples saved to: {outputs_dir}/")


if __name__ == "__main__":
    generate_context_pack()
