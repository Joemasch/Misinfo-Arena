"""
Run Replay — research-grade replay from JSON v2 runs and episodes.

Data source: runs/<run_id>/episodes.jsonl (read-only). No judge/agent calls.
Model-agnostic: works with any LLM provider stored in config_snapshot.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.io.run_store_v2_read import list_runs, load_episodes
from arena.analysis.strategy_lens import extract_strategy_signals
from arena.analysis.citation_tracker import (
    extract_citations, citation_summary,
    CREDIBILITY_LABELS, CREDIBILITY_COLORS, CREDIBILITY_ORDER,
)
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.components.replay_styles import inject_replay_css, verdict_card_html

RUNS_DIR = "runs"
SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"

SIGNAL_LABELS = {
    "citation_like":          "Citations / source references",
    "numeric_specificity":    "Specific numbers & statistics",
    "causal_markers":         "Causal reasoning",
    "counterargument":        "Direct counterarguments",
    "rhetorical_questions":   "Rhetorical questions",
    "emotional_framing":      "Emotional framing",
    "conspiracy_framing":     "Conspiracy / distrust framing",
    "vague_sources":          "Vague or unnamed sources",
    "refutation_structure":   "Structured refutation",
    "uncertainty_calibration":"Acknowledgment of uncertainty",
}

METRIC_LABELS = {
    "truthfulness_proxy": "Factual Grounding",
    "evidence_quality":   "Evidence Quality",
    "reasoning_quality":  "Reasoning",
    "responsiveness":     "Responsiveness",
    "persuasion":         "Persuasion",
    "civility":           "Civility",
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_turn_pairs(ep: dict) -> list[dict]:
    turns = ep.get("turns") or []
    if not turns:
        return []
    by_idx: dict[int, list[dict]] = {}
    for t in turns:
        idx = t.get("turn_index", 0)
        by_idx.setdefault(idx, []).append(t)
    out = []
    for turn_idx in sorted(by_idx.keys()):
        messages = by_idx[turn_idx]
        spreader_text = debunker_text = ""
        for m in messages:
            name = (m.get("name") or m.get("role") or "").lower()
            content = (m.get("content") or "").strip()
            if name == "spreader":
                spreader_text = content
            elif name == "debunker":
                debunker_text = content
        out.append({"pair_idx": turn_idx + 1, "spreader_text": spreader_text, "debunker_text": debunker_text})
    return out


def normalize_scorecard(ep: dict) -> list[dict]:
    results = ep.get("results") or {}
    scorecard = results.get("scorecard") or []
    out = []
    for row in scorecard:
        if not isinstance(row, dict):
            continue
        spreader = float(row.get("spreader", 0) or 0)
        debunker = float(row.get("debunker", 0) or 0)
        weight   = float(row.get("weight",   0) or 0)
        delta    = debunker - spreader
        out.append({
            "metric":        row.get("metric", ""),
            "spreader":      spreader,
            "debunker":      debunker,
            "delta":         delta,
            "weight":        weight,
            "weighted_delta": delta * weight,
        })
    return out


def derived_verdict_fields(ep: dict) -> dict:
    results    = ep.get("results") or {}
    concession = ep.get("concession") or {}
    totals     = results.get("totals") or {}
    ts = totals.get("spreader")
    td = totals.get("debunker")
    try:   ts = float(ts) if ts is not None else None
    except (TypeError, ValueError): ts = None
    try:   td = float(td) if td is not None else None
    except (TypeError, ValueError): td = None
    margin     = (td - ts) if td is not None and ts is not None else None
    abs_margin = abs(margin) if margin is not None else None
    rows = normalize_scorecard(ep)
    for r in rows:
        r["abs_weighted_delta"] = abs(r.get("weighted_delta", 0) or 0)
    rows_sorted = sorted(rows, key=lambda x: -x["abs_weighted_delta"])
    top_drivers: list[tuple[str, str]] = []
    for r in rows_sorted[:3]:
        metric = METRIC_LABELS.get(r.get("metric", ""), (r.get("metric") or "").replace("_", " ").title())
        wd = r.get("weighted_delta") or 0
        top_drivers.append((metric, "benefits fact-checker" if wd > 0 else "benefits spreader"))
    winner_role = (results.get("winner") or "").strip().lower()
    return {
        "totals_spreader":      ts,
        "totals_debunker":      td,
        "margin":               margin,
        "abs_margin":           abs_margin,
        "winner_role":          winner_role,
        "confidence":           results.get("judge_confidence"),
        "end_trigger":          (concession.get("trigger") or "").strip(),
        "completed_turn_pairs": results.get("completed_turn_pairs"),
        "planned_max_turns":    (ep.get("config_snapshot") or {}).get("planned_max_turns"),
        "top_drivers":          top_drivers,
        "scorecard_sorted":     rows_sorted,
        "reason":               results.get("reason", ""),
    }


def episode_header_fields(ep: dict) -> dict:
    results    = ep.get("results") or {}
    config     = ep.get("config_snapshot") or {}
    concession = ep.get("concession") or {}
    judge_audit = ep.get("judge_audit") or {}
    totals     = results.get("totals") or {}
    return {
        "claim":                ep.get("claim", ""),
        "created_at":           ep.get("created_at", ""),
        "planned_max_turns":    config.get("planned_max_turns"),
        "completed_turn_pairs": results.get("completed_turn_pairs"),
        "end_trigger":          concession.get("trigger", ""),
        "winner":               results.get("winner", ""),
        "judge_confidence":     results.get("judge_confidence"),
        "totals_spreader":      totals.get("spreader"),
        "totals_debunker":      totals.get("debunker"),
        "judge_audit_status":   judge_audit.get("status"),
        "judge_audit_mode":     judge_audit.get("mode"),
    }


# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _cached_load_episodes(run_id: str, mtime: float, _runs_dir: str, _refresh_token: float = 0.0):
    return load_episodes(run_id, _runs_dir, _refresh_token)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _scorecard_html_table(rows: list[dict], winner_role: str) -> str:
    """Inline HTML scorecard: per-metric bars showing raw scores (0–10)."""
    if not rows:
        return ""
    # Find row with highest abs weighted delta for highlight
    top_metric = max(rows, key=lambda r: abs(r.get("weighted_delta", 0) or 0)).get("metric", "") if rows else ""

    rows_by_metric = {r.get("metric", ""): r for r in rows}
    canonical_order = [
        "truthfulness_proxy", "evidence_quality", "reasoning_quality",
        "responsiveness", "persuasion", "civility",
    ]
    ordered = [rows_by_metric[m] for m in canonical_order if m in rows_by_metric]
    # Append any unexpected metrics at end
    seen = set(canonical_order)
    ordered += [r for r in rows if r.get("metric", "") not in seen]

    html = '<table style="width:100%;border-collapse:collapse;font-size:0.93rem;">'
    html += (
        '<thead><tr>'
        '<th style="text-align:left;padding:0.4rem 0.5rem;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
        'border-bottom:1px solid rgba(0,0,0,0.08);">Dimension</th>'
        '<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#E8524A;font-weight:700;'
        'border-bottom:1px solid rgba(0,0,0,0.08);">Spreader</th>'
        '<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#3A7EC7;font-weight:700;'
        'border-bottom:1px solid rgba(0,0,0,0.08);">Fact-checker</th>'
        '<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
        'border-bottom:1px solid rgba(0,0,0,0.08);">Wt.</th>'
        '<th style="text-align:center;padding:0.4rem 0.5rem;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
        'border-bottom:1px solid rgba(0,0,0,0.08);">Winner</th>'
        '</tr></thead><tbody>'
    )

    for r in ordered:
        metric  = r.get("metric", "")
        label   = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        s_score = r.get("spreader", 0) or 0
        d_score = r.get("debunker", 0) or 0
        weight  = r.get("weight", 0) or 0
        delta   = d_score - s_score
        is_top  = (metric == top_metric)
        row_bg  = "background:rgba(240,165,0,0.08);" if is_top else ""

        row_winner = "debunker" if delta > 0.05 else ("spreader" if delta < -0.05 else "draw")
        if row_winner == "debunker":
            win_label = '<span style="color:#3A7EC7;font-weight:700;">✓ FC</span>'
        elif row_winner == "spreader":
            win_label = '<span style="color:#E8524A;font-weight:700;">✓ Sp</span>'
        else:
            win_label = '<span style="color:#9ca3af;">—</span>'

        def bar(score: float, color: str) -> str:
            pct = max(0, min(100, score / 10 * 100))
            return (
                f'<div style="display:flex;align-items:center;gap:0.4rem;">'
                f'<div style="flex:1;background:rgba(200,200,200,0.25);border-radius:3px;height:8px;">'
                f'<div style="width:{pct:.0f}%;background:{color};height:8px;border-radius:3px;"></div>'
                f'</div>'
                f'<span style="min-width:2rem;text-align:right;font-size:0.88rem;font-weight:600;">'
                f'{score:.1f}</span>'
                f'</div>'
            )

        top_marker = ' ⭑' if is_top else ''
        html += (
            f'<tr style="{row_bg}">'
            f'<td style="padding:0.5rem 0.5rem;font-weight:{"700" if is_top else "500"};'
            f'border-bottom:1px solid rgba(0,0,0,0.05);">{label}{top_marker}</td>'
            f'<td style="padding:0.5rem 0.5rem;border-bottom:1px solid rgba(0,0,0,0.05);">'
            f'{bar(s_score, SPREADER_COLOR)}</td>'
            f'<td style="padding:0.5rem 0.5rem;border-bottom:1px solid rgba(0,0,0,0.05);">'
            f'{bar(d_score, DEBUNKER_COLOR)}</td>'
            f'<td style="padding:0.5rem 0.5rem;text-align:center;font-size:0.82rem;color:#6b7280;'
            f'border-bottom:1px solid rgba(0,0,0,0.05);">{weight:.0%}</td>'
            f'<td style="padding:0.5rem 0.5rem;text-align:center;'
            f'border-bottom:1px solid rgba(0,0,0,0.05);">{win_label}</td>'
            f'</tr>'
        )

    html += '</tbody></table>'
    html += (
        '<p style="font-size:0.78rem;color:#9ca3af;margin-top:0.5rem;">'
        'Scores 0–10 &nbsp;·&nbsp; Wt. = dimension weight toward final margin &nbsp;·&nbsp; '
        '⭑ = biggest swing &nbsp;·&nbsp; FC = Fact-checker, Sp = Spreader'
        '</p>'
    )
    return html


# ---------------------------------------------------------------------------
# Turn trajectory helpers
# ---------------------------------------------------------------------------

# Signal weights for computing per-turn argument strength proxies.
# Positive = helps that side; negative = hurts that side.
_FC_SIGNAL_WEIGHTS: dict[str, float] = {
    "citation_like":          2.0,
    "numeric_specificity":    1.5,
    "causal_markers":         1.5,
    "refutation_structure":   2.0,
    "counterargument":        1.5,
    "uncertainty_calibration":1.0,
    "conspiracy_framing":    -1.5,
    "vague_sources":         -1.0,
}
_SPR_SIGNAL_WEIGHTS: dict[str, float] = {
    "emotional_framing":      2.0,
    "conspiracy_framing":     1.5,
    "vague_sources":          1.5,
    "rhetorical_questions":   1.0,
    "citation_like":          1.0,
    "causal_markers":         1.0,
    "refutation_structure":  -0.5,
    "uncertainty_calibration":-0.5,
}


def _compute_turn_trajectory(turn_pairs: list[dict]) -> list[dict]:
    """Per-turn heuristic argument strength (0–10) for each side.

    Uses ``extract_strategy_signals([pair])`` on each individual turn so we get
    per-turn signal counts, then maps them to a weighted score.  The result is
    normalised so the strongest single turn = 10.
    """
    rows: list[dict] = []
    for pair in turn_pairs:
        sig     = extract_strategy_signals([pair])
        sc      = sig.get("spreader") or {}
        dc      = sig.get("debunker") or {}
        fc_raw  = max(0.0, sum(dc.get(k, 0) * w for k, w in _FC_SIGNAL_WEIGHTS.items()))
        spr_raw = max(0.0, sum(sc.get(k, 0) * w for k, w in _SPR_SIGNAL_WEIGHTS.items()))
        rows.append({
            "turn":    pair.get("pair_idx", len(rows) + 1),
            "fc_raw":  fc_raw,
            "spr_raw": spr_raw,
        })
    if not rows:
        return []
    max_val = max(max(r["fc_raw"] for r in rows), max(r["spr_raw"] for r in rows), 1.0)
    for r in rows:
        r["fc_score"]  = round(r["fc_raw"]  / max_val * 10, 2)
        r["spr_score"] = round(r["spr_raw"] / max_val * 10, 2)
    return rows


def _trajectory_chart(trajectory: list[dict], winner_role: str) -> go.Figure:
    """Plotly line chart — per-turn heuristic argument strength."""
    turns     = [r["turn"] for r in trajectory]
    fc_scores = [r["fc_score"]  for r in trajectory]
    spr_scores= [r["spr_score"] for r in trajectory]

    winner_color = {
        "debunker": DEBUNKER_COLOR,
        "spreader": SPREADER_COLOR,
        "draw":     DRAW_COLOR,
    }.get(winner_role, "#888")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=turns, y=fc_scores, mode="lines+markers", name="Fact-checker",
        line=dict(color=DEBUNKER_COLOR, width=2.5),
        marker=dict(size=9, color=DEBUNKER_COLOR, line=dict(width=1.5, color="white")),
        hovertemplate="Turn %{x}<br>Fact-checker strength: <b>%{y:.1f}</b>/10<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=turns, y=spr_scores, mode="lines+markers", name="Spreader",
        line=dict(color=SPREADER_COLOR, width=2.5),
        marker=dict(size=9, color=SPREADER_COLOR, line=dict(width=1.5, color="white")),
        hovertemplate="Turn %{x}<br>Spreader strength: <b>%{y:.1f}</b>/10<extra></extra>",
    ))
    fig.add_hline(
        y=5, line_dash="dot", line_color="rgba(150,150,150,0.4)",
        annotation_text="midpoint", annotation_font_size=10,
        annotation_font_color="#aaa",
    )
    fig.update_layout(
        xaxis=dict(
            title="Turn", tickmode="linear", dtick=1,
            tickfont=dict(size=11), gridcolor="rgba(200,200,200,0.2)",
        ),
        yaxis=dict(
            title="Argument strength (0–10)", range=[0, 10.8],
            gridcolor="rgba(200,200,200,0.3)", tickfont=dict(size=11),
        ),
        legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=15, b=75, l=55, r=15), height=260,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Summary tab helpers
# ---------------------------------------------------------------------------

def _render_debate_brief(ep: dict, d: dict) -> None:
    """Render a structured 'Debate Brief' card — all inline styles, no blank lines."""
    winner  = d.get("winner_role", "")
    conf    = d.get("confidence")
    ts      = d.get("totals_spreader")
    td      = d.get("totals_debunker")
    margin  = d.get("margin")
    drivers = d.get("top_drivers") or []
    comp    = d.get("completed_turn_pairs")
    plan    = d.get("planned_max_turns")

    if winner == "debunker":
        winner_disp, w_color = "Fact-checker", DEBUNKER_COLOR
    elif winner == "spreader":
        winner_disp, w_color = "Spreader", SPREADER_COLOR
    else:
        winner_disp, w_color = "Draw", DRAW_COLOR

    conf_str   = f"{float(conf):.0%}" if conf is not None else "—"
    td_str     = f"{td:.1f}" if td is not None else "—"
    ts_str     = f"{ts:.1f}" if ts is not None else "—"
    margin_str = f"{margin:+.2f}" if margin is not None else "—"
    turns_str  = f"{comp} of {plan}" if comp is not None and plan is not None else "—"

    # Strategy signals (regex)
    pairs   = normalize_turn_pairs(ep)
    signals = extract_strategy_signals(pairs) if pairs else {}
    spr_sig = signals.get("spreader") or {}
    deb_sig = signals.get("debunker") or {}
    top_spr = [SIGNAL_LABELS.get(k, k.replace("_", " ").title())
               for k, v in sorted(spr_sig.items(), key=lambda x: -x[1])[:3] if v > 0]
    top_deb = [SIGNAL_LABELS.get(k, k.replace("_", " ").title())
               for k, v in sorted(deb_sig.items(), key=lambda x: -x[1])[:3] if v > 0]

    # LLM-labeled tactics
    sa         = ep.get("strategy_analysis") or {}
    spr_labels = sa.get("spreader_strategies") or []
    deb_labels = sa.get("debunker_strategies") or []

    # Inline style constants — no CSS classes, avoids Streamlit markdown parser issues
    LS  = ("font-size:0.7rem;font-weight:700;text-transform:uppercase;"
           "letter-spacing:0.08em;color:#9ca3af;margin:0.85rem 0 0.2rem 0;")
    LS0 = ("font-size:0.7rem;font-weight:700;text-transform:uppercase;"
           "letter-spacing:0.08em;color:#9ca3af;margin:0 0 0.2rem 0;")
    VS  = "font-size:0.95rem;color:#1f2937;line-height:1.5;margin:0;"
    BL  = "font-size:0.92rem;color:#374151;margin:0.15rem 0 0.15rem 0.8rem;"

    # Build as list of compact parts — joining avoids blank lines that break Streamlit HTML
    parts = [
        '<div style="border:1px solid rgba(0,0,0,0.08);border-radius:10px;'
        'padding:1rem 1.2rem;background:rgba(0,0,0,0.02);">',
        f'<p style="{LS0}">Outcome</p>',
        f'<p style="{VS}"><span style="color:{w_color};font-weight:700;">{winner_disp} won</span>'
        f'&nbsp;·&nbsp;Confidence: <strong>{conf_str}</strong>&nbsp;·&nbsp;{turns_str} turns</p>',
        f'<p style="{LS}">Scores</p>',
        f'<p style="{VS}"><span style="color:{DEBUNKER_COLOR};font-weight:600;">Fact-checker {td_str}</span>'
        f'&nbsp;vs.&nbsp;<span style="color:{SPREADER_COLOR};font-weight:600;">Spreader {ts_str}</span>'
        f'&nbsp;&nbsp;<span style="color:#6b7280;font-size:0.88rem;">Margin: {margin_str}</span></p>',
    ]

    if drivers:
        parts.append(f'<p style="{LS}">What decided the outcome</p>')
        for m, dir_ in drivers:
            parts.append(f'<p style="{BL}">• <strong>{m}</strong> — {dir_}</p>')

    if top_spr or spr_labels:
        tactics = spr_labels if spr_labels else top_spr
        parts.append(f'<p style="{LS}">Spreader tactics detected</p>')
        for t in tactics[:4]:
            parts.append(f'<p style="{BL}">• {t}</p>')

    if top_deb or deb_labels:
        tactics = deb_labels if deb_labels else top_deb
        parts.append(f'<p style="{LS}">Fact-checker tactics detected</p>')
        for t in tactics[:4]:
            parts.append(f'<p style="{BL}">• {t}</p>')

    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_episode_replay_page():
    inject_replay_css()

    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0

    st.markdown('<p class="rp-page-title">Run Replay</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-page-subtitle">Browse and analyze any completed run — '
        'single-claim variance analysis or multi-claim comparisons. '
        'Works with any AI model. Data is read-only.</p>',
        unsafe_allow_html=True,
    )

    refresh_token    = st.session_state.get("runs_refresh_token", 0)
    selected_run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=refresh_token, limit=None)

    if not selected_run_ids:
        st.info("No completed runs found yet. Run a debate in the Arena tab to see results here.")
        return

    runs_list = list_runs(RUNS_DIR, refresh_token=refresh_token)

    # ── Load all episodes ──────────────────────────────────────────────────
    all_episodes_by_run: dict[str, list[dict]] = {}
    for run_id in selected_run_ids:
        run_info = next((r for r in runs_list if r["run_id"] == run_id), None)
        if not run_info:
            continue
        mtime = run_info.get("mtime", 0.0)
        episodes, warnings = _cached_load_episodes(run_id, mtime, RUNS_DIR, refresh_token)
        all_episodes_by_run[run_id] = episodes
        for w in warnings:
            st.caption(f"⚠️ [{run_id}] {w}")

    # ── Sort runs newest-first, keep only those with loaded episodes ────────
    from datetime import datetime
    runs_list_sorted = sorted(runs_list, key=lambda r: r.get("mtime", 0), reverse=True)
    valid_runs = [r for r in runs_list_sorted if r["run_id"] in selected_run_ids
                  and all_episodes_by_run.get(r["run_id"])]

    if not valid_runs:
        st.info("No episodes found in selected runs.")
        return

    # ── Shared cell-style helpers ──────────────────────────────────────────
    def _outcome_style(val: str) -> str:
        return {
            "FC Won":  "background-color:rgba(58,126,199,0.14);color:#1a5fa8;font-weight:700;",
            "Spr Won": "background-color:rgba(232,82,74,0.12);color:#c0392b;font-weight:700;",
            "Draw":    "background-color:rgba(240,165,0,0.12);color:#92650a;font-weight:700;",
        }.get(val, "")

    def _conf_style(val) -> str:
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return ""
        v = float(val)
        if v >= 0.80: return "background-color:rgba(22,163,74,0.15);color:#15803d;font-weight:700;"
        if v >= 0.65: return "background-color:rgba(132,204,22,0.13);color:#4d7c0f;font-weight:700;"
        if v >= 0.50: return "background-color:rgba(234,179,8,0.13);color:#a16207;font-weight:700;"
        return "background-color:rgba(220,38,38,0.1);color:#b91c1c;font-weight:700;"

    def _trigger_style(val: str) -> str:
        if val == "Concession":
            return "background-color:rgba(13,148,136,0.12);color:#0f766e;font-weight:700;"
        if val == "Max turns":
            return "background-color:rgba(107,114,128,0.09);color:#6b7280;"
        return ""

    # ── Analytics handoff — extract before rendering so pop() works ────────
    target_run = st.session_state.pop("replay_target_run_id", None)
    target_ep  = st.session_state.pop("replay_target_episode_id", None)
    st.session_state.pop("replay_target_source", None)

    # ════════════════════════════════════════════════════════════════════════
    # LEVEL 1 — Run browser
    # ════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<p class="rp-tab-section" style="margin-top:0;">Runs — newest first</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.84rem;color:#9ca3af;margin:-0.25rem 0 0.6rem 0;">'
        'Click a run to see its episodes below.</p>',
        unsafe_allow_html=True,
    )

    run_rows = []
    for run_info in valid_runs:
        run_id   = run_info["run_id"]
        episodes = all_episodes_by_run.get(run_id, [])

        try:
            dt       = datetime.fromtimestamp(run_info["mtime"])
            date_str = dt.strftime("%b %d, %H:%M")
        except Exception:
            date_str = "—"

        outcomes = [((ep.get("results") or {}).get("winner") or "").lower() for ep in episodes]
        fc_n     = sum(1 for o in outcomes if o == "debunker")
        spr_n    = sum(1 for o in outcomes if o == "spreader")

        n_variants    = run_info.get("claim_variants_count") or 1
        claim_preview = run_info.get("claim_preview") or "—"
        claims_disp   = (f"{n_variants} claims" if n_variants > 1
                         else (claim_preview[:70] + ("…" if len(claim_preview) > 70 else "")))

        confs   = [float((ep.get("results") or {}).get("judge_confidence") or 0)
                   for ep in episodes
                   if (ep.get("results") or {}).get("judge_confidence") is not None]
        avg_conf = (sum(confs) / len(confs)) if confs else None

        run_rows.append({
            "Date":      date_str,
            "Episodes":  len(episodes),
            "Claim(s)":  claims_disp,
            "FC / Spr":  f"FC {fc_n} / Spr {spr_n}",
            "Avg Conf.": avg_conf,
        })

    run_df = pd.DataFrame(run_rows)
    styled_run_df = (
        run_df.style
        .map(_conf_style, subset=["Avg Conf."])
        .format({"Avg Conf.": lambda v: f"{v:.0%}" if v is not None and v == v else "—"})
    )

    preselect_run_idx = 0
    if target_run is not None:
        for i, r in enumerate(valid_runs):
            if str(r["run_id"]) == str(target_run):
                preselect_run_idx = i
                break

    run_event = st.dataframe(
        styled_run_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Date":      st.column_config.TextColumn(width="small"),
            "Episodes":  st.column_config.NumberColumn(width="small"),
            "Claim(s)":  st.column_config.TextColumn(),
            "FC / Spr":  st.column_config.TextColumn(width="small"),
            "Avg Conf.": st.column_config.TextColumn(width="small"),
        },
        key="run_browser_df",
    )

    run_sel_rows    = (run_event.selection.rows or []) if run_event.selection else []
    active_run_idx  = run_sel_rows[0] if run_sel_rows else preselect_run_idx
    selected_run_info = valid_runs[active_run_idx]
    selected_run_id   = selected_run_info["run_id"]

    st.markdown('<div class="ma-replay-divider" style="margin:0.75rem 0;"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # LEVEL 2 — Episode browser for the selected run
    # ════════════════════════════════════════════════════════════════════════
    episodes_in_run = all_episodes_by_run.get(selected_run_id, [])
    if not episodes_in_run:
        st.info(f"No episodes found in run {selected_run_id}.")
        return

    n_ep      = len(episodes_in_run)
    n_claims  = selected_run_info.get("claim_variants_count") or 1
    run_label = "Multi-claim run" if n_claims > 1 else "Single-claim run"

    st.markdown(
        f'<p class="rp-tab-section">{run_label} — {n_ep} episode{"s" if n_ep != 1 else ""}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.84rem;color:#9ca3af;margin:-0.25rem 0 0.6rem 0;">'
        'Click an episode to analyze it below.</p>',
        unsafe_allow_html=True,
    )

    ep_rows = []
    for ep in episodes_in_run:
        h        = episode_header_fields(ep)
        winner   = (h.get("winner") or "").lower()
        conf     = h.get("judge_confidence")
        conf_val = float(conf) if conf is not None else None
        comp     = h.get("completed_turn_pairs")
        plan     = h.get("planned_max_turns")
        trigger  = (h.get("end_trigger") or "").lower()

        outcome_str = {"debunker": "FC Won", "spreader": "Spr Won", "draw": "Draw"}.get(winner, "—")
        trigger_str = {"max_turns": "Max turns", "concession": "Concession",
                       "concession_keyword": "Concession"}.get(
                       trigger, trigger.replace("_", " ").title() if trigger else "—")
        turns_str = f"{comp}/{plan}" if comp is not None and plan is not None else "—"

        ep_rows.append({
            "Ep":       ep.get("episode_id", "?"),
            "Claim":    h.get("claim") or "—",
            "Outcome":  outcome_str,
            "Conf.":    conf_val,
            "Turns":    turns_str,
            "Ended by": trigger_str,
        })

    ep_df = pd.DataFrame(ep_rows)
    styled_ep_df = (
        ep_df.style
        .map(_outcome_style, subset=["Outcome"])
        .map(_conf_style,    subset=["Conf."])
        .map(_trigger_style, subset=["Ended by"])
        .format({"Conf.": lambda v: f"{v:.0%}" if v is not None and v == v else "—"})
    )

    preselect_ep_idx = 0
    if target_ep is not None:
        for i, ep in enumerate(episodes_in_run):
            if str(ep.get("episode_id", "?")) == str(target_ep):
                preselect_ep_idx = i
                break

    ep_event = st.dataframe(
        styled_ep_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Ep":       st.column_config.NumberColumn(width=50),
            "Claim":    st.column_config.TextColumn(),
            "Outcome":  st.column_config.TextColumn(width="small"),
            "Conf.":    st.column_config.TextColumn(width="small"),
            "Turns":    st.column_config.TextColumn(width="small"),
            "Ended by": st.column_config.TextColumn(width="small"),
        },
        key=f"episode_browser_df_{selected_run_id}",
    )

    # ── Episode index resolution: dataframe click + prev/next buttons ────────
    ep_idx_key = f"ep_idx_{selected_run_id}"
    ep_src_key = f"ep_src_{selected_run_id}"

    if ep_idx_key not in st.session_state:
        st.session_state[ep_idx_key] = preselect_ep_idx
        st.session_state[ep_src_key] = "init"

    ep_sel_rows = (ep_event.selection.rows or []) if ep_event.selection else []
    nav_src     = st.session_state.get(ep_src_key, "none")

    if nav_src == "button":
        # Button was just pressed — session state already updated by on_click callback
        active_ep_idx = st.session_state[ep_idx_key]
        st.session_state[ep_src_key] = "none"
    elif ep_sel_rows:
        # User clicked a row in the episode table
        active_ep_idx = ep_sel_rows[0]
        st.session_state[ep_idx_key] = active_ep_idx
    else:
        active_ep_idx = st.session_state[ep_idx_key]

    active_ep_idx = max(0, min(active_ep_idx, n_ep - 1))
    st.session_state[ep_idx_key] = active_ep_idx
    selected_ep = episodes_in_run[active_ep_idx]

    # ── Resolve header fields here so nav bar and detail area share them ────
    h       = episode_header_fields(selected_ep)
    winner  = (h.get("winner") or "").lower()
    conf_h  = h.get("judge_confidence")
    comp_h  = h.get("completed_turn_pairs")
    plan_h  = h.get("planned_max_turns")
    trigger_h = (h.get("end_trigger") or "").lower()
    created_h = (h.get("created_at") or "")[:16]

    winner_disp_h = {"debunker": "Fact-checker won", "spreader": "Spreader won",
                     "draw": "Draw"}.get(winner, "—")
    conf_str_h    = f"{float(conf_h):.0%}" if conf_h is not None else "?"
    turns_str_h   = (f"{comp_h}/{plan_h}" if comp_h is not None and plan_h is not None else "—")
    trigger_str_h = {"max_turns": "max turns", "concession": "concession",
                     "concession_keyword": "concession"}.get(trigger_h, trigger_h.replace("_", " "))

    st.markdown('<div class="ma-replay-divider" style="margin:0.75rem 0;"></div>', unsafe_allow_html=True)

    # ── Prev / Next navigation bar ─────────────────────────────────────────
    def _go_prev():
        st.session_state[ep_idx_key] = max(0, st.session_state[ep_idx_key] - 1)
        st.session_state[ep_src_key] = "button"

    def _go_next():
        st.session_state[ep_idx_key] = min(n_ep - 1, st.session_state[ep_idx_key] + 1)
        st.session_state[ep_src_key] = "button"

    nav_l, nav_c, nav_r = st.columns([1, 8, 1])
    with nav_l:
        st.button("← Prev", on_click=_go_prev, key="ep_prev_btn",
                  disabled=(active_ep_idx == 0), use_container_width=True)
    with nav_c:
        st.markdown(
            f'<p style="text-align:center;font-size:0.84rem;color:#6b7280;margin:0.3rem 0;">'
            f'<strong style="color:#374151;">Episode {active_ep_idx + 1} of {n_ep}</strong>'
            f'&nbsp; in this run &nbsp;·&nbsp; {winner_disp_h} ({conf_str_h})'
            f'&nbsp;·&nbsp; {turns_str_h} turns &nbsp;·&nbsp; {created_h}'
            f'</p>',
            unsafe_allow_html=True,
        )
    with nav_r:
        st.button("Next →", on_click=_go_next, key="ep_next_btn",
                  disabled=(active_ep_idx >= n_ep - 1), use_container_width=True)

    # ── Claim banner ───────────────────────────────────────────────────────
    claim_text = selected_ep.get("claim") or "—"
    st.markdown(
        f'<div class="rp-claim-banner">'
        f'<div class="rp-claim-label">Debate Claim</div>'
        f'<div class="rp-claim-text">{claim_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ma-replay-divider"></div>', unsafe_allow_html=True)

    # ── Derive verdict fields once (used by multiple tabs) ─────────────────
    d = derived_verdict_fields(selected_ep)

    # ── Tabs (Verdict first) ───────────────────────────────────────────────
    tab_verdict, tab_summary, tab_transcript, tab_strategy, tab_compare, tab_citations = st.tabs([
        "Verdict & Scorecard", "Summary", "Transcript", "Strategy Lens",
        f"Run Comparison ({n_ep})", "Citations",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — VERDICT & SCORECARD
    # ════════════════════════════════════════════════════════════════════════
    with tab_verdict:
        turns_str2 = f"{d.get('completed_turn_pairs')}/{d.get('planned_max_turns')}" \
            if d.get("completed_turn_pairs") is not None and d.get("planned_max_turns") is not None else "—"

        card_html = verdict_card_html(
            winner    = (d.get("winner_role") or "?").title(),
            confidence= d.get("confidence"),
            margin    = d.get("margin"),
            end_trigger=d.get("end_trigger") or "—",
            turns_str = turns_str2,
            top_drivers=d.get("top_drivers") or [],
        )
        st.markdown(card_html, unsafe_allow_html=True)

        reason = d.get("reason", "")
        if reason:
            st.markdown(
                f'<div class="rp-reason-box"><strong>Judge\'s reasoning:</strong> {reason}</div>',
                unsafe_allow_html=True,
            )

        # Scorecard table
        rows = d.get("scorecard_sorted") or []
        if rows:
            st.markdown(
                '<p class="rp-tab-section">Score breakdown by dimension</p>',
                unsafe_allow_html=True,
            )
            scorecard_html = _scorecard_html_table(rows, d.get("winner_role", ""))
            st.markdown(scorecard_html, unsafe_allow_html=True)

        # Turn-by-turn momentum trajectory
        traj_pairs = normalize_turn_pairs(selected_ep)
        if len(traj_pairs) >= 2:
            trajectory = _compute_turn_trajectory(traj_pairs)
            if trajectory:
                st.markdown(
                    '<p class="rp-tab-section" style="margin-top:1.4rem;">Argument momentum — turn by turn</p>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(
                    _trajectory_chart(trajectory, d.get("winner_role", "")),
                    use_container_width=True,
                )
                st.markdown(
                    '<p style="font-size:0.78rem;color:#9ca3af;margin-top:-0.3rem;">'
                    'Heuristic proxy — computed from regex signal counts per turn (citations, '
                    'causal markers, emotional framing, etc.), not LLM scores. '
                    'Shows <em>relative</em> argument density per side, normalised to 0–10. '
                    'Gaps between lines indicate momentum shifts.'
                    '</p>',
                    unsafe_allow_html=True,
                )

        # Download button (moved from Export tab)
        st.markdown('<div class="ma-replay-divider" style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
        ep_json_dl = json.dumps(selected_ep, indent=2, default=str)
        st.download_button(
            "Download episode JSON",
            ep_json_dl,
            file_name=f"episode_{selected_ep.get('episode_id', '')}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — SUMMARY
    # ════════════════════════════════════════════════════════════════════════
    with tab_summary:
        # Always show the structured Debate Brief first
        st.markdown(
            '<p class="rp-tab-section">Debate Brief</p>',
            unsafe_allow_html=True,
        )
        _render_debate_brief(selected_ep, d)

        # Narrative summary (stored or on-demand)
        st.markdown(
            '<p class="rp-tab-section">Narrative Analysis</p>',
            unsafe_allow_html=True,
        )
        summaries = selected_ep.get("summaries") or {}
        ver = (summaries.get("version") or "").strip()

        if ver.startswith("summary_"):
            # Stored summary — show full text directly
            full     = summaries.get("full") or summaries.get("abridged") or ""
            if full:
                st.markdown(
                    f'<div class="rp-summary-prose">{full}</div>',
                    unsafe_allow_html=True,
                )
        else:
            # On-demand generation
            from arena.analysis.replay_summary_helper import get_or_generate_replay_summary

            episode_id = selected_ep.get("episode_id", "")
            btn_key    = f"gen_replay_summary::{selected_run_id}::{episode_id}"
            cache      = st.session_state.get("replay_summary_cache_v1", {})
            cache_key  = (selected_run_id, episode_id)
            payload    = cache.get(cache_key)

            if payload:
                full_text = payload.get("full_text") or ""
                st.markdown(
                    f'<div class="rp-summary-prose">{full_text}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="rp-summary-meta">'
                    f'{payload.get("version", "")} &nbsp;·&nbsp; '
                    f'{payload.get("model", "")} &nbsp;·&nbsp; '
                    f'{str(payload.get("generated_at", ""))[:19]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if payload.get("quality_warnings"):
                    st.warning(" / ".join(payload["quality_warnings"]))
            else:
                st.info(
                    "No narrative summary stored for this episode yet. "
                    "Click below to generate one using AI."
                )
                if st.button("Generate narrative summary", key=btn_key, type="secondary"):
                    with st.spinner("Generating summary…"):
                        get_or_generate_replay_summary(selected_run_id, selected_ep)
                    cache = st.session_state.get("replay_summary_cache_v1", {})
                    if cache_key in cache:
                        payload = cache[cache_key]
                        st.success("Summary generated.")
                        full_text = payload.get("full_text") or ""
                        st.markdown(
                            f'<div class="rp-summary-prose">{full_text}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.error("Summary generation failed. Check the Audit tab for details.")

            err_key = f"replay_summary_error::{selected_run_id}::{episode_id}"
            err     = st.session_state.get(err_key)
            if err:
                with st.expander("Error details", expanded=False):
                    st.write(f"**Stage:** {err.get('stage')}")
                    st.write(f"**Error:** {err.get('exc_type')} — {err.get('message')}")
                    st.code(err.get("traceback", ""), language="text")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — TRANSCRIPT
    # ════════════════════════════════════════════════════════════════════════
    with tab_transcript:
        pairs   = normalize_turn_pairs(selected_ep)
        planned = (selected_ep.get("config_snapshot") or {}).get("planned_max_turns") or len(pairs)

        if not pairs:
            st.info("No transcript data stored for this episode.")
        else:
            ep_id = selected_ep.get("episode_id", "")

            st.markdown(
                f'<p style="font-size:0.88rem;color:#6b7280;margin-bottom:1rem;">'
                f'{len(pairs)} turn pairs &nbsp;·&nbsp; '
                f'<span style="color:{SPREADER_COLOR};font-weight:600;">Spreader</span> '
                f'vs. <span style="color:{DEBUNKER_COLOR};font-weight:600;">Fact-checker</span>'
                f'</p>',
                unsafe_allow_html=True,
            )

            # ── Chat bubble view ───────────────────────────────────────────
            for p in pairs:
                turn_num = p.get("pair_idx", "?")
                s_text   = (p.get("spreader_text") or "").strip()
                d_text   = (p.get("debunker_text") or "").strip()

                st.markdown(
                    f'<p class="rp-turn-header">Turn {turn_num} of {planned}</p>',
                    unsafe_allow_html=True,
                )
                if s_text:
                    st.markdown(
                        f'<div class="rp-bubble rp-bubble-spreader">'
                        f'<div class="rp-bubble-role">Spreader</div>'
                        f'<div class="rp-bubble-body">{s_text}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                if d_text:
                    st.markdown(
                        f'<div class="rp-bubble rp-bubble-debunker">'
                        f'<div class="rp-bubble-role">Fact-checker</div>'
                        f'<div class="rp-bubble-body">{d_text}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # ── Download buttons ───────────────────────────────────────────
            transcript_lines = []
            for p in pairs:
                transcript_lines.append(f"--- Turn {p.get('pair_idx')} of {planned} ---")
                transcript_lines.append("Spreader:\n" + (p.get("spreader_text") or ""))
                transcript_lines.append("Fact-checker:\n" + (p.get("debunker_text") or ""))
            transcript_txt  = "\n\n".join(transcript_lines)
            transcript_json = json.dumps(pairs, indent=2, default=str)

            st.markdown('<div class="ma-replay-divider" style="margin-top:1.2rem;"></div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "Download transcript (.txt)",
                    transcript_txt,
                    file_name=f"transcript_ep{ep_id}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    "Download transcript (.json)",
                    transcript_json,
                    file_name=f"transcript_ep{ep_id}.json",
                    mime="application/json",
                    use_container_width=True,
                )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 4 — STRATEGY LENS
    # ════════════════════════════════════════════════════════════════════════
    with tab_strategy:
        pairs2   = normalize_turn_pairs(selected_ep)
        signals  = extract_strategy_signals(pairs2)
        spr      = signals.get("spreader") or {}
        deb      = signals.get("debunker") or {}
        ex       = signals.get("examples") or {}

        all_keys = sorted(set(spr) | set(deb))
        active   = [(k, spr.get(k, 0), deb.get(k, 0)) for k in all_keys if spr.get(k, 0) + deb.get(k, 0) > 0]

        if not active:
            st.info("No argument signals detected in this debate's transcript.")
        else:
            st.markdown(
                '<p style="font-size:0.88rem;color:#6b7280;margin-bottom:0.75rem;">'
                'Signal counts are regex-detected from the transcript. '
                'Bar length is proportional to usage within each side.</p>',
                unsafe_allow_html=True,
            )
            max_spr = max((spr.get(k, 0) for k, _, _ in active), default=1) or 1
            max_deb = max((deb.get(k, 0) for k, _, _ in active), default=1) or 1

            lens_html = (
                '<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">'
                '<thead><tr>'
                '<th style="text-align:left;padding:0.35rem 0.5rem;font-size:0.72rem;'
                'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;font-weight:700;'
                'border-bottom:1px solid rgba(0,0,0,0.08);">Tactic</th>'
                '<th style="text-align:left;padding:0.35rem 0.5rem;font-size:0.72rem;'
                'text-transform:uppercase;letter-spacing:0.07em;color:#E8524A;font-weight:700;'
                'border-bottom:1px solid rgba(0,0,0,0.08);width:32%;">Spreader</th>'
                '<th style="text-align:left;padding:0.35rem 0.5rem;font-size:0.72rem;'
                'text-transform:uppercase;letter-spacing:0.07em;color:#3A7EC7;font-weight:700;'
                'border-bottom:1px solid rgba(0,0,0,0.08);width:32%;">Fact-checker</th>'
                '</tr></thead><tbody>'
            )

            for k, s_cnt, d_cnt in active:
                label   = SIGNAL_LABELS.get(k, k.replace("_", " ").title())
                s_pct   = s_cnt / max_spr * 100
                d_pct   = d_cnt / max_deb * 100

                def bar_cell(count: int, pct: float, color: str) -> str:
                    return (
                        f'<td style="padding:0.4rem 0.5rem;border-bottom:1px solid rgba(0,0,0,0.05);">'
                        f'<div style="display:flex;align-items:center;gap:0.5rem;">'
                        f'<div style="flex:1;background:rgba(200,200,200,0.2);border-radius:3px;height:10px;">'
                        f'<div style="width:{pct:.0f}%;background:{color};height:10px;border-radius:3px;opacity:0.85;"></div>'
                        f'</div>'
                        f'<span style="min-width:1.5rem;text-align:right;font-weight:600;font-size:0.85rem;">'
                        f'{count}</span>'
                        f'</div></td>'
                    )

                lens_html += (
                    f'<tr>'
                    f'<td style="padding:0.4rem 0.5rem;border-bottom:1px solid rgba(0,0,0,0.05);'
                    f'font-size:0.88rem;color:#374151;">{label}</td>'
                    f'{bar_cell(s_cnt, s_pct, SPREADER_COLOR)}'
                    f'{bar_cell(d_cnt, d_pct, DEBUNKER_COLOR)}'
                    f'</tr>'
                )

            lens_html += '</tbody></table>'
            st.markdown(lens_html, unsafe_allow_html=True)

        # LLM-labeled strategy analysis (if available)
        sa = selected_ep.get("strategy_analysis") or {}
        if sa.get("status") == "ok":
            st.markdown('<p class="rp-tab-section">AI-labeled strategies</p>', unsafe_allow_html=True)
            s_prim  = sa.get("spreader_primary") or "—"
            d_prim  = sa.get("debunker_primary") or "—"
            s_list  = sa.get("spreader_strategies") or []
            d_list  = sa.get("debunker_strategies") or []
            c1, c2  = st.columns(2)
            with c1:
                st.markdown(f"**Spreader primary:** {s_prim}")
                if s_list:
                    for lbl in s_list:
                        st.markdown(f"- {lbl}")
            with c2:
                st.markdown(f"**Fact-checker primary:** {d_prim}")
                if d_list:
                    for lbl in d_list:
                        st.markdown(f"- {lbl}")
            if sa.get("notes"):
                st.caption(sa["notes"])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 5 — RUN COMPARISON
    # ════════════════════════════════════════════════════════════════════════
    with tab_compare:
        if n_ep < 2:
            st.info(
                "Only one episode in this run. Run more debates with this claim "
                "to compare results across episodes."
            )
        else:
            # ── Summary banner ─────────────────────────────────────────────
            all_winners = [(ep.get("results") or {}).get("winner", "").lower()
                           for ep in episodes_in_run]
            fc_wins   = sum(1 for w in all_winners if w == "debunker")
            spr_wins  = sum(1 for w in all_winners if w == "spreader")
            draws     = sum(1 for w in all_winners if w == "draw")
            all_confs = [float((ep.get("results") or {}).get("judge_confidence") or 0)
                         for ep in episodes_in_run
                         if (ep.get("results") or {}).get("judge_confidence") is not None]
            avg_conf_all = sum(all_confs) / len(all_confs) if all_confs else None

            banner_parts = [
                '<div style="display:flex;gap:1.5rem;flex-wrap:wrap;'
                'background:rgba(0,0,0,0.02);border:1px solid rgba(0,0,0,0.07);'
                'border-radius:10px;padding:0.9rem 1.2rem;margin-bottom:1.2rem;">',
                f'<div style="text-align:center;">'
                f'<div style="font-size:1.6rem;font-weight:700;">{n_ep}</div>'
                f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                f'color:#9ca3af;">Episodes</div></div>',
                f'<div style="text-align:center;">'
                f'<div style="font-size:1.6rem;font-weight:700;color:{DEBUNKER_COLOR};">{fc_wins}</div>'
                f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                f'color:#9ca3af;">FC Wins</div></div>',
                f'<div style="text-align:center;">'
                f'<div style="font-size:1.6rem;font-weight:700;color:{SPREADER_COLOR};">{spr_wins}</div>'
                f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                f'color:#9ca3af;">Spr Wins</div></div>',
                f'<div style="text-align:center;">'
                f'<div style="font-size:1.6rem;font-weight:700;color:{DRAW_COLOR};">{draws}</div>'
                f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                f'color:#9ca3af;">Draws</div></div>',
            ]
            if avg_conf_all is not None:
                banner_parts.append(
                    f'<div style="text-align:center;">'
                    f'<div style="font-size:1.6rem;font-weight:700;">{avg_conf_all:.0%}</div>'
                    f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;'
                    f'color:#9ca3af;">Avg Confidence</div></div>'
                )
            banner_parts.append('</div>')
            st.markdown("".join(banner_parts), unsafe_allow_html=True)

            # ── Episode-by-episode outcomes table ──────────────────────────
            st.markdown(
                '<p class="rp-tab-section">Episode outcomes</p>',
                unsafe_allow_html=True,
            )

            outcome_rows = []
            for i, ep in enumerate(episodes_in_run):
                h_i      = episode_header_fields(ep)
                d_i      = derived_verdict_fields(ep)
                winner_i = (h_i.get("winner") or "").lower()
                conf_i   = h_i.get("judge_confidence")
                comp_i   = h_i.get("completed_turn_pairs")
                plan_i   = h_i.get("planned_max_turns")
                trigger_i = (h_i.get("end_trigger") or "").lower()
                ts_i     = d_i.get("totals_spreader")
                td_i     = d_i.get("totals_debunker")
                margin_i = d_i.get("margin")

                outcome_str_i = {"debunker": "FC Won", "spreader": "Spr Won", "draw": "Draw"}.get(winner_i, "—")
                trigger_str_i = {"max_turns": "Max turns", "concession": "Concession",
                                 "concession_keyword": "Concession"}.get(trigger_i,
                                 trigger_i.replace("_", " ").title() if trigger_i else "—")
                turns_str_i   = f"{comp_i}/{plan_i}" if comp_i is not None and plan_i is not None else "—"

                outcome_rows.append({
                    "Ep":         i + 1,
                    "Outcome":    outcome_str_i,
                    "Conf.":      float(conf_i) if conf_i is not None else None,
                    "FC score":   round(td_i, 1) if td_i is not None else None,
                    "Spr score":  round(ts_i, 1) if ts_i is not None else None,
                    "Margin":     round(margin_i, 2) if margin_i is not None else None,
                    "Turns":      turns_str_i,
                    "Ended by":   trigger_str_i,
                })

            cmp_df = pd.DataFrame(outcome_rows)
            styled_cmp = (
                cmp_df.style
                .map(_outcome_style, subset=["Outcome"])
                .map(_conf_style,    subset=["Conf."])
                .map(_trigger_style, subset=["Ended by"])
                .format({
                    "Conf.":     lambda v: f"{v:.0%}" if v is not None and v == v else "—",
                    "FC score":  lambda v: f"{v:.1f}" if v is not None and v == v else "—",
                    "Spr score": lambda v: f"{v:.1f}" if v is not None and v == v else "—",
                    "Margin":    lambda v: f"{v:+.2f}" if v is not None and v == v else "—",
                })
            )
            st.dataframe(
                styled_cmp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ep":        st.column_config.NumberColumn(width=50),
                    "Outcome":   st.column_config.TextColumn(width="small"),
                    "Conf.":     st.column_config.TextColumn(width="small"),
                    "FC score":  st.column_config.TextColumn(width="small"),
                    "Spr score": st.column_config.TextColumn(width="small"),
                    "Margin":    st.column_config.TextColumn(width="small"),
                    "Turns":     st.column_config.TextColumn(width="small"),
                    "Ended by":  st.column_config.TextColumn(width="small"),
                },
            )

            # ── Per-metric comparison chart ────────────────────────────────
            st.markdown(
                '<p class="rp-tab-section" style="margin-top:1.4rem;">Score comparison across episodes</p>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Each group shows how Fact-checker and Spreader scored on every dimension "
                "across all episodes. Taller blue bars = stronger fact-checker performance."
            )

            metric_order = [
                "truthfulness_proxy", "evidence_quality", "reasoning_quality",
                "responsiveness", "persuasion", "civility",
            ]

            # Build traces: one FC trace per episode, one Spr trace per episode
            # Group by metric on x-axis
            ep_labels = [f"Ep {i+1}" for i in range(n_ep)]
            metric_display = [METRIC_LABELS.get(m, m.replace("_"," ").title()) for m in metric_order]

            # For each episode, collect scores per metric
            fc_scores_by_ep  = []  # list of dicts: metric -> score
            spr_scores_by_ep = []
            for ep in episodes_in_run:
                sc = {r.get("metric", ""): r for r in normalize_scorecard(ep)}
                fc_scores_by_ep.append({m: sc[m]["debunker"] if m in sc else 0 for m in metric_order})
                spr_scores_by_ep.append({m: sc[m]["spreader"] if m in sc else 0 for m in metric_order})

            fig_cmp = go.Figure()

            for i, ep_label in enumerate(ep_labels):
                fc_vals  = [fc_scores_by_ep[i].get(m, 0) for m in metric_order]
                spr_vals = [spr_scores_by_ep[i].get(m, 0) for m in metric_order]
                opacity  = 0.9 if i == active_ep_idx else 0.5

                fig_cmp.add_trace(go.Bar(
                    name=f"{ep_label} · FC",
                    x=metric_display,
                    y=fc_vals,
                    marker_color=DEBUNKER_COLOR,
                    opacity=opacity,
                    legendgroup=ep_label,
                    legendgrouptitle_text=ep_label if i == 0 else None,
                    offsetgroup=i * 2,
                    text=[f"{v:.1f}" for v in fc_vals],
                    textposition="outside",
                    textfont_size=9,
                    showlegend=True,
                ))
                fig_cmp.add_trace(go.Bar(
                    name=f"{ep_label} · Spr",
                    x=metric_display,
                    y=spr_vals,
                    marker_color=SPREADER_COLOR,
                    opacity=opacity,
                    legendgroup=ep_label,
                    offsetgroup=i * 2 + 1,
                    text=[f"{v:.1f}" for v in spr_vals],
                    textposition="outside",
                    textfont_size=9,
                    showlegend=True,
                ))

            fig_cmp.update_layout(
                barmode="group",
                height=380,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font_size=11,
                ),
                yaxis=dict(
                    range=[0, 11],
                    gridcolor="rgba(0,0,0,0.06)",
                    title="Score (0–10)",
                    title_font_size=11,
                ),
                xaxis=dict(tickfont_size=11),
                font=dict(family="system-ui, -apple-system, sans-serif"),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)
            st.caption(
                f"Currently viewing Episode {active_ep_idx + 1} (full opacity). "
                f"Other episodes shown at reduced opacity for comparison."
            )

            # ── Config diff ────────────────────────────────────────────────
            configs = [(ep.get("config_snapshot") or {}) for ep in episodes_in_run]
            diff_keys = ["planned_max_turns", "model_spreader", "model_debunker"]
            diff_label = {
                "planned_max_turns": "Max turns",
                "model_spreader":    "Spreader model",
                "model_debunker":    "FC model",
            }
            diffs_found = {}
            for k in diff_keys:
                vals = [c.get(k) for c in configs]
                unique_vals = set(str(v) for v in vals if v is not None)
                if len(unique_vals) > 1:
                    diffs_found[k] = vals

            if diffs_found:
                st.markdown(
                    '<p class="rp-tab-section" style="margin-top:1.2rem;">'
                    'What changed across episodes</p>',
                    unsafe_allow_html=True,
                )
                diff_html_parts = [
                    '<div style="background:rgba(234,179,8,0.07);border:1px solid rgba(234,179,8,0.3);'
                    'border-radius:8px;padding:0.8rem 1.1rem;">',
                    '<p style="font-size:0.82rem;color:#92650a;margin:0 0 0.5rem 0;font-weight:600;">'
                    '⚠ Configuration varied — these differences may explain outcome changes</p>',
                ]
                for k, vals in diffs_found.items():
                    label = diff_label.get(k, k.replace("_", " ").title())
                    val_parts = [f"Ep {i+1}: <strong>{v}</strong>" for i, v in enumerate(vals)]
                    diff_html_parts.append(
                        f'<p style="font-size:0.9rem;color:#374151;margin:0.2rem 0;">'
                        f'<span style="color:#9ca3af;font-size:0.78rem;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.06em;">{label}</span> — '
                        + " · ".join(val_parts) + "</p>"
                    )
                diff_html_parts.append('</div>')
                st.markdown("".join(diff_html_parts), unsafe_allow_html=True)
            else:
                st.markdown(
                    '<p style="font-size:0.84rem;color:#9ca3af;margin-top:0.5rem;">'
                    'All episodes used identical configuration.</p>',
                    unsafe_allow_html=True,
                )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 6 — CITATIONS
    # ════════════════════════════════════════════════════════════════════════
    with tab_citations:
        cite_pairs = normalize_turn_pairs(selected_ep)
        if not cite_pairs:
            st.info("No transcript data available — cannot extract citations.")
        else:
            citations = extract_citations(cite_pairs)
            spr_cites = citations.get("spreader", [])
            deb_cites = citations.get("debunker", [])
            spr_summary = citation_summary(spr_cites)
            deb_summary = citation_summary(deb_cites)

            # ── Credibility score banner ───────────────────────────────────
            def _cred_score_display(score: "float | None", label: str, color: str) -> str:
                if score is None:
                    val, sub = "—", "No citations found"
                else:
                    val = f"{score:.0%}"
                    if score >= 0.80:
                        sub = "Strong sourcing"
                    elif score >= 0.55:
                        sub = "Mixed sourcing"
                    else:
                        sub = "Weak / vague sourcing"
                return (
                    f'<div style="flex:1;min-width:160px;background:rgba(0,0,0,0.02);'
                    f'border:1px solid rgba(0,0,0,0.08);border-radius:10px;'
                    f'padding:0.9rem 1.2rem;text-align:center;">'
                    f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.08em;color:{color};margin-bottom:0.2rem;">{label}</div>'
                    f'<div style="font-size:2rem;font-weight:700;color:#1f2937;">{val}</div>'
                    f'<div style="font-size:0.8rem;color:#9ca3af;">{sub}</div>'
                    f'</div>'
                )

            banner_html = (
                '<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.2rem;">'
                + _cred_score_display(spr_summary["credibility_score"], "Spreader credibility score", SPREADER_COLOR)
                + _cred_score_display(deb_summary["credibility_score"], "Fact-checker credibility score", DEBUNKER_COLOR)
                + '</div>'
            )
            st.markdown(banner_html, unsafe_allow_html=True)
            st.markdown(
                '<p style="font-size:0.8rem;color:#9ca3af;margin-top:-0.5rem;margin-bottom:1rem;">'
                'Credibility score = weighted average of citation quality: '
                'named credible institutions score 1.0, established outlets 0.65, '
                'vague attributions 0.3, uncreditable sources 0.0.'
                '</p>',
                unsafe_allow_html=True,
            )

            # ── Per-side citation detail ───────────────────────────────────
            def _cite_list_html(cites: list, side_color: str) -> str:
                if not cites:
                    return (
                        '<p style="font-size:0.9rem;color:#9ca3af;font-style:italic;">'
                        'No citations detected in this transcript.</p>'
                    )
                sorted_cites = sorted(
                    cites,
                    key=lambda c: (CREDIBILITY_ORDER.get(c.credibility, 9), c.turn_index),
                )
                parts = []
                for c in sorted_cites:
                    bg, fg = CREDIBILITY_COLORS.get(c.credibility, ("rgba(0,0,0,0.04)", "#374151"))
                    cred_label = CREDIBILITY_LABELS.get(c.credibility, c.credibility.title())
                    type_disp  = c.source_type.replace("_", " ").title()
                    parts.append(
                        f'<div style="background:{bg};border-left:3px solid {fg};'
                        f'border-radius:0 6px 6px 0;padding:0.55rem 0.9rem;margin-bottom:0.5rem;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;'
                        f'margin-bottom:0.2rem;">'
                        f'<span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:0.07em;color:{fg};">{cred_label}</span>'
                        f'<span style="font-size:0.72rem;color:#9ca3af;">Turn {c.turn_index} · {type_disp}</span>'
                        f'</div>'
                        f'<div style="font-size:0.9rem;color:#1f2937;font-family:monospace;'
                        f'word-break:break-all;">{c.raw_text}</div>'
                        f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.15rem;">{c.reason}</div>'
                        f'</div>'
                    )
                return "".join(parts)

            # Credibility breakdown mini-bars
            def _tier_bars_html(summary: dict, color: str) -> str:
                counts = summary["counts"]
                total  = summary["total"] or 1
                parts  = []
                for tier in ("high", "moderate", "questionable", "uncreditable"):
                    n   = counts.get(tier, 0)
                    pct = n / total * 100
                    _, fg = CREDIBILITY_COLORS.get(tier, ("", "#9ca3af"))
                    lbl = CREDIBILITY_LABELS.get(tier, tier.title())
                    parts.append(
                        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.3rem;">'
                        f'<div style="width:7rem;font-size:0.8rem;color:#374151;">{lbl}</div>'
                        f'<div style="flex:1;background:rgba(200,200,200,0.2);border-radius:3px;height:8px;">'
                        f'<div style="width:{pct:.0f}%;background:{fg};height:8px;border-radius:3px;opacity:0.85;"></div>'
                        f'</div>'
                        f'<div style="font-size:0.8rem;font-weight:600;color:{fg};min-width:1.5rem;">{n}</div>'
                        f'</div>'
                    )
                return "".join(parts)

            col_spr, col_deb = st.columns(2)

            with col_spr:
                st.markdown(
                    f'<p class="rp-tab-section" style="color:{SPREADER_COLOR};">Spreader citations</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(_tier_bars_html(spr_summary, SPREADER_COLOR), unsafe_allow_html=True)
                st.markdown(
                    f'<p style="font-size:0.78rem;color:#9ca3af;margin:0.5rem 0 0.75rem 0;">'
                    f'{spr_summary["total"]} citation(s) detected</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(_cite_list_html(spr_cites, SPREADER_COLOR), unsafe_allow_html=True)

            with col_deb:
                st.markdown(
                    f'<p class="rp-tab-section" style="color:{DEBUNKER_COLOR};">Fact-checker citations</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(_tier_bars_html(deb_summary, DEBUNKER_COLOR), unsafe_allow_html=True)
                st.markdown(
                    f'<p style="font-size:0.78rem;color:#9ca3af;margin:0.5rem 0 0.75rem 0;">'
                    f'{deb_summary["total"]} citation(s) detected</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(_cite_list_html(deb_cites, DEBUNKER_COLOR), unsafe_allow_html=True)

            st.markdown(
                '<p style="font-size:0.78rem;color:#9ca3af;margin-top:1rem;border-top:1px solid '
                'rgba(0,0,0,0.07);padding-top:0.5rem;">'
                'Citations are detected using regex pattern matching — URLs, named institutions, '
                '"according to" constructions, and vague attributions. '
                'Credibility is assessed by domain and institution name against a curated list. '
                'Manual verification is always recommended for research use.'
                '</p>',
                unsafe_allow_html=True,
            )

