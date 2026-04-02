"""
Import and minimal runtime smoke tests for Analytics page (Phase 4A).
"""

import json
import tempfile
from pathlib import Path

from arena.analysis.episode_dataset import (
    build_episode_df,
    build_episode_long_df,
)


def test_import_render_analytics_page():
    """Import render_analytics_page without error."""
    from arena.presentation.streamlit.pages.analytics_page import render_analytics_page

    assert callable(render_analytics_page)


def test_import_build_functions():
    """Import build_episode_df and build_episode_long_df."""
    assert callable(build_episode_df)
    assert callable(build_episode_long_df)


def test_synthetic_temp_run_long_df_12_rows_and_arena_type():
    """Build long_df on synthetic temp run with 1 complete episode; verify 12 rows and arena_type."""
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp)
        run_id = "synthetic_run"
        run_dir = runs / run_id
        run_dir.mkdir()

        run_json = {
            "schema_version": "2.0",
            "run_id": run_id,
            "arena_type": "single_claim",
            "created_at": "2026-01-01T12:00:00",
            "run_config": {
                "agents": {
                    "spreader": {"model": "gpt-4o"},
                    "debunker": {"model": "gpt-4o"},
                    "judge": {"model": "heuristic"},
                },
            },
            "storage": {},
        }
        (run_dir / "run.json").write_text(json.dumps(run_json, indent=2))

        scorecard = [
            {"metric": "truthfulness_proxy", "spreader": 5.0, "debunker": 7.0, "weight": 0.2},
            {"metric": "evidence_quality", "spreader": 5.0, "debunker": 7.0, "weight": 0.2},
            {"metric": "reasoning_quality", "spreader": 5.0, "debunker": 7.0, "weight": 0.2},
            {"metric": "responsiveness", "spreader": 5.0, "debunker": 7.0, "weight": 0.15},
            {"metric": "persuasion", "spreader": 5.0, "debunker": 7.0, "weight": 0.15},
            {"metric": "civility", "spreader": 5.0, "debunker": 7.0, "weight": 0.1},
        ]
        episode = {
            "schema_version": "2.0",
            "run_id": run_id,
            "episode_id": 1,
            "claim": "test",
            "results": {"winner": "debunker", "judge_confidence": 0.8, "scorecard": scorecard},
            "config_snapshot": {"planned_max_turns": 3},
            "judge_audit": {"status": "success", "mode": "heuristic"},
            "concession": {},
            "summaries": {},
            "turns": [],
        }
        (run_dir / "episodes.jsonl").write_text(json.dumps(episode) + "\n")

        wide_df, _ = build_episode_df([run_id], runs_dir=str(runs))
        long_df = build_episode_long_df([run_id], runs_dir=str(runs))

        assert len(wide_df) == 1
        assert "arena_type" in wide_df.columns
        assert wide_df["arena_type"].iloc[0] == "single_claim"

        assert len(long_df) == 12
        assert "arena_type" in long_df.columns
        assert (long_df["arena_type"] == "single_claim").all()


def test_no_traj_view_symbol_left():
    """Regression: traj_view was renamed to trajectory_view_effective; view=traj_view must not appear."""
    repo_root = Path(__file__).resolve().parent.parent
    p = repo_root / "src" / "arena" / "presentation" / "streamlit" / "pages" / "analytics_page.py"
    txt = p.read_text(encoding="utf-8")
    assert "view=traj_view" not in txt, "Obsolete view=traj_view should be view=trajectory_view_effective"


def test_compute_episode_trajectory_view_param():
    """Regression: compute_episode_trajectory accepts view='raw'."""
    from arena.analysis.research_analytics import compute_episode_trajectory
    import pandas as pd
    df = pd.DataFrame([
        {"episode_index": 0, "side": "spreader", "metric_name": "persuasion", "metric_value": 5.0},
        {"episode_index": 0, "side": "debunker", "metric_name": "persuasion", "metric_value": 6.0},
        {"episode_index": 1, "side": "spreader", "metric_name": "persuasion", "metric_value": 4.5},
        {"episode_index": 1, "side": "debunker", "metric_name": "persuasion", "metric_value": 5.5},
    ])
    result = compute_episode_trajectory(df, "persuasion", view="raw")
    assert "episode_index" in result.columns
    assert "spreader_value" in result.columns
    assert "debunker_value" in result.columns
