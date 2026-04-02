"""
Claim-level analytics for Advanced Claim Analysis.

Computes difficulty index, claim-level aggregations, and turn-sensitivity metrics.
"""

from __future__ import annotations

import pandas as pd


def compute_claim_difficulty_index(
    debunker_win_rate: float,
    avg_confidence: float,
    anomaly_rate: float,
) -> float:
    """
    Compute difficulty index for a claim.

    Higher = harder to debunk.
    Formula: (1 - debunker_win_rate) * 0.4 + (1 - avg_confidence) * 0.3 + anomaly_rate * 0.3

    All inputs should be 0-1. Returns 0-1.
    """
    drw = max(0.0, min(1.0, float(debunker_win_rate)))
    conf = max(0.0, min(1.0, float(avg_confidence)))
    anom = max(0.0, min(1.0, float(anomaly_rate)))
    return round((1 - drw) * 0.4 + (1 - conf) * 0.3 + anom * 0.3, 3)


def build_claim_level_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a claim-level dataframe with difficulty index and aggregated metrics.

    Groups by claim text. Returns one row per unique claim with:
    claim, claim_domain, claim_type, claim_complexity, episodes, debunker_win_rate,
    avg_confidence, anomaly_rate, difficulty_index
    """
    if df.empty or "claim" not in df.columns:
        return pd.DataFrame()

    df_work = df.copy()
    df_work["_claim_norm"] = df_work["claim"].fillna("").astype(str).str.strip()
    df_work = df_work[df_work["_claim_norm"] != ""]

    if df_work.empty:
        return pd.DataFrame()

    winners = (
        df_work["winner"].fillna("").astype(str).str.strip().str.lower()
        if "winner" in df_work.columns
        else pd.Series("", index=df_work.index)
    )
    df_work["_debunker_win"] = (winners == "debunker").astype(int)

    conf = pd.to_numeric(df_work["judge_confidence"], errors="coerce").fillna(0) if "judge_confidence" in df_work.columns else pd.Series(0.0, index=df_work.index)
    df_work["_conf"] = conf.clip(0, 1)

    err = pd.to_numeric(df_work["error_flag"], errors="coerce").fillna(0).astype(bool).astype(int) if "error_flag" in df_work.columns else pd.Series(0, index=df_work.index)
    df_work["_err"] = err

    grp = df_work.groupby("_claim_norm")
    out = pd.DataFrame({
        "claim": grp["claim"].first(),
        "episodes": grp.size(),
        "debunker_win_rate": (grp["_debunker_win"].sum() / grp.size()).round(3),
        "avg_confidence": grp["_conf"].mean().round(3),
        "anomaly_rate": (grp["_err"].sum() / grp.size()).round(3),
    })
    for col in ["claim_domain", "claim_type", "claim_complexity"]:
        if col in df_work.columns:
            out[col] = grp[col].first().fillna("unknown")
        else:
            out[col] = "unknown"
    out = out.reset_index(drop=True)

    out["difficulty_index"] = out.apply(
        lambda r: compute_claim_difficulty_index(
            r["debunker_win_rate"], r["avg_confidence"], r["anomaly_rate"]
        ),
        axis=1,
    )
    return out


def build_turn_sensitivity_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build turn-limit sensitivity dataframe.

    Groups by planned_max_turns. Returns:
    planned_max_turns, episodes, debunker_win_rate, avg_confidence, avg_margin
    """
    col = "planned_max_turns"
    if df.empty or col not in df.columns:
        return pd.DataFrame()

    df_work = df.copy()
    winners = (
        df_work["winner"].fillna("").astype(str).str.strip().str.lower()
        if "winner" in df_work.columns
        else pd.Series("", index=df_work.index)
    )
    df_work["_debunker_win"] = (winners == "debunker").astype(int)
    df_work["_conf"] = pd.to_numeric(df_work["judge_confidence"], errors="coerce").fillna(0) if "judge_confidence" in df_work.columns else 0.0
    df_work["_marg"] = pd.to_numeric(df_work["abs_margin"], errors="coerce").fillna(0) if "abs_margin" in df_work.columns else 0.0

    grp = df_work.groupby(col, dropna=False)
    out = grp.agg(
        episodes=("_debunker_win", "count"),
        debunker_win_rate=("_debunker_win", "mean"),
        avg_confidence=("_conf", "mean"),
        avg_margin=("_marg", "mean"),
    ).round(3)
    out = out.reset_index()
    return out.sort_values(col, ascending=True)
