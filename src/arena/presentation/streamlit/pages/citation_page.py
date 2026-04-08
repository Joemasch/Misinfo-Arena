"""
Citation Tracker — aggregate citation behaviour across all runs and episodes.

Shows how each agent (spreader vs fact-checker) uses sources across the entire
dataset.  Both single-claim and multi-claim runs are included because citation
behaviour is an agent property, not a run-type property.  A filter lets users
narrow to a specific run type if needed.

No LLM calls — all analysis is regex + domain-heuristic from citation_tracker.py.
Model-agnostic: works regardless of which LLM provider generated the transcripts.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.io.run_store_v2_read import list_runs, load_episodes
from arena.analysis.citation_tracker import (
    extract_citations,
    citation_summary,
    CREDIBILITY_LABELS,
    CREDIBILITY_COLORS,
    CREDIBILITY_ORDER,
)
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.styles import PLOTLY_LAYOUT

RUNS_DIR      = "runs"
SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"
DRAW_COLOR     = "#D4A843"

TIER_ORDER = ["high", "moderate", "questionable", "uncreditable"]


# ---------------------------------------------------------------------------
# Shared turn-pair normaliser (mirrors replay_page.py — no cross-page import)
# ---------------------------------------------------------------------------

def _normalize_turn_pairs(ep: dict) -> list[dict]:
    turns = ep.get("turns") or []
    if not turns:
        return []
    by_idx: dict[int, list[dict]] = {}
    for t in turns:
        idx = t.get("turn_index", 0)
        by_idx.setdefault(idx, []).append(t)
    out = []
    for turn_idx in sorted(by_idx.keys()):
        msgs = by_idx[turn_idx]
        spr_text = deb_text = ""
        for m in msgs:
            name    = (m.get("name") or m.get("role") or "").lower()
            content = (m.get("content") or "").strip()
            if name == "spreader":
                spr_text = content
            elif name == "debunker":
                deb_text = content
        out.append({
            "pair_idx":      turn_idx + 1,
            "spreader_text": spr_text,
            "debunker_text": deb_text,
        })
    return out


# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=120)
def _load_citation_dataset(
    run_ids: tuple, runs_dir: str, token: float
) -> tuple[list[dict], pd.DataFrame]:
    """
    Returns
    -------
    episode_records : list[dict]
        One entry per episode with per-side credibility scores and counts.
    flat_df : pd.DataFrame
        One row per individual citation instance across all episodes.
    """
    episode_records: list[dict] = []
    flat_rows:       list[dict] = []

    for rid in run_ids:
        eps, _ = load_episodes(rid, runs_dir, token)
        for ep in eps:
            pairs = _normalize_turn_pairs(ep)
            if not pairs:
                continue

            cites   = extract_citations(pairs)
            spr_sum = citation_summary(cites.get("spreader", []))
            deb_sum = citation_summary(cites.get("debunker", []))

            results = ep.get("results") or {}
            config  = ep.get("config_snapshot") or {}
            winner  = results.get("winner", "").strip().lower()
            created = ep.get("created_at", "")

            # Detect run type from total_claims field
            total_claims = ep.get("total_claims", 1) or 1
            run_type = "multi-claim" if total_claims > 1 else "single-claim"

            episode_records.append({
                "run_id":          rid,
                "episode_id":      ep.get("episode_id", ""),
                "claim":           ep.get("claim", ""),
                "created_at":      created,
                "winner":          winner,
                "run_type":        run_type,
                "model_spreader":  config.get("model_spreader", "—"),
                "model_debunker":  config.get("model_debunker", "—"),
                "fc_cred_score":   deb_sum["credibility_score"],
                "spr_cred_score":  spr_sum["credibility_score"],
                "fc_n_cites":      deb_sum["total"],
                "spr_n_cites":     spr_sum["total"],
                "fc_counts":       deb_sum["counts"],
                "spr_counts":      spr_sum["counts"],
            })

            for side, cite_list in (("spreader", cites.get("spreader", [])),
                                    ("debunker",  cites.get("debunker",  []))):
                for c in cite_list:
                    flat_rows.append({
                        "run_id":      rid,
                        "episode_id":  ep.get("episode_id", ""),
                        "run_type":    run_type,
                        "winner":      winner,
                        "side":        side,
                        "raw_text":    c.raw_text,
                        "source_type": c.source_type,
                        "credibility": c.credibility,
                        "turn":        c.turn_index,
                    })

    flat_df = pd.DataFrame(flat_rows) if flat_rows else pd.DataFrame(
        columns=["run_id","episode_id","run_type","winner","side",
                 "raw_text","source_type","credibility","turn"]
    )
    return episode_records, flat_df


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _credibility_comparison_chart(flat_df: pd.DataFrame) -> go.Figure:
    """Stacked horizontal bar: credibility tier breakdown for each side."""
    fig = go.Figure()
    tier_colors = {
        "high":          "#4CAF7D",
        "moderate":      "#6BA87D",
        "questionable":  "#D4A843",
        "uncreditable":  "#C9363E",
    }
    for tier in TIER_ORDER:
        vals = []
        for side in ("debunker", "spreader"):
            sub   = flat_df[flat_df["side"] == side]
            total = len(sub)
            count = int((sub["credibility"] == tier).sum())
            vals.append(count / total * 100 if total else 0)

        fig.add_trace(go.Bar(
            name=CREDIBILITY_LABELS[tier],
            y=["Fact-checker", "Spreader"],
            x=vals,
            orientation="h",
            marker_color=tier_colors[tier],
            opacity=0.88,
            text=[f"{v:.0f}%" if v >= 6 else "" for v in vals],
            textposition="inside",
            textfont=dict(size=11, color="white"),
            hovertemplate=f"{CREDIBILITY_LABELS[tier]}: <b>%{{x:.1f}}%</b><extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        xaxis=dict(range=[0, 105], ticksuffix="%", showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=13)),
        legend=dict(
            orientation="h", y=-0.25, x=0.5, xanchor="center",
            font=dict(size=11), traceorder="normal",
        ),
        margin=dict(t=5, b=65, l=10, r=10), height=160,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _source_type_chart(flat_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: citation type breakdown per side."""
    type_labels = {
        "url":          "URL",
        "institution":  "Named institution",
        "according_to": "\"According to\"",
        "vague":        "Vague attribution",
        "statistic":    "Statistic",
    }
    all_types = flat_df["source_type"].dropna().unique().tolist()
    all_types = [t for t in ["url","institution","according_to","vague","statistic"]
                 if t in all_types]

    fig = go.Figure()
    for side, color, label in (
        ("debunker", DEBUNKER_COLOR, "Fact-checker"),
        ("spreader", SPREADER_COLOR, "Spreader"),
    ):
        sub   = flat_df[flat_df["side"] == side]
        total = len(sub) or 1
        vals  = [int((sub["source_type"] == t).sum()) / total * 100 for t in all_types]
        fig.add_trace(go.Bar(
            name=label,
            x=[type_labels.get(t, t) for t in all_types],
            y=vals,
            marker_color=color,
            opacity=0.85,
            text=[f"{v:.0f}%" if v >= 4 else "" for v in vals],
            textposition="outside",
            textfont=dict(size=10),
            hovertemplate="%{x}: <b>%{y:.1f}%</b> of all citations<extra>" + label + "</extra>",
        ))

    fig.update_layout(
        barmode="group",
        yaxis=dict(ticksuffix="%", gridcolor="#2A2A2A", tickfont=dict(size=11)),
        xaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=70, l=45, r=10), height=310,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _credibility_over_time_chart(ep_records: list[dict]) -> "go.Figure | None":
    """Line chart: per-episode credibility score over time for each side."""
    records_with_dt = []
    for r in ep_records:
        try:
            dt = datetime.fromisoformat(str(r["created_at"])[:19])
        except Exception:
            continue
        if r.get("fc_cred_score") is not None or r.get("spr_cred_score") is not None:
            records_with_dt.append({**r, "_dt": dt})

    if len(records_with_dt) < 2:
        return None

    records_with_dt.sort(key=lambda x: x["_dt"])
    xs        = [r["_dt"] for r in records_with_dt]
    fc_scores = [r.get("fc_cred_score")  for r in records_with_dt]
    spr_scores= [r.get("spr_cred_score") for r in records_with_dt]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=fc_scores, mode="lines+markers", name="Fact-checker",
        line=dict(color=DEBUNKER_COLOR, width=2.5),
        marker=dict(size=8, color=DEBUNKER_COLOR, line=dict(width=1.5, color="white")),
        hovertemplate="%{x|%b %d %H:%M}<br>FC credibility: <b>%{y:.0%}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=spr_scores, mode="lines+markers", name="Spreader",
        line=dict(color=SPREADER_COLOR, width=2.5),
        marker=dict(size=8, color=SPREADER_COLOR, line=dict(width=1.5, color="white")),
        hovertemplate="%{x|%b %d %H:%M}<br>Spreader credibility: <b>%{y:.0%}</b><extra></extra>",
    ))
    fig.add_hline(y=0.5, line_dash="dot", line_color="rgba(150,150,150,0.4)",
                  annotation_text="50%", annotation_font_size=10, annotation_font_color="#aaa")
    fig.update_layout(
        xaxis=dict(tickfont=dict(size=10), gridcolor="#2A2A2A"),
        yaxis=dict(
            tickformat=".0%", range=[0, 1.05],
            gridcolor="#2A2A2A", tickfont=dict(size=11),
            title="Credibility score",
        ),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=70, l=55, r=10), height=300,
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _top_sources_html(flat_df: pd.DataFrame, side: str, top_n: int = 10) -> str:
    """Ranked list of most-cited raw_text values for one side."""
    sub = flat_df[
        (flat_df["side"] == side) &
        (flat_df["source_type"].isin(["url", "institution", "according_to"]))
    ]
    if sub.empty:
        return '<p style="font-size:0.9rem;color:#9ca3af;font-style:italic;">No named sources detected.</p>'

    counts = Counter(zip(sub["raw_text"], sub["credibility"]))
    top    = counts.most_common(top_n)

    parts = []
    for (raw, cred), n in top:
        bg, fg = CREDIBILITY_COLORS.get(cred, ("rgba(255,255,255,0.04)", "#888"))
        label  = CREDIBILITY_LABELS.get(cred, cred.title())
        display = raw[:80] + ("…" if len(raw) > 80 else "")
        parts.append(
            f'<div style="display:flex;align-items:center;gap:0.6rem;'
            f'padding:0.4rem 0.6rem;margin-bottom:0.3rem;'
            f'background:{bg};border-radius:6px;">'
            f'<span style="font-size:0.78rem;font-weight:700;color:{fg};'
            f'min-width:5.5rem;">{label}</span>'
            f'<span style="font-size:0.88rem;color:var(--color-text-primary, #E8E4D9);flex:1;'
            f'font-family:monospace;word-break:break-all;">{display}</span>'
            f'<span style="font-size:0.78rem;color:#9ca3af;white-space:nowrap;">×{n}</span>'
            f'</div>'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_citation_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    # ── Page CSS ──────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .ct-page-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem; font-weight: 700; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0; line-height: 1.2;
        text-align: center;
    }
    .ct-page-subtitle {
        font-size: 1rem; color: var(--color-text-muted, #888); margin: 0 0 1.5rem 0;
        text-align: center;
    }
    .ct-section {
        font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; color: #9ca3af;
        border-bottom: 1px solid var(--color-border, #2A2A2A);
        padding-bottom: 0.3rem; margin: 1.6rem 0 0.8rem 0;
    }
    .ct-section:first-child { margin-top: 0; }
    .ct-prose {
        font-size: 0.94rem; color: var(--color-text-muted, #888); line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .ct-divider { border: none; border-top: 1px solid var(--color-border, #2A2A2A); margin: 1.6rem 0; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="ct-page-title">Citation Tracker</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-page-subtitle">'
        'How each agent uses sources across all runs — single-claim and multi-claim combined. '
        'Citation behaviour is an agent property, not a run-type property. '
        'All analysis is model-agnostic.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token   = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed runs yet. Run some debates in the Arena tab first.")
        return

    with st.spinner("Extracting citations from all episodes…"):
        ep_records, flat_df = _load_citation_dataset(tuple(run_ids), RUNS_DIR, token)

    if not ep_records:
        st.info("No episodes with transcript data found.")
        return

    # ── Filters ───────────────────────────────────────────────────────────
    with st.expander("Filters", expanded=False):
        run_types = sorted({r["run_type"] for r in ep_records})
        sel_type  = st.multiselect(
            "Run type", run_types, default=[],
            key="ct_run_type",
            help="Leave empty to include all run types.",
        )
        all_models = sorted({r["model_spreader"] for r in ep_records}
                            | {r["model_debunker"] for r in ep_records}
                            - {"—", "", None})
        sel_models = st.multiselect(
            "Models (either side)", all_models, default=[],
            key="ct_models",
        )

    # Apply filters
    filtered_records = ep_records
    if sel_type:
        filtered_records = [r for r in filtered_records if r["run_type"] in sel_type]
    if sel_models:
        filtered_records = [
            r for r in filtered_records
            if r["model_spreader"] in sel_models or r["model_debunker"] in sel_models
        ]

    filtered_ids = {(r["run_id"], str(r["episode_id"])) for r in filtered_records}
    if not flat_df.empty:
        filt_flat = flat_df[
            flat_df.apply(lambda row: (row["run_id"], str(row["episode_id"])) in filtered_ids, axis=1)
        ].copy()
    else:
        filt_flat = flat_df.copy()

    n_eps         = len(filtered_records)
    total_cites   = len(filt_flat) if not filt_flat.empty else 0
    fc_cites_all  = filt_flat[filt_flat["side"] == "debunker"] if not filt_flat.empty else pd.DataFrame()
    spr_cites_all = filt_flat[filt_flat["side"] == "spreader"] if not filt_flat.empty else pd.DataFrame()

    fc_scores  = [r["fc_cred_score"]  for r in filtered_records if r.get("fc_cred_score")  is not None]
    spr_scores = [r["spr_cred_score"] for r in filtered_records if r.get("spr_cred_score") is not None]
    avg_fc  = sum(fc_scores)  / len(fc_scores)  if fc_scores  else None
    avg_spr = sum(spr_scores) / len(spr_scores) if spr_scores else None

    # ── Overview cards ────────────────────────────────────────────────────
    st.markdown('<p class="ct-section" style="margin-top:0;">Overview</p>', unsafe_allow_html=True)

    def _card(label: str, value: str, sub: str = "", color: str = "#E8E4D9") -> str:
        # Shrink font for long values (e.g., "Comparable", "Fact-checker")
        _fs = "1.3rem" if len(value) > 6 else "1.8rem"
        return (
            f'<div style="flex:1;min-width:130px;background:var(--color-surface, #111);'
            f'border:1px solid var(--color-border, #2A2A2A);border-radius:10px;padding:0.9rem 1.1rem;">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.2rem;">{label}</div>'
            f'<div style="font-size:{_fs};font-weight:700;color:{color};line-height:1.2;">{value}</div>'
            f'<div style="font-size:0.8rem;color:#9ca3af;margin-top:0.1rem;">{sub}</div>'
            f'</div>'
        )

    better_side = "—"
    if avg_fc is not None and avg_spr is not None:
        if avg_fc > avg_spr + 0.05:
            better_side = "Fact-checker"
            better_color = DEBUNKER_COLOR
        elif avg_spr > avg_fc + 0.05:
            better_side = "Spreader"
            better_color = SPREADER_COLOR
        else:
            better_side = "Comparable"
            better_color = "#9ca3af"
    else:
        better_color = "#9ca3af"

    cards_html = (
        '<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.2rem;">'
        + _card("Episodes analysed", str(n_eps))
        + _card("Total citations", str(total_cites), f"{len(fc_cites_all)} FC · {len(spr_cites_all)} Spr")
        + _card("FC credibility", f"{avg_fc:.0%}" if avg_fc is not None else "—",
                "Avg across all episodes", DEBUNKER_COLOR)
        + _card("Spr credibility", f"{avg_spr:.0%}" if avg_spr is not None else "—",
                "Avg across all episodes", SPREADER_COLOR)
        + _card("Better sourcing", better_side, "by credibility score", better_color)
        + '</div>'
    )
    st.markdown(cards_html, unsafe_allow_html=True)

    if total_cites == 0:
        st.info(
            "No citations were detected in the filtered episodes. "
            "This can happen if the transcripts are short or agents rarely cite sources explicitly."
        )
        return

    # ── Credibility comparison ─────────────────────────────────────────────
    st.markdown('<hr class="ct-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ct-section">Credibility breakdown — side by side</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-prose">'
        'For every citation detected, we classify it into one of four tiers based on the source. '
        'A high proportion of green (high credibility) means that agent is backing its claims '
        'with verifiable, authoritative sources. A high proportion of yellow/red means it is '
        'relying on vague or unverifiable attributions.'
        '</p>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(_credibility_comparison_chart(filt_flat), use_container_width=True)

    # Compact tier summary (replaces redundant table — chart above shows the same data)
    tier_parts = []
    for tier in TIER_ORDER:
        fc_n  = int((fc_cites_all["credibility"] == tier).sum()) if not fc_cites_all.empty else 0
        spr_n = int((spr_cites_all["credibility"] == tier).sum()) if not spr_cites_all.empty else 0
        label = CREDIBILITY_LABELS[tier]
        color = CREDIBILITY_COLORS.get(tier, "#888")
        tier_parts.append(
            f'<span style="color:{color};font-weight:600">{label}</span>: '
            f'FC {fc_n} · Spr {spr_n}'
        )
    st.markdown(
        '<p style="font-size:0.85rem;color:var(--color-text-muted,#888);margin-top:0.5rem">'
        + ' &nbsp;│&nbsp; '.join(tier_parts)
        + '</p>',
        unsafe_allow_html=True,
    )

    # ── Citation type breakdown ────────────────────────────────────────────
    st.markdown('<hr class="ct-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ct-section">Citation type breakdown</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-prose">'
        'How each agent references sources: full URLs, named institutions, '
        '"according to" constructions, or vague attributions ("experts say", "studies show"). '
        'Vague attributions are the lowest-quality citation type — a high proportion suggests '
        'an agent is asserting without verifying.'
        '</p>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(_source_type_chart(filt_flat), use_container_width=True)

    # ── Top cited sources ──────────────────────────────────────────────────
    st.markdown('<hr class="ct-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ct-section">Most-cited named sources</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-prose">'
        'Which specific sources does each agent cite most often? '
        'Vague attributions are excluded here — only URLs, named institutions, '
        'and "according to" constructions are counted.'
        '</p>',
        unsafe_allow_html=True,
    )
    col_fc, col_spr = st.columns(2)
    with col_fc:
        st.markdown(
            f'<p style="font-size:0.82rem;font-weight:700;color:{DEBUNKER_COLOR};'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.5rem;">'
            f'Fact-checker</p>',
            unsafe_allow_html=True,
        )
        st.markdown(_top_sources_html(filt_flat, "debunker"), unsafe_allow_html=True)
    with col_spr:
        st.markdown(
            f'<p style="font-size:0.82rem;font-weight:700;color:{SPREADER_COLOR};'
            f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.5rem;">'
            f'Spreader</p>',
            unsafe_allow_html=True,
        )
        st.markdown(_top_sources_html(filt_flat, "spreader"), unsafe_allow_html=True)

    # ── Credibility over time ──────────────────────────────────────────────
    st.markdown('<hr class="ct-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ct-section">Credibility score over time</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-prose">'
        'Does citation quality change as more debates are run? '
        'Each point is one episode, ordered chronologically. '
        'A rising line means that agent is getting better at citing credible sources '
        'across successive debates.'
        '</p>',
        unsafe_allow_html=True,
    )
    time_fig = _credibility_over_time_chart(filtered_records)
    if time_fig is None:
        st.caption("Need at least 2 episodes with timestamps to show a trend.")
    else:
        st.plotly_chart(time_fig, use_container_width=True)

    # ── Episode scoreboard ─────────────────────────────────────────────────
    st.markdown('<hr class="ct-divider">', unsafe_allow_html=True)
    st.markdown('<p class="ct-section">Episode citation scoreboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ct-prose">'
        'Every episode ranked by fact-checker credibility score. '
        'Helps identify which specific debates had the best and worst sourcing quality.'
        '</p>',
        unsafe_allow_html=True,
    )

    score_rows = []
    for r in sorted(filtered_records,
                    key=lambda x: (x.get("fc_cred_score") or 0),
                    reverse=True):
        winner = r.get("winner", "").lower()
        outcome = {"debunker": "FC Won", "spreader": "Spr Won", "draw": "Draw"}.get(winner, "—")
        score_rows.append({
            "Run":         r["run_id"][-13:],  # show last 13 chars (YYYYMMDD_HHMMSS)
            "Ep":          r["episode_id"],
            "Claim":       (r.get("claim") or "—")[:60],
            "Outcome":     outcome,
            "FC cred.":    r.get("fc_cred_score"),
            "Spr cred.":   r.get("spr_cred_score"),
            "FC cites":    r.get("fc_n_cites", 0),
            "Spr cites":   r.get("spr_n_cites", 0),
        })

    score_df = pd.DataFrame(score_rows)

    def _outcome_style(val: str) -> str:
        return {
            "FC Won":  "background-color:rgba(74,127,165,0.18);color:#4A7FA5;font-weight:700;",
            "Spr Won": "background-color:rgba(212,168,67,0.18);color:#D4A843;font-weight:700;",
            "Draw":    "background-color:rgba(212,168,67,0.12);color:#D4A843;font-weight:700;",
        }.get(val, "")

    def _cred_style(val) -> str:
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return ""
        v = float(val)
        if v >= 0.75: return "background-color:rgba(22,163,74,0.14);color:#15803d;font-weight:700;"
        if v >= 0.50: return "background-color:rgba(132,204,22,0.12);color:#4d7c0f;font-weight:700;"
        if v >= 0.30: return "background-color:rgba(234,179,8,0.12);color:#a16207;font-weight:700;"
        return "background-color:rgba(220,38,38,0.09);color:#b91c1c;font-weight:700;"

    styled_score = (
        score_df.style
        .map(_outcome_style, subset=["Outcome"])
        .map(_cred_style, subset=["FC cred.", "Spr cred."])
        .format({
            "FC cred.":  lambda v: f"{v:.0%}" if v is not None and v == v else "—",
            "Spr cred.": lambda v: f"{v:.0%}" if v is not None and v == v else "—",
        })
    )
    st.dataframe(
        styled_score,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Run":       st.column_config.TextColumn(width="small"),
            "Ep":        st.column_config.NumberColumn(width=50),
            "Claim":     st.column_config.TextColumn(),
            "Outcome":   st.column_config.TextColumn(width="small"),
            "FC cred.":  st.column_config.TextColumn(width="small"),
            "Spr cred.": st.column_config.TextColumn(width="small"),
            "FC cites":  st.column_config.NumberColumn(width="small"),
            "Spr cites": st.column_config.NumberColumn(width="small"),
        },
    )

    st.markdown(
        '<p style="font-size:0.78rem;color:#9ca3af;margin-top:0.5rem;">'
        'Citations detected via regex pattern matching. Credibility assessed by domain '
        'and institution name against a curated reference list. '
        'Manual verification recommended for research use. '
        'To inspect citations for a specific episode, open it in the <b>Run Replay</b> tab.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Data export ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Export citation data")
    st.caption(
        "Download the full citation dataset for use in your thesis appendix, "
        "external analysis, or cross-referencing with transcript data."
    )

    export_col1, export_col2 = st.columns(2)

    with export_col1:
        if not filt_flat.empty:
            csv_bytes = filt_flat.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download all citations (.csv)",
                data=csv_bytes,
                file_name="citation_tracker_export.csv",
                mime="text/csv",
                use_container_width=True,
                help="One row per citation detected. Includes side, credibility tier, raw text, run ID, and episode ID.",
            )
        else:
            st.button("⬇️ Download all citations (.csv)", disabled=True, use_container_width=True)

    with export_col2:
        if not score_df.empty:
            # Export the episode scoreboard (cleaned, no styling)
            score_export = score_df.copy()
            score_csv = score_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download episode scoreboard (.csv)",
                data=score_csv,
                file_name="citation_episode_scoreboard.csv",
                mime="text/csv",
                use_container_width=True,
                help="One row per episode. Includes FC and Spreader credibility scores, citation counts, and outcome.",
            )
        else:
            st.button("⬇️ Download episode scoreboard (.csv)", disabled=True, use_container_width=True)
