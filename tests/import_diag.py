#!/usr/bin/env python3
"""
Import Diagnostic Script for Misinformation Arena v2

This script diagnoses import resolution issues with the arena package.
Run from repository root: python import_diag.py
"""

import sys
import os

def main():
    print("=" * 60)
    print("MISINFORMATION ARENA IMPORT DIAGNOSTIC")
    print("=" * 60)

    # a) Python version and executable
    print("a) Python Version & Executable:")
    print(f"   Python version: {sys.version}")
    print(f"   Executable: {sys.executable}")
    print()

    # b) Current working directory
    print("b) Current Working Directory:")
    print(f"   CWD: {os.getcwd()}")
    print()

    # c) sys.path analysis
    print("c) sys.path Analysis:")
    print(f"   Total sys.path entries: {len(sys.path)}")
    print("   First 10 entries:")
    for i, path in enumerate(sys.path[:10]):
        marker = " <-- SRC DIR" if "src" in path else ""
        print(f"   {i}: {path}{marker}")

    if len(sys.path) > 10:
        print(f"   ... and {len(sys.path) - 10} more")
    print()

    # d) src directory status
    src_path = os.path.join(os.getcwd(), "src")
    print("d) src Directory Status:")
    print(f"   src exists: {os.path.exists(src_path)}")
    print(f"   src is dir: {os.path.isdir(src_path)}")
    print(f"   src/arena exists: {os.path.exists(os.path.join(src_path, 'arena'))}")
    print(f"   src on sys.path: {src_path in sys.path}")
    print()

    # e) arena package resolution
    print("e) Arena Package Resolution:")
    try:
        import arena
        print("   ✅ import arena: SUCCESS")
        if hasattr(arena, '__file__'):
            print(f"   arena.__file__: {arena.__file__}")
        if hasattr(arena, '__path__'):
            print(f"   arena.__path__: {arena.__path__}")

        # Check which arena directory it's coming from
        if hasattr(arena, '__file__'):
            if 'src' in arena.__file__:
                print("   📁 Source: src/arena/")
            else:
                print("   📁 Source: root/arena/")
    except ImportError as e:
        print(f"   ❌ import arena: FAILED - {e}")
    print()

    # f) Specific arena submodules
    print("f) Arena Submodule Resolution:")
    # Test modules that don't import streamlit first
    safe_submodules = ['factories', 'concession', 'judge']
    streamlit_submodules = ['agents', 'config', 'state']

    all_submodules = safe_submodules + streamlit_submodules

    for submodule in all_submodules:
        module_name = f'arena.{submodule}'
        try:
            module = __import__(module_name, fromlist=[''])
            status = "✅ SUCCESS"
            file_info = ""
            if hasattr(module, '__file__'):
                file_info = f" ({module.__file__})"
        except ImportError as e:
            status = f"❌ FAILED - {e}"
            file_info = ""
        except Exception as e:
            if "streamlit" in str(e).lower():
                status = "⚠️  STREAMLIT DEP - can't test outside app"
                file_info = " (expected in Streamlit context)"
            else:
                status = f"❌ ERROR - {e}"
                file_info = ""

        print(f"   {module_name}: {status}{file_info}")
    print()

    # g) Check for duplicate arena directories
    print("g) Duplicate Package Detection:")
    root_arena = os.path.join(os.getcwd(), "arena")
    src_arena = os.path.join(os.getcwd(), "src", "arena")

    print(f"   Root arena/ exists: {os.path.exists(root_arena)}")
    print(f"   src/arena/ exists: {os.path.exists(src_arena)}")

    if os.path.exists(root_arena) and os.path.exists(src_arena):
        print("   ⚠️  WARNING: Duplicate arena directories detected!")
        print("      This can cause import shadowing and confusion.")

        # Check which one is being used
        try:
            import arena
            if hasattr(arena, '__file__') and 'src' in arena.__file__:
                print("      Currently using: src/arena/")
            else:
                print("      Currently using: root/arena/")
        except:
            print("      Cannot determine which is being used due to import failure")
    else:
        print("   ✅ No duplicate arena directories found")
    print()

    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
