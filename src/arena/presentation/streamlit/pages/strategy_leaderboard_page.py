"""
Strategy Leaderboard — research-grade strategy analytics from completed debates.

Uses persisted strategy_analysis (taxonomy-constrained LLM labels).
All charts use Plotly. No matplotlib. Read-only; no agent/judge calls.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.colors as pc
import streamlit as st

from arena.analysis.episode_dataset import build_strategy_long_df
from arena.analysis.research_analytics import (
    apply_strategy_filters,
    compute_strategy_leaderboard,
    compute_strategy_win_rate_table,
    compute_primary_strategy_performance,
    compute_run_level_strategy_report,
)
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

RUNS_DIR       = "runs"
SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _label(s: str) -> str:
    """snake_case → Title Case with spaces."""
    return (s or "").replace("_", " ").title()


def _win_rate_color(rate: float) -> str:
    """Green → amber → red gradient based on win rate (0–100)."""
    if rate >= 65:
        return "rgba(22,163,74,0.15)"
    if rate >= 45:
        return "rgba(234,179,8,0.13)"
    return "rgba(220,38,38,0.10)"


# ---------------------------------------------------------------------------
# Page CSS
# ---------------------------------------------------------------------------

def _inject_styles() -> None:
    st.markdown("""
    <style>
    .sl-page-title {
        font-size: 2rem; font-weight: 700; letter-spacing: -0.02em;
        margin: 0 0 0.2rem 0; line-height: 1.2;
    }
    .sl-page-subtitle {
        font-size: 1rem; color: #6b7280; margin: 0 0 1.5rem 0;
    }
    .sl-section {
        font-size: 1.35rem; font-weight: 700; color: #111;
        margin: 2.2rem 0 0.2rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #e8e8e8;
    }
    .sl-question {
        font-size: 1rem; font-weight: 700; color: #222; margin-bottom: 0.35rem;
    }
    .sl-prose {
        font-size: 0.94rem; color: #444; line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .sl-caption {
        font-size: 0.82rem; color: #6b7280; line-height: 1.5;
        margin-top: 0.3rem; margin-bottom: 1rem; max-width: 760px;
    }
    .sl-divider { border: none; border-top: 1px solid #e8e8e8; margin: 2rem 0; }
    .sl-sub {
        font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; color: #9ca3af;
        border-bottom: 1px solid rgba(0,0,0,0.07);
        padding-bottom: 0.25rem; margin: 1.2rem 0 0.6rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_strategy_df(run_ids: tuple, runs_dir: str, token: float) -> pd.DataFrame:
    return build_strategy_long_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)


@st.cache_data(show_spinner=False)
def _load_emergent_df(run_ids: tuple, runs_dir: str, token: float) -> pd.DataFrame:
    """Load emergent (non-taxonomy) strategy observations from all episodes."""
    import json, os
    from pathlib import Path

    rows: list[dict] = []
    for run_id in run_ids:
        ep_path = Path(runs_dir) / run_id / "episodes.jsonl"
        if not ep_path.exists():
            continue
        with ep_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ep = json.loads(line)
                except Exception:
                    continue
                sa = ep.get("strategy_analysis") or {}
                emergent = sa.get("emergent_strategies") or []
                winner = (ep.get("results") or {}).get("winner", "unknown")
                for entry in emergent:
                    if not isinstance(entry, dict):
                        continue
                    label = str(entry.get("label") or "").strip()
                    side  = str(entry.get("side") or "").strip()
                    desc  = str(entry.get("description") or "").strip()
                    if label and side:
                        rows.append({
                            "run_id":      run_id,
                            "episode_id":  ep.get("episode_id", 0),
                            "side":        side,
                            "label":       label,
                            "description": desc,
                            "winner":      winner,
                        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["run_id", "episode_id", "side", "label", "description", "winner"]
    )


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _freq_chart(freq_df: pd.DataFrame, color: str, label_col: str = "strategy_label",
                count_col: str = "count", pct_col: str = "percent") -> go.Figure:
    """Horizontal bar — strategy frequency ranked by count."""
    df = freq_df.copy().sort_values(count_col, ascending=True)
    labels = [_label(s) for s in df[label_col]]
    counts = df[count_col].tolist()
    pcts   = df[pct_col].tolist() if pct_col in df.columns else [None] * len(counts)

    fig = go.Figure(go.Bar(
        y=labels, x=counts, orientation="h",
        marker_color=color, opacity=0.85,
        text=[f"{c}  ({p:.0f}%)" if p is not None else str(c)
              for c, p in zip(counts, pcts)],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="%{y}<br>Count: <b>%{x}</b><extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Episodes", tickfont=dict(size=10),
                   gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=10, b=35, l=10, r=80),
        height=max(220, len(labels) * 34 + 60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _win_rate_chart(wr_df: pd.DataFrame, side: str) -> go.Figure:
    """Horizontal bar chart coloured by win rate (green = high, red = low)."""
    color = DEBUNKER_COLOR if side == "debunker" else SPREADER_COLOR
    df = wr_df.copy().sort_values("win_rate", ascending=True)
    labels    = [_label(s) for s in df["strategy_label"]]
    win_rates = df["win_rate"].tolist()
    totals    = df["usage_count"].tolist() if "usage_count" in df.columns else df["total"].tolist()

    # Color each bar: green/amber/red based on win rate
    bar_colors = [
        "#22c55e" if wr >= 65 else ("#eab308" if wr >= 45 else "#ef4444")
        for wr in win_rates
    ]

    fig = go.Figure(go.Bar(
        y=labels, x=win_rates, orientation="h",
        marker_color=bar_colors, opacity=0.85,
        text=[f"{wr:.0f}%  (n={n})" for wr, n in zip(win_rates, totals)],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="%{y}<br>Win rate: <b>%{x:.1f}%</b><extra></extra>",
    ))
    fig.add_vline(x=50, line_dash="dot", line_color="rgba(150,150,150,0.5)",
                  annotation_text="50%", annotation_font_size=10,
                  annotation_font_color="#aaa")
    fig.update_layout(
        xaxis=dict(title="Win rate (%)", range=[0, 115], ticksuffix="%",
                   tickfont=dict(size=10), gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=10, b=40, l=10, r=90),
        height=max(220, len(labels) * 34 + 60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _primary_perf_chart(primary_df: pd.DataFrame) -> go.Figure:
    """Grouped horizontal bar: primary strategy usage by side."""
    spr = primary_df[primary_df["side"] == "spreader"].copy()
    deb = primary_df[primary_df["side"] == "debunker"].copy()

    fig = go.Figure()
    for df_side, color, name in (
        (spr, SPREADER_COLOR, "Spreader"),
        (deb, DEBUNKER_COLOR, "Fact-checker"),
    ):
        if df_side.empty:
            continue
        fig.add_trace(go.Bar(
            name=name,
            y=[_label(s) for s in df_side["strategy_label"]],
            x=df_side["primary_usage"].tolist(),
            orientation="h",
            marker_color=color,
            opacity=0.85,
            text=[str(v) for v in df_side["primary_usage"]],
            textposition="outside",
            textfont=dict(size=10),
            hovertemplate="%{y}<br>Used as primary: <b>%{x}</b> times<extra>" + name + "</extra>",
        ))

    fig.update_layout(
        barmode="group",
        xaxis=dict(title="Used as primary strategy (episode count)",
                   gridcolor="rgba(200,200,200,0.3)", tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=70, l=10, r=60),
        height=max(280, len(primary_df["strategy_label"].unique()) * 22 + 100),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig



def _claim_heatmap(pivot_df: pd.DataFrame, colorscale: str, title: str) -> go.Figure:
    """Plotly heatmap — strategy × claim attribute frequency."""
    row_labels = [_label(idx) for idx in pivot_df.index]
    col_labels = [str(c) for c in pivot_df.columns]
    z          = pivot_df.values.tolist()

    fig = go.Figure(go.Heatmap(
        z=z,
        x=col_labels,
        y=row_labels,
        colorscale=colorscale,
        hovertemplate="<b>%{y}</b> in <b>%{x}</b>: %{z} episodes<extra></extra>",
        colorbar=dict(title="Episodes", tickfont=dict(size=10)),
    ))
    fig.update_layout(
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
        margin=dict(t=10, b=100, l=10, r=10),
        height=max(350, len(row_labels) * 26 + 140),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_strategy_leaderboard_page():
    _inject_styles()

    st.markdown('<p class="sl-page-title">Strategy Leaderboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-page-subtitle">'
        'Which rhetorical tactics do agents use most, and which ones actually win? '
        'Every episode is labelled post-debate by an AI analyst using a fixed taxonomy '
        'of 10 spreader and 10 fact-checker strategies.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Data loading ───────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token   = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed runs found yet. Run a debate in the Arena tab first.")
        return

    strategy_long_df = _load_strategy_df(tuple(run_ids), RUNS_DIR, token)

    if strategy_long_df.empty:
        st.info(
            "No strategy analysis data yet. Strategy labelling runs automatically "
            "after each debate — complete a few more runs to see results here."
        )
        return

    # ── Filters ───────────────────────────────────────────────────────────
    arena_opts      = [x for x in strategy_long_df.get("arena_mode",      pd.Series()).dropna().unique() if str(x) not in ("nan","None")]
    claim_type_opts = [x for x in strategy_long_df.get("claim_type",      pd.Series()).dropna().unique() if str(x) not in ("nan","None")]

    with st.expander("Filters", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_arena = st.multiselect("Arena mode", arena_opts, default=[], key="sl_arena")
        with fc2:
            sel_claim_type = st.multiselect("Claim type", claim_type_opts, default=[], key="sl_claim_type")

    filtered = apply_strategy_filters(
        strategy_long_df,
        arena_modes=sel_arena or None,
        claim_types=sel_claim_type or None,
    )

    if filtered.empty:
        st.warning("No strategy data matches the current filters. Try removing some filters.")
        return

    # ── Pre-compute all analytics ──────────────────────────────────────────
    lb          = compute_strategy_leaderboard(filtered)
    win_rate_df = compute_strategy_win_rate_table(filtered)
    primary_df  = compute_primary_strategy_performance(filtered)
    run_report  = compute_run_level_strategy_report(filtered)

    spr_freq = lb.get("spreader_strategy_freq", pd.DataFrame())
    deb_freq = lb.get("debunker_strategy_freq", pd.DataFrame())

    # ── Overview cards ─────────────────────────────────────────────────────
    ep_col = [c for c in ["run_id","episode_index"] if c in filtered.columns]
    n_eps  = filtered.drop_duplicates(subset=ep_col).shape[0] if ep_col else filtered.shape[0]

    top_spr = _label(spr_freq.iloc[0]["strategy_label"]) if not spr_freq.empty else "—"
    top_deb = _label(deb_freq.iloc[0]["strategy_label"]) if not deb_freq.empty else "—"

    spr_wr = lb.get("spreader_win_rate", pd.DataFrame())
    deb_wr = lb.get("debunker_win_rate", pd.DataFrame())
    best_spr_wr = (
        spr_wr.loc[spr_wr["win_rate"].idxmax()] if not spr_wr.empty and "win_rate" in spr_wr.columns else None
    )
    best_deb_wr = (
        deb_wr.loc[deb_wr["win_rate"].idxmax()] if not deb_wr.empty and "win_rate" in deb_wr.columns else None
    )

    def _card(label: str, value: str, sub: str = "", color: str = "#1f2937") -> str:
        return (
            f'<div style="flex:1;min-width:140px;background:rgba(0,0,0,0.02);'
            f'border:1px solid rgba(0,0,0,0.08);border-radius:10px;padding:0.85rem 1.1rem;">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.2rem;">{label}</div>'
            f'<div style="font-size:1.55rem;font-weight:700;color:{color};line-height:1.15;">{value}</div>'
            f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.15rem;">{sub}</div>'
            f'</div>'
        )

    best_spr_str = (
        f"{_label(best_spr_wr['strategy_label'])} ({best_spr_wr['win_rate']:.0f}%)"
        if best_spr_wr is not None else "—"
    )
    best_deb_str = (
        f"{_label(best_deb_wr['strategy_label'])} ({best_deb_wr['win_rate']:.0f}%)"
        if best_deb_wr is not None else "—"
    )

    cards_html = (
        '<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.5rem;">'
        + _card("Episodes with strategy data", str(n_eps))
        + _card("Most-used spreader tactic", top_spr, "by episode count", SPREADER_COLOR)
        + _card("Most-used FC tactic", top_deb, "by episode count", DEBUNKER_COLOR)
        + _card("Highest-win spreader tactic", best_spr_str, "among used strategies", SPREADER_COLOR)
        + _card("Highest-win FC tactic", best_deb_str, "among used strategies", DEBUNKER_COLOR)
        + '</div>'
    )
    st.markdown(cards_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 — STRATEGY FREQUENCY
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sl-section">Part I: How often does each strategy appear?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-prose">'
        'Frequency counts how many episodes an AI analyst labelled as using a given strategy. '
        'A high-frequency strategy is one both sides reach for often — but frequency alone '
        'doesn\'t mean it works. See Part II for win rates.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_spr, col_deb = st.columns(2)

    with col_spr:
        st.markdown(
            f'<p class="sl-sub" style="color:{SPREADER_COLOR};">Spreader strategies</p>',
            unsafe_allow_html=True,
        )
        if not spr_freq.empty:
            st.plotly_chart(_freq_chart(spr_freq, SPREADER_COLOR), use_container_width=True)
        else:
            st.caption("No spreader strategy data.")

    with col_deb:
        st.markdown(
            f'<p class="sl-sub" style="color:{DEBUNKER_COLOR};">Fact-checker strategies</p>',
            unsafe_allow_html=True,
        )
        if not deb_freq.empty:
            st.plotly_chart(_freq_chart(deb_freq, DEBUNKER_COLOR), use_container_width=True)
        else:
            st.caption("No fact-checker strategy data.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 — WIN RATES
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sl-section">Part II: Which strategies win?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-prose">'
        'Win rate = percentage of episodes where the labelled agent won, '
        'among all episodes where that strategy was detected. '
        '<span style="color:#22c55e;font-weight:600;">Green ≥ 65%</span> — '
        'consistently wins. '
        '<span style="color:#eab308;font-weight:600;">Amber 45–65%</span> — '
        'mixed results. '
        '<span style="color:#ef4444;font-weight:600;">Red &lt; 45%</span> — '
        'associated with losing. '
        'Sample size (n=) is shown — treat low-n rates with caution.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not win_rate_df.empty:
        spr_wr_full = win_rate_df[win_rate_df["side"] == "spreader"].copy()
        deb_wr_full = win_rate_df[win_rate_df["side"] == "debunker"].copy()

        wr_col_spr, wr_col_deb = st.columns(2)

        with wr_col_spr:
            st.markdown(
                f'<p class="sl-sub" style="color:{SPREADER_COLOR};">Spreader win rates</p>',
                unsafe_allow_html=True,
            )
            if not spr_wr_full.empty:
                st.plotly_chart(_win_rate_chart(spr_wr_full, "spreader"), use_container_width=True)
            else:
                st.caption("No spreader win rate data.")

        with wr_col_deb:
            st.markdown(
                f'<p class="sl-sub" style="color:{DEBUNKER_COLOR};">Fact-checker win rates</p>',
                unsafe_allow_html=True,
            )
            if not deb_wr_full.empty:
                st.plotly_chart(_win_rate_chart(deb_wr_full, "debunker"), use_container_width=True)
            else:
                st.caption("No fact-checker win rate data.")
    else:
        st.caption("No win rate data available.")

    # ── Primary strategy performance ───────────────────────────────────────
    st.markdown('<hr class="sl-divider" style="margin:1.2rem 0;">', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-question">Which strategy did each side rely on most as their <em>primary</em> tactic?</p>'
        '<p class="sl-prose">'
        'The primary strategy is the single most dominant tactic the analyst flagged for that agent '
        'in a given episode. This shows how often each strategy was chosen as the lead approach, '
        'not just a secondary tactic.'
        '</p>',
        unsafe_allow_html=True,
    )
    if not primary_df.empty:
        st.plotly_chart(_primary_perf_chart(primary_df), use_container_width=True)
    else:
        st.caption("No primary strategy data.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 — STRATEGY × CLAIM TYPE (split by side)
    # ══════════════════════════════════════════════════════════════════════
    has_ct = "claim_type" in filtered.columns and filtered["claim_type"].notna().any()

    if has_ct:
        st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
        st.markdown(
            '<p class="sl-section">Part III: Does claim type affect strategy choice?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sl-prose">'
            'Which tactics does each side use for different claim types? '
            'A strategy concentrated in one domain but absent from others is a domain-specific finding. '
            'Spreader and fact-checker tactics are shown separately so you can see which side drives the pattern.'
            '</p>',
            unsafe_allow_html=True,
        )

        _spr_data = filtered[filtered["side"] == "spreader"].copy() if "side" in filtered.columns else pd.DataFrame()
        _deb_data = filtered[filtered["side"] == "debunker"].copy() if "side" in filtered.columns else pd.DataFrame()

        def _build_side_heatmap(side_df, title, colorscale):
            if side_df.empty or "claim_type" not in side_df.columns:
                return None
            side_df["claim_type"] = side_df["claim_type"].fillna("(unknown)").astype(str)
            agg = side_df.groupby(["strategy_label", "claim_type"], dropna=False).size().reset_index(name="count")
            pivot = agg.pivot_table(index="strategy_label", columns="claim_type", values="count", fill_value=0)
            if pivot.empty or pivot.size < 2:
                return None
            return _claim_heatmap(pivot, colorscale, title)

        hm_col1, hm_col2 = st.columns(2)
        with hm_col1:
            st.markdown(
                '<p class="sl-sub">Spreader tactics by claim type</p>',
                unsafe_allow_html=True,
            )
            fig_spr_hm = _build_side_heatmap(_spr_data, "Spreader × Claim Type", "Reds")
            if fig_spr_hm:
                st.plotly_chart(fig_spr_hm, use_container_width=True)
            else:
                st.caption("Not enough spreader strategy data across claim types.")

        with hm_col2:
            st.markdown(
                '<p class="sl-sub">Fact-checker tactics by claim type</p>',
                unsafe_allow_html=True,
            )
            fig_deb_hm = _build_side_heatmap(_deb_data, "Fact-checker × Claim Type", "Blues")
            if fig_deb_hm:
                st.plotly_chart(fig_deb_hm, use_container_width=True)
            else:
                st.caption("Not enough fact-checker strategy data across claim types.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 5 — RUN-LEVEL REPORT
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-section">Run-level strategy breakdown</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sl-prose">'
        'Strategy usage and win rates broken down by run. '
        'Useful for spotting whether a particular strategy was effective in one run '
        'but not another — which can indicate sensitivity to claim type or agent model.'
        '</p>',
        unsafe_allow_html=True,
    )

    if not run_report.empty:
        def _wr_style(val) -> str:
            try:
                v = float(val)
            except (TypeError, ValueError):
                return ""
            if v >= 65: return "background-color:rgba(22,163,74,0.13);color:#15803d;font-weight:600;"
            if v >= 45: return "background-color:rgba(234,179,8,0.12);color:#a16207;font-weight:600;"
            return "background-color:rgba(220,38,38,0.09);color:#b91c1c;font-weight:600;"

        disp = run_report.copy()
        disp["strategy_label"] = disp["strategy_label"].apply(_label)
        # Use run_label if available, fallback to run_id
        _run_col = "run_label" if "run_label" in disp.columns else "run_id"
        disp = disp.rename(columns={
            _run_col:          "Run",
            "strategy_label":  "Strategy",
            "strategy_count":  "Count",
            "wins":            "Wins",
            "win_rate":        "Win rate",
        })
        # Drop raw run_id if run_label was used
        if "run_id" in disp.columns and "Run" in disp.columns:
            disp = disp.drop(columns=["run_id"])

        styled = (
            disp.style
            .map(_wr_style, subset=["Win rate"])
            .format({"Win rate": lambda v: f"{v:.0f}%" if v == v else "—"})
        )
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Run":      st.column_config.TextColumn(width="small"),
                "Strategy": st.column_config.TextColumn(),
                "Count":    st.column_config.NumberColumn(width="small"),
                "Wins":     st.column_config.NumberColumn(width="small"),
                "Win rate": st.column_config.TextColumn(width="small"),
            },
        )
        if len(run_report) > 100:
            st.caption(f"Showing first 100 of {len(run_report)} rows.")
    else:
        st.caption("No run-level strategy data available.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6 — EMERGING PATTERNS
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-section">Part V: Emerging patterns — beyond the taxonomy</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sl-prose">'
        'The AI analyst is also asked to flag any notable tactics that don\'t fit the standard '
        '20-label taxonomy. These emergent observations are captured verbatim and tracked below. '
        'Labels appearing <b>3 or more times</b> are candidates for promotion into the taxonomy. '
        'This section will populate as more debates are run.'
        '</p>',
        unsafe_allow_html=True,
    )

    emergent_df = _load_emergent_df(tuple(run_ids), RUNS_DIR, token)

    if emergent_df.empty:
        st.info(
            "No emergent tactics detected yet. This section fills in as debates run — "
            "emergent capture is active in all new episodes."
        )
    else:
        # Aggregate: count occurrences per (side, label)
        freq = (
            emergent_df.groupby(["side", "label"])
            .agg(count=("label", "count"), description=("description", "first"))
            .reset_index()
            .sort_values("count", ascending=False)
        )

        # Candidates (≥3 appearances)
        candidates = freq[freq["count"] >= 3]

        if not candidates.empty:
            st.markdown(
                '<p class="sl-sub" style="color:#7c3aed;">Candidate tactics (≥ 3 observations)</p>',
                unsafe_allow_html=True,
            )
            for _, row in candidates.iterrows():
                side_color = SPREADER_COLOR if row["side"] == "spreader" else DEBUNKER_COLOR
                side_label = "Spreader" if row["side"] == "spreader" else "Fact-checker"
                st.markdown(
                    f'<div style="display:flex;align-items:flex-start;gap:0.75rem;'
                    f'padding:0.65rem 0.9rem;margin-bottom:0.5rem;'
                    f'background:rgba(124,58,237,0.04);border-left:3px solid {side_color};'
                    f'border-radius:0 6px 6px 0;">'
                    f'<div style="min-width:90px;font-size:0.72rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.06em;color:{side_color};'
                    f'padding-top:0.1rem;">{side_label}</div>'
                    f'<div style="flex:1;">'
                    f'<span style="font-weight:700;font-size:0.95rem;">'
                    f'{_label(row["label"])}</span>'
                    f'<span style="margin-left:0.6rem;font-size:0.8rem;color:#9ca3af;">'
                    f'× {int(row["count"])}</span>'
                    f'<div style="font-size:0.85rem;color:#4b5563;margin-top:0.2rem;">'
                    f'{row["description"]}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        # Full emergent table
        with st.expander(f"All emergent observations ({len(emergent_df)} total)", expanded=False):
            disp = emergent_df[["side", "label", "count" if "count" in emergent_df.columns else "side",
                                 "description", "run_id"]].copy()
            # Merge count in
            disp = emergent_df.merge(
                freq[["side", "label", "count"]], on=["side", "label"], how="left"
            )[["side", "label", "count", "description", "run_id", "episode_id"]]
            disp["label"] = disp["label"].apply(_label)
            disp["side"]  = disp["side"].str.title()
            disp = disp.rename(columns={
                "side": "Side", "label": "Tactic", "count": "Total seen",
                "description": "Description", "run_id": "Run", "episode_id": "Episode",
            })
            st.dataframe(disp.drop_duplicates(), use_container_width=True, hide_index=True)

    st.markdown(
        '<p class="sl-caption" style="margin-top:1.5rem;">'
        'Taxonomy labels are assigned by an AI analyst using a fixed 20-label taxonomy '
        '(10 spreader, 10 fact-checker). Emergent observations are captured separately '
        'and not filtered. Win rates should be interpreted cautiously when n &lt; 5. '
        'See the <b>Analytics</b> tab for strategy × outcome correlation across all episodes.'
        '</p>',
        unsafe_allow_html=True,
    )
