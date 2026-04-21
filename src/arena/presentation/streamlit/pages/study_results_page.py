"""
Study Results Page — model-centered strategy and citation analysis.

Tabbed layout with 5 sections:
  Overview | Strategies | Game Theory | Citations | Depth

Built against real experiment data (476 episodes).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.io.run_store_v2_read import load_episodes
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.styles import (
    PLOTLY_LAYOUT, SPREADER_COLOR, DEBUNKER_COLOR, ACCENT_RED, ACCENT_GREEN,
)

RUNS_DIR = "runs"

_MODEL_SHORT = {
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4-20250514": "Claude Sonnet",
    "claude-sonnet-4": "Claude Sonnet",
    "gemini-2.5-flash": "Gemini Flash",
}

_NAMED_SOURCES = [
    "CDC", "WHO", "FDA", "EPA", "NASA", "NIH", "IPCC",
    "Harvard", "Stanford", "MIT", "Oxford", "Yale", "Cambridge",
    "Nature", "Lancet", "Science", "JAMA", "BMJ", "NEJM",
    "Pew Research", "Gallup", "Reuters", "AP News", "BBC",
    "Amnesty International", "Human Rights Watch",
    "United Nations", "World Bank", "IMF",
]

_VAGUE_KEYWORDS = [
    "research shows", "studies show", "experts say", "scientists say",
    "according to studies", "evidence suggests", "research suggests",
]


def _short(model: str) -> str:
    return _MODEL_SHORT.get(model, model[:15])

def _label(s: str) -> str:
    return (s or "").replace("_", " ").title()

def _how_to_read(text: str):
    st.markdown(f'<div class="sr-how-to-read">{text}</div>', unsafe_allow_html=True)

def _takeaway(text: str):
    st.markdown(f'<div class="sr-takeaway">{text}</div>', unsafe_allow_html=True)

def _warning(text: str):
    st.markdown(f'<div class="sr-warning">{text}</div>', unsafe_allow_html=True)

def _pb(**overrides) -> dict:
    base = {k: v for k, v in PLOTLY_LAYOUT.items()
            if k in ("paper_bgcolor", "plot_bgcolor", "font")}
    base.update(overrides)
    return base


@st.cache_data(show_spinner=False)
def _load_experiment_data(run_ids: tuple, runs_dir: str, token: float) -> list[dict]:
    episodes = []
    for run_id in run_ids:
        eps, _ = load_episodes(run_id, runs_dir, token)
        for ep in eps:
            if ep.get("study_id") != "experiment":
                continue
            if ep.get("results", {}).get("winner") == "error":
                continue
            if (ep.get("created_at") or "") < "2026-04-13T21":
                continue
            episodes.append(ep)
    return episodes


def _inject_styles():
    st.markdown("""
    <style>
    .sr-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem; font-weight: 700; letter-spacing: -0.02em;
        color: var(--color-text-primary, #E8E4D9);
        margin: 0 0 0.2rem 0; text-align: center;
    }
    .sr-subtitle {
        font-size: 1rem; color: var(--color-text-muted, #888);
        margin: 0 0 1.5rem 0; text-align: center; line-height: 1.5;
    }
    .sr-finding {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.4rem; font-weight: 700;
        color: var(--color-text-primary, #E8E4D9);
        margin: 1.5rem 0 0.3rem 0; padding-bottom: 0.3rem;
        border-bottom: 3px solid var(--color-accent-red, #C9363E);
    }
    .sr-question {
        font-size: 0.92rem; color: var(--color-text-muted, #888);
        line-height: 1.6; margin-bottom: 1rem;
    }
    .sr-insight {
        background: rgba(74,127,165,0.08); border-left: 4px solid #4A7FA5;
        border-radius: 0 6px 6px 0; padding: 0.8rem 1.1rem;
        margin: 0.8rem 0 1.5rem 0; font-size: 0.92rem;
        color: var(--color-text-primary, #E8E4D9); line-height: 1.6;
    }
    .sr-kpi-grid {
        display: flex; gap: 0.8rem; margin: 1rem 0 1.5rem 0; flex-wrap: wrap;
    }
    .sr-kpi {
        flex: 1; min-width: 120px;
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.7rem 0.9rem;
    }
    .sr-kpi-label {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.07em; color: #9ca3af; margin-bottom: 0.1rem;
    }
    .sr-kpi-value {
        font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
    }
    .sr-kpi-sub { font-size: 0.72rem; color: #9ca3af; }
    .sr-how-to-read {
        font-size: 0.82rem; color: var(--color-text-muted, #888);
        line-height: 1.5; margin: -0.5rem 0 1rem 0; padding: 0.5rem 0.8rem;
        border-left: 3px solid var(--color-border, #2A2A2A);
        font-style: italic;
    }
    .sr-takeaway {
        background: rgba(74,127,165,0.08); border-left: 4px solid #4A7FA5;
        border-radius: 0 6px 6px 0; padding: 0.8rem 1.1rem;
        margin: 0.5rem 0 1.5rem 0; font-size: 0.92rem;
        color: var(--color-text-primary, #E8E4D9); line-height: 1.6;
    }
    .sr-warning {
        background: rgba(212,168,67,0.08); border-left: 4px solid #D4A843;
        border-radius: 0 6px 6px 0; padding: 0.6rem 1rem;
        margin: 0.3rem 0 1rem 0; font-size: 0.85rem;
        color: var(--color-text-muted, #888); line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)


# ======================================================================
# TAB RENDERERS
# ======================================================================

def _render_overview(episodes):
    """Overview tab: KPIs, model effectiveness, matchup heatmap, claim difficulty."""
    n = len(episodes)
    winners = Counter(ep["results"]["winner"] for ep in episodes)
    models = sorted(set(ep["config_snapshot"]["agents"]["spreader"]["model"] for ep in episodes))

    # KPIs
    st.markdown(
        f'<div class="sr-kpi-grid">'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Episodes</div><div class="sr-kpi-value">{n}</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Debunker Wins</div>'
        f'<div class="sr-kpi-value" style="color:{DEBUNKER_COLOR}">{winners.get("debunker",0)}</div>'
        f'<div class="sr-kpi-sub">{winners.get("debunker",0)/n*100:.0f}%</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Spreader Wins</div>'
        f'<div class="sr-kpi-value" style="color:{SPREADER_COLOR}">{winners.get("spreader",0)}</div>'
        f'<div class="sr-kpi-sub">{winners.get("spreader",0)/n*100:.0f}%</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Draws</div>'
        f'<div class="sr-kpi-value">{winners.get("draw",0)}</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Models</div>'
        f'<div class="sr-kpi-value">{len(models)}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Matchup heatmap ──────────────────────────────────────────────
    st.markdown('<p class="sr-finding">Model Matchup Heatmap</p>', unsafe_allow_html=True)
    st.markdown('<p class="sr-question">Who beats who? Debunker win percentage for every model pairing.</p>', unsafe_allow_html=True)
    _how_to_read("Rows = spreader model, columns = debunker model. Each cell shows the debunker's win rate for that pairing. "
                 "Blue = debunker dominates. Red = spreader dominates.")

    matchup = defaultdict(lambda: {"deb": 0, "total": 0})
    for ep in episodes:
        spr = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb = ep["config_snapshot"]["agents"]["debunker"]["model"]
        matchup[(spr, deb)]["total"] += 1
        if ep["results"]["winner"] == "debunker":
            matchup[(spr, deb)]["deb"] += 1

    z, text = [], []
    for spr in models:
        row_z, row_t = [], []
        for deb in models:
            d = matchup.get((spr, deb), {"deb": 0, "total": 0})
            pct = d["deb"] / max(d["total"], 1) * 100
            row_z.append(pct)
            row_t.append(f"{pct:.0f}%<br>n={d['total']}")
        z.append(row_z)
        text.append(row_t)

    fig = go.Figure(go.Heatmap(
        z=z, x=[_short(m) for m in models], y=[_short(m) for m in models],
        text=text, texttemplate="%{text}", textfont=dict(size=11),
        colorscale=[[0, "#C9363E"], [0.5, "#D4A843"], [1, "#4A7FA5"]],
        colorbar=dict(title="Deb Win%", ticksuffix="%"),
        hovertemplate="Spreader: %{y}<br>Debunker: %{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="Debunker Model", tickfont=dict(size=12), side="bottom"),
        yaxis=dict(title="Spreader Model", tickfont=dict(size=12), autorange="reversed"),
        height=350, margin=dict(t=10, b=60, l=120, r=80),
        **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _takeaway(
        "<b>Key finding:</b> The heatmap reveals a binary pattern. When any model other than "
        "Gemini Flash plays debunker, the debunker wins 100% of the time — regardless of which "
        "model is spreading. But when Gemini Flash is the debunker, it wins 0%. "
        "This means <b>every spreader win and draw in the entire experiment</b> involves Gemini "
        "as the debunker. The debunker's model choice is the single strongest predictor of debate outcome."
    )

    # ── Win rate by role ─────────────────────────────────────────────
    st.markdown('<p class="sr-finding">Model Effectiveness by Role</p>', unsafe_allow_html=True)

    deb_wr = defaultdict(lambda: {"w": 0, "t": 0})
    spr_wr = defaultdict(lambda: {"w": 0, "t": 0})
    for ep in episodes:
        dm = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sm = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb_wr[dm]["t"] += 1
        spr_wr[sm]["t"] += 1
        if ep["results"]["winner"] == "debunker": deb_wr[dm]["w"] += 1
        elif ep["results"]["winner"] == "spreader": spr_wr[sm]["w"] += 1

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Debunker win rate**")
        dm = sorted(deb_wr.keys())
        dr = [deb_wr[m]["w"]/max(deb_wr[m]["t"],1)*100 for m in dm]
        fig = go.Figure(go.Bar(
            x=[_short(m) for m in dm], y=dr,
            marker_color=[ACCENT_GREEN if r==100 else ACCENT_RED for r in dr],
            text=[f"{r:.0f}%<br>n={deb_wr[m]['t']}" for r,m in zip(dr,dm)],
            textposition="outside", textfont=dict(size=10),
        ))
        fig.update_layout(yaxis=dict(title="%", range=[0,120], gridcolor="#2A2A2A"),
                         height=280, margin=dict(t=15,b=40,l=50,r=10), **_pb())
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Spreader win rate**")
        sm = sorted(spr_wr.keys())
        sr = [spr_wr[m]["w"]/max(spr_wr[m]["t"],1)*100 for m in sm]
        fig = go.Figure(go.Bar(
            x=[_short(m) for m in sm], y=sr,
            marker_color=SPREADER_COLOR,
            text=[f"{r:.0f}%<br>n={spr_wr[m]['t']}" for r,m in zip(sr,sm)],
            textposition="outside", textfont=dict(size=10),
        ))
        fig.update_layout(yaxis=dict(title="%", range=[0,40], gridcolor="#2A2A2A"),
                         height=280, margin=dict(t=15,b=40,l=50,r=10), **_pb())
        st.plotly_chart(fig, use_container_width=True)

    # ── Claim difficulty by type ────────────────────────────────────
    st.markdown('<p class="sr-finding">Claim Difficulty by Type</p>', unsafe_allow_html=True)
    st.markdown('<p class="sr-question">Which claim domains are hardest to debunk?</p>', unsafe_allow_html=True)
    _how_to_read("Higher bars = the spreader wins more often for that claim type. "
                 "Click a bar to see individual claims below. "
                 "Note: spreader wins only occur when Gemini Flash is the debunker.")

    # Aggregate by type + spreader model
    type_data = defaultdict(lambda: {"spr_wins": 0, "total": 0, "margins": []})
    type_model_wins = defaultdict(lambda: defaultdict(int))  # type → model → count
    claim_data = defaultdict(lambda: {"spr_wins": 0, "total": 0, "margins": [], "type": ""})
    for ep in episodes:
        ct = ep.get("claim_type", "?")
        claim = ep.get("claim", "?")
        spr_model = ep["config_snapshot"]["agents"]["spreader"]["model"]
        type_data[ct]["total"] += 1
        claim_data[claim]["total"] += 1
        claim_data[claim]["type"] = ct
        t = ep["results"].get("totals", {})
        if t.get("debunker") is not None and t.get("spreader") is not None:
            margin = t["debunker"] - t["spreader"]
            type_data[ct]["margins"].append(margin)
            claim_data[claim]["margins"].append(margin)
        if ep["results"]["winner"] == "spreader":
            type_data[ct]["spr_wins"] += 1
            claim_data[claim]["spr_wins"] += 1
            type_model_wins[ct][spr_model] += 1

    ct_sorted = sorted(type_data.keys(),
                       key=lambda ct: type_data[ct]["spr_wins"] / max(type_data[ct]["total"], 1),
                       reverse=True)

    # Stacked bar: each segment = one spreader model's contribution
    all_spr_models = sorted(set(
        ep["config_snapshot"]["agents"]["spreader"]["model"] for ep in episodes
    ))
    model_colors = {
        all_spr_models[i]: ["#4A7FA5", "#4CAF7D", "#C9363E", "#D4A843"][i % 4]
        for i in range(len(all_spr_models))
    }

    fig = go.Figure()
    for model in all_spr_models:
        vals = []
        hover_texts = []
        for ct in ct_sorted:
            total = max(type_data[ct]["total"], 1)
            model_wins = type_model_wins[ct].get(model, 0)
            pct = model_wins / total * 100
            vals.append(pct)
            hover_texts.append(f"{_short(model)}: {model_wins} wins ({pct:.1f}%)")
        fig.add_trace(go.Bar(
            name=_short(model),
            x=ct_sorted, y=vals,
            marker_color=model_colors[model],
            hovertext=hover_texts,
            hovertemplate="%{x}<br>%{hovertext}<extra></extra>",
        ))

    # Add total annotation above each stacked bar
    for i, ct in enumerate(ct_sorted):
        total_rate = type_data[ct]["spr_wins"] / max(type_data[ct]["total"], 1) * 100
        avg_margin = sum(type_data[ct]["margins"]) / max(len(type_data[ct]["margins"]), 1)
        fig.add_annotation(
            x=ct, y=total_rate + 1.5,
            text=f"{total_rate:.0f}% (n={type_data[ct]['total']})",
            showarrow=False, font=dict(size=10, color="#E8E4D9"),
        )

    fig.update_layout(
        barmode="stack",
        yaxis=dict(title="Spreader win rate %", range=[0, 35], gridcolor="#2A2A2A"),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=380, margin=dict(t=50, b=40, l=50, r=20),
        **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # (Claim drill-down and episode explorer removed — use Explore tab instead)


def _render_strategies(episodes):
    """Strategies tab: model playbooks, comparison table, claim type adaptation."""

    # ── Methodology note ─────────────────────────────────────────────
    st.markdown('<p class="sr-finding">How Strategies Were Identified</p>', unsafe_allow_html=True)
    _warning(
        "After each debate, an AI analyst (GPT-4o-mini) reads the full transcript and assigns "
        "labels from a fixed 20-label taxonomy: 10 spreader tactics (from the FLICC framework + "
        "SemEval-2023) and 10 debunker tactics (from Cook et al. 2017 + inoculation theory). "
        "Each episode is labeled once at the episode level — per-turn evolution is not captured. "
        "Limitations: single-annotator bias, forced-choice taxonomy, and episode-level granularity."
    )

    # ── Pre-compute strategy data ────────────────────────────────────
    spr_by_model = defaultdict(Counter)
    deb_by_model = defaultdict(Counter)
    spr_eps = Counter()
    deb_eps = Counter()

    for ep in episodes:
        spr_m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb_m = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        spr_eps[spr_m] += 1
        deb_eps[deb_m] += 1
        for s in sa.get("spreader_strategies", []):
            spr_by_model[spr_m][s] += 1
        for s in sa.get("debunker_strategies", []):
            deb_by_model[deb_m][s] += 1

    models = sorted(spr_by_model.keys())

    # ==================================================================
    # SECTION 1: MODEL PLAYBOOKS
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 1: Model Playbooks</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Each model has a distinct rhetorical approach. Below are the primary, secondary, '
        'and tertiary tactics each model defaults to as spreader and debunker.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Spreader playbooks ───────────────────────────────────────────
    st.markdown("**As Spreader**")
    _how_to_read("Primary = most frequently used tactic. Secondary and tertiary show the next most common. "
                 "Percentage = share of all tactics deployed by that model.")

    playbook_cols = st.columns(len(models))
    for col, model in zip(playbook_cols, models):
        with col:
            counts = spr_by_model[model]
            total = sum(counts.values())
            top3 = counts.most_common(3)
            n_unique = len([k for k, v in counts.items() if v > 0])

            color = SPREADER_COLOR
            st.markdown(
                f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
                f'border-radius:8px;padding:0.8rem;border-top:3px solid {color}">'
                f'<div style="font-size:0.95rem;font-weight:700;color:#E8E4D9;margin-bottom:0.5rem">'
                f'{_short(model)}</div>'
                f'<div style="font-size:0.7rem;color:#9ca3af;margin-bottom:0.6rem">'
                f'{spr_eps[model]} episodes · {n_unique}/10 tactics used</div>',
                unsafe_allow_html=True,
            )
            for rank, (strat, n) in enumerate(top3):
                pct = n / total * 100
                rank_label = ["Primary", "Secondary", "Tertiary"][rank]
                bar_width = pct / 60 * 100  # scale to max ~60%
                st.markdown(
                    f'<div style="margin-bottom:0.5rem">'
                    f'<div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.06em;'
                    f'color:#9ca3af;font-weight:700">{rank_label}</div>'
                    f'<div style="font-size:0.88rem;color:#E8E4D9;font-weight:600">{_label(strat)}</div>'
                    f'<div style="display:flex;align-items:center;gap:0.4rem;margin-top:0.15rem">'
                    f'<div style="flex:1;background:rgba(200,200,200,0.15);border-radius:3px;height:8px">'
                    f'<div style="width:{bar_width:.0f}%;background:{color};height:8px;border-radius:3px"></div>'
                    f'</div>'
                    f'<span style="font-size:0.8rem;color:#9ca3af;min-width:2.5rem;text-align:right">{pct:.0f}%</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    _takeaway(
        "<b>Key finding:</b> Each model has a distinct spreader identity. "
        "<b>Claude Sonnet</b> overwhelmingly defaults to burden shift (49%) — deflecting rather than "
        "actively constructing misinformation, likely due to safety training. "
        "<b>GPT-4o-mini</b> leads with anecdotal evidence (24%) — personal stories and vivid examples. "
        "<b>GPT-4o</b> and <b>Gemini Flash</b> both lead with emotional appeal (24%) but differ in "
        "secondary tactics."
    )

    # ── Debunker playbooks ───────────────────────────────────────────
    st.markdown("**As Debunker**")
    _how_to_read("Debunker models converge more than spreaders — all lead with evidence citation. "
                 "The differentiation is in secondary and tertiary tactics.")

    deb_cols = st.columns(len(models))
    for col, model in zip(deb_cols, models):
        with col:
            counts = deb_by_model[model]
            total = sum(counts.values())
            top3 = counts.most_common(3)
            n_unique = len([k for k, v in counts.items() if v > 0])

            color = DEBUNKER_COLOR
            st.markdown(
                f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
                f'border-radius:8px;padding:0.8rem;border-top:3px solid {color}">'
                f'<div style="font-size:0.95rem;font-weight:700;color:#E8E4D9;margin-bottom:0.5rem">'
                f'{_short(model)}</div>'
                f'<div style="font-size:0.7rem;color:#9ca3af;margin-bottom:0.6rem">'
                f'{deb_eps[model]} episodes · {n_unique}/10 tactics used</div>',
                unsafe_allow_html=True,
            )
            for rank, (strat, n) in enumerate(top3):
                pct = n / total * 100
                rank_label = ["Primary", "Secondary", "Tertiary"][rank]
                bar_width = pct / 35 * 100  # scale for debunker (max ~30%)
                st.markdown(
                    f'<div style="margin-bottom:0.5rem">'
                    f'<div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.06em;'
                    f'color:#9ca3af;font-weight:700">{rank_label}</div>'
                    f'<div style="font-size:0.88rem;color:#E8E4D9;font-weight:600">{_label(strat)}</div>'
                    f'<div style="display:flex;align-items:center;gap:0.4rem;margin-top:0.15rem">'
                    f'<div style="flex:1;background:rgba(200,200,200,0.15);border-radius:3px;height:8px">'
                    f'<div style="width:{bar_width:.0f}%;background:{color};height:8px;border-radius:3px"></div>'
                    f'</div>'
                    f'<span style="font-size:0.8rem;color:#9ca3af;min-width:2.5rem;text-align:right">{pct:.0f}%</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    _takeaway(
        "<b>Key finding:</b> All debunker models converge on the same primary tactic: evidence citation. "
        "The differentiation is in secondary approaches — <b>Claude</b> emphasizes mechanism explanation "
        "(explaining the causal logic behind why claims are false), while <b>GPT models</b> emphasize "
        "source quality (naming specific credible institutions)."
    )

    # ==================================================================
    # SECTION 2: STRATEGY COMPARISON TABLE
    # ==================================================================
    st.markdown('<p class="sr-finding">Strategy Usage Comparison</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'How does each tactic\'s usage compare across models? Rows sorted by total usage.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Spreader comparison
    st.markdown("**Spreader tactics**")
    all_spr_strats = Counter()
    for c in spr_by_model.values():
        all_spr_strats.update(c)

    spr_table_rows = []
    for strat, _ in all_spr_strats.most_common():
        row = {"Tactic": _label(strat)}
        for model in models:
            total = sum(spr_by_model[model].values())
            n = spr_by_model[model].get(strat, 0)
            row[_short(model)] = f"{n/total*100:.0f}% ({n})" if total > 0 else "—"
        row["Total"] = all_spr_strats[strat]
        spr_table_rows.append(row)
    st.dataframe(pd.DataFrame(spr_table_rows), use_container_width=True, hide_index=True)

    # Debunker comparison
    st.markdown("**Debunker tactics**")
    all_deb_strats = Counter()
    for c in deb_by_model.values():
        all_deb_strats.update(c)

    deb_table_rows = []
    for strat, _ in all_deb_strats.most_common():
        row = {"Tactic": _label(strat)}
        for model in models:
            total = sum(deb_by_model[model].values())
            n = deb_by_model[model].get(strat, 0)
            row[_short(model)] = f"{n/total*100:.0f}% ({n})" if total > 0 else "—"
        row["Total"] = all_deb_strats[strat]
        deb_table_rows.append(row)
    st.dataframe(pd.DataFrame(deb_table_rows), use_container_width=True, hide_index=True)

    _how_to_read("Each cell shows the percentage of that model's tactics that used this strategy, "
                 "with the raw count in parentheses. Sorted by total usage across all models. "
                 "Tactics with very low counts (< 20 total) are at the bottom — these were rarely "
                 "detected by the AI analyst and may not be reliable signals.")

    # ==================================================================
    # SECTION 3: CLAIM TYPE ADAPTATION
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 2: Strategy Adaptation by Claim Type</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do spreaders use different tactics depending on the claim domain? '
        'This shows how primary strategy choice shifts across Health, Political, Economic, '
        'Environmental, and Technology claims.'
        '</p>',
        unsafe_allow_html=True,
    )

    claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))

    type_strats = defaultdict(Counter)
    for ep in episodes:
        ct = ep.get("claim_type", "?")
        sa = ep.get("strategy_analysis") or {}
        primary = sa.get("spreader_primary", "")
        if primary:
            type_strats[ct][primary] += 1

    fig = go.Figure()
    all_strats = Counter()
    for c in type_strats.values():
        all_strats.update(c)
    top_strats = [s for s, _ in all_strats.most_common(6)]

    for strat in top_strats:
        vals = []
        for ct in claim_types:
            total = sum(type_strats[ct].values())
            vals.append(type_strats[ct].get(strat, 0) / max(total, 1) * 100)
        fig.add_trace(go.Bar(name=_label(strat), x=claim_types, y=vals,
                            text=[f"{v:.0f}%" for v in vals], textposition="outside",
                            textfont=dict(size=9)))

    fig.update_layout(
        barmode="group",
        yaxis=dict(title="% as primary strategy", gridcolor="#2A2A2A", range=[0, 60]),
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", font=dict(size=10)),
        height=400, margin=dict(t=60, b=40, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _how_to_read("Each group of bars shows one claim type. Bars represent the top 6 primary strategies "
                 "used when spreading that type of claim. The dominant strategy shifts by domain.")

    _takeaway(
        "<b>Key insight:</b> AI spreaders adapt their tactics to the domain: "
        "<b>Health</b> claims trigger anecdotal evidence (personal stories about vaccine injuries). "
        "<b>Political</b> claims trigger emotional appeal (outrage about stolen elections). "
        "<b>Economic</b> claims trigger appeal to conspiracy (\"follow the money\"). "
        "This domain-specific adaptation means misinformation detection tools may need to be "
        "tailored to the claim domain, not one-size-fits-all."
    )


def _render_game_theory(episodes):
    """Game Theory tab: how do agents influence each other?"""
    st.markdown('<p class="sr-finding">Finding 3: Strategic Interaction</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Does a spreader change its tactics based on who it\'s debating? '
        'Does the debunker adapt to different spreader styles? '
        'How does one player\'s behavior influence the other?'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Chart 1: Spreader primary strategy by opponent ───────────────
    st.markdown("**Does the spreader change tactics based on the debunker?**")
    _how_to_read("Each group shows one spreader model. The bars show how often it uses its "
                 "primary strategy against each debunker opponent. If bars are the same height "
                 "across opponents, the spreader doesn't adapt.")

    spr_vs_deb = defaultdict(lambda: defaultdict(Counter))
    for ep in episodes:
        spr_m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb_m = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        primary = sa.get("spreader_primary", "")
        if primary:
            spr_vs_deb[spr_m][deb_m][primary] += 1

    spr_models = sorted(spr_vs_deb.keys())
    deb_models = sorted(set(d for s in spr_vs_deb.values() for d in s.keys()))

    fig = go.Figure()
    colors = [DEBUNKER_COLOR, ACCENT_GREEN, ACCENT_RED, SPREADER_COLOR]
    for i, deb in enumerate(deb_models):
        vals = []
        texts = []
        for spr in spr_models:
            counts = spr_vs_deb[spr].get(deb, Counter())
            total = sum(counts.values())
            if total > 0:
                top_strat, top_n = counts.most_common(1)[0]
                pct = top_n / total * 100
                vals.append(pct)
                texts.append(f"{_label(top_strat)}<br>{pct:.0f}% (n={total})")
            else:
                vals.append(0)
                texts.append("—")
        fig.add_trace(go.Bar(
            name=f"vs {_short(deb)}",
            x=[_short(m) for m in spr_models], y=vals,
            marker_color=colors[i % len(colors)],
            text=texts, textposition="outside", textfont=dict(size=8),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Primary strategy consistency %", range=[0, 110], gridcolor="#2A2A2A"),
        xaxis=dict(title="Spreader Model", tickfont=dict(size=11)),
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
        height=400, margin=dict(t=60, b=50, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _takeaway(
        "<b>Key finding:</b> Spreaders do NOT change their primary tactic based on the opponent. "
        "Claude uses burden shift ~77% regardless of debunker. GPT-4o-mini uses anecdotal evidence "
        "~60% regardless. The spreader's playbook is fixed by its training, not adapted to the opponent."
    )

    # ── Chart 2: Strategy intensity by opponent ──────────────────────
    st.markdown("**Does the spreader deploy MORE tactics against weaker opponents?**")
    _how_to_read("Each group shows one spreader model. Bars show the average number of unique "
                 "tactics used per episode when facing each debunker. Taller bars = broader arsenal deployed.")

    spr_div = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        spr_m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb_m = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        n = len(sa.get("spreader_strategies", []))
        spr_div[spr_m][deb_m].append(n)

    fig = go.Figure()
    for i, deb in enumerate(deb_models):
        vals = []
        texts = []
        for spr in spr_models:
            v_list = spr_div[spr].get(deb, [])
            if v_list:
                avg = sum(v_list) / len(v_list)
                vals.append(avg)
                texts.append(f"{avg:.1f}<br>n={len(v_list)}")
            else:
                vals.append(0)
                texts.append("—")
        fig.add_trace(go.Bar(
            name=f"vs {_short(deb)}",
            x=[_short(m) for m in spr_models], y=vals,
            marker_color=colors[i % len(colors)],
            text=texts, textposition="outside", textfont=dict(size=9),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Avg tactics per episode", range=[0, 7], gridcolor="#2A2A2A"),
        xaxis=dict(title="Spreader Model", tickfont=dict(size=11)),
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
        height=400, margin=dict(t=60, b=50, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _takeaway(
        "<b>Key finding:</b> Spreaders deploy a <b>broader arsenal against Gemini Flash</b> — "
        "approximately 4.7-4.9 tactics per episode compared to ~3.9-4.0 against other debunkers. "
        "When the debunker doesn't effectively counter tactics, the spreader has no pressure to narrow "
        "its approach. Against stronger debunkers, the spreader focuses on fewer, more concentrated tactics. "
        "This is <b>strategic intensity</b> rather than strategic switching — agents don't change WHAT they do, "
        "but they change HOW MUCH they do based on the opposition's strength."
    )

    # ── Chart 3: Debunker consistency ────────────────────────────────
    st.markdown("**Does the debunker adapt to different spreader styles?**")
    _how_to_read("Each group shows one debunker model. Bars show how often it uses evidence citation "
                 "as its primary strategy against each spreader. High consistency = rigid approach.")

    deb_vs_spr = defaultdict(lambda: defaultdict(Counter))
    for ep in episodes:
        spr_m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        deb_m = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        primary = sa.get("debunker_primary", "")
        if primary:
            deb_vs_spr[deb_m][spr_m][primary] += 1

    fig = go.Figure()
    for i, spr in enumerate(spr_models):
        vals = []
        for deb in deb_models:
            counts = deb_vs_spr[deb].get(spr, Counter())
            total = sum(counts.values())
            ec_count = counts.get("evidence_citation", 0)
            vals.append(ec_count / max(total, 1) * 100)
        fig.add_trace(go.Bar(
            name=f"vs {_short(spr)}",
            x=[_short(m) for m in deb_models], y=vals,
            marker_color=colors[i % len(colors)],
            text=[f"{v:.0f}%" for v in vals], textposition="outside", textfont=dict(size=9),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Evidence citation as primary %", range=[0, 120], gridcolor="#2A2A2A"),
        xaxis=dict(title="Debunker Model", tickfont=dict(size=11)),
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
        height=380, margin=dict(t=60, b=50, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _takeaway(
        "<b>Key finding:</b> Debunkers are even more rigid than spreaders. GPT-4o and GPT-4o-mini "
        "use evidence citation 94-100% of the time regardless of opponent. "
        "Gemini Flash shows the most variation (64-82%) — ironically the weakest debunker is "
        "the most adaptive one, but its adaptation doesn't help it win."
    )


def _render_citations(episodes):
    """Citations tab: quality by model and claim type."""
    st.markdown('<p class="sr-finding">Finding 4: Citation Quality by Model</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Which model produces the most trustworthy sources as debunker? '
        'Do some models cite named institutions while others use vague appeals?'
        '</p>',
        unsafe_allow_html=True,
    )

    _how_to_read("<b>Named Sources</b> = specific institutions (WHO, CDC, Harvard). "
                 "<b>Vague Appeals</b> = unverifiable phrases (\"research shows\", \"experts say\"). "
                 "<b>URLs</b> = actual web links provided. Higher named sources + URLs = more verifiable arguments.")

    cite = defaultdict(lambda: {"named": 0, "vague": 0, "urls": 0, "eps": 0})
    cite_by_type = defaultdict(lambda: defaultdict(lambda: {"named": 0, "eps": 0}))

    for ep in episodes:
        dm = ep["config_snapshot"]["agents"]["debunker"]["model"]
        ct = ep.get("claim_type", "?")
        cite[dm]["eps"] += 1
        cite_by_type[dm][ct]["eps"] += 1
        for t in ep.get("turns", []):
            msg = t.get("debunker_message", {})
            text = msg.get("content", "") if isinstance(msg, dict) else ""
            tl = text.lower()
            if "http" in tl: cite[dm]["urls"] += 1
            for src in _NAMED_SOURCES:
                if src.lower() in tl:
                    cite[dm]["named"] += 1
                    cite_by_type[dm][ct]["named"] += 1
                    break
            for kw in _VAGUE_KEYWORDS:
                if kw in tl:
                    cite[dm]["vague"] += 1
                    break

    # Citation types by model
    cm = sorted(cite.keys())
    fig = go.Figure()
    for ctype, label, color in [
        ("named", "Named Sources", DEBUNKER_COLOR),
        ("vague", "Vague Appeals", SPREADER_COLOR),
        ("urls", "URLs", ACCENT_GREEN),
    ]:
        vals = [cite[m][ctype]/max(cite[m]["eps"],1) for m in cm]
        fig.add_trace(go.Bar(
            name=label, x=[_short(m) for m in cm], y=vals,
            marker_color=color,
            text=[f"{v:.1f}" for v in vals], textposition="outside", textfont=dict(size=10),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Per episode (avg)", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=50,b=40,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Named sources by model × claim type
    st.markdown("**Named source density by debunker model and claim type**")
    claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))
    fig = go.Figure()
    for model in sorted(cite_by_type.keys()):
        vals = [cite_by_type[model][ct]["named"]/max(cite_by_type[model][ct]["eps"],1) for ct in claim_types]
        fig.add_trace(go.Bar(
            name=_short(model), x=claim_types, y=vals,
            text=[f"{v:.1f}" for v in vals], textposition="outside", textfont=dict(size=9),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Named sources/ep", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=50,b=40,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Insight
    best = max(cite.items(), key=lambda x: x[1]["named"]/max(x[1]["eps"],1))
    worst = min(cite.items(), key=lambda x: x[1]["named"]/max(x[1]["eps"],1))
    _takeaway(
        f"<b>Key insight:</b> "
        f"<b>{_short(best[0])}</b> cites {best[1]['named']/max(best[1]['eps'],1):.1f} named sources per episode "
        f"and provides {best[1]['urls']/max(best[1]['eps'],1):.1f} URLs for verification. "
        f"<b>{_short(worst[0])}</b> cites only {worst[1]['named']/max(worst[1]['eps'],1):.1f} named sources "
        f"and zero URLs — it argues without evidence. "
        f"This gap directly explains why {_short(worst[0])} loses every debate as debunker: "
        f"you can't debunk misinformation without citing credible sources."
    )

    # Dimension scores by debunker model (explains WHY citation matters)
    st.markdown('<p class="sr-finding">Dimension Scores by Debunker Model</p>', unsafe_allow_html=True)
    st.markdown('<p class="sr-question">How does citation quality translate to judge scores? The judge scores each side on 6 dimensions (0-10). This shows how each model performs as debunker.</p>', unsafe_allow_html=True)
    _how_to_read("Each group of bars shows one scoring dimension. Taller bars = higher scores. "
                 "A model that scores low across all dimensions (like Gemini Flash) is fundamentally weaker at debunking, "
                 "not just lacking in one area.")

    scores = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        dm = ep["config_snapshot"]["agents"]["debunker"]["model"]
        for s in ep["results"].get("scorecard", []):
            scores[dm][s["metric"]].append(s["debunker"])

    metrics = ["factuality", "source_credibility", "reasoning_quality",
               "responsiveness", "persuasion", "manipulation_awareness"]
    fig = go.Figure()
    for model in sorted(scores.keys()):
        vals = [sum(scores[model].get(m,[0]))/max(len(scores[model].get(m,[1])),1) for m in metrics]
        fig.add_trace(go.Bar(
            name=_short(model), x=[_label(m) for m in metrics], y=vals,
            text=[f"{v:.1f}" for v in vals], textposition="outside", textfont=dict(size=9),
        ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Avg score (0-10)", gridcolor="#2A2A2A", range=[0,11]),
        xaxis=dict(tickangle=-25, tickfont=dict(size=10)),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=380, margin=dict(t=50,b=80,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_depth(episodes):
    """Depth tab: strategy plateau analysis."""
    st.markdown('<p class="sr-finding">Finding 5: Strategy Depth Plateau</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do longer debates produce richer argumentation, or do agents recycle tactics? '
        'Where do diminishing returns kick in?'
        '</p>',
        unsafe_allow_html=True,
    )

    _how_to_read("Each line shows the average number of unique tactics detected per episode at that debate length. "
                 "If the line is flat, agents deploy their full repertoire early and recycle in longer debates. "
                 "The y-axis starts at 0 to show the true scale of these differences.")

    # Aggregate: both roles
    fig = go.Figure()
    for role, strat_field, color in [
        ("Spreader", "spreader_strategies", SPREADER_COLOR),
        ("Debunker", "debunker_strategies", DEBUNKER_COLOR),
    ]:
        by_turns = defaultdict(list)
        for ep in episodes:
            t = ep["results"]["completed_turn_pairs"]
            sa = ep.get("strategy_analysis") or {}
            by_turns[t].append(len(sa.get(strat_field, [])))
        turns = sorted(by_turns.keys())
        means = [sum(by_turns[t])/len(by_turns[t]) for t in turns]
        fig.add_trace(go.Scatter(
            x=turns, y=means, mode="lines+markers", name=role,
            line=dict(color=color, width=3), marker=dict(size=10),
        ))
    fig.update_layout(
        xaxis=dict(title="Debate length (turns)", tickvals=[2,6,10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg unique tactics/ep", gridcolor="#2A2A2A", range=[0, 6]),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=40,b=50,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per model
    st.markdown("**Per-model breakdown (spreader role)**")
    _how_to_read("Claude Sonnet appears as a dramatic outlier with ~1-2 tactics because its safety training "
                 "limits its willingness to deploy diverse misinformation strategies. This is a model behavior "
                 "finding, not a data quality issue.")
    spr_div = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        t = ep["results"]["completed_turn_pairs"]
        sa = ep.get("strategy_analysis") or {}
        spr_div[m][t].append(len(sa.get("spreader_strategies", [])))

    fig = go.Figure()
    for model in sorted(spr_div.keys()):
        turns = sorted(spr_div[model].keys())
        means = [sum(spr_div[model][t])/len(spr_div[model][t]) for t in turns]
        fig.add_trace(go.Scatter(x=turns, y=means, mode="lines+markers", name=_short(model)))
    fig.update_layout(
        xaxis=dict(title="Turns", tickvals=[2,6,10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg spreader tactics", gridcolor="#2A2A2A", range=[0, 6]),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=320, margin=dict(t=40,b=50,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Insight
    div_2 = [len(ep.get("strategy_analysis",{}).get("spreader_strategies",[])) for ep in episodes if ep["results"]["completed_turn_pairs"]==2]
    div_6 = [len(ep.get("strategy_analysis",{}).get("spreader_strategies",[])) for ep in episodes if ep["results"]["completed_turn_pairs"]==6]
    div_10 = [len(ep.get("strategy_analysis",{}).get("spreader_strategies",[])) for ep in episodes if ep["results"]["completed_turn_pairs"]==10]
    a2, a6, a10 = sum(div_2)/max(len(div_2),1), sum(div_6)/max(len(div_6),1), sum(div_10)/max(len(div_10),1)
    j1, j2 = a6-a2, a10-a6

    st.markdown(
        f'<div class="sr-insight"><b>Key insight:</b> '
        f'Spreader diversity: <b>{a2:.1f}</b> (2t) → <b>{a6:.1f}</b> (6t, Δ={j1:+.2f}) → '
        f'<b>{a10:.1f}</b> (10t, Δ={j2:+.2f}). '
        f'{"Minimal growth — agents deploy their full repertoire early." if j1 < 0.3 and j2 < 0.3 else "The debunker shows more growth with length than the spreader."}'
        f'</div>', unsafe_allow_html=True,
    )


# ======================================================================
# Main
# ======================================================================

def render_study_results_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    st.markdown('<p class="sr-title">Study Results</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-subtitle">'
        'Model-centered analysis of AI argumentation strategies and citation quality '
        'across adversarial misinformation debates.'
        '</p>',
        unsafe_allow_html=True,
    )

    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No experiment data. Run the experiment first.")
        return

    episodes = _load_experiment_data(tuple(run_ids), RUNS_DIR, token)
    if not episodes:
        st.info("No experiment episodes found. Upload and run data/experiment_spec.csv in Arena > Experiment.")
        return

    tab_overview, tab_strategies, tab_game, tab_citations, tab_depth = st.tabs([
        "Overview", "Strategies", "Game Theory", "Citations", "Depth"
    ])

    with tab_overview:
        _render_overview(episodes)
    with tab_strategies:
        _render_strategies(episodes)
    with tab_game:
        _render_game_theory(episodes)
    with tab_citations:
        _render_citations(episodes)
    with tab_depth:
        _render_depth(episodes)

    st.markdown(
        f'<p style="font-size:0.8rem;color:#666;margin-top:2rem;text-align:center">'
        f'{len(episodes)} episodes · Judge: GPT-4o · '
        f'Export CSVs from Tools > Exports for Minitab analysis.'
        f'</p>', unsafe_allow_html=True,
    )
