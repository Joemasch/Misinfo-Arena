"""
Batch Experiment Engine for Misinformation Arena v2.

Runs an N × M × C grid (spreader variants × debunker variants × claims)
synchronously, yielding progress updates as it goes.

Each cell in the grid is one mini-debate:  spreader and debunker alternate for
`turns_per_episode` turn-pairs, then the AgentJudge scores the transcript.
Results are collected in memory and can be saved to disk as a JSONL experiment log.

Usage (from Streamlit page)::

    config = BatchConfig(
        spreader_prompts=[{"name": "IME507", "text": "..."}],
        debunker_prompts=[{"name": "IME507", "text": "..."}],
        claims=["Vaccines cause autism", "Climate change is fake"],
        turns_per_episode=5,
        model_spreader="gpt-4o-mini",
        model_debunker="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        temperature_spreader=0.7,
        temperature_debunker=0.7,
    )
    for progress, result in run_batch_experiment(config):
        # progress: (current, total) int tuple
        # result: BatchResult or None (in-progress update)
        ...
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PromptVariant:
    name: str
    text: str


@dataclass
class BatchConfig:
    spreader_prompts: List[PromptVariant]
    debunker_prompts: List[PromptVariant]
    claims: List[str]
    turns_per_episode: int = 5
    model_spreader: str = "gpt-4o-mini"
    model_debunker: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o-mini"
    temperature_spreader: float = 0.7
    temperature_debunker: float = 0.7
    judge_temperature: float = 0.10
    judge_consistency_runs: int = 1


@dataclass
class EpisodeOutcome:
    spreader_prompt_name: str
    debunker_prompt_name: str
    claim: str
    winner: str
    judge_confidence: float
    spreader_total: float
    debunker_total: float
    scorecard: List[dict]
    reason: str
    completed_turns: int
    error: Optional[str] = None


@dataclass
class BatchResult:
    experiment_id: str
    config: dict
    outcomes: List[EpisodeOutcome] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def _build_debate_messages(
    spreader_prompt: str,
    debunker_prompt: str,
    claim: str,
    model_spreader: str,
    model_debunker: str,
    temperature_spreader: float,
    temperature_debunker: float,
    turns_per_episode: int,
) -> Tuple[list, int]:
    """Run a mini-debate and return (turn list for judge, completed turns)."""
    from arena.agents import (
        OpenAIAgent, AnthropicAgent, GeminiAgent, GrokAgent,
        is_anthropic_model, is_gemini_model, is_grok_model,
    )
    from arena.types import AgentRole

    def _sub(prompt: str) -> str:
        return prompt.replace("{claim}", claim)

    def _make_agent(role: AgentRole, model: str, temperature: float):
        if is_anthropic_model(model):
            return AnthropicAgent(role=role, model=model, temperature=temperature)
        if is_gemini_model(model):
            return GeminiAgent(role=role, model=model, temperature=temperature)
        if is_grok_model(model):
            return GrokAgent(role=role, model=model, temperature=temperature)
        return OpenAIAgent(role=role, model=model, temperature=temperature)

    spreader = _make_agent(AgentRole.SPREADER, model_spreader, temperature_spreader)
    debunker = _make_agent(AgentRole.DEBUNKER, model_debunker, temperature_debunker)

    history: list[dict] = []
    turns_for_judge: list[dict] = []

    for turn_i in range(turns_per_episode):
        # ── Spreader turn ──
        s_context = {
            "topic": claim,
            "system_prompt": _sub(spreader_prompt),
            "conversation_history": history,
        }
        s_text = spreader.generate(s_context)
        history.append({"role": "spreader", "content": s_text})

        # ── Debunker turn ──
        d_context = {
            "topic": claim,
            "system_prompt": _sub(debunker_prompt),
            "conversation_history": history,
        }
        d_text = debunker.generate(d_context)
        history.append({"role": "debunker", "content": d_text})

        turns_for_judge.append({
            "spreader_message": {"content": s_text},
            "debunker_message": {"content": d_text},
        })

    return turns_for_judge, turns_per_episode


def _judge_turns(
    turns_for_judge: list,
    judge_model: str,
    judge_temperature: float,
    judge_consistency_runs: int,
    judge_prompt_template: Optional[str] = None,
    allow_heuristic_fallback: bool = True,
):
    """Call AgentJudge. Falls back to HeuristicJudge only if allowed.

    For experiment runs, set allow_heuristic_fallback=False so judge failures
    produce explicit errors rather than silent lower-quality scores.
    """
    from arena.judge import AgentJudge, HeuristicJudge, JudgeDecision

    class _FakeCfg:
        max_turns = 10
        topic = ""

    cfg = _FakeCfg()
    try:
        aj = AgentJudge(
            model=judge_model,
            temperature=judge_temperature,
            static_prompt_template=judge_prompt_template,
            consistency_runs=judge_consistency_runs,
        )
        return aj.evaluate_match(turns_for_judge, cfg)
    except Exception as e:
        if not allow_heuristic_fallback:
            raise  # Let experiment engine handle the error explicitly
        hj = HeuristicJudge()
        return hj.evaluate_match(turns_for_judge, cfg)


def run_batch_experiment(
    config: BatchConfig,
    judge_prompt_template: Optional[str] = None,
    save_dir: Optional[Path] = None,
) -> Generator[Tuple[Tuple[int, int], Optional[EpisodeOutcome]], None, BatchResult]:
    """
    Run every combination of spreader_prompt × debunker_prompt × claim.

    Yields (progress_tuple, outcome) for each completed cell.
    Returns a BatchResult with all outcomes when exhausted.

    progress_tuple = (completed: int, total: int)
    """
    combos = [
        (sp, dp, cl)
        for sp in config.spreader_prompts
        for dp in config.debunker_prompts
        for cl in config.claims
    ]
    total = len(combos)
    experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    result = BatchResult(experiment_id=experiment_id, config=asdict(config))

    for idx, (sp, dp, claim) in enumerate(combos):
        error_msg: Optional[str] = None
        outcome: Optional[EpisodeOutcome] = None

        try:
            turns, n_turns = _build_debate_messages(
                spreader_prompt=sp.text,
                debunker_prompt=dp.text,
                claim=claim,
                model_spreader=config.model_spreader,
                model_debunker=config.model_debunker,
                temperature_spreader=config.temperature_spreader,
                temperature_debunker=config.temperature_debunker,
                turns_per_episode=config.turns_per_episode,
            )
            decision = _judge_turns(
                turns_for_judge=turns,
                judge_model=config.judge_model,
                judge_temperature=config.judge_temperature,
                judge_consistency_runs=config.judge_consistency_runs,
                judge_prompt_template=judge_prompt_template,
            )

            def _get(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            scorecard_raw = _get(decision, "scorecard", [])
            scorecard_list = []
            for ms in scorecard_raw:
                if isinstance(ms, dict):
                    scorecard_list.append(ms)
                else:
                    scorecard_list.append({
                        "metric": getattr(ms, "metric", ""),
                        "spreader": getattr(ms, "spreader", 0.0),
                        "debunker": getattr(ms, "debunker", 0.0),
                        "weight": getattr(ms, "weight", 0.0),
                    })

            totals = _get(decision, "totals", {}) or {}
            outcome = EpisodeOutcome(
                spreader_prompt_name=sp.name,
                debunker_prompt_name=dp.name,
                claim=claim,
                winner=_get(decision, "winner", "draw"),
                judge_confidence=float(_get(decision, "confidence", 0.5)),
                spreader_total=float(totals.get("spreader", 0.0)),
                debunker_total=float(totals.get("debunker", 0.0)),
                scorecard=scorecard_list,
                reason=_get(decision, "reason", ""),
                completed_turns=n_turns,
            )
        except Exception as e:
            error_msg = str(e)[:300]
            outcome = EpisodeOutcome(
                spreader_prompt_name=sp.name,
                debunker_prompt_name=dp.name,
                claim=claim,
                winner="error",
                judge_confidence=0.0,
                spreader_total=0.0,
                debunker_total=0.0,
                scorecard=[],
                reason="",
                completed_turns=0,
                error=error_msg,
            )

        result.outcomes.append(outcome)
        yield (idx + 1, total), outcome

    # Optionally save to disk
    if save_dir is not None:
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
            out_path = save_dir / f"{experiment_id}.jsonl"
            with out_path.open("w", encoding="utf-8") as fh:
                for ep in result.outcomes:
                    fh.write(json.dumps(asdict(ep)) + "\n")
            result_path = save_dir / f"{experiment_id}_summary.json"
            result_path.write_text(
                json.dumps({
                    "experiment_id": experiment_id,
                    "created_at": result.created_at,
                    "total_episodes": len(result.outcomes),
                    "config": result.config,
                }, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Spec-CSV Experiment Engine (per-episode model configs)
# ---------------------------------------------------------------------------

@dataclass
class SpecRow:
    """One row from a spec CSV — defines a single episode."""
    claim: str
    study_id: str = ""
    condition: str = ""
    run_group: str = ""
    claim_type: str = ""
    spreader_model: str = "gpt-4o-mini"
    debunker_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o-mini"
    max_turns: int = 5
    consistency_runs: int = 1


def parse_spec_csv(path_or_buffer) -> list[SpecRow]:
    """
    Parse a spec CSV into SpecRow objects.

    Required column: claim
    Optional columns: study_id, condition, run_group, claim_type,
        spreader_model, debunker_model, judge_model, max_turns, consistency_runs

    Missing optional columns get defaults from SpecRow.
    """
    import pandas as pd
    import io

    if isinstance(path_or_buffer, (str, Path)):
        df = pd.read_csv(path_or_buffer)
    elif hasattr(path_or_buffer, "read"):
        df = pd.read_csv(path_or_buffer)
    else:
        df = pd.read_csv(io.BytesIO(path_or_buffer))

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "claim" not in df.columns:
        raise ValueError(f"Spec CSV must have a 'claim' column. Found: {list(df.columns)}")

    rows: list[SpecRow] = []
    defaults = SpecRow(claim="")
    for _, raw in df.iterrows():
        claim = str(raw.get("claim", "")).strip()
        if not claim or claim.lower() == "nan":
            continue
        rows.append(SpecRow(
            claim=claim,
            study_id=str(raw.get("study_id", defaults.study_id) or "").strip(),
            condition=str(raw.get("condition", defaults.condition) or "").strip(),
            run_group=str(raw.get("run_group", defaults.run_group) or "").strip(),
            claim_type=str(raw.get("claim_type", defaults.claim_type) or "").strip(),
            spreader_model=str(raw.get("spreader_model", defaults.spreader_model) or defaults.spreader_model).strip(),
            debunker_model=str(raw.get("debunker_model", defaults.debunker_model) or defaults.debunker_model).strip(),
            judge_model=str(raw.get("judge_model", defaults.judge_model) or defaults.judge_model).strip(),
            max_turns=int(raw.get("max_turns", defaults.max_turns) or defaults.max_turns),
            consistency_runs=int(raw.get("consistency_runs", defaults.consistency_runs) or defaults.consistency_runs),
        ))

    return rows


def run_experiment_from_spec(
    spec_rows: list[SpecRow],
    spreader_prompt: str,
    debunker_prompt: str,
    judge_prompt_template: Optional[str] = None,
    temperature_spreader: float = 0.85,
    temperature_debunker: float = 0.40,
    judge_temperature: float = 0.10,
) -> Generator[Tuple[Tuple[int, int], Optional[dict]], None, None]:
    """
    Run experiments from a spec CSV. Each row = one episode with per-row model configs.

    Groups rows by run_group to create separate runs in runs/<run_id>/.
    Episodes are saved in v2 format with study_id and condition.

    Yields (progress_tuple, episode_summary_dict) for each completed episode.
    """
    from arena.io.run_store import make_run_id, write_run_json, append_episode_jsonl
    from collections import OrderedDict

    if not spec_rows:
        return

    total = len(spec_rows)

    # Group rows by run_group (preserve order)
    groups: OrderedDict[str, list[tuple[int, SpecRow]]] = OrderedDict()
    for i, row in enumerate(spec_rows):
        key = row.run_group or f"auto_{i}"
        if key not in groups:
            groups[key] = []
        groups[key].append((i, row))

    # Map run_group -> run_id
    run_ids: dict[str, str] = {}
    for group_key in groups:
        run_ids[group_key] = make_run_id()

    completed = 0
    for group_key, indexed_rows in groups.items():
        run_id = run_ids[group_key]

        # Write run.json metadata
        first_row = indexed_rows[0][1]
        run_obj = {
            "schema_version": "2.0",
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "arena_type": "experiment",
            "study_id": first_row.study_id,
            "condition": first_row.condition,
            "input": {
                "claims": [r.claim for _, r in indexed_rows],
                "run_group": group_key,
            },
            "run_config": {
                "episode_count": len(indexed_rows),
                "agents": {
                    "spreader": {"model": "per-episode"},
                    "debunker": {"model": "per-episode"},
                    "judge": {"model": "per-episode"},
                },
            },
            "storage": {"episodes_file": "episodes.jsonl"},
        }
        write_run_json(run_id, run_obj)

        for ep_idx, (global_idx, row) in enumerate(indexed_rows):
            error_msg: Optional[str] = None
            episode_obj: Optional[dict] = None

            try:
                turns, n_turns = _build_debate_messages(
                    spreader_prompt=spreader_prompt,
                    debunker_prompt=debunker_prompt,
                    claim=row.claim,
                    model_spreader=row.spreader_model,
                    model_debunker=row.debunker_model,
                    temperature_spreader=temperature_spreader,
                    temperature_debunker=temperature_debunker,
                    turns_per_episode=row.max_turns,
                )

                decision = _judge_turns(
                    turns_for_judge=turns,
                    judge_model=row.judge_model,
                    judge_temperature=judge_temperature,
                    judge_consistency_runs=row.consistency_runs,
                    judge_prompt_template=judge_prompt_template,
                    allow_heuristic_fallback=False,  # Experiments: explicit errors only
                )

                def _get(obj, key, default=None):
                    if isinstance(obj, dict):
                        return obj.get(key, default)
                    return getattr(obj, key, default)

                scorecard_raw = _get(decision, "scorecard", [])
                scorecard_list = []
                for ms in scorecard_raw:
                    if isinstance(ms, dict):
                        scorecard_list.append(ms)
                    else:
                        scorecard_list.append({
                            "metric": getattr(ms, "metric", ""),
                            "spreader": getattr(ms, "spreader", 0.0),
                            "debunker": getattr(ms, "debunker", 0.0),
                            "weight": getattr(ms, "weight", 0.0),
                        })

                totals = _get(decision, "totals", {}) or {}

                episode_obj = {
                    "schema_version": "2.0",
                    "run_id": run_id,
                    "episode_id": ep_idx,
                    "study_id": row.study_id,
                    "condition": row.condition,
                    "created_at": datetime.now().isoformat(),
                    "claim": row.claim,
                    "claim_index": ep_idx,
                    "total_claims": len(indexed_rows),
                    "config_snapshot": {
                        "planned_max_turns": row.max_turns,
                        "agents": {
                            "spreader": {
                                "model": row.spreader_model,
                                "temperature": temperature_spreader,
                            },
                            "debunker": {
                                "model": row.debunker_model,
                                "temperature": temperature_debunker,
                            },
                            "judge": {
                                "type": "agent",
                                "model": row.judge_model,
                                "temperature": judge_temperature,
                                "consistency_n": row.consistency_runs,
                            },
                        },
                    },
                    "results": {
                        "completed_turn_pairs": n_turns,
                        "winner": _get(decision, "winner", "draw"),
                        "judge_confidence": float(_get(decision, "confidence", 0.5)),
                        "reason": _get(decision, "reason", ""),
                        "totals": totals if isinstance(totals, dict) else {"spreader": 0, "debunker": 0},
                        "scorecard": scorecard_list,
                    },
                    "concession": {
                        "early_stop": False,
                        "trigger": "max_turns",
                        "conceded_by": None,
                        "concession_turn": None,
                    },
                    "turns": turns,
                    "judge_audit": {
                        "status": "success",
                        "mode": "agent",
                        "version": f"agent_v1:{row.judge_model}",
                    },
                }

                # Add claim metadata if provided
                if row.claim_type:
                    episode_obj["claim_type"] = row.claim_type

            except Exception as e:
                error_msg = str(e)[:300]
                episode_obj = {
                    "schema_version": "2.0",
                    "run_id": run_id,
                    "episode_id": ep_idx,
                    "study_id": row.study_id,
                    "condition": row.condition,
                    "created_at": datetime.now().isoformat(),
                    "claim": row.claim,
                    "claim_index": ep_idx,
                    "total_claims": len(indexed_rows),
                    "config_snapshot": {
                        "planned_max_turns": row.max_turns,
                        "agents": {
                            "spreader": {"model": row.spreader_model},
                            "debunker": {"model": row.debunker_model},
                            "judge": {"model": row.judge_model},
                        },
                    },
                    "results": {
                        "completed_turn_pairs": 0,
                        "winner": "error",
                        "judge_confidence": 0.0,
                        "reason": error_msg,
                        "totals": {"spreader": 0, "debunker": 0},
                        "scorecard": [],
                    },
                    "concession": {"early_stop": False, "trigger": "error"},
                    "turns": [],
                    "judge_audit": {
                        "status": "error",
                        "error_message": error_msg,
                        "mode": "error",
                    },
                }
                if row.claim_type:
                    episode_obj["claim_type"] = row.claim_type

            # Persist to v2 format
            append_episode_jsonl(run_id, episode_obj)

            completed += 1
            summary = {
                "run_id": run_id,
                "run_group": group_key,
                "episode_id": ep_idx,
                "claim": row.claim,
                "winner": episode_obj["results"]["winner"],
                "confidence": episode_obj["results"]["judge_confidence"],
                "error": error_msg,
                "spreader_model": row.spreader_model,
                "debunker_model": row.debunker_model,
                "judge_model": row.judge_model,
                "max_turns": row.max_turns,
            }
            yield (completed, total), summary
