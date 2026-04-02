"""
Research-centric analytics helpers for Phase 4B.

Pure functions operating on long-format episode DataFrames.
No Streamlit imports.
"""

from __future__ import annotations

import itertools
from typing import Any

import pandas as pd

from arena.analysis.episode_dataset import CANONICAL_METRICS


def apply_research_filters(
    long_df: pd.DataFrame,
    arena_types: list[str] | None = None,
    judge_modes: list[str] | None = None,
    spreader_models: list[str] | None = None,
    debunker_models: list[str] | None = None,
    judge_models: list[str] | None = None,
    exclude_error_episodes: bool = True,
) -> pd.DataFrame:
    """
    Returns filtered long_df.
    - Filters are optional. If a list is None or empty, do not filter on it.
    - If exclude_error_episodes is True, drop rows where error_flag is True.
    - long_df already excludes missing-scorecard episodes; keep that invariant.
    """
    if long_df.empty:
        return long_df

    out = long_df.copy()

    if exclude_error_episodes:
        err = out.get("error_flag")
        if err is not None:
            mask = pd.to_numeric(err, errors="coerce").fillna(False).astype(bool)
            out = out.loc[~mask]

    if arena_types:
        out = out[out["arena_type"].astype(str).isin(arena_types)]

    if judge_modes:
        out = out[out["judge_mode"].astype(str).isin(judge_modes)]

    if spreader_models:
        out = out[out["model_spreader"].astype(str).isin(spreader_models)]

    if debunker_models:
        out = out[out["model_debunker"].astype(str).isin(debunker_models)]

    if judge_models:
        out = out[out["model_judge"].astype(str).isin(judge_models)]

    return out


def compute_transparency_summary(long_df: pd.DataFrame) -> dict:
    """
    Returns dict with:
      - n_runs
      - n_episodes
      - n_rows
      - arena_type_counts (dict)
      - judge_mode_counts (dict)
      - spreader_model_counts (dict)
      - debunker_model_counts (dict)
      - judge_model_counts (dict)
      - error_row_rate (float 0..1)
    Episode count must be unique (run_id, episode_id).
    """
    if long_df.empty:
        return {
            "n_runs": 0,
            "n_episodes": 0,
            "n_rows": 0,
            "arena_type_counts": {},
            "judge_mode_counts": {},
            "spreader_model_counts": {},
            "debunker_model_counts": {},
            "judge_model_counts": {},
            "error_row_rate": 0.0,
        }

    n_runs = long_df["run_id"].nunique()
    ep_key = ["run_id", "episode_index"] if "episode_index" in long_df.columns else ["run_id", "episode_id"]
    ep_key = [c for c in ep_key if c in long_df.columns]
    n_episodes = long_df.drop_duplicates(subset=ep_key).shape[0] if ep_key else 0
    n_rows = len(long_df)

    def _counts(col: str) -> dict:
        c = long_df[col].dropna().astype(str)
        return c.value_counts().to_dict()

    arena_type_counts = _counts("arena_type")
    judge_mode_counts = _counts("judge_mode")
    spreader_model_counts = _counts("model_spreader")
    debunker_model_counts = _counts("model_debunker")
    judge_model_counts = _counts("model_judge")

    err = long_df.get("error_flag")
    if err is not None:
        error_row_rate = float(pd.to_numeric(err, errors="coerce").fillna(False).astype(bool).mean())
    else:
        error_row_rate = 0.0

    return {
        "n_runs": int(n_runs),
        "n_episodes": int(n_episodes),
        "n_rows": int(n_rows),
        "arena_type_counts": arena_type_counts,
        "judge_mode_counts": judge_mode_counts,
        "spreader_model_counts": spreader_model_counts,
        "debunker_model_counts": debunker_model_counts,
        "judge_model_counts": judge_model_counts,
        "error_row_rate": error_row_rate,
    }


def compute_strength_fingerprint(
    long_df: pd.DataFrame,
    agg: str = "mean",
    view: str = "raw",
) -> pd.DataFrame:
    """
    Returns df indexed by metric_name with columns:
      - spreader_value
      - debunker_value
      - delta_value (debunker - spreader)
    Aggregation is over unique episodes (run_id, episode_id) for each (metric_name, side).
    Normalized view: min-max normalize per metric across the two sides (0..1) for display.
    Delta view: return delta_value and still return all columns.
    """
    if long_df.empty or "metric_name" not in long_df.columns or "side" not in long_df.columns:
        return pd.DataFrame(columns=["spreader_value", "debunker_value", "delta_value"])

    # Coerce metric_value to numeric
    df = long_df.copy()
    df["metric_value_num"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value_num"])

    if df.empty:
        return pd.DataFrame(columns=["spreader_value", "debunker_value", "delta_value"])

    # Use (run_id, episode_index) as episode key (episode_index always present in long format)
    ep_idx = df["episode_index"] if "episode_index" in df.columns else df.get("episode_id", 0)
    df["_ep_key"] = df["run_id"].astype(str) + "_" + ep_idx.astype(str)

    # Aggregate per (episode_key, metric_name, side) first (one value per episode per metric per side)
    ep_keys = ["_ep_key", "metric_name", "side"]
    ep_df = df.groupby(ep_keys, dropna=False)["metric_value_num"]

    if agg == "mean":
        ep_agg = ep_df.mean()
    elif agg == "sum":
        ep_agg = ep_df.sum()
    elif agg == "median":
        ep_agg = ep_df.median()
    else:
        ep_agg = ep_df.mean()

    ep_agg = ep_agg.reset_index()

    # Pivot: one row per metric_name
    pivot = ep_agg.pivot_table(
        index="metric_name",
        columns="side",
        values="metric_value_num",
        aggfunc=agg,
    )

    spreader_col = "spreader" if "spreader" in pivot.columns else None
    debunker_col = "debunker" if "debunker" in pivot.columns else None

    result = pd.DataFrame(index=pivot.index)
    result["spreader_value"] = pivot[spreader_col] if spreader_col else float("nan")
    result["debunker_value"] = pivot[debunker_col] if debunker_col else float("nan")
    result["delta_value"] = result["debunker_value"] - result["spreader_value"]

    # Canonical metric order
    order = [m for m in CANONICAL_METRICS if m in result.index]
    rest = [m for m in result.index if m not in order]
    result = result.reindex(order + sorted(rest))

    if view == "normalized":
        # Min-max per metric across both sides (0..1)
        for idx in result.index:
            s = result.loc[idx, "spreader_value"]
            d = result.loc[idx, "debunker_value"]
            vals = [v for v in (s, d) if pd.notna(v)]
            if len(vals) >= 2:
                lo, hi = min(vals), max(vals)
                if hi > lo:
                    result.loc[idx, "spreader_value"] = (s - lo) / (hi - lo) if pd.notna(s) else float("nan")
                    result.loc[idx, "debunker_value"] = (d - lo) / (hi - lo) if pd.notna(d) else float("nan")
                else:
                    result.loc[idx, "spreader_value"] = 0.5 if pd.notna(s) else float("nan")
                    result.loc[idx, "debunker_value"] = 0.5 if pd.notna(d) else float("nan")

    return result.reset_index()


def apply_strategy_filters(
    strategy_long_df: pd.DataFrame,
    arena_modes: list[str] | None = None,
    claim_types: list[str] | None = None,
    claim_domains: list[str] | None = None,
) -> pd.DataFrame:
    """
    Filter strategy-long DataFrame by arena_mode, claim_type, claim_domain.

    Empty/None filter means no filter (include all).
    """
    if strategy_long_df.empty:
        return strategy_long_df
    out = strategy_long_df.copy()
    if arena_modes and "arena_mode" in out.columns:
        out = out[out["arena_mode"].astype(str).isin(arena_modes)]
    if claim_types and "claim_type" in out.columns:
        out = out[out["claim_type"].astype(str).isin(claim_types)]
    if claim_domains and "claim_domain" in out.columns:
        out = out[out["claim_domain"].astype(str).isin(claim_domains)]
    return out


def compute_strategy_leaderboard(strategy_long_df: pd.DataFrame) -> dict:
    """
    Compute leaderboard aggregates from strategy-long DataFrame.

    Returns dict with:
      - spreader_strategy_freq: DataFrame (strategy_label, count, percent)
      - debunker_strategy_freq: DataFrame (strategy_label, count, percent)
      - spreader_win_rate: DataFrame (strategy_label, wins, total, win_rate)
      - debunker_win_rate: DataFrame (strategy_label, wins, total, win_rate)
      - primary_spreader_freq: DataFrame (strategy_label, count)
      - primary_debunker_freq: DataFrame (strategy_label, count)
      - strategy_by_claim_type: DataFrame (strategy_label, side, claim_type, count)
      - strategy_by_claim_domain: DataFrame (strategy_label, side, claim_domain, count)
    """
    out: dict = {
        "spreader_strategy_freq": pd.DataFrame(),
        "debunker_strategy_freq": pd.DataFrame(),
        "spreader_win_rate": pd.DataFrame(),
        "debunker_win_rate": pd.DataFrame(),
        "primary_spreader_freq": pd.DataFrame(),
        "primary_debunker_freq": pd.DataFrame(),
        "strategy_by_claim_type": pd.DataFrame(),
        "strategy_by_claim_domain": pd.DataFrame(),
    }
    if strategy_long_df.empty:
        return out

    df = strategy_long_df.copy()

    # Spreader strategy frequency
    spr = df[df["side"] == "spreader"]
    if not spr.empty:
        cnt = spr["strategy_label"].value_counts().reset_index()
        cnt.columns = ["strategy_label", "count"]
        cnt["percent"] = (cnt["count"] / cnt["count"].sum() * 100).round(1)
        out["spreader_strategy_freq"] = cnt

        # Win rate: spreader wins when winner == "spreader"
        spr_wins = spr.assign(won=(spr["winner"].fillna("").str.strip().str.lower() == "spreader"))
        wr = spr_wins.groupby("strategy_label").agg(wins=("won", "sum"), total=("won", "count")).reset_index()
        wr["win_rate"] = (wr["wins"] / wr["total"] * 100).round(1)
        out["spreader_win_rate"] = wr

        # Primary spreader frequency
        prim_spr = spr[spr["is_primary"] == True]
        if not prim_spr.empty:
            out["primary_spreader_freq"] = prim_spr["strategy_label"].value_counts().reset_index()
            out["primary_spreader_freq"].columns = ["strategy_label", "count"]

    # Debunker strategy frequency
    deb = df[df["side"] == "debunker"]
    if not deb.empty:
        cnt = deb["strategy_label"].value_counts().reset_index()
        cnt.columns = ["strategy_label", "count"]
        cnt["percent"] = (cnt["count"] / cnt["count"].sum() * 100).round(1)
        out["debunker_strategy_freq"] = cnt

        # Win rate: debunker wins when winner == "debunker"
        deb_wins = deb.assign(won=(deb["winner"].fillna("").str.strip().str.lower() == "debunker"))
        wr = deb_wins.groupby("strategy_label").agg(wins=("won", "sum"), total=("won", "count")).reset_index()
        wr["win_rate"] = (wr["wins"] / wr["total"] * 100).round(1)
        out["debunker_win_rate"] = wr

        # Primary debunker frequency
        prim_deb = deb[deb["is_primary"] == True]
        if not prim_deb.empty:
            out["primary_debunker_freq"] = prim_deb["strategy_label"].value_counts().reset_index()
            out["primary_debunker_freq"].columns = ["strategy_label", "count"]

    # Strategy by claim_type
    if "claim_type" in df.columns:
        agg = df.groupby(["strategy_label", "side", "claim_type"], dropna=False).size().reset_index(name="count")
        out["strategy_by_claim_type"] = agg

    # Strategy by claim_domain
    if "claim_domain" in df.columns:
        agg = df.groupby(["strategy_label", "side", "claim_domain"], dropna=False).size().reset_index(name="count")
        out["strategy_by_claim_domain"] = agg

    return out


# ---------------------------------------------------------------------------
# Phase 3 — Research Analytics Layer
# ---------------------------------------------------------------------------

def compute_strategy_claim_type_heatmap(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot table: rows=strategy_label, columns=claim_type, values=count.
    Missing combinations filled with 0.
    """
    if strategy_long_df.empty or "claim_type" not in strategy_long_df.columns:
        return pd.DataFrame()
    df = strategy_long_df.copy()
    df["claim_type"] = df["claim_type"].fillna("(unknown)").astype(str)
    agg = df.groupby(["strategy_label", "claim_type"], dropna=False).size().reset_index(name="count")
    pivot = agg.pivot_table(index="strategy_label", columns="claim_type", values="count", fill_value=0)
    return pivot


def compute_strategy_claim_domain_heatmap(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot table: rows=strategy_label, columns=claim_domain, values=count.
    Missing combinations filled with 0.
    """
    if strategy_long_df.empty or "claim_domain" not in strategy_long_df.columns:
        return pd.DataFrame()
    df = strategy_long_df.copy()
    df["claim_domain"] = df["claim_domain"].fillna("(unknown)").astype(str)
    agg = df.groupby(["strategy_label", "claim_domain"], dropna=False).size().reset_index(name="count")
    pivot = agg.pivot_table(index="strategy_label", columns="claim_domain", values="count", fill_value=0)
    return pivot


def compute_strategy_win_rate_table(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Table: strategy_label, side, usage_count, wins, win_rate.
    Win: spreader wins when winner==spreader; debunker when winner==debunker.
    Sorted by usage_count descending.
    """
    if strategy_long_df.empty:
        return pd.DataFrame(columns=["strategy_label", "side", "usage_count", "wins", "win_rate"])
    df = strategy_long_df.copy()
    df["won"] = (
        df["winner"].fillna("").astype(str).str.strip().str.lower()
        == df["side"].fillna("").astype(str).str.strip().str.lower()
    )
    grp = df.groupby(["strategy_label", "side"], dropna=False).agg(
        usage_count=("won", "count"),
        wins=("won", "sum"),
    ).reset_index()
    grp["win_rate"] = (grp["wins"] / grp["usage_count"] * 100).round(1)
    grp = grp.sort_values("usage_count", ascending=False).reset_index(drop=True)
    return grp


def compute_primary_strategy_performance(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Usage and win rate for strategies where is_primary==True.
    Columns: strategy_label, side, primary_usage, primary_wins, primary_win_rate.
    """
    if strategy_long_df.empty or "is_primary" not in strategy_long_df.columns:
        return pd.DataFrame()
    prim = strategy_long_df[strategy_long_df["is_primary"] == True]
    if prim.empty:
        return pd.DataFrame(columns=["strategy_label", "side", "primary_usage", "primary_wins", "primary_win_rate"])
    prim = prim.copy()
    prim["won"] = (
        prim["winner"].fillna("").astype(str).str.strip().str.lower()
        == prim["side"].fillna("").astype(str).str.strip().str.lower()
    )
    grp = prim.groupby(["strategy_label", "side"], dropna=False).agg(
        primary_usage=("won", "count"),
        primary_wins=("won", "sum"),
    ).reset_index()
    grp["primary_win_rate"] = (grp["primary_wins"] / grp["primary_usage"] * 100).round(1)
    return grp.sort_values("primary_usage", ascending=False).reset_index(drop=True)


def compute_strategy_cooccurrence(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Co-occurrence matrix: strategy_A x strategy_B.
    M[i][j] = number of episodes containing both strategy i and j.
    Diagonal M[i][i] = number of episodes containing strategy i.
    Uses pandas groupby; no nested row loops.
    """
    if strategy_long_df.empty:
        return pd.DataFrame()
    ep_key = ["run_id", "episode_index"] if "episode_index" in strategy_long_df.columns else ["run_id", "episode_id"]
    ep_key = [c for c in ep_key if c in strategy_long_df.columns]
    if not ep_key:
        return pd.DataFrame()

    # Per episode: unique strategy labels
    ep_strategies = strategy_long_df.groupby(ep_key)["strategy_label"].apply(
        lambda x: list(x.dropna().unique().astype(str))
    ).reset_index()
    ep_strategies.columns = ep_key + ["strategies"]

    # Build pair counts using explode: for each episode, create (a, b) for each pair
    rows: list[dict] = []
    for _, row in ep_strategies.iterrows():
        strategies = [s for s in row["strategies"] if s and str(s).strip()]
        if not strategies:
            continue
        for a in strategies:
            for b in strategies:
                rows.append({"strategy_a": a, "strategy_b": b})
    if not rows:
        return pd.DataFrame()
    pair_df = pd.DataFrame(rows)
    matrix = pair_df.groupby(["strategy_a", "strategy_b"]).size().unstack(fill_value=0)
    return matrix


def compute_run_level_strategy_report(strategy_long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per run: strategy_label, strategy_count, wins, win_rate.
    Group by run_id, strategy_label.
    """
    if strategy_long_df.empty:
        return pd.DataFrame()
    df = strategy_long_df.copy()
    df["won"] = (
        df["winner"].fillna("").astype(str).str.strip().str.lower()
        == df["side"].fillna("").astype(str).str.strip().str.lower()
    )
    grp = df.groupby(["run_id", "strategy_label"], dropna=False).agg(
        strategy_count=("won", "count"),
        wins=("won", "sum"),
    ).reset_index()
    grp["win_rate"] = (grp["wins"] / grp["strategy_count"] * 100).round(1)
    return grp.sort_values(["run_id", "strategy_count"], ascending=[True, False]).reset_index(drop=True)


def compute_episode_trajectory(
    long_df: pd.DataFrame,
    metric_name: str,
    view: str = "raw",
) -> pd.DataFrame:
    """
    Returns df with columns:
      - episode_index
      - spreader_value
      - debunker_value
    Aggregation: mean across all rows sharing (episode_index, side) after filtering.
    Normalized: min-max across both sides globally for this metric in the filtered dataset.
    """
    if long_df.empty or "metric_name" not in long_df.columns:
        return pd.DataFrame(columns=["episode_index", "spreader_value", "debunker_value"])

    sub = long_df[long_df["metric_name"] == metric_name].copy()
    if sub.empty:
        return pd.DataFrame(columns=["episode_index", "spreader_value", "debunker_value"])

    sub["metric_value_num"] = pd.to_numeric(sub["metric_value"], errors="coerce")
    sub = sub.dropna(subset=["metric_value_num"])

    if sub.empty:
        return pd.DataFrame(columns=["episode_index", "spreader_value", "debunker_value"])

    # Aggregate: mean per (episode_index, side)
    agg_df = sub.groupby(["episode_index", "side"], dropna=False)["metric_value_num"].mean().reset_index()
    pivot = agg_df.pivot_table(index="episode_index", columns="side", values="metric_value_num")
    result = pd.DataFrame(index=sorted(pivot.index.unique()))
    result.index.name = "episode_index"
    result["spreader_value"] = pivot["spreader"] if "spreader" in pivot.columns else float("nan")
    result["debunker_value"] = pivot["debunker"] if "debunker" in pivot.columns else float("nan")
    result = result.sort_index().reset_index()

    if view == "normalized":
        s_vals = result["spreader_value"].dropna()
        d_vals = result["debunker_value"].dropna()
        all_vals = pd.concat([s_vals, d_vals])
        if len(all_vals) >= 2:
            lo, hi = float(all_vals.min()), float(all_vals.max())
            if hi > lo:
                result["spreader_value"] = (result["spreader_value"] - lo) / (hi - lo)
                result["debunker_value"] = (result["debunker_value"] - lo) / (hi - lo)
            else:
                result["spreader_value"] = result["spreader_value"].apply(lambda x: 0.5 if pd.notna(x) else x)
                result["debunker_value"] = result["debunker_value"].apply(lambda x: 0.5 if pd.notna(x) else x)

    return result
