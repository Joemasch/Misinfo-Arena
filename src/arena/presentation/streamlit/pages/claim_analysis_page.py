"""
Claim Analysis Page for Misinfo Arena v2.

Analyzes debate outcomes grouped by claim text. Works with or without
claim_type/domain/complexity metadata — uses claim text as the primary
grouping unit when metadata is absent.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.analysis.claim_analysis import build_claim_level_df, build_turn_sensitivity_df
from arena.analysis.episode_dataset import build_episode_df
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids

RUNS_DIR = "runs"

SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"

CLAIM_META_KEYS = ["claim_type", "claim_complexity",
                   "claim_verifiability", "claim_structure"]


# ── Cached data loader ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _get_cached_episode_df(
    selected_run_ids: tuple[str, ...], runs_dir: str, refresh_token: float
) -> pd.DataFrame:
    df, _ = build_episode_df(list(selected_run_ids), runs_dir=runs_dir, refresh_token=refresh_token)
    return df


# ── Helpers ─────────────────────────────────────────────────────────────────

def _safe_str(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "unknown"
    s = str(x).strip()
    return s if s else "unknown"


def _trunc(text: str, n: int = 55) -> str:
    """Truncate at a word boundary to avoid cutting mid-word."""
    s = str(text or "").strip()
    if len(s) <= n:
        return s
    # Find last space before n so we don't cut mid-word
    cut = s.rfind(" ", 0, n)
    if cut <= 0:
        cut = n
    return s[:cut].rstrip() + "…"


def _win_rate_color(rate: float) -> str:
    """Return a hex color on a red→yellow→green scale for a 0–1 win rate."""
    if rate >= 0.75: return "#16a34a"
    if rate >= 0.55: return "#84cc16"
    if rate >= 0.40: return "#eab308"
    return "#dc2626"


# ── Chart builders ──────────────────────────────────────────────────────────

def _outcome_stacked_bar(claim_df: pd.DataFrame, episode_df: pd.DataFrame) -> go.Figure:
    """Stacked bar: FC wins / Spreader wins / Draw per unique claim."""
    if claim_df.empty or "claim" not in claim_df.columns:
        return go.Figure()

    winners = (
        episode_df["winner"].fillna("").astype(str).str.strip().str.lower()
        if "winner" in episode_df.columns
        else pd.Series("", index=episode_df.index)
    )
    episode_df = episode_df.copy()
    episode_df["_winner"] = winners
    episode_df["_claim_trunc"] = episode_df["claim"].fillna("").astype(str).apply(lambda x: _trunc(x, 50))

    grp    = episode_df.groupby("_claim_trunc")["_winner"]
    labels = list(grp.groups.keys())
    fc     = [int((grp.get_group(k) == "debunker").sum()) for k in labels]
    spr    = [int((grp.get_group(k) == "spreader").sum()) for k in labels]
    draws  = [int((grp.get_group(k) == "draw").sum())    for k in labels]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Fact-checker won", x=labels, y=fc,
                         marker_color=DEBUNKER_COLOR, opacity=0.85))
    fig.add_trace(go.Bar(name="Spreader won",     x=labels, y=spr,
                         marker_color=SPREADER_COLOR, opacity=0.85))
    fig.add_trace(go.Bar(name="Draw",             x=labels, y=draws,
                         marker_color=DRAW_COLOR, opacity=0.85))
    fig.update_layout(
        barmode="stack",
        xaxis=dict(tickangle=-30, tickfont=dict(size=11)),
        yaxis=dict(title="Episodes", tickfont=dict(size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=40, b=80),
        height=340,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _win_rate_bar(claim_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: debunker win rate per claim, colored by rate."""
    if claim_df.empty:
        return go.Figure()
    df = claim_df.sort_values("debunker_win_rate", ascending=True)
    labels = [_trunc(str(c), 60) for c in df["claim"]]
    rates  = df["debunker_win_rate"].tolist()
    colors = [_win_rate_color(r) for r in rates]
    texts  = [f"{r:.0%}" for r in rates]

    fig = go.Figure(go.Bar(
        x=rates, y=labels, orientation="h",
        marker_color=colors,
        text=texts, textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>FC win rate: <b>%{x:.1%}</b><extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Fact-checker win rate", range=[0, 1.15],
                   tickformat=".0%", tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), automargin=True),
        height=max(200, len(labels) * 36 + 60),
        margin=dict(l=10, r=60, t=10, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    fig.add_vline(x=0.5, line_dash="dash", line_width=1,
                  line_color="rgba(0,0,0,0.2)",
                  annotation_text="50%", annotation_position="top right",
                  annotation_font_size=10)
    return fig


def _confidence_bar(claim_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: avg confidence per claim."""
    if claim_df.empty:
        return go.Figure()
    df = claim_df.sort_values("avg_confidence", ascending=True)
    labels = [_trunc(str(c), 60) for c in df["claim"]]
    vals   = df["avg_confidence"].tolist()
    texts  = [f"{v:.0%}" for v in vals]

    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color="rgba(107,114,128,0.6)",
        text=texts, textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Avg confidence: <b>%{x:.1%}</b><extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Average judge confidence", range=[0, 1.15],
                   tickformat=".0%", tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), automargin=True),
        height=max(200, len(labels) * 36 + 60),
        margin=dict(l=10, r=60, t=10, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def _type_heatmap(df: pd.DataFrame) -> go.Figure | None:
    """Claim type × complexity heatmap of debunker win rate."""
    df_hm = df.copy()
    df_hm["_ct"] = df_hm["claim_type"].apply(_safe_str) if "claim_type" in df_hm.columns else "unknown"
    df_hm["_cc"] = df_hm["claim_complexity"].apply(_safe_str) if "claim_complexity" in df_hm.columns else "unknown"
    winners = df_hm["winner"].fillna("").astype(str).str.strip().str.lower() if "winner" in df_hm.columns else pd.Series("", index=df_hm.index)
    df_hm["_deb"] = (winners == "debunker").astype(int)
    pivot = df_hm.groupby(["_ct", "_cc"])["_deb"].mean().unstack(fill_value=float("nan")).round(3)
    if pivot.empty or pivot.size < 2:
        return None
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale="RdYlGn", zmin=0, zmax=1,
        text=[[f"{v:.0%}" if v == v else "—" for v in row] for row in pivot.values],
        texttemplate="%{text}", textfont={"size": 12},
        hovertemplate="Type: %{y}<br>Complexity: %{x}<br>FC win rate: %{z:.1%}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Claim Complexity", yaxis_title="Claim Type",
        height=max(300, len(pivot.index) * 45 + 100),
        margin=dict(l=10, r=10, t=10, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ── Page ─────────────────────────────────────────────────────────────────────

def render_claim_analysis_page():
    st.markdown("## Claim Analysis")
    st.markdown(
        '<p style="color:#6b7280;margin-top:-0.5rem;margin-bottom:1.5rem;">'
        "How debate outcomes vary across different claims — "
        "grouped by claim text, with additional breakdowns when claim metadata is available.</p>",
        unsafe_allow_html=True,
    )

    # ── Load data ────────────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    refresh_token    = st.session_state["runs_refresh_token"]
    selected_run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=refresh_token, limit=None)

    if not selected_run_ids:
        st.info("No completed runs found yet. Run a debate to generate results.")
        return

    try:
        df = _get_cached_episode_df(tuple(selected_run_ids), RUNS_DIR, refresh_token)
    except Exception as e:
        st.error(f"Failed to load episode data: {e}")
        return

    if df.empty:
        st.info("No episodes found. Run some debates to generate results.")
        return

    # ── Build claim-level summary (works with or without metadata) ───────────
    claim_df = build_claim_level_df(df)
    has_metadata = (
        "claim_type" in df.columns
        and df["claim_type"].notna().any()
        and (df["claim_type"].astype(str).str.strip() != "").any()
    )

    winners_col = (
        df["winner"].fillna("").astype(str).str.strip().str.lower()
        if "winner" in df.columns
        else pd.Series("", index=df.index)
    )
    n_total     = len(df)
    n_fc        = int((winners_col == "debunker").sum())
    n_spr       = int((winners_col == "spreader").sum())
    n_draw      = int((winners_col == "draw").sum())
    fc_rate     = n_fc / n_total if n_total else 0
    conf_vals   = pd.to_numeric(df.get("judge_confidence", pd.Series(dtype=float)), errors="coerce")
    avg_conf    = float(conf_vals.mean()) if conf_vals.notna().any() else None
    n_claims    = len(claim_df)

    # ── Overview metrics ─────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Episodes", n_total)
    c2.metric("Unique Claims", n_claims)
    c3.metric("FC Win Rate", f"{fc_rate:.0%}")
    c4.metric("Avg Confidence", f"{avg_conf:.0%}" if avg_conf is not None else "—")
    c5.metric("Has Metadata", "Yes" if has_metadata else "No")

    if not has_metadata:
        st.info(
            "**No claim metadata found in these episodes.** "
            "Analysis below is grouped by claim text. "
            "Claim metadata (type, domain, complexity) is auto-enriched when the claim metadata "
            "enrichment step runs after each debate — it requires a connected OpenAI key and "
            "may not have run for older episodes."
        )

    st.markdown("---")

    # ── Section 1: Claim performance table ──────────────────────────────────
    st.markdown("### Claim Performance")
    st.markdown(
        '<p style="font-size:0.88rem;color:#6b7280;margin-top:-0.5rem;margin-bottom:0.75rem;">'
        "One row per unique claim. Sorted by difficulty — claims the fact-checker struggled with most appear first. "
        "Difficulty = low win rate + low confidence + high error rate.</p>",
        unsafe_allow_html=True,
    )

    if not claim_df.empty:
        disp = claim_df.copy()
        disp["claim_short"] = disp["claim"].apply(lambda x: _trunc(str(x), 70))
        disp["fc_win_rate"] = disp["debunker_win_rate"].map(lambda v: f"{v:.0%}")
        disp["confidence"]  = disp["avg_confidence"].map(lambda v: f"{v:.0%}")
        disp["difficulty"]  = disp["difficulty_index"].map(lambda v: f"{v:.2f}")

        table_cols = ["claim_short"]
        rename_map = {
            "claim_short": "Claim",
            "episodes":    "Episodes",
            "fc_win_rate": "FC Win Rate",
            "confidence":  "Avg Confidence",
            "difficulty":  "Difficulty ↑",
        }
        if has_metadata:
            for col in ["claim_type", "claim_complexity"]:
                if col in disp.columns:
                    table_cols.append(col)
                    rename_map[col] = col.replace("claim_", "").replace("_", " ").title()
        table_cols += ["episodes", "fc_win_rate", "confidence", "difficulty"]

        disp_sorted = disp.sort_values("difficulty_index", ascending=False)
        st.dataframe(
            disp_sorted[table_cols].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Not enough claim data to compute summary.")

    st.markdown("---")

    # ── Section 2: Outcome breakdown ─────────────────────────────────────────
    st.markdown("### Outcome Breakdown by Claim")
    st.markdown(
        '<p style="font-size:0.88rem;color:#6b7280;margin-top:-0.5rem;margin-bottom:0.75rem;">'
        "How many times each claim ended with the fact-checker winning, spreader winning, or a draw.</p>",
        unsafe_allow_html=True,
    )
    if not claim_df.empty and n_total > 0:
        fig_stacked = _outcome_stacked_bar(claim_df, df)
        st.plotly_chart(fig_stacked, use_container_width=True)
    else:
        st.caption("No outcome data available.")

    st.markdown("---")

    # ── Section 3: Win rate & confidence charts ──────────────────────────────
    if not claim_df.empty and len(claim_df) > 1:
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Fact-checker Win Rate")
            st.markdown(
                '<p style="font-size:0.85rem;color:#6b7280;margin-top:-0.4rem;">50% dashed line = coin flip.</p>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(_win_rate_bar(claim_df), use_container_width=True)
        with col_r:
            st.markdown("### Average Judge Confidence")
            st.markdown(
                '<p style="font-size:0.85rem;color:#6b7280;margin-top:-0.4rem;">Higher confidence = more decisive result.</p>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(_confidence_bar(claim_df), use_container_width=True)
        st.markdown("---")

    # ── Section 4: Metadata analysis (only when metadata exists) ─────────────
    if has_metadata:
        st.markdown("### Breakdown by Claim Type")

        def _group_table(col: str) -> pd.DataFrame:
            if col not in df.columns:
                return pd.DataFrame()
            s = df[col].apply(_safe_str)
            counts = s.value_counts()
            tab = pd.DataFrame({col: counts.index, "episodes": counts.values})
            tab["pct"] = (tab["episodes"] / tab["episodes"].sum() * 100).round(1)
            # Win rates per group
            win_map = (
                df.assign(_g=s, _w=(winners_col == "debunker").astype(int))
                .groupby("_g")["_w"].mean().round(3)
            )
            tab["fc_win_rate"] = tab[col].map(win_map).map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
            return tab.sort_values("episodes", ascending=False)

        meta_tabs = st.tabs(["By Type", "By Complexity"])
        for tab_ui, col, label in zip(
            meta_tabs,
            ["claim_type", "claim_complexity"],
            ["Claim Type", "Claim Complexity"],
        ):
            with tab_ui:
                tab_df = _group_table(col)
                if not tab_df.empty:
                    st.dataframe(
                        tab_df.rename(columns={col: label, "episodes": "Episodes",
                                                "pct": "% of total", "fc_win_rate": "FC Win Rate"}),
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.caption(
                        f"No {label.lower()} data in the current episodes. "
                        "This field is populated by the auto-enrichment step that runs "
                        "after each debate. Older episodes may not have this data yet."
                    )

        st.markdown("---")

    # ── Section 5: Turn sensitivity ──────────────────────────────────────────
    turn_df = build_turn_sensitivity_df(df)
    if not turn_df.empty and len(turn_df) > 1:
        st.markdown("### Debate Length vs Outcome")
        st.markdown(
            '<p style="font-size:0.88rem;color:#6b7280;margin-top:-0.5rem;margin-bottom:0.75rem;">'
            "Does giving debates more turns help the fact-checker? "
            "Each row is a distinct planned turn limit.</p>",
            unsafe_allow_html=True,
        )

        # ── Model filter for turn sensitivity ───────────────────────────────
        st.markdown("**Filter by model**")
        _ts_models_spr = sorted(df["model_spreader"].dropna().unique().tolist()) if "model_spreader" in df.columns else []
        _ts_models_deb = sorted(df["model_debunker"].dropna().unique().tolist()) if "model_debunker" in df.columns else []

        _ts_c1, _ts_c2 = st.columns(2)
        with _ts_c1:
            _ts_spr = st.selectbox("Spreader", ["All"] + _ts_models_spr, key="ts_spr_model")
        with _ts_c2:
            _ts_deb = st.selectbox("Fact-checker", ["All"] + _ts_models_deb, key="ts_deb_model")

        _ts_df = df.copy()
        if _ts_spr != "All" and "model_spreader" in _ts_df.columns:
            _ts_df = _ts_df[_ts_df["model_spreader"] == _ts_spr]
        if _ts_deb != "All" and "model_debunker" in _ts_df.columns:
            _ts_df = _ts_df[_ts_df["model_debunker"] == _ts_deb]

        turn_df = build_turn_sensitivity_df(_ts_df)
        if turn_df.empty or len(turn_df) < 1:
            st.info("No episodes match the selected model filter.")
        else:
            disp_turn = turn_df.copy()
            disp_turn["debunker_win_rate"] = disp_turn["debunker_win_rate"].map(lambda v: f"{v:.0%}")
            disp_turn["avg_confidence"]    = disp_turn["avg_confidence"].map(lambda v: f"{v:.0%}")
            disp_turn["avg_margin"]        = disp_turn["avg_margin"].map(lambda v: f"{v:.2f}")
            st.dataframe(
                disp_turn.rename(columns={
                    "planned_max_turns": "Max Turns",
                    "episodes":          "Episodes",
                    "debunker_win_rate": "FC Win Rate",
                    "avg_confidence":    "Avg Confidence",
                    "avg_margin":        "Avg Margin",
                }),
                use_container_width=True, hide_index=True,
            )

        # ── Score margin vs turn count chart ────────────────────────────────
        if "planned_max_turns" in _ts_df.columns and _ts_df["planned_max_turns"].nunique() >= 2:
            st.markdown(
                '<p style="font-size:0.88rem;color:#6b7280;margin-top:0.5rem;margin-bottom:0.75rem;">'
                "How the average score margin and persuasion score change as debates get longer.</p>",
                unsafe_allow_html=True,
            )
            _margin_col = pd.to_numeric(_ts_df.get("abs_margin", pd.Series(dtype=float)), errors="coerce")
            _turn_col = pd.to_numeric(_ts_df["planned_max_turns"], errors="coerce")
            _chart_df = pd.DataFrame({"planned_max_turns": _turn_col, "abs_margin": _margin_col}).dropna()

            has_persuasion = "metric_persuasion_spreader" in _ts_df.columns
            if has_persuasion:
                _chart_df["persuasion_spreader"] = pd.to_numeric(
                    _ts_df.get("metric_persuasion_spreader", pd.Series(dtype=float)), errors="coerce"
                )

            _chart_agg = _chart_df.groupby("planned_max_turns", dropna=True).mean(numeric_only=True).reset_index()
            _chart_agg = _chart_agg.sort_values("planned_max_turns")

            if len(_chart_agg) >= 2:
                from plotly.subplots import make_subplots

                fig_turn = make_subplots(specs=[[{"secondary_y": has_persuasion}]])
                fig_turn.add_trace(
                    go.Scatter(
                        x=_chart_agg["planned_max_turns"],
                        y=_chart_agg["abs_margin"],
                        name="Avg score margin",
                        mode="lines+markers",
                        line=dict(color=DEBUNKER_COLOR, width=2),
                        marker=dict(size=8),
                        hovertemplate="Turns: %{x}<br>Avg margin: %{y:.2f}<extra></extra>",
                    ),
                    secondary_y=False,
                )
                if has_persuasion and "persuasion_spreader" in _chart_agg.columns and _chart_agg["persuasion_spreader"].notna().any():
                    fig_turn.add_trace(
                        go.Scatter(
                            x=_chart_agg["planned_max_turns"],
                            y=_chart_agg["persuasion_spreader"],
                            name="Avg spreader persuasion",
                            mode="lines+markers",
                            line=dict(color=SPREADER_COLOR, width=2, dash="dot"),
                            marker=dict(size=8),
                            hovertemplate="Turns: %{x}<br>Persuasion: %{y:.1f}<extra></extra>",
                        ),
                        secondary_y=True,
                    )
                    fig_turn.update_yaxes(title_text="Persuasion score (0-10)", secondary_y=True,
                                          tickfont=dict(size=11), range=[0, 10])

                fig_turn.update_xaxes(title_text="Planned max turns", tickfont=dict(size=11),
                                      dtick=1)
                fig_turn.update_yaxes(title_text="Average score margin", secondary_y=False,
                                      tickfont=dict(size=11))
                fig_turn.update_layout(
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    margin=dict(l=10, r=10, t=40, b=40),
                    height=340,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_turn, use_container_width=True)

        st.markdown("---")

    # ── Section 5b: Claim consistency ────────────────────────────────────────
    if not df.empty and "claim" in df.columns:
        _claims_norm = df["claim"].fillna("").astype(str).str.strip()
        _claim_counts = _claims_norm.value_counts()
        _multi_claims = _claim_counts[_claim_counts >= 2].index.tolist()

        if _multi_claims:
            st.markdown("### Outcome Consistency")
            st.markdown(
                '<p style="font-size:0.88rem;color:#6b7280;margin-top:-0.5rem;margin-bottom:0.75rem;">'
                "When the same claim is debated under different conditions (different models, "
                "turn counts), do the outcomes stay consistent? Claims with mixed results are "
                "the most interesting — they reveal where the outcome depends on the model or "
                "debate length rather than the claim itself.</p>",
                unsafe_allow_html=True,
            )

            _consist_rows = []
            _winners_lower = (
                df["winner"].fillna("").astype(str).str.strip().str.lower()
                if "winner" in df.columns
                else pd.Series("", index=df.index)
            )
            _conf_numeric = pd.to_numeric(
                df.get("judge_confidence", pd.Series(dtype=float)), errors="coerce"
            )
            _margin_numeric = pd.to_numeric(
                df.get("abs_margin", pd.Series(dtype=float)), errors="coerce"
            )

            for claim_text in _multi_claims:
                _mask = _claims_norm == claim_text
                _ep_count = int(_mask.sum())
                _w = _winners_lower[_mask]
                _fc_wins = int((_w == "debunker").sum())
                _spr_wins = int((_w == "spreader").sum())
                _draws = _ep_count - _fc_wins - _spr_wins
                _fc_rate_val = _fc_wins / _ep_count if _ep_count else 0.0
                _unique_winners = _w[_w != ""].nunique()
                _conf_std = float(_conf_numeric[_mask].std()) if _conf_numeric[_mask].notna().sum() >= 2 else 0.0
                _avg_margin = float(_margin_numeric[_mask].mean()) if _margin_numeric[_mask].notna().any() else 0.0

                # Models used
                _models = set()
                if "model_spreader" in df.columns:
                    _models.update(df.loc[_mask, "model_spreader"].dropna().unique())
                if "model_debunker" in df.columns:
                    _models.update(df.loc[_mask, "model_debunker"].dropna().unique())

                # Consistency label
                if _unique_winners <= 1:
                    _label = "Consistent"
                elif _unique_winners == 2 and _draws == 0:
                    _label = "Mixed"
                else:
                    _label = "Highly variable"

                _consist_rows.append({
                    "Claim": _trunc(claim_text, 55),
                    "Episodes": _ep_count,
                    "FC Wins": _fc_wins,
                    "Spr Wins": _spr_wins,
                    "Draws": _draws,
                    "FC Win %": f"{_fc_rate_val:.0%}",
                    "Avg Margin": f"{_avg_margin:.2f}",
                    "Consistency": _label,
                    "Models": len(_models),
                })

            _consist_df = pd.DataFrame(_consist_rows)
            # Sort: most variable first
            _sort_order = {"Highly variable": 0, "Mixed": 1, "Consistent": 2}
            _consist_df["_sort"] = _consist_df["Consistency"].map(_sort_order)
            _consist_df = _consist_df.sort_values("_sort").drop(columns=["_sort"])

            def _consistency_color(val):
                if val == "Highly variable":
                    return "background-color: rgba(232,82,74,0.12); color: #b91c1c; font-weight: 600;"
                if val == "Mixed":
                    return "background-color: rgba(240,165,0,0.12); color: #92650a; font-weight: 600;"
                return "background-color: rgba(34,197,94,0.10); color: #166534; font-weight: 600;"

            styled = _consist_df.style.map(_consistency_color, subset=["Consistency"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.markdown(
                '<p style="font-size:0.82rem;color:#666;margin-top:0.3rem">'
                '<b>Consistent</b> = same winner every time. '
                '<b>Mixed</b> = 2 different winners. '
                '<b>Highly variable</b> = all 3 outcomes appeared. '
                'Variable claims are where model choice or debate length matters most.'
                '</p>',
                unsafe_allow_html=True,
            )
            st.markdown("---")

    # ── Section 6: Episode explorer with replay links ─────────────────────────
    st.markdown("### Episode Explorer")
    st.markdown(
        '<p style="font-size:0.88rem;color:#6b7280;margin-top:-0.5rem;margin-bottom:0.75rem;">'
        "Filter episodes by claim, outcome, or model to find specific debates. "
        "Select an episode to jump to its full transcript in the Replay tab.</p>",
        unsafe_allow_html=True,
    )

    df_f = df.copy()
    df_f["_winner"] = winners_col

    all_claims = sorted(df_f["claim"].fillna("").astype(str).str.strip().unique().tolist())
    all_claims = [c for c in all_claims if c]
    claim_display = ["All claims"] + [_trunc(c, 90) for c in all_claims]
    claim_full_map = {_trunc(c, 90): c for c in all_claims}

    _n_filter_cols = 2
    if has_metadata:
        _n_filter_cols = 3
    if "model_spreader" in df_f.columns:
        _n_filter_cols += 1

    filter_cols = st.columns(_n_filter_cols)
    _fc_idx = 0
    with filter_cols[_fc_idx]:
        sel_claim = st.selectbox("Claim", claim_display, key="ca_claim_sel")
    _fc_idx += 1
    with filter_cols[_fc_idx]:
        sel_win = st.selectbox("Outcome", ["All", "FC Won", "Spreader Won", "Draw"], key="ca_winner_sel")
    _fc_idx += 1

    if has_metadata:
        ct_opts = ["All"] + sorted(df_f["claim_type"].dropna().astype(str).unique().tolist()) if "claim_type" in df_f.columns else ["All"]
        with filter_cols[_fc_idx]:
            sel_ct = st.selectbox("Claim Type", ct_opts, key="ca_type_sel")
        _fc_idx += 1
    else:
        sel_ct = "All"

    if "model_spreader" in df_f.columns and _fc_idx < len(filter_cols):
        _model_opts = ["All"] + sorted(df_f["model_spreader"].dropna().unique().tolist())
        with filter_cols[_fc_idx]:
            sel_model = st.selectbox("Spreader model", _model_opts, key="ca_model_sel")
    else:
        sel_model = "All"

    mask = pd.Series(True, index=df_f.index)
    if sel_claim != "All claims":
        full_claim = claim_full_map.get(sel_claim, sel_claim)
        mask &= df_f["claim"].fillna("").astype(str).str.strip() == full_claim
    if sel_win == "FC Won":
        mask &= df_f["_winner"] == "debunker"
    elif sel_win == "Spreader Won":
        mask &= df_f["_winner"] == "spreader"
    elif sel_win == "Draw":
        mask &= df_f["_winner"] == "draw"
    if sel_ct != "All" and "claim_type" in df_f.columns:
        mask &= df_f["claim_type"].fillna("").astype(str) == sel_ct
    if sel_model != "All" and "model_spreader" in df_f.columns:
        mask &= df_f["model_spreader"].fillna("").astype(str) == sel_model

    drill = df_f[mask].copy()
    keep_cols = [c for c in [
        "run_label", "episode_id", "winner", "judge_confidence",
        "abs_margin", "planned_max_turns", "model_spreader", "model_debunker",
        "claim_type", "end_trigger",
    ] if c in drill.columns]
    drill = drill[keep_cols].sort_values(
        "judge_confidence" if "judge_confidence" in drill.columns else keep_cols[0],
        ascending=False, na_position="last",
    )

    st.caption(f"{len(drill)} episode{'s' if len(drill) != 1 else ''} match.")
    st.dataframe(drill.head(50), use_container_width=True, hide_index=True)

    # Jump to replay
    if not drill.empty and "run_id" in df_f.columns:
        _ep_options = []
        for _, row in drill.head(50).iterrows():
            _orig = df_f[(df_f["run_label"] == row.get("run_label")) & (df_f["episode_id"] == row.get("episode_id"))]
            if not _orig.empty:
                _rid = str(_orig.iloc[0].get("run_id", ""))
                _eid = str(row.get("episode_id", ""))
                _winner = str(row.get("winner", "")).title()
                _claim = str(drill.iloc[0].get("run_label", ""))[:40] if "run_label" in drill.columns else ""
                _ep_options.append((f"{_claim} — Ep {_eid} — {_winner}", _rid, _eid))

        if _ep_options:
            sel_ep = st.selectbox(
                "Select episode to replay",
                range(len(_ep_options)),
                format_func=lambda i: _ep_options[i][0],
                key="ca_replay_select",
            )
            if st.button("Open in Replay", key="ca_replay_btn"):
                _, _rid, _eid = _ep_options[sel_ep]
                st.session_state["replay_target_run_id"] = _rid
                st.session_state["replay_target_episode_id"] = _eid
                st.session_state["replay_target_source"] = "claim_analysis"
                st.info("Switch to the **Replay** tab to view this episode.")

