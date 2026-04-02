"""
Tests for Phase 4A: run metadata ingestion and long-format analytics layer.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from arena.io.run_store_v2_read import (
    load_run_metadata,
    extract_run_metadata_fields,
)
from arena.analysis.episode_dataset import (
    CANONICAL_METRICS,
    episode_to_long_rows,
    episode_to_row,
    build_episode_df,
    build_episode_long_df,
)


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def tmp_runs_dir():
    """Temporary runs directory with run.json and episodes.jsonl."""
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp)
        run_id = "test_run_001"
        run_dir = runs / run_id
        run_dir.mkdir()

        run_json = {
            "schema_version": "2.0",
            "run_id": run_id,
            "created_at": "2026-01-01T12:00:00",
            "arena_type": "single_claim",
            "input": {"single_claim": "test claim", "claims": []},
            "run_config": {
                "episode_count": 1,
                "agents": {
                    "spreader": {"model": "gpt-4o", "temperature": 0.7},
                    "debunker": {"model": "gpt-4o", "temperature": 0.7},
                    "judge": {"model": "heuristic", "temperature": None},
                },
                "judge_weights": {
                    "factuality": 0.167,
                    "source_credibility": 0.167,
                    "reasoning_quality": 0.167,
                    "responsiveness": 0.167,
                    "persuasion": 0.167,
                    "manipulation_awareness": 0.167,
                },
            },
            "storage": {"episodes_file": "episodes.jsonl"},
        }
        with open(run_dir / "run.json", "w") as f:
            json.dump(run_json, f, indent=2)

        episode_full = {
            "schema_version": "2.0",
            "run_id": run_id,
            "episode_id": 1,
            "created_at": "2026-01-01T12:01:00",
            "claim": "test claim",
            "config_snapshot": {
                "planned_max_turns": 3,
                "agents": {
                    "spreader": {"model": "gpt-4o"},
                    "debunker": {"model": "gpt-4o"},
                    "judge": {"model": "heuristic", "type": "heuristic"},
                },
            },
            "results": {
                "completed_turn_pairs": 3,
                "winner": "debunker",
                "judge_confidence": 0.8,
                "reason": "Test reason",
                "totals": {"spreader": 5.0, "debunker": 7.0},
                "scorecard": [
                    {"metric": "factuality", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                    {"metric": "source_credibility", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                    {"metric": "reasoning_quality", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                    {"metric": "responsiveness", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                    {"metric": "persuasion", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                    {"metric": "manipulation_awareness", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                ],
            },
            "concession": {"early_stop": False, "trigger": "max_turns", "conceded_by": None},
            "summaries": {"abridged": "", "full": "", "version": "v0"},
            "turns": [],
            "judge_audit": {"status": "success", "mode": "heuristic", "version": "heuristic"},
        }

        with open(run_dir / "episodes.jsonl", "w") as f:
            f.write(json.dumps(episode_full) + "\n")

        yield runs


# -------------------------------------------------------------------------
# Tests: run.json metadata extraction
# -------------------------------------------------------------------------

def test_load_run_metadata_missing_file():
    with tempfile.TemporaryDirectory() as tmp:
        meta = load_run_metadata(tmp, "nonexistent_run")
    assert meta is None


def test_load_run_metadata_success(tmp_runs_dir):
    meta = load_run_metadata(str(tmp_runs_dir), "test_run_001")
    assert meta is not None
    assert meta.get("arena_type") == "single_claim"
    assert meta.get("run_id") == "test_run_001"
    assert (meta.get("run_config") or {}).get("agents")


def test_extract_run_metadata_fields_none():
    out = extract_run_metadata_fields(None)
    assert out["arena_type"] == "single_claim"
    assert out["run_spreader_model"] is None
    assert out["run_debunker_model"] is None
    assert out["run_judge_model"] is None
    assert out["run_created_at"] is None


def test_extract_run_metadata_fields_success(tmp_runs_dir):
    meta = load_run_metadata(str(tmp_runs_dir), "test_run_001")
    out = extract_run_metadata_fields(meta)
    assert out["arena_type"] == "single_claim"
    assert out["run_spreader_model"] == "gpt-4o"
    assert out["run_debunker_model"] == "gpt-4o"
    assert out["run_judge_model"] == "heuristic"
    assert out["run_created_at"] == "2026-01-01T12:00:00"


# -------------------------------------------------------------------------
# Tests: episode_to_long_rows
# -------------------------------------------------------------------------

def test_episode_to_long_rows_returns_12_for_6_metrics():
    ep = {
        "episode_id": 1,
        "claim": "x",
        "results": {
            "winner": "debunker",
            "judge_confidence": 0.8,
            "scorecard": [
                {"metric": "factuality", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                {"metric": "source_credibility", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                {"metric": "reasoning_quality", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                {"metric": "responsiveness", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                {"metric": "persuasion", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
                {"metric": "manipulation_awareness", "spreader": 5.0, "debunker": 7.0, "weight": 0.167},
            ],
        },
        "config_snapshot": {"planned_max_turns": 3},
        "judge_audit": {"status": "success", "mode": "heuristic"},
    }
    run_meta = {"arena_type": "single_claim", "run_spreader_model": "gpt-4o", "run_debunker_model": "gpt-4o", "run_judge_model": "heuristic"}
    rows = episode_to_long_rows("run_001", ep, 0, run_meta)
    assert len(rows) == 12
    assert all(r["side"] in ("spreader", "debunker") for r in rows)
    assert all(r["metric_name"] in CANONICAL_METRICS for r in rows)
    assert all(r["arena_type"] == "single_claim" for r in rows)
    assert all(r["is_canonical_metric"] for r in rows)


def test_episode_to_long_rows_missing_scorecard_returns_empty():
    ep = {
        "episode_id": 1,
        "results": {"winner": "debunker", "judge_confidence": 0.8},
    }
    rows = episode_to_long_rows("run_001", ep, 0)
    assert rows == []


def test_episode_to_long_rows_scorecard_none_returns_empty():
    ep = {
        "episode_id": 1,
        "results": {"scorecard": None},
    }
    rows = episode_to_long_rows("run_001", ep, 0)
    assert rows == []


# -------------------------------------------------------------------------
# Tests: build_episode_long_df
# -------------------------------------------------------------------------

def test_build_episode_long_df_attaches_arena_type(tmp_runs_dir):
    df = build_episode_long_df(["test_run_001"], runs_dir=str(tmp_runs_dir))
    assert not df.empty
    assert "arena_type" in df.columns
    assert (df["arena_type"] == "single_claim").all()


def test_build_episode_long_df_empty_for_missing_run():
    with tempfile.TemporaryDirectory() as tmp:
        df = build_episode_long_df(["nonexistent"], runs_dir=tmp)
    assert df.empty


# -------------------------------------------------------------------------
# Tests: build_episode_df (wide) includes run metadata
# -------------------------------------------------------------------------

def test_build_episode_df_includes_arena_type(tmp_runs_dir):
    df, warnings = build_episode_df(["test_run_001"], runs_dir=str(tmp_runs_dir))
    assert not df.empty
    assert "arena_type" in df.columns
    assert (df["arena_type"] == "single_claim").all()


def test_build_episode_df_includes_run_metadata_columns(tmp_runs_dir):
    df, _ = build_episode_df(["test_run_001"], runs_dir=str(tmp_runs_dir))
    for col in ("arena_type", "run_spreader_model", "run_debunker_model", "run_judge_model", "run_created_at"):
        assert col in df.columns
