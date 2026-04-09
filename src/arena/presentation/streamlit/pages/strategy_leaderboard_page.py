"""
Strategy Analytics — descriptive strategy analysis from completed debates.

Shows what tactics agents use, how often, and how they vary by claim type.
Does NOT show per-strategy win rates (misleading when one side dominates).
Strategy × outcome analyses belong in Study Results (Phase 7).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.analysis.episode_dataset import build_strategy_long_df
from arena.analysis.research_analytics import (
    apply_strategy_filters,
    compute_strategy_leaderboard,
    compute_primary_strategy_performance,
)
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.styles import PLOTLY_LAYOUT

RUNS_DIR       = "runs"
SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"


def _label(s: str) -> str:
    return (s or "").replace("_", " ").title()


def _inject_styles() -> None:
    st.markdown("""
    <style>
    .sl-page-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem; font-weight: 700; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0; line-height: 1.2; text-align: center;
    }
    .sl-page-subtitle {
        font-size: 1rem; color: var(--color-text-muted, #888); margin: 0 0 1.5rem 0;
        text-align: center;
    }
    .sl-section {
        font-size: 1.35rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
        margin: 2.2rem 0 0.2rem 0; padding-bottom: 0.3rem;
        border-bottom: 2px solid var(--color-border, #2A2A2A);
    }
    .sl-prose {
        font-size: 0.94rem; color: var(--color-text-muted, #888); line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .sl-sub {
        font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; color: #9ca3af;
        border-bottom: 1px solid var(--color-border, #2A2A2A);
        padding-bottom: 0.25rem; margin: 1.2rem 0 0.6rem 0;
    }
    .sl-divider { border: none; border-top: 1px solid var(--color-border, #2A2A2A); margin: 2rem 0; }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load_strategy_df(run_ids: tuple, runs_dir: str, token: float) -> pd.DataFrame:
    return build_strategy_long_df(list(run_ids), runs_dir=runs_dir, refresh_token=token)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _freq_chart(freq_df: pd.DataFrame, color: str) -> go.Figure:
    df = freq_df.copy().sort_values("count", ascending=True)
    labels = [_label(s) for s in df["strategy_label"]]
    counts = df["count"].tolist()
    pcts = df["percent"].tolist() if "percent" in df.columns else [None] * len(counts)

    fig = go.Figure(go.Bar(
        y=labels, x=counts, orientation="h",
        marker_color=color, opacity=0.85,
        text=[f"{c}  ({p:.0f}%)" if p is not None else str(c) for c, p in zip(counts, pcts)],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="%{y}<br>Count: <b>%{x}</b><extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Episodes", tickfont=dict(size=10), gridcolor="#2A2A2A"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=10, b=35, l=10, r=80),
        height=max(220, len(labels) * 34 + 60),
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _primary_perf_chart(primary_df: pd.DataFrame) -> go.Figure:
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
            orientation="h", marker_color=color, opacity=0.85,
            text=[str(v) for v in df_side["primary_usage"]],
            textposition="outside", textfont=dict(size=10),
            hovertemplate="%{y}<br>Used as primary: <b>%{x}</b> times<extra>" + name + "</extra>",
        ))

    fig.update_layout(
        barmode="group",
        xaxis=dict(title="Used as primary strategy (episode count)",
                   gridcolor="#2A2A2A", tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=12)),
        margin=dict(t=10, b=70, l=10, r=60),
        height=max(280, len(primary_df["strategy_label"].unique()) * 22 + 100),
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


def _claim_heatmap(pivot_df: pd.DataFrame, colorscale: str) -> go.Figure:
    row_labels = [_label(idx) for idx in pivot_df.index]
    col_labels = [str(c) for c in pivot_df.columns]
    z = pivot_df.values.tolist()

    fig = go.Figure(go.Heatmap(
        z=z, x=col_labels, y=row_labels, colorscale=colorscale,
        hovertemplate="<b>%{y}</b> in <b>%{x}</b>: %{z} episodes<extra></extra>",
        colorbar=dict(title="Episodes", tickfont=dict(size=10)),
    ))
    fig.update_layout(
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
        margin=dict(t=10, b=100, l=10, r=10),
        height=max(350, len(row_labels) * 26 + 140),
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k in ("paper_bgcolor", "plot_bgcolor", "font")},
    )
    return fig


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_strategy_leaderboard_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    st.markdown('<p class="sl-page-title">Strategy Analytics</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-page-subtitle">'
        'What rhetorical tactics do agents use, and how do they vary by claim type? '
        'Every episode is labelled post-debate using a fixed taxonomy '
        'of 10 spreader and 10 fact-checker strategies.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Data loading ──────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No completed runs found yet. Run a debate in the Arena tab first.")
        return

    strategy_long_df = _load_strategy_df(tuple(run_ids), RUNS_DIR, token)

    if strategy_long_df.empty:
        st.info("No strategy analysis data yet. Complete a few debates to see results here.")
        return

    # ── Filters ───────────────────────────────────────────────────────────
    claim_type_opts = [x for x in strategy_long_df.get("claim_type", pd.Series()).dropna().unique()
                       if str(x) not in ("nan", "None")]

    if claim_type_opts:
        with st.expander("Filters", expanded=False):
            sel_claim_type = st.multiselect("Claim type", claim_type_opts, default=[], key="sl_claim_type")
        filtered = apply_strategy_filters(strategy_long_df, claim_types=sel_claim_type or None)
    else:
        filtered = strategy_long_df

    if filtered.empty:
        st.warning("No strategy data matches the current filters.")
        return

    # ── Pre-compute ───────────────────────────────────────────────────────
    lb = compute_strategy_leaderboard(filtered)
    primary_df = compute_primary_strategy_performance(filtered)

    spr_freq = lb.get("spreader_strategy_freq", pd.DataFrame())
    deb_freq = lb.get("debunker_strategy_freq", pd.DataFrame())

    # ── Overview cards ────────────────────────────────────────────────────
    ep_col = [c for c in ["run_id", "episode_index"] if c in filtered.columns]
    n_eps = filtered.drop_duplicates(subset=ep_col).shape[0] if ep_col else filtered.shape[0]

    top_spr = _label(spr_freq.iloc[0]["strategy_label"]) if not spr_freq.empty else "—"
    top_deb = _label(deb_freq.iloc[0]["strategy_label"]) if not deb_freq.empty else "—"

    # Average strategy diversity per episode
    ep_key_cols = [c for c in ["run_id", "episode_index", "side"] if c in filtered.columns]
    if ep_key_cols:
        diversity = filtered.groupby([c for c in ["run_id", "episode_index"] if c in filtered.columns])["strategy_label"].nunique()
        avg_diversity = f"{diversity.mean():.1f}" if len(diversity) > 0 else "—"
    else:
        avg_diversity = "—"

    def _card(label: str, value: str, sub: str = "", color: str = "#E8E4D9") -> str:
        return (
            f'<div style="flex:1;min-width:140px;background:var(--color-surface, #111);'
            f'border:1px solid var(--color-border, #2A2A2A);border-radius:10px;padding:0.85rem 1.1rem;">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.2rem;">{label}</div>'
            f'<div style="font-size:1.55rem;font-weight:700;color:{color};line-height:1.15;">{value}</div>'
            f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.15rem;">{sub}</div>'
            f'</div>'
        )

    cards_html = (
        '<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.5rem;">'
        + _card("Episodes analyzed", str(n_eps))
        + _card("Most-used spreader tactic", top_spr, "by episode count", SPREADER_COLOR)
        + _card("Most-used FC tactic", top_deb, "by episode count", DEBUNKER_COLOR)
        + _card("Avg strategies per episode", avg_diversity, "unique tactics detected")
        + '</div>'
    )
    st.markdown(cards_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 — STRATEGY FREQUENCY
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sl-section">How often does each strategy appear?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-prose">'
        'Frequency counts how many episodes featured a given strategy. '
        'This shows what each side\'s default tactical repertoire looks like — '
        'which tools they reach for most often.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_spr, col_deb = st.columns(2)
    with col_spr:
        st.markdown(f'<p class="sl-sub" style="color:{SPREADER_COLOR};">Spreader strategies</p>', unsafe_allow_html=True)
        if not spr_freq.empty:
            st.plotly_chart(_freq_chart(spr_freq, SPREADER_COLOR), use_container_width=True)
        else:
            st.caption("No spreader strategy data.")
    with col_deb:
        st.markdown(f'<p class="sl-sub" style="color:{DEBUNKER_COLOR};">Fact-checker strategies</p>', unsafe_allow_html=True)
        if not deb_freq.empty:
            st.plotly_chart(_freq_chart(deb_freq, DEBUNKER_COLOR), use_container_width=True)
        else:
            st.caption("No fact-checker strategy data.")

    # ── Primary strategy usage ────────────────────────────────────────────
    st.markdown('<hr class="sl-divider" style="margin:1.2rem 0;">', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-section">Which strategy is the go-to primary tactic?</p>'
        '<p class="sl-prose">'
        'The primary strategy is the single most dominant tactic the analyst flagged for each agent '
        'in a given episode. This shows which strategy each side leads with, '
        'not just what they use alongside other tactics.'
        '</p>',
        unsafe_allow_html=True,
    )
    if not primary_df.empty:
        st.plotly_chart(_primary_perf_chart(primary_df), use_container_width=True)
    else:
        st.caption("No primary strategy data.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 — STRATEGY × CLAIM TYPE
    # ══════════════════════════════════════════════════════════════════════
    has_ct = "claim_type" in filtered.columns and filtered["claim_type"].notna().any()

    if has_ct:
        st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
        st.markdown('<p class="sl-section">Does claim type affect strategy choice?</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sl-prose">'
            'Do agents adjust their tactics based on the claim domain? '
            'A strategy concentrated in one domain but absent from others suggests '
            'domain-specific rhetorical adaptation.'
            '</p>',
            unsafe_allow_html=True,
        )

        _spr_data = filtered[filtered["side"] == "spreader"].copy() if "side" in filtered.columns else pd.DataFrame()
        _deb_data = filtered[filtered["side"] == "debunker"].copy() if "side" in filtered.columns else pd.DataFrame()

        def _build_side_heatmap(side_df, colorscale):
            if side_df.empty or "claim_type" not in side_df.columns:
                return None
            side_df["claim_type"] = side_df["claim_type"].fillna("(unknown)").astype(str)
            agg = side_df.groupby(["strategy_label", "claim_type"], dropna=False).size().reset_index(name="count")
            pivot = agg.pivot_table(index="strategy_label", columns="claim_type", values="count", fill_value=0)
            if pivot.empty or pivot.size < 2:
                return None
            return _claim_heatmap(pivot, colorscale)

        hm_col1, hm_col2 = st.columns(2)
        with hm_col1:
            st.markdown('<p class="sl-sub">Spreader tactics by claim type</p>', unsafe_allow_html=True)
            fig = _build_side_heatmap(_spr_data, "Reds")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Not enough data across claim types.")
        with hm_col2:
            st.markdown('<p class="sl-sub">Fact-checker tactics by claim type</p>', unsafe_allow_html=True)
            fig = _build_side_heatmap(_deb_data, "Blues")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Not enough data across claim types.")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 — STRATEGY DRILLDOWN
    # ══════════════════════════════════════════════════════════════════════
    st.markdown('<hr class="sl-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sl-section">Strategy Drilldown</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sl-prose">'
        'Select a strategy to see which episodes used it, what claims were debated, '
        'and how the debate ended. Click through to Replay for full transcript details.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Build strategy options grouped by side
    all_strategies = sorted(filtered["strategy_label"].dropna().unique())
    spr_strategies = sorted(filtered[filtered["side"] == "spreader"]["strategy_label"].dropna().unique()) if "side" in filtered.columns else []
    deb_strategies = sorted(filtered[filtered["side"] == "debunker"]["strategy_label"].dropna().unique()) if "side" in filtered.columns else []

    side_pick = st.radio("Side", ["Spreader", "Fact-checker"], horizontal=True, key="sl_drill_side")
    strategy_list = spr_strategies if side_pick == "Spreader" else deb_strategies
    strategy_labels = [_label(s) for s in strategy_list]

    if not strategy_list:
        st.caption("No strategies available for this side.")
    else:
        selected_label = st.selectbox(
            "Strategy",
            options=strategy_labels,
            key="sl_drill_strategy",
        )
        # Map back to raw label
        selected_raw = strategy_list[strategy_labels.index(selected_label)] if selected_label in strategy_labels else None

        if selected_raw:
            side_key = "spreader" if side_pick == "Spreader" else "debunker"
            matches = filtered[
                (filtered["strategy_label"] == selected_raw) &
                (filtered["side"] == side_key)
            ].copy()

            if matches.empty:
                st.caption("No episodes found with this strategy.")
            else:
                # Deduplicate to one row per episode
                ep_cols = [c for c in ["run_id", "episode_id", "episode_index"] if c in matches.columns]
                episodes = matches.drop_duplicates(subset=ep_cols) if ep_cols else matches

                n_episodes = len(episodes)
                st.markdown(
                    f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
                    f'border-radius:8px;padding:0.8rem 1rem;margin-bottom:1rem;">'
                    f'<span style="font-weight:700;color:{"#D4A843" if side_key == "spreader" else "#4A7FA5"}">'
                    f'{selected_label}</span> appeared in '
                    f'<b>{n_episodes}</b> episode{"s" if n_episodes != 1 else ""}'
                    f'{" as primary tactic in " + str(int(episodes["is_primary"].sum())) + " of them" if "is_primary" in episodes.columns else ""}.'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Episode table
                display_cols = []
                col_map = {}
                for src, dst in [
                    ("claim", "Claim"), ("claim_type", "Type"),
                    ("winner", "Winner"), ("judge_confidence", "Confidence"),
                    ("margin", "Margin"), ("is_primary", "Primary"),
                    ("run_id", "Run ID"),
                ]:
                    if src in episodes.columns:
                        display_cols.append(src)
                        col_map[src] = dst

                if display_cols:
                    disp = episodes[display_cols].copy().rename(columns=col_map)
                    if "Claim" in disp.columns:
                        disp["Claim"] = disp["Claim"].apply(lambda x: (str(x)[:50] + "…") if len(str(x)) > 50 else str(x))
                    if "Winner" in disp.columns:
                        disp["Winner"] = disp["Winner"].str.title().str.replace("Debunker", "Fact-checker")
                    if "Confidence" in disp.columns:
                        disp["Confidence"] = disp["Confidence"].apply(lambda x: f"{x:.0%}" if pd.notna(x) else "—")
                    if "Margin" in disp.columns:
                        disp["Margin"] = disp["Margin"].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
                    if "Primary" in disp.columns:
                        disp["Primary"] = disp["Primary"].apply(lambda x: "Yes" if x else "")

                    st.dataframe(disp, use_container_width=True, hide_index=True)

                    # Replay link
                    if "run_id" in episodes.columns and "episode_id" in episodes.columns:
                        st.caption("To view a full transcript, note the Run ID and find it in the Replay tab.")

    st.markdown(
        '<p style="font-size:0.82rem;color:var(--color-text-muted,#888);line-height:1.5;'
        'margin-top:2rem;max-width:760px;">'
        'Strategy labels are assigned by an AI analyst using a fixed 20-label taxonomy '
        '(10 spreader, 10 fact-checker). Strategy data describes agent behavior — '
        'it does not predict outcomes. For strategy × outcome analysis, see Study Results.'
        '</p>',
        unsafe_allow_html=True,
    )
