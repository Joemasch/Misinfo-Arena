"""
Tests for research_analytics pure functions.
"""

import pandas as pd
import pytest

from arena.analysis.research_analytics import (
    apply_research_filters,
    compute_transparency_summary,
    compute_strength_fingerprint,
    compute_episode_trajectory,
)


def _make_synthetic_long_df():
    """2 runs, 2 episodes, 6 metrics, 2 sides."""
    rows = []
    metrics = ["truthfulness_proxy", "evidence_quality", "reasoning_quality", "responsiveness", "persuasion", "civility"]
    for run_id in ["r1", "r2"]:
        for ep_idx in range(2):
            ep_id = f"ep{ep_idx}"
            for metric in metrics:
                for side in ["spreader", "debunker"]:
                    val = 5.0 + (1 if side == "debunker" else -1) * 0.5
                    rows.append({
                        "run_id": run_id,
                        "episode_id": ep_id,
                        "episode_index": ep_idx,
                        "arena_type": "single_claim" if run_id == "r1" else "golden_set_v1",
                        "judge_mode": "agent",
                        "model_spreader": "gpt-4o",
                        "model_debunker": "gpt-4o",
                        "model_judge": "gpt-4o",
                        "side": side,
                        "metric_name": metric,
                        "metric_value": val,
                        "error_flag": ep_idx == 1 and run_id == "r2",
                    })
    return pd.DataFrame(rows)


def test_apply_research_filters_excludes_error_rows_when_enabled():
    df = _make_synthetic_long_df()
    filtered = apply_research_filters(df, exclude_error_episodes=True)
    assert "error_flag" in df.columns
    err_rows = df[df["error_flag"] == True]
    assert len(err_rows) > 0
    assert len(filtered) < len(df)
    # No rows with error_flag True should remain
    if "error_flag" in filtered.columns:
        assert (filtered["error_flag"] == True).sum() == 0


def test_compute_transparency_summary_returns_correct_counts():
    df = _make_synthetic_long_df()
    summary = compute_transparency_summary(df)
    assert summary["n_runs"] == 2
    assert summary["n_episodes"] == 4  # 2 runs * 2 episodes
    assert summary["n_rows"] == len(df)
    assert "arena_type_counts" in summary
    assert "judge_mode_counts" in summary
    assert summary["arena_type_counts"].get("single_claim", 0) > 0
    assert summary["arena_type_counts"].get("golden_set_v1", 0) > 0


def test_compute_strength_fingerprint_mean_aggregation():
    df = _make_synthetic_long_df()
    fp = compute_strength_fingerprint(df, agg="mean", view="raw")
    assert "metric_name" in fp.columns
    assert "spreader_value" in fp.columns
    assert "debunker_value" in fp.columns
    assert "delta_value" in fp.columns
    assert len(fp) == 6
    # Debunker should generally score higher than spreader in synthetic data
    deltas = fp["delta_value"].dropna()
    assert (deltas > 0).sum() >= 1


def test_compute_strength_fingerprint_normalized_returns_0_to_1():
    df = _make_synthetic_long_df()
    fp = compute_strength_fingerprint(df, agg="mean", view="normalized")
    for col in ["spreader_value", "debunker_value"]:
        vals = fp[col].dropna()
        if len(vals) > 0:
            assert vals.min() >= 0
            assert vals.max() <= 1


def test_compute_episode_trajectory_returns_sorted_episode_index_and_columns():
    df = _make_synthetic_long_df()
    traj = compute_episode_trajectory(df, "persuasion", view="raw")
    assert "episode_index" in traj.columns
    assert "spreader_value" in traj.columns
    assert "debunker_value" in traj.columns
    assert traj["episode_index"].is_monotonic_increasing
    assert len(traj) >= 2


def test_apply_research_filters_judge_modes_excludes_heuristic():
    """Applying judge_modes=['agent'] excludes rows with judge_mode='heuristic'."""
    rows = []
    metrics = ["persuasion", "civility"]
    for run_id, judge_mode in [("r1", "agent"), ("r2", "heuristic")]:
        for ep_idx in range(1):
            for metric in metrics:
                for side in ["spreader", "debunker"]:
                    rows.append({
                        "run_id": run_id,
                        "episode_id": f"e{ep_idx}",
                        "episode_index": ep_idx,
                        "judge_mode": judge_mode,
                        "side": side,
                        "metric_name": metric,
                        "metric_value": 5.0,
                        "error_flag": False,
                    })
    df = pd.DataFrame(rows)
    filtered = apply_research_filters(df, judge_modes=["agent"], exclude_error_episodes=False)
    assert len(filtered) > 0
    assert filtered["judge_mode"].nunique() == 1
    assert (filtered["judge_mode"] == "agent").all()
    assert "heuristic" not in filtered["judge_mode"].values
