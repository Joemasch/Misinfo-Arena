import sys
import ast
from pathlib import Path

# Add src directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

use_case_files = [
  "arena/application/use_cases/execute_next_turn.py",
]

print(f"Testing syntax of use case modules in {SRC}...")

for use_case_file in use_case_files:
    file_path = SRC / use_case_file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Parse as AST to check syntax
        ast.parse(source, filename=str(file_path))
        print(f"✅ {use_case_file} - syntax OK")

    except SyntaxError as e:
        print(f"❌ {use_case_file} - syntax error: {e}")
        raise
    except Exception as e:
        print(f"❌ {use_case_file} - error: {e}")
        raise

print("OK: Wave 3 use case modules have valid Python syntax")
