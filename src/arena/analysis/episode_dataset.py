"""
Episode-level dataset builder for Analytics (JSON v2 only).

Read-only: flattens runs/<run_id>/episodes.jsonl into a single DataFrame
and computes aggregates. No writing, no agent/judge calls.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from arena.io.run_store_v2_read import (
    load_episodes,
    load_run_metadata,
    extract_run_metadata_fields,
)


CANONICAL_METRICS = [
    "factuality",
    "source_credibility",
    "reasoning_quality",
    "responsiveness",
    "persuasion",
    "manipulation_awareness",
]

# Backward compat: old metric names still present in stored episodes
_METRIC_ALIASES = {
    "truthfulness_proxy": "factuality",
    "evidence_quality": "source_credibility",
    "civility": "manipulation_awareness",
}


def _build_run_label(claim: str | None, created_at: str | None, run_id: str) -> str:
    """Build a human-readable label like 'Vaccines cause autism (Apr 2)'."""
    claim_part = (claim or "")[:45]
    if len(claim or "") > 45:
        claim_part += "..."
    if not claim_part:
        claim_part = run_id

    date_part = ""
    if created_at and len(created_at) >= 10:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_part = dt.strftime("%b %-d")
        except Exception:
            date_part = created_at[:10]

    if date_part:
        return f"{claim_part} ({date_part})"
    return claim_part


def _sanitize_metric_key(name: str) -> str:
    """Make metric name safe for use as column suffix (alphanumeric + underscore)."""
    if not name:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(name)).strip("_") or "unknown"


def episode_to_row(
    run_id: str,
    ep: dict,
    ep_index: int,
    run_meta_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Flatten a single JSON v2 episode into one row dict.

    Uses defensive getters; missing values become None or (missing) where noted.
    run_meta_fields: optional dict from extract_run_metadata_fields(run.json).
    """
    config = ep.get("config_snapshot") or {}
    agents = config.get("agents") or {}
    results = ep.get("results") or {}
    concession = ep.get("concession") or {}
    judge_audit = ep.get("judge_audit") or {}
    totals = results.get("totals") or {}

    episode_id = ep.get("episode_id") or ep.get("episode_idx") or ep_index
    completed = results.get("completed_turn_pairs")
    planned = config.get("planned_max_turns")
    winner = results.get("winner")
    judge_confidence = results.get("judge_confidence")
    tot_s = totals.get("spreader")
    tot_d = totals.get("debunker")

    try:
        margin = (float(tot_d) - float(tot_s)) if tot_d is not None and tot_s is not None else None
    except (TypeError, ValueError):
        margin = None
    abs_margin = abs(margin) if margin is not None else None

    judge_status = judge_audit.get("status")
    judge_mode = (
        judge_audit.get("mode")
        or ((agents.get("judge") or {}).get("type") if isinstance(agents.get("judge"), dict) else None)
    )
    error_flag = (judge_status != "success") or (judge_mode != "agent")

    def _get_model(role: str) -> str | None:
        a = agents.get(role) or {}
        return a.get("model") if isinstance(a, dict) else None

    # Prompt variant IDs
    spr_agent = agents.get("spreader") or {}
    deb_agent = agents.get("debunker") or {}
    jud_agent = agents.get("judge") or {}

    # Model provider tag (for cross-provider filtering)
    _ms = (_get_model("spreader") or run_meta_fields.get("run_spreader_model", "") if run_meta_fields else "") or ""
    _md = (_get_model("debunker") or run_meta_fields.get("run_debunker_model", "") if run_meta_fields else "") or ""
    def _detect_provider(m: str) -> str | None:
        if not m:
            return None
        if m.startswith("claude-"):
            return "anthropic"
        if m.startswith("gemini-"):
            return "google"
        if m.startswith("grok-"):
            return "xai"
        if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3"):
            return "openai"
        return "openai"  # default assumption

    provider_spreader = _detect_provider(_ms)
    provider_debunker = _detect_provider(_md)
    cross_provider = (provider_spreader != provider_debunker) if (provider_spreader and provider_debunker) else False

    # Response length from turns
    turns_raw = ep.get("turns") or []
    total_spreader_chars = 0
    total_debunker_chars = 0
    spreader_msg_count = 0
    debunker_msg_count = 0
    for t in turns_raw:
        if not isinstance(t, dict):
            continue
        # Paired format: {spreader_message: {content: ...}, debunker_message: {content: ...}}
        s_msg = t.get("spreader_message")
        d_msg = t.get("debunker_message")
        if s_msg or d_msg:
            s_text = s_msg.get("content", "") if isinstance(s_msg, dict) else str(s_msg) if s_msg else ""
            d_text = d_msg.get("content", "") if isinstance(d_msg, dict) else str(d_msg) if d_msg else ""
            total_spreader_chars += len(s_text)
            total_debunker_chars += len(d_text)
            if s_text:
                spreader_msg_count += 1
            if d_text:
                debunker_msg_count += 1
        # Flat format: {name: "spreader"/"debunker", content: "...", turn_index: N}
        elif t.get("name") and t.get("content"):
            text = str(t["content"])
            if t["name"] == "spreader":
                total_spreader_chars += len(text)
                spreader_msg_count += 1
            elif t["name"] == "debunker":
                total_debunker_chars += len(text)
                debunker_msg_count += 1
    avg_spreader_chars = total_spreader_chars / max(spreader_msg_count, 1)
    avg_debunker_chars = total_debunker_chars / max(debunker_msg_count, 1)

    run_meta = run_meta_fields or {}
    row: dict[str, Any] = {
        "run_id": run_id,
        "episode_index": ep_index,
        "episode_id": episode_id,
        "created_at": ep.get("created_at"),
        "claim": ep.get("claim"),
        "claim_id": ep.get("claim_id"),
        "claim_type": ep.get("claim_type"),
        "claim_complexity": ep.get("claim_complexity"),
        "claim_verifiability": ep.get("claim_verifiability"),
        "claim_structure": ep.get("claim_structure"),
        "claim_label_source": ep.get("claim_label_source"),
        "claim_index": ep.get("claim_index", ep_index),
        "total_claims": ep.get("total_claims", 1),
        "planned_max_turns": planned,
        "completed_turn_pairs": completed,
        "end_trigger": concession.get("trigger"),
        "early_stop": concession.get("early_stop"),
        # Concession details
        "conceded_by": concession.get("conceded_by"),
        "concession_turn": concession.get("concession_turn"),
        "winner": winner,
        "judge_confidence": judge_confidence,
        "totals_spreader": tot_s,
        "totals_debunker": tot_d,
        "margin": margin,
        "abs_margin": abs_margin,
        "judge_status": judge_status,
        "judge_mode": judge_mode,
        "judge_version": judge_audit.get("version"),
        "error_flag": error_flag,
        "model_spreader": _get_model("spreader") or run_meta.get("run_spreader_model"),
        "model_debunker": _get_model("debunker") or run_meta.get("run_debunker_model"),
        "judge_model": (
            _get_model("judge") if "judge" in agents else (judge_audit.get("version") or judge_audit.get("model"))
        ) or run_meta.get("run_judge_model"),
        # Provider tags
        "provider_spreader": provider_spreader,
        "provider_debunker": provider_debunker,
        "cross_provider": cross_provider,
        # Prompt variant tracking
        "prompt_id_spreader": spr_agent.get("prompt_id") if isinstance(spr_agent, dict) else None,
        "prompt_id_debunker": deb_agent.get("prompt_id") if isinstance(deb_agent, dict) else None,
        "prompt_customized_spreader": spr_agent.get("prompt_customized") if isinstance(spr_agent, dict) else None,
        "prompt_customized_debunker": deb_agent.get("prompt_customized") if isinstance(deb_agent, dict) else None,
        # Judge consistency
        "judge_consistency_n": jud_agent.get("consistency_n") if isinstance(jud_agent, dict) else None,
        "judge_consistency_std": jud_agent.get("consistency_std") if isinstance(jud_agent, dict) else None,
        # Response length
        "total_spreader_chars": total_spreader_chars,
        "total_debunker_chars": total_debunker_chars,
        "avg_spreader_chars": round(avg_spreader_chars),
        "avg_debunker_chars": round(avg_debunker_chars),
        # Temperature (for auditability, not analysis)
        "temperature_spreader": spr_agent.get("temperature") if isinstance(spr_agent, dict) else None,
        "temperature_debunker": deb_agent.get("temperature") if isinstance(deb_agent, dict) else None,
        # Human-readable run label (claim preview + date)
        "run_label": _build_run_label(ep.get("claim"), ep.get("created_at"), run_id),
        # Existing
        "summary_version": (ep.get("summaries") or {}).get("version"),
        "arena_type": run_meta.get("arena_type"),
        "run_spreader_model": run_meta.get("run_spreader_model"),
        "run_debunker_model": run_meta.get("run_debunker_model"),
        "run_judge_model": run_meta.get("run_judge_model"),
        "run_created_at": run_meta.get("run_created_at"),
    }

    # Strategy analysis (Phase 2: null-safe extraction)
    sa = ep.get("strategy_analysis") or {}
    row["strategy_analysis_present"] = bool(sa)
    row["strategy_analysis_status"] = sa.get("status")
    row["strategy_analysis_version"] = sa.get("version")
    row["strategy_taxonomy_version"] = sa.get("taxonomy_version")
    row["strategy_analyst_type"] = sa.get("analyst_type")
    row["strategy_model"] = sa.get("model")
    row["strategy_generated_at"] = sa.get("generated_at")
    row["strategy_spreader_primary"] = sa.get("spreader_primary")
    row["strategy_debunker_primary"] = sa.get("debunker_primary")
    spreader_list = sa.get("spreader_strategies")
    debunker_list = sa.get("debunker_strategies")
    if not isinstance(spreader_list, list):
        spreader_list = []
    if not isinstance(debunker_list, list):
        debunker_list = []
    row["strategy_spreader_list"] = spreader_list
    row["strategy_debunker_list"] = debunker_list
    row["strategy_notes"] = sa.get("notes") or ""
    row["strategy_spreader_count"] = len(spreader_list)
    row["strategy_debunker_count"] = len(debunker_list)

    # Top driver from scorecard (below)
    row["top_driver_metric"] = None
    row["top_driver_weighted_delta"] = None

    scorecard = results.get("scorecard") or []
    for item in scorecard:
        if not isinstance(item, dict):
            continue
        metric_name = item.get("metric") or "unknown"
        key = _sanitize_metric_key(metric_name)
        spreader_val = item.get("spreader")
        debunker_val = item.get("debunker")
        weight = item.get("weight")
        try:
            s = float(spreader_val) if spreader_val is not None else None
            d = float(debunker_val) if debunker_val is not None else None
            w = float(weight) if weight is not None else 1.0
        except (TypeError, ValueError):
            s = d = None
            w = 1.0
        delta = (d - s) if s is not None and d is not None else None
        weighted_delta = (delta * w) if delta is not None else None

        row[f"metric_{key}_spreader"] = s
        row[f"metric_{key}_debunker"] = d
        row[f"metric_{key}_delta"] = delta
        row[f"metric_{key}_weighted_delta"] = weighted_delta

        # Track top driver by abs(weighted_delta)
        if weighted_delta is not None and (row["top_driver_weighted_delta"] is None or abs(weighted_delta) > abs(row["top_driver_weighted_delta"] or 0)):
            row["top_driver_metric"] = metric_name
            row["top_driver_weighted_delta"] = weighted_delta

    return row


def build_episode_df(
    selected_run_ids: list[str],
    runs_dir: str | Path = "runs",
    refresh_token: float = 0.0,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Load episodes for selected runs and flatten to one DataFrame (one row per episode).

    No recomputation; read-only from runs/<run_id>/episodes.jsonl.
    Returns (dataframe, combined_warnings).
    """
    all_rows: list[dict[str, Any]] = []
    all_warnings: list[str] = []

    runs_dir_path = Path(runs_dir) if isinstance(runs_dir, str) else runs_dir
    for run_id in selected_run_ids:
        run_meta = load_run_metadata(runs_dir_path, run_id)
        run_meta_fields = extract_run_metadata_fields(run_meta)
        episodes, warnings = load_episodes(run_id, runs_dir, refresh_token)
        for i, ep in enumerate(episodes):
            all_rows.append(episode_to_row(run_id, ep, i, run_meta_fields))
        all_warnings.extend([f"[{run_id}] {w}" for w in warnings])

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    return df, all_warnings


def episode_to_long_rows(
    run_id: str,
    ep: dict,
    ep_index: int,
    run_meta_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Convert one episode into long-format metric rows.
    Returns [] if scorecard missing. Excludes episodes without results.scorecard.
    """
    results = ep.get("results") or {}
    scorecard = results.get("scorecard")

    if not isinstance(scorecard, list):
        return []

    judge_audit = ep.get("judge_audit") or {}
    config_snapshot = ep.get("config_snapshot") or {}
    agents = config_snapshot.get("agents") or {}

    judge_mode = (
        judge_audit.get("mode")
        or (agents.get("judge") or {}).get("type") if isinstance(agents.get("judge"), dict) else None
    )

    winner = results.get("winner")
    confidence = results.get("judge_confidence")
    planned_max_turns = config_snapshot.get("planned_max_turns")
    completed_turn_pairs = results.get("completed_turn_pairs")

    status = judge_audit.get("status")
    error_flag = status not in (None, "success", "ok") if judge_audit else False

    run_meta = run_meta_fields or {}
    rows: list[dict[str, Any]] = []

    for item in scorecard:
        metric_name = item.get("metric")
        if not metric_name:
            continue

        for side in ("spreader", "debunker"):
            value = item.get(side)
            row = {
                "run_id": run_id,
                "episode_id": ep.get("episode_id"),
                "episode_index": ep_index,
                "arena_type": run_meta.get("arena_type") or "single_claim",
                "claim_index": ep.get("claim_index", ep_index),
                "total_claims": ep.get("total_claims", 1),
                "claim": ep.get("claim"),
                "claim_id": ep.get("claim_id"),
                "claim_type": ep.get("claim_type"),
                "claim_complexity": ep.get("claim_complexity"),
                "claim_verifiability": ep.get("claim_verifiability"),
                "claim_structure": ep.get("claim_structure"),
                "claim_label_source": ep.get("claim_label_source"),
                "side": side,
                "metric_name": metric_name,
                "metric_value": value,
                "weight": item.get("weight"),
                "winner": winner,
                "judge_confidence": confidence,
                "judge_mode": judge_mode,
                "planned_max_turns": planned_max_turns,
                "completed_turn_pairs": completed_turn_pairs,
                "error_flag": error_flag,
                "model_spreader": (agents.get("spreader") or {}).get("model")
                or run_meta.get("run_spreader_model"),
                "model_debunker": (agents.get("debunker") or {}).get("model")
                or run_meta.get("run_debunker_model"),
                "model_judge": (agents.get("judge") or {}).get("model")
                or run_meta.get("run_judge_model"),
                "is_canonical_metric": metric_name in CANONICAL_METRICS,
            }
            rows.append(row)

    return rows


def build_episode_long_df(
    selected_run_ids: list[str],
    runs_dir: str | Path = "runs",
    refresh_token: float = 0.0,
) -> pd.DataFrame:
    """
    Build long-format (tidy) analytics table for radar/trajectory charts.
    One row per (episode, metric, side). Excludes episodes missing results.scorecard.
    """
    runs_dir_path = Path(runs_dir) if isinstance(runs_dir, str) else runs_dir
    all_rows: list[dict[str, Any]] = []

    for run_id in selected_run_ids:
        run_meta = load_run_metadata(runs_dir_path, run_id)
        run_meta_fields = extract_run_metadata_fields(run_meta)
        episodes, _ = load_episodes(run_id, runs_dir, refresh_token)
        for idx, ep in enumerate(episodes):
            rows = episode_to_long_rows(run_id, ep, idx, run_meta_fields)
            all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)


def episode_to_strategy_long_rows(
    run_id: str,
    ep: dict,
    ep_index: int,
    run_meta_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Convert one episode with strategy_analysis into long-format rows (episode × side × strategy_label).

    Returns [] if strategy_analysis missing, status != "ok", or strategy lists empty.
    Each row: run_id, episode_id, claim, side, strategy_label, is_primary, winner, etc.
    """
    sa = ep.get("strategy_analysis") or {}
    if not sa or sa.get("status") != "ok":
        return []

    spreader_list = sa.get("spreader_strategies")
    debunker_list = sa.get("debunker_strategies")
    if not isinstance(spreader_list, list):
        spreader_list = []
    if not isinstance(debunker_list, list):
        debunker_list = []

    if not spreader_list and not debunker_list:
        return []

    results = ep.get("results") or {}
    winner = results.get("winner")
    judge_confidence = results.get("judge_confidence")
    tot_s = (results.get("totals") or {}).get("spreader")
    tot_d = (results.get("totals") or {}).get("debunker")
    try:
        margin = (float(tot_d) - float(tot_s)) if tot_d is not None and tot_s is not None else None
    except (TypeError, ValueError):
        margin = None

    spreader_primary = sa.get("spreader_primary")
    debunker_primary = sa.get("debunker_primary")
    run_meta = run_meta_fields or {}
    arena_mode = run_meta.get("arena_type") or "single_claim"

    base = {
        "run_id": run_id,
        "run_label": _build_run_label(ep.get("claim"), ep.get("created_at"), run_id),
        "episode_id": ep.get("episode_id") or ep_index,
        "episode_index": ep_index,
        "claim": ep.get("claim"),
        "claim_id": ep.get("claim_id"),
        "claim_type": ep.get("claim_type"),
        "claim_complexity": ep.get("claim_complexity"),
        "claim_index": ep.get("claim_index", ep_index),
        "total_claims": ep.get("total_claims", 1),
        "strategy_analysis_status": sa.get("status"),
        "winner": winner,
        "winning_side": winner,
        "judge_confidence": judge_confidence,
        "margin": margin,
        "arena_mode": arena_mode,
    }

    rows: list[dict[str, Any]] = []
    for label in spreader_list:
        if not label or not isinstance(label, str):
            continue
        label_str = str(label).strip()
        rows.append({
            **base,
            "side": "spreader",
            "strategy_label": label_str,
            "is_primary": label_str == spreader_primary,
        })
    for label in debunker_list:
        if not label or not isinstance(label, str):
            continue
        label_str = str(label).strip()
        rows.append({
            **base,
            "side": "debunker",
            "strategy_label": label_str,
            "is_primary": label_str == debunker_primary,
        })
    return rows


def build_strategy_long_df(
    selected_run_ids: list[str],
    runs_dir: str | Path = "runs",
    refresh_token: float = 0.0,
) -> pd.DataFrame:
    """
    Build strategy-long dataset (episode × side × strategy_label) for leaderboard aggregation.

    One row per (episode, side, strategy_label). Skips episodes without strategy_analysis
    or with status != "ok" or empty strategy lists.
    """
    runs_dir_path = Path(runs_dir) if isinstance(runs_dir, str) else runs_dir
    all_rows: list[dict[str, Any]] = []

    for run_id in selected_run_ids:
        run_meta = load_run_metadata(runs_dir_path, run_id)
        run_meta_fields = extract_run_metadata_fields(run_meta)
        episodes, _ = load_episodes(run_id, runs_dir, refresh_token)
        for idx, ep in enumerate(episodes):
            rows = episode_to_strategy_long_rows(run_id, ep, idx, run_meta_fields)
            all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)


def compute_aggregates(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute aggregate tables and values for the Analytics UI.

    Returns dict with: n_episodes, n_runs, debunker_win_rate, avg_confidence,
    fallback_rate, win_distribution, confidence_bins, metric_means_by_role,
    metric_delta_means, by_turn_plan, by_run.
    """
    out: dict[str, Any] = {}
    if df.empty:
        out["n_episodes"] = 0
        out["n_runs"] = 0
        out["debunker_win_rate"] = None
        out["avg_confidence"] = None
        out["fallback_rate"] = None
        out["win_distribution"] = pd.DataFrame()
        out["confidence_bins"] = pd.DataFrame()
        out["metric_means_by_role"] = pd.DataFrame()
        out["metric_delta_means"] = pd.DataFrame()
        out["by_turn_plan"] = pd.DataFrame()
        out["by_run"] = pd.DataFrame()
        return out

    n = len(df)
    out["n_episodes"] = n
    out["n_runs"] = df["run_id"].nunique()

    winners = df["winner"].dropna().str.strip().str.lower()
    debunker_wins = (winners == "debunker").sum()
    out["debunker_win_rate"] = (debunker_wins / len(winners)) if len(winners) else None

    conf = pd.to_numeric(df["judge_confidence"], errors="coerce")
    out["avg_confidence"] = conf.mean(skipna=True) if conf.notna().any() else None

    err = df.get("error_flag")
    if err is not None:
        out["fallback_rate"] = err.mean() if err.dtype == bool else pd.to_numeric(err, errors="coerce").mean()
    else:
        out["fallback_rate"] = None

    # Win distribution table
    win_counts = df["winner"].fillna("(missing)").str.strip().str.lower().value_counts()
    win_dist = pd.DataFrame({
        "winner": win_counts.index,
        "count": win_counts.values,
        "percent": (win_counts.values / n * 100).round(1),
    })
    out["win_distribution"] = win_dist

    # Confidence bins [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    conf_series = pd.to_numeric(df["judge_confidence"], errors="coerce").dropna()
    if len(conf_series):
        bin_labels = [f"{bins[i]}-{bins[i+1]}" for i in range(len(bins) - 1)]
        conf_binned = pd.cut(conf_series, bins=bins, labels=bin_labels, include_lowest=True)
        conf_bins_df = conf_binned.value_counts().sort_index().reset_index()
        conf_bins_df.columns = ["bin", "count"]
        conf_bins_df["percent"] = (conf_bins_df["count"] / conf_bins_df["count"].sum() * 100).round(1)
        out["confidence_bins"] = conf_bins_df
    else:
        out["confidence_bins"] = pd.DataFrame(columns=["bin", "count", "percent"])

    # Metric means by role (metric_*_spreader, metric_*_debunker)
    metric_spreader_cols = [c for c in df.columns if c.startswith("metric_") and c.endswith("_spreader")]
    metric_debunker_cols = [c for c in df.columns if c.startswith("metric_") and c.endswith("_debunker")]
    if metric_spreader_cols or metric_debunker_cols:
        names = sorted({c.replace("metric_", "").replace("_spreader", "").replace("_debunker", "") for c in metric_spreader_cols + metric_debunker_cols})
        means_s = [df[f"metric_{n}_spreader"].mean() if f"metric_{n}_spreader" in df.columns else None for n in names]
        means_d = [df[f"metric_{n}_debunker"].mean() if f"metric_{n}_debunker" in df.columns else None for n in names]
        out["metric_means_by_role"] = pd.DataFrame({
            "metric": names,
            "mean_spreader": means_s,
            "mean_debunker": means_d,
        })
    else:
        out["metric_means_by_role"] = pd.DataFrame(columns=["metric", "mean_spreader", "mean_debunker"])

    # Metric delta means (mean delta, mean abs delta, mean weighted delta)
    delta_cols = [c for c in df.columns if c.startswith("metric_") and c.endswith("_delta")]
    wdelta_cols = [c for c in df.columns if c.startswith("metric_") and c.endswith("_weighted_delta")]
    if delta_cols or wdelta_cols:
        names = sorted({c.replace("metric_", "").replace("_delta", "").replace("_weighted_delta", "") for c in delta_cols + wdelta_cols})
        mean_delta = []
        mean_abs_delta = []
        mean_weighted_delta = []
        for n in names:
            dcol = f"metric_{n}_delta"
            wcol = f"metric_{n}_weighted_delta"
            d = df[dcol].mean() if dcol in df.columns else None
            ad = df[dcol].abs().mean() if dcol in df.columns else None
            wd = df[wcol].mean() if wcol in df.columns else None
            mean_delta.append(d)
            mean_abs_delta.append(ad)
            mean_weighted_delta.append(wd)
        out["metric_delta_means"] = pd.DataFrame({
            "metric": names,
            "mean_delta": mean_delta,
            "mean_abs_delta": mean_abs_delta,
            "mean_weighted_delta": mean_weighted_delta,
        })
    else:
        out["metric_delta_means"] = pd.DataFrame(columns=["metric", "mean_delta", "mean_abs_delta", "mean_weighted_delta"])

    # By planned_max_turns
    if "planned_max_turns" in df.columns:
        g = df.groupby("planned_max_turns", dropna=False)
        by_plan = g.size().reset_index(name="count")
        win_by_plan = df.assign(_w=df["winner"].fillna("").str.strip().str.lower() == "debunker").groupby(df["planned_max_turns"])["_w"].mean() * 100
        by_plan["win_rate_debunker"] = by_plan["planned_max_turns"].map(win_by_plan)
        by_plan["avg_confidence"] = by_plan["planned_max_turns"].map(g["judge_confidence"].apply(lambda s: pd.to_numeric(s, errors="coerce").mean()))
        if "abs_margin" in df.columns:
            by_plan["avg_abs_margin"] = by_plan["planned_max_turns"].map(g["abs_margin"].mean())
        out["by_turn_plan"] = by_plan
    else:
        out["by_turn_plan"] = pd.DataFrame()

    # By run_id
    g_run = df.groupby("run_id", dropna=False)
    by_run = g_run.size().reset_index(name="count")
    win_by_run = df.assign(_w=df["winner"].fillna("").str.strip().str.lower() == "debunker").groupby(df["run_id"])["_w"].mean() * 100
    by_run["win_rate_debunker"] = by_run["run_id"].map(win_by_run)
    if "error_flag" in df.columns:
        by_run["fallback_rate"] = by_run["run_id"].map(g_run["error_flag"].mean())
    else:
        by_run["fallback_rate"] = None
    by_run["avg_confidence"] = by_run["run_id"].map(g_run["judge_confidence"].apply(lambda s: pd.to_numeric(s, errors="coerce").mean()))
    out["by_run"] = by_run

    return out
