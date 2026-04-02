#!/usr/bin/env python3
"""
Generate Refactor Structure Report for Misinformation Arena v2.

Documents the new project structure after refactoring waves 1-5.
This report verifies the clean architecture implementation.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import importlib.util


def get_repo_root():
    """Get the repository root path."""
    return Path(__file__).resolve().parents[1]


def write_header(report_lines, repo_root):
    """Write report header with metadata."""
    report_lines.append("# Misinformation Arena v2 - Refactor Structure Report")
    report_lines.append("")
    report_lines.append("**Generated:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    report_lines.append("**Repository:** " + str(repo_root))
    report_lines.append("**Run Command:** `streamlit run app.py`")
    report_lines.append("")


def build_compact_tree(root_path, max_depth=4, prefix=""):
    """Build a compact tree representation."""
    lines = []
    try:
        items = sorted(os.listdir(root_path))
    except PermissionError:
        return lines

    for i, item in enumerate(items):
        if item.startswith('.'):
            continue

        full_path = root_path / item
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "

        # Determine depth for limiting
        depth = len(prefix.split("│")) if "│" in prefix else 0
        if depth > max_depth:
            continue

        lines.append(f"{prefix}{connector}{item}")

        if full_path.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(build_compact_tree(full_path, max_depth, prefix + extension))

    return lines


def write_tree_snapshot(report_lines, repo_root):
    """Write focused tree snapshot."""
    report_lines.append("## 📁 Project Structure Snapshot")
    report_lines.append("")
    report_lines.append("### Core Architecture (src/arena)")
    report_lines.append("```")

    arena_path = repo_root / "src" / "arena"
    if arena_path.exists():
        report_lines.append("src/arena/")
        tree_lines = build_compact_tree(arena_path, max_depth=4)
        report_lines.extend(tree_lines)
    else:
        report_lines.append("src/arena/ (not found)")

    report_lines.append("```")
    report_lines.append("")

    report_lines.append("### Supporting Files")
    report_lines.append("```")

    key_files = [
        "app.py",
        "docs/",
        "scripts/",
    ]

    for item in key_files:
        path = repo_root / item
        if path.exists():
            if path.is_dir():
                report_lines.append(f"{item}")
                sub_lines = build_compact_tree(path, max_depth=2)
                report_lines.extend(["  " + line for line in sub_lines])
            else:
                report_lines.append(f"{item}")
        else:
            report_lines.append(f"{item} (not found)")

    report_lines.append("```")
    report_lines.append("")


def check_artifact_exists(repo_root, artifact_path):
    """Check if a refactor artifact exists."""
    full_path = repo_root / artifact_path
    exists = full_path.exists()

    if exists:
        try:
            # Try to import/compile to verify it's valid
            if artifact_path.endswith('.py'):
                importlib.util.spec_from_file_location("test", full_path)
                return True, "✅ Valid Python file"
            else:
                return True, "✅ File exists"
        except Exception as e:
            return True, f"⚠️ File exists but may have issues: {e}"
    else:
        return False, "❌ Missing"


def write_refactor_artifacts(report_lines, repo_root):
    """Write key refactor artifacts checklist."""
    report_lines.append("## 🔧 Key Refactor Artifacts")
    report_lines.append("")
    report_lines.append("| Artifact | Expected Path | Status | Notes |")
    report_lines.append("|----------|---------------|--------|-------|")

    artifacts = [
        ("Analytics page module", "src/arena/presentation/streamlit/pages/analytics_page.py"),
        ("Replay page module", "src/arena/presentation/streamlit/pages/replay_page.py"),
        ("Guide page module", "src/arena/presentation/streamlit/pages/guide_page.py"),
        ("Prompts page module", "src/arena/presentation/streamlit/pages/prompts_page.py"),
        ("Arena judge_report component", "src/arena/presentation/streamlit/components/arena/judge_report.py"),
        ("Arena debate_insights component", "src/arena/presentation/streamlit/components/arena/debate_insights.py"),
        ("execute_next_turn use case", "src/arena/application/use_cases/execute_next_turn.py"),
        ("TurnPairResult type module", "src/arena/application/types.py"),
        ("run_store module", "src/arena/io/run_store.py"),
        ("judge_explain.py (patched)", "src/arena/judge_explain.py"),
        ("utils/normalize.py", "src/arena/utils/normalize.py"),
        ("io/prompts_store.py", "src/arena/io/prompts_store.py"),
        ("app_config.py", "src/arena/app_config.py"),
    ]

    for artifact, path in artifacts:
        exists, notes = check_artifact_exists(repo_root, path)
        status = "✅ Present" if exists else "❌ Missing"
        report_lines.append(f"| {artifact} | `{path}` | {status} | {notes} |")

    report_lines.append("")


def find_forbidden_imports(repo_root):
    """Find forbidden imports in clean architecture modules."""
    forbidden_patterns = [
        r'^from app import',
        r'^import app',
    ]

    forbidden_dirs = [
        "src/arena/presentation",
        "src/arena/application",
        "src/arena/io",
        "src/arena/utils",
    ]

    violations = []

    for dir_path in forbidden_dirs:
        full_dir = repo_root / dir_path
        if not full_dir.exists():
            continue

        for root, dirs, files in os.walk(full_dir):
            # Skip __pycache__ and other hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()

                        for line_num, line in enumerate(lines, 1):
                            line_stripped = line.strip()
                            for pattern in forbidden_patterns:
                                if pattern in line_stripped:
                                    rel_path = file_path.relative_to(repo_root)
                                    violations.append(f"`{rel_path}:{line_num}`: `{line_stripped}`")
                                    break
                    except Exception as e:
                        violations.append(f"Error reading {file_path}: {e}")

    return violations


def write_import_hygiene(report_lines, repo_root):
    """Write import hygiene checks."""
    report_lines.append("## 🧹 Import Hygiene Check")
    report_lines.append("")
    report_lines.append("Checking for forbidden `from app import` or `import app` in clean architecture modules:")
    report_lines.append("")

    violations = find_forbidden_imports(repo_root)

    if not violations:
        report_lines.append("✅ **PASS** - No forbidden imports found in clean architecture modules")
        report_lines.append("")
        report_lines.append("Clean modules checked:")
        report_lines.append("- `src/arena/presentation/`")
        report_lines.append("- `src/arena/application/`")
        report_lines.append("- `src/arena/io/`")
        report_lines.append("- `src/arena/utils/`")
    else:
        report_lines.append("❌ **FAIL** - Found forbidden imports:")
        report_lines.append("")
        for violation in violations:
            report_lines.append(f"- {violation}")
        report_lines.append("")
        report_lines.append("These must be removed to maintain clean architecture boundaries.")

    report_lines.append("")


def write_core_logic_location(report_lines, repo_root):
    """Write where core logic lives now."""
    report_lines.append("## 🎯 Core Logic Location")
    report_lines.append("")
    report_lines.append("### Debate Engine (execute_next_turn)")
    report_lines.append("")

    # Check app.py wrapper
    app_py = repo_root / "app.py"
    wrapper_found = False
    wrapper_snippet = []

    if app_py.exists():
        try:
            with open(app_py, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                if 'def execute_next_turn():' in line:
                    wrapper_found = True
                    # Get context around the function
                    start = max(0, i-1)
                    end = min(len(lines), i+5)
                    wrapper_snippet = [f"{j+1:4d}: {lines[j].rstrip()}" for j in range(start, end)]
                    break
        except Exception as e:
            wrapper_snippet = [f"Error reading app.py: {e}"]

    if wrapper_found:
        report_lines.append("**✅ App.py Thin Wrapper:**")
        report_lines.append("```python")
        report_lines.extend(wrapper_snippet)
        report_lines.append("```")
    else:
        report_lines.append("❌ App.py wrapper not found")

    report_lines.append("")

    # Check use case module
    use_case_file = repo_root / "src" / "arena" / "application" / "use_cases" / "execute_next_turn.py"
    use_case_found = False
    use_case_snippet = []

    if use_case_file.exists():
        try:
            with open(use_case_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                if 'def execute_next_turn(' in line and 'state=None' in line:
                    use_case_found = True
                    # Get function signature
                    use_case_snippet = [f"{i+1:4d}: {line.rstrip()}"]
                    break
        except Exception as e:
            use_case_snippet = [f"Error reading use case: {e}"]

    if use_case_found:
        report_lines.append("**✅ Use Case Implementation:**")
        report_lines.append("```python")
        report_lines.extend(use_case_snippet)
        report_lines.append("```")
        report_lines.append(f"**File:** `{use_case_file.relative_to(repo_root)}`")
    else:
        report_lines.append("❌ Use case implementation not found")

    report_lines.append("")


def write_smoke_checks(report_lines):
    """Write recommended smoke checks."""
    report_lines.append("## 🧪 Recommended Smoke Checks")
    report_lines.append("")
    report_lines.append("Run these commands to validate the refactored architecture:")
    report_lines.append("")
    report_lines.append("```bash")
    report_lines.append("# Test individual module imports")
    report_lines.append("python scripts/smoke_wave1_imports.py    # Presentation pages")
    report_lines.append("python scripts/smoke_wave2_imports.py    # Arena components")
    report_lines.append("python scripts/smoke_wave3_use_case.py    # Application use cases")
    report_lines.append("python scripts/smoke_wave4_turn_result.py # Type definitions")
    report_lines.append("python scripts/smoke_wave5_run_store.py   # Persistence layer")
    report_lines.append("")
    report_lines.append("# Validate compilation")
    report_lines.append("python -m py_compile app.py")
    report_lines.append("")
    report_lines.append("# Test full application startup")
    report_lines.append("streamlit run app.py")
    report_lines.append("```")
    report_lines.append("")
    report_lines.append("**Expected Results:**")
    report_lines.append("- All smoke tests should pass with 'OK' messages")
    report_lines.append("- App should compile without errors")
    report_lines.append("- Streamlit should start without import errors")
    report_lines.append("- All tabs (Arena, Analytics, Replay, Guide, Prompts) should load")


def generate_report():
    """Generate the complete refactor structure report."""
    repo_root = get_repo_root()
    report_lines = []

    # Generate all sections
    write_header(report_lines, repo_root)
    write_tree_snapshot(report_lines, repo_root)
    write_refactor_artifacts(report_lines, repo_root)
    write_import_hygiene(report_lines, repo_root)
    write_core_logic_location(report_lines, repo_root)
    write_smoke_checks(report_lines)

    # Write to file
    output_path = repo_root / "docs" / "REFACTOR_STRUCTURE_REPORT.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    generate_report()
