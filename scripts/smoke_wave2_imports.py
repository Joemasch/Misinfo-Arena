import sys
import ast
from pathlib import Path

# Add src directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

component_files = [
  "arena/presentation/streamlit/components/arena/judge_report.py",
  "arena/presentation/streamlit/components/arena/debate_insights.py",
]

print(f"Testing syntax of arena component modules in {SRC}...")

for component_file in component_files:
    file_path = SRC / component_file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Parse as AST to check syntax
        ast.parse(source, filename=str(file_path))
        print(f"✅ {component_file} - syntax OK")

    except SyntaxError as e:
        print(f"❌ {component_file} - syntax error: {e}")
        raise
    except Exception as e:
        print(f"❌ {component_file} - error: {e}")
        raise

print("OK: Wave 2 arena component modules have valid Python syntax")

