#!/usr/bin/env python3
"""
Import Health Check Script for Misinformation Arena

This script verifies that all critical arena imports work correctly.
It can be run standalone or as part of CI/CD pipelines.

Usage:
    python scripts/import_health_check.py

Exit codes:
    0: All imports successful
    1: Import failures detected
"""

import sys
import os
from pathlib import Path

def main():
    """Run import health checks."""
    print("🔍 Misinformation Arena Import Health Check")
    print("=" * 50)

    # Setup sys.path like app.py does
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"

    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
        print(f"✅ Added src/ to sys.path: {src_dir}")
    else:
        print(f"✅ src/ already on sys.path or not found: {src_dir}")

    print()

    # Test arena package resolution
    print("📦 Testing arena package resolution...")
    try:
        import arena
        print("✅ arena package imported successfully")

        if hasattr(arena, '__file__'):
            arena_file = Path(arena.__file__)
            if 'src' in str(arena_file):
                print(f"✅ arena resolved to src/: {arena_file}")
            else:
                print(f"⚠️  arena NOT resolved to src/: {arena_file}")
                return False
        else:
            print("⚠️  arena has no __file__ attribute")

    except ImportError as e:
        print(f"❌ Failed to import arena package: {e}")
        return False

    print()

    # Test critical submodules (non-streamlit dependent)
    print("📚 Testing critical submodules...")
    critical_modules = [
        'arena.config',
        'arena.factories',
        'arena.concession',
        'arena.judge',
        'arena.storage',
        'arena.analytics',
        'arena.judge_explain',
    ]

    failed_modules = []

    for module_name in critical_modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            failed_modules.append(module_name)
        except Exception as e:
            # Handle streamlit dependencies gracefully
            if 'streamlit' in str(e).lower():
                print(f"⚠️  {module_name}: Has streamlit dependency (expected)")
            else:
                print(f"❌ {module_name}: Unexpected error: {e}")
                failed_modules.append(module_name)

    print()

    # Test streamlit-dependent modules (if streamlit available)
    print("🎨 Testing streamlit-dependent modules...")
    streamlit_modules = [
        'arena.agents',
        'arena.state',
    ]

    streamlit_available = False
    try:
        import streamlit as st
        streamlit_available = True
        print("✅ Streamlit available, testing dependent modules...")
    except ImportError:
        print("⚠️  Streamlit not available, skipping dependent modules")
    except Exception as e:
        # Handle cases where streamlit import fails due to environment issues
        print("⚠️  Streamlit import failed, skipping dependent modules")
        print(f"   (Error: {e})")

    if streamlit_available:
        for module_name in streamlit_modules:
            try:
                __import__(module_name)
                print(f"✅ {module_name}")
            except Exception as e:
                print(f"❌ {module_name}: {e}")
                failed_modules.append(module_name)

    print()

    # Check for duplicate arena directories
    print("🔍 Checking for duplicate arena directories...")
    root_arena = repo_root / "arena"
    src_arena = repo_root / "src" / "arena"

    if root_arena.exists():
        print(f"❌ Duplicate arena/ directory found at repo root: {root_arena}")
        print("   This will cause import shadowing. Remove or rename it.")
        failed_modules.append("duplicate-arena-directory")
    else:
        print("✅ No duplicate arena/ directory at repo root")

    if not src_arena.exists():
        print(f"❌ src/arena/ directory missing: {src_arena}")
        failed_modules.append("missing-src-arena")
    else:
        print("✅ src/arena/ directory exists")

    print()

    # Summary
    if failed_modules:
        print("❌ IMPORT HEALTH CHECK FAILED")
        print(f"   {len(failed_modules)} issues found:")
        for failure in failed_modules:
            print(f"   - {failure}")
        print()
        print("🔧 To fix:")
        print("   1. Ensure src/ is on sys.path before importing arena")
        print("   2. Remove any duplicate arena/ directories")
        print("   3. Check that all modules exist in src/arena/")
        return False
    else:
        print("✅ IMPORT HEALTH CHECK PASSED")
        print("   All critical imports working correctly")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
