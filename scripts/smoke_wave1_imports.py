import sys
import ast
from pathlib import Path

# Add src directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

page_files = [
  "arena/presentation/streamlit/pages/analytics_page.py",
  "arena/presentation/streamlit/pages/replay_page.py",
  "arena/presentation/streamlit/pages/guide_page.py",
  "arena/presentation/streamlit/pages/prompts_page.py",
]

print(f"Testing syntax of page modules in {SRC}...")

for page_file in page_files:
    file_path = SRC / page_file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Parse as AST to check syntax
        ast.parse(source, filename=str(file_path))
        print(f"✅ {page_file} - syntax OK")

    except SyntaxError as e:
        print(f"❌ {page_file} - syntax error: {e}")
        raise
    except Exception as e:
        print(f"❌ {page_file} - error: {e}")
        raise

print("OK: Wave 1 page modules have valid Python syntax")
