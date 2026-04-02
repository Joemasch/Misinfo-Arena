#!/usr/bin/env python3
"""
Wave 3 Dependency Check - Verify use case module independence

Analyzes src/arena/application/use_cases/execute_next_turn.py for dependencies
and generates docs/WAVE3_DEPENDENCY_CHECK.md report.
"""

import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple


def extract_imports_from_file(file_path: Path) -> List[Tuple[int, str]]:
    """Extract all import statements from a Python file with line numbers."""
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line.startswith(('import ', 'from ')) and 'import' in line:
                imports.append((i, line))
    except Exception as e:
        imports.append((0, f"ERROR reading {file_path}: {e}"))

    return imports


def extract_function_signatures(file_path: Path) -> List[Tuple[int, str]]:
    """Extract function definitions from a Python file."""
    signatures = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line.startswith('def ') and '(' in line:
                signatures.append((i, line))
    except Exception as e:
        signatures.append((0, f"ERROR reading {file_path}: {e}"))

    return signatures


def find_symbol_usage_in_function(file_path: Path, function_name: str) -> Set[str]:
    """Find all symbols (function calls, attribute access) used within a specific function."""
    symbols = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the function
        func_pattern = rf'def {re.escape(function_name)}\s*\([^)]*\):'
        func_match = re.search(func_pattern, content, re.MULTILINE)
        if not func_match:
            return symbols

        func_start = func_match.start()

        # Find the end of the function (next function def or end of file)
        next_func_pattern = r'\n[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\):\s*$'
        next_func_match = re.search(next_func_pattern, content[func_start + 1:], re.MULTILINE)

        if next_func_match:
            func_end = func_start + next_func_match.start()
        else:
            func_end = len(content)

        function_content = content[func_start:func_end]

        # Extract symbols using AST
        try:
            tree = ast.parse(function_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Load, ast.Del)):
                    # Variable/attribute access
                    symbols.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # Attribute access like obj.attr
                    symbols.add(node.attr)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    # Function calls
                    symbols.add(node.func.id)
        except:
            # Fallback: regex-based extraction
            symbol_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
            found_symbols = re.findall(symbol_pattern, function_content)
            symbols.update(found_symbols)

    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")

    return symbols


def find_app_imports_in_repo(repo_root: Path) -> List[Tuple[str, int, str]]:
    """Search the entire repository for imports from app.py."""
    app_imports = []

    # Patterns to search for
    patterns = [
        r'from app import',
        r'from app\.',
        r'import app',
        r'from app\.py',
        r'app\.py'
    ]

    # Walk through all Python files
    for root, dirs, files in os.walk(repo_root):
        # Skip common directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', '.git']]

        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines, 1):
                        line_stripped = line.strip()
                        for pattern in patterns:
                            if re.search(pattern, line_stripped):
                                rel_path = file_path.relative_to(repo_root)
                                app_imports.append((str(rel_path), i, line_stripped))
                                break
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return app_imports


def analyze_symbol_origins(use_case_file: Path, symbols: Set[str]) -> Dict[str, Dict]:
    """Analyze where each symbol comes from."""
    origins = {}

    # Read the file content
    try:
        with open(use_case_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"error": str(e)}

    # Check each symbol
    for symbol in sorted(symbols):
        # Skip Python builtins and obvious locals
        if symbol in ['True', 'False', 'None', 'len', 'str', 'int', 'min', 'max', 'range', 'enumerate', 'reversed', 'zip', 'dict', 'list', 'set', 'print', 'isinstance', 'hasattr', 'getattr', 'setattr']:
            continue

        origin_info = {
            "symbol": symbol,
            "origin": "unknown",
            "source": "",
            "notes": ""
        }

        # Check if defined locally in the file
        if f'def {symbol}' in content or f'class {symbol}' in content or f'{symbol} =' in content:
            if f'def {symbol}' in content:
                origin_info["origin"] = "local_function"
                origin_info["source"] = str(use_case_file.name)
            elif f'class {symbol}' in content:
                origin_info["origin"] = "local_class"
                origin_info["source"] = str(use_case_file.name)
            else:
                origin_info["origin"] = "local_variable"
                origin_info["source"] = str(use_case_file.name)
        else:
            # Check imports
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('from ') and ' import ' in line:
                    # from module import symbol1, symbol2
                    parts = line.split(' import ')
                    if len(parts) == 2:
                        module = parts[0].replace('from ', '')
                        imported_symbols = [s.strip() for s in parts[1].split(',')]
                        if symbol in imported_symbols:
                            origin_info["origin"] = "imported"
                            origin_info["source"] = module
                            break
                elif line.startswith('import '):
                    # import module or import module as alias
                    parts = line.split()
                    if len(parts) >= 2:
                        module = parts[1]
                        if symbol == module or (len(parts) >= 4 and parts[3] == symbol):
                            origin_info["origin"] = "imported"
                            origin_info["source"] = module
                            break

        # Special checks
        if symbol in ['DEBUG_DIAG']:
            if 'from app import DEBUG_DIAG' in content:
                origin_info["origin"] = "from_app_py"
                origin_info["source"] = "app.py"
                origin_info["notes"] = "CRITICAL: Direct dependency on app.py"
            elif symbol in content and 'DEBUG_DIAG = False' in content:
                origin_info["origin"] = "local_fallback"
                origin_info["source"] = str(use_case_file.name)

        if origin_info["origin"] == "unknown":
            origin_info["notes"] = "May be missing import or undefined"

        origins[symbol] = origin_info

    return origins


def generate_report():
    """Generate the dependency check report."""
    repo_root = Path(__file__).resolve().parent.parent
    use_case_file = repo_root / "src" / "arena" / "application" / "use_cases" / "execute_next_turn.py"

    report = []

    # Title and summary
    report.append("# Wave 3 Dependency Check Report")
    report.append("")
    report.append("Analysis of `src/arena/application/use_cases/execute_next_turn.py` dependencies")
    report.append("")

    # 1. Inspect the use-case module
    report.append("## 1. Use-Case Module Inspection")
    report.append("")

    if not use_case_file.exists():
        report.append("❌ ERROR: Use case file not found!")
        report.append("")
        summary_verdict = "ERROR: Use case file missing"
    else:
        # Extract imports
        imports = extract_imports_from_file(use_case_file)
        if imports:
            report.append("### Import Block")
            report.append("```python")
            for line_num, import_stmt in imports:
                report.append("2d")
            report.append("```")
            report.append("")

        # Extract function signatures
        signatures = extract_function_signatures(use_case_file)
        execute_next_turn_sig = None
        for line_num, sig in signatures:
            if 'def execute_next_turn' in sig:
                execute_next_turn_sig = (line_num, sig)
                break

        if execute_next_turn_sig:
            report.append("### Function Signature")
            report.append("```python")
            report.append("4d")
            report.append("```")
            report.append("")

        # Find symbols used in execute_next_turn
        symbols_used = find_symbol_usage_in_function(use_case_file, "execute_next_turn")
        report.append("### Symbols Referenced in execute_next_turn")
        report.append(f"Found {len(symbols_used)} unique symbols:")
        for symbol in sorted(symbols_used):
            report.append(f"- `{symbol}`")
        report.append("")

        # 2. Static dependency scan
        report.append("## 2. Repository-Wide App.py Import Scan")
        report.append("")

        app_imports = find_app_imports_in_repo(repo_root)
        if app_imports:
            report.append("⚠️  **WARNING: Found imports from app.py!**")
            report.append("")
            for file_path, line_num, line_content in app_imports:
                report.append(f"- `{file_path}:{line_num}`: `{line_content}`")
            report.append("")
        else:
            report.append("✅ **No imports from app.py found in repository.**")
            report.append("")

        # 3. Symbol origin classification
        report.append("## 3. Symbol Origin Classification")
        report.append("")

        symbol_origins = analyze_symbol_origins(use_case_file, symbols_used)

        if "error" in symbol_origins:
            report.append(f"❌ Error analyzing symbols: {symbol_origins['error']}")
        else:
            report.append("| Symbol | Used in execute_next_turn | Origin | Source | Notes |")
            report.append("|--------|-------------------------|--------|--------|-------|")

            has_app_dependency = False
            for symbol, info in symbol_origins.items():
                origin_display = info["origin"].replace("_", " ").title()
                if info["origin"] == "from_app_py":
                    has_app_dependency = True
                    origin_display = "❌ **From App.py**"

                notes = info["notes"] or ""
                report.append(f"| `{symbol}` | ✅ | {origin_display} | `{info['source']}` | {notes} |")

            report.append("")

        # 4. Circular import risk
        report.append("## 4. Circular Import Risk Assessment")
        report.append("")

        circular_risks = []

        # Check if use case imports presentation modules
        presentation_imports = [imp for _, imp in imports if 'arena.presentation' in imp]
        if presentation_imports:
            circular_risks.append("⚠️  Use case imports presentation modules (should not happen)")

        # Check if use case imports app.py
        app_py_imports = [imp for _, imp in imports if 'app' in imp and 'app.py' not in imp]
        if app_py_imports:
            circular_risks.append("❌ **CRITICAL: Use case imports app.py directly**")

        if not circular_risks:
            report.append("✅ **No circular import risks detected.**")
            report.append("")
            report.append("Use case properly imports only from:")
            report.append("- Standard library")
            report.append("- Domain/infrastructure modules (`arena.*`)")
            report.append("- No presentation layer dependencies")
        else:
            for risk in circular_risks:
                report.append(risk)
            report.append("")

        # Summary verdict
        report.append("## Summary Verdict")
        report.append("")

        if "error" in symbol_origins:
            summary_verdict = "ERROR: Could not analyze dependencies"
        elif has_app_dependency:
            summary_verdict = "❌ **UNSAFE: Depends on app.py**"
        elif circular_risks:
            summary_verdict = "❌ **UNSAFE: Circular import risk**"
        elif not use_case_file.exists():
            summary_verdict = "ERROR: Use case file missing"
        else:
            summary_verdict = "✅ **SAFE: No app.py dependency**"

        report.append(f"**{summary_verdict}**")

    # Write the report
    output_path = repo_root / "docs" / "WAVE3_DEPENDENCY_CHECK.md"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    generate_report()

