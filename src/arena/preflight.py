"""
Import preflight checks for Misinformation Arena.

This module contains health checks that run early in app startup to catch
import resolution issues before they cause runtime errors.
"""

import sys
from pathlib import Path


def assert_src_arena():
    """
    Assert that the arena package is being imported from src/arena/,
    not from a duplicate directory that could cause import shadowing.

    This prevents the ModuleNotFoundError issues that occur when there are
    duplicate arena directories in the repository.

    Raises:
        RuntimeError: If arena is not imported from src/arena/
    """
    try:
        import arena

        # Check if arena is coming from src/arena/
        if hasattr(arena, '__file__'):
            arena_path = Path(arena.__file__).resolve()
            src_arena_path = Path(__file__).resolve().parent  # src/arena/

            if not str(arena_path).startswith(str(src_arena_path.parent)):
                raise RuntimeError(
                    f"arena package not imported from src/arena/!\n"
                    f"  Current location: {arena_path}\n"
                    f"  Expected location: {src_arena_path}\n"
                    f"  This usually means there's a duplicate arena/ directory\n"
                    f"  shadowing the intended src/arena/ package.\n"
                    f"  \n"
                    f"  To fix:\n"
                    f"  1. Check for duplicate arena/ directories in repo root\n"
                    f"  2. Remove or rename conflicting directories\n"
                    f"  3. Ensure src/ is on sys.path before importing arena"
                )

        elif hasattr(arena, '__path__'):
            # For namespace packages
            arena_paths = [Path(p).resolve() for p in arena.__path__]
            src_arena_path = Path(__file__).resolve().parent

            if not any(str(src_arena_path.parent) in str(p) for p in arena_paths):
                raise RuntimeError(
                    f"arena package not found in src/arena/!\n"
                    f"  Found paths: {arena_paths}\n"
                    f"  Expected in: {src_arena_path}\n"
                    f"  \n"
                    f"  This usually means src/ is not on sys.path or\n"
                    f"  the src/arena/ package structure is incomplete."
                )

    except ImportError as e:
        raise RuntimeError(
            f"Cannot import arena package!\n"
            f"  Error: {e}\n"
            f"  \n"
            f"  This usually means:\n"
            f"  1. src/ is not on sys.path\n"
            f"  2. src/arena/ package is missing or incomplete\n"
            f"  3. There are no __init__.py files in package directories\n"
            f"  \n"
            f"  Ensure src/ is added to sys.path before importing arena."
        )


def check_critical_imports():
    """
    Check that all critical arena submodules can be imported.

    This catches import issues early rather than at runtime when
    the modules are first used.

    Raises:
        RuntimeError: If any critical imports fail
    """
    critical_modules = [
        'arena.config',
        'arena.factories',
        'arena.concession',
        'arena.judge',
        # Note: arena.agents and arena.state have streamlit dependencies
        # so they can't be tested here
    ]

    failed_imports = []

    for module_name in critical_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            failed_imports.append(f"{module_name}: {e}")
        except Exception as e:
            # Other exceptions (like streamlit dependencies) are OK here
            # We only care about import resolution
            if "No module named" in str(e):
                failed_imports.append(f"{module_name}: {e}")

    if failed_imports:
        raise RuntimeError(
            f"Critical arena imports failed!\n"
            f"  Failed modules:\n" +
            "\n".join(f"    - {failure}" for failure in failed_imports) + "\n"
            f"  \n"
            f"  This usually means the src/arena/ package structure is incomplete\n"
            f"  or there are missing module files."
        )


def run_preflight_checks():
    """
    Run all preflight checks for the arena package.

    This should be called early in app startup, after sys.path is set up
    but before any arena functionality is used.

    Raises:
        RuntimeError: If any preflight checks fail
    """
    assert_src_arena()
    check_critical_imports()


