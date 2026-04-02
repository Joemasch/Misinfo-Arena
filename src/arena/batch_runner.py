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
):
    """Call AgentJudge; fall back to HeuristicJudge on failure."""
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
    except Exception:
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
