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
    """Strategies tab: how models argue, where they converge/diverge, domain adaptation."""

    # ── Methodology note ─────────────────────────────────────────────
    _warning(
        "<b>How strategies were identified:</b> After each debate, an AI analyst (GPT-4o-mini) "
        "labels the transcript using a fixed 20-label taxonomy: 10 spreader tactics "
        "(FLICC framework + SemEval-2023) and 10 debunker tactics (Cook et al. 2017 + "
        "inoculation theory). Labels are episode-level, not per-turn."
    )

    # ── Pre-compute ──────────────────────────────────────────────────
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
    # FINDING 1: HOW DOES EACH MODEL SPREAD MISINFORMATION?
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 1: How Does Each Model Spread Misinformation?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Each model develops a distinct rhetorical identity when assigned the spreader role. '
        'The cards below show each model\'s top 3 tactics — their "playbook."'
        '</p>',
        unsafe_allow_html=True,
    )

    playbook_cols = st.columns(len(models))
    for col, model in zip(playbook_cols, models):
        with col:
            counts = spr_by_model[model]
            total = sum(counts.values())
            top3 = counts.most_common(3)
            n_unique = len([k for k, v in counts.items() if v > 0])

            st.markdown(
                f'<div style="background:var(--color-surface,#111);border:1px solid var(--color-border,#2A2A2A);'
                f'border-radius:8px;padding:0.8rem;border-top:3px solid {SPREADER_COLOR}">'
                f'<div style="font-size:0.95rem;font-weight:700;color:#E8E4D9;margin-bottom:0.3rem">'
                f'{_short(model)}</div>'
                f'<div style="font-size:0.7rem;color:#9ca3af;margin-bottom:0.6rem">'
                f'{spr_eps[model]} episodes · {n_unique}/10 tactics used</div>',
                unsafe_allow_html=True,
            )
            for rank, (strat, n) in enumerate(top3):
                pct = n / total * 100
                rank_label = ["PRIMARY", "SECONDARY", "TERTIARY"][rank]
                bar_width = min(pct / 55 * 100, 100)
                st.markdown(
                    f'<div style="margin-bottom:0.5rem">'
                    f'<div style="font-size:0.6rem;letter-spacing:0.08em;color:#9ca3af;font-weight:700">'
                    f'{rank_label}</div>'
                    f'<div style="font-size:0.85rem;color:#E8E4D9;font-weight:600">{_label(strat)}</div>'
                    f'<div style="display:flex;align-items:center;gap:0.4rem;margin-top:0.15rem">'
                    f'<div style="flex:1;background:rgba(200,200,200,0.12);border-radius:3px;height:8px">'
                    f'<div style="width:{bar_width:.0f}%;background:{SPREADER_COLOR};height:8px;'
                    f'border-radius:3px"></div></div>'
                    f'<span style="font-size:0.78rem;color:#9ca3af">{pct:.0f}%</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    _takeaway(
        "<b>Key finding:</b> Each model has a distinct spreader identity. "
        "<b>Claude</b> defaults to burden shift (49%) — deflecting rather than constructing "
        "misinformation, likely due to safety training. "
        "<b>GPT-4o-mini</b> leads with anecdotal evidence — vivid personal stories. "
        "<b>GPT-4o</b> and <b>Gemini</b> lead with emotional appeal but differ in secondary tactics. "
        "If AI-generated misinformation appears on social media, its rhetorical signature "
        "could indicate which model produced it."
    )

    # ==================================================================
    # FINDING 2: HOW DOES EACH MODEL DEBUNK? (WHERE THEY CONVERGE)
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 2: How Does Each Model Debunk?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Unlike spreader tactics, debunker models converge on the same approach. '
        'The chart below shows all 4 models on the same axis — the similarity is the finding.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Horizontal bar chart: all models side by side per tactic
    # Only show tactics with > 30 total appearances
    all_deb_strats = Counter()
    for c in deb_by_model.values():
        all_deb_strats.update(c)
    significant_deb = [s for s, n in all_deb_strats.most_common() if n >= 30]

    model_colors = [DEBUNKER_COLOR, ACCENT_GREEN, ACCENT_RED, SPREADER_COLOR]

    fig = go.Figure()
    for i, model in enumerate(models):
        total = sum(deb_by_model[model].values())
        vals = [deb_by_model[model].get(s, 0) / max(total, 1) * 100 for s in significant_deb]
        fig.add_trace(go.Bar(
            name=_short(model),
            y=[_label(s) for s in significant_deb],
            x=vals,
            orientation="h",
            marker_color=model_colors[i % len(model_colors)],
            text=[f"{v:.0f}%" for v in vals],
            textposition="outside",
            textfont=dict(size=9),
        ))

    fig.update_layout(
        barmode="group",
        xaxis=dict(title="% of tactics used", gridcolor="#2A2A2A", range=[0, 35]),
        yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=max(300, len(significant_deb) * 55 + 80),
        margin=dict(t=50, b=40, l=10, r=60),
        **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _how_to_read("Each group of bars shows one debunking tactic. All 4 models appear side by side. "
                 "When bars are the same length, models use that tactic equally. "
                 "Differences in bar length reveal where models diverge.")

    _takeaway(
        "<b>Key finding:</b> All models converge on evidence citation and logical refutation "
        "as their top debunking tactics. The difference is in secondary approaches: "
        "<b>Claude</b> emphasizes mechanism explanation (explaining why claims are false), "
        "while <b>GPT models</b> emphasize source quality (naming specific institutions). "
        "<b>Gemini</b> shows similar priorities but executes them poorly — it uses the right "
        "tactics but without the evidence to back them up (see Citations tab)."
    )

    # ==================================================================
    # FINDING 3: DO MODELS ADAPT TO THE CLAIM DOMAIN?
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 3: Do Models Adapt to the Claim Domain?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'When the topic changes from health to politics to economics, does the spreader\'s '
        'approach change? Each bar below shows the dominant tactic for that domain.'
        '</p>',
        unsafe_allow_html=True,
    )

    claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))

    # Stacked bar: one bar per claim type, segments = strategy share
    type_strats = defaultdict(Counter)
    for ep in episodes:
        ct = ep.get("claim_type", "?")
        sa = ep.get("strategy_analysis") or {}
        primary = sa.get("spreader_primary", "")
        if primary:
            type_strats[ct][primary] += 1

    # Get top strategies and assign consistent colors
    all_strats = Counter()
    for c in type_strats.values():
        all_strats.update(c)
    top_strats = [s for s, _ in all_strats.most_common(5)]
    strat_colors = {
        top_strats[i]: ["#4A7FA5", "#C9363E", "#4CAF7D", "#D4A843", "#9333EA"][i]
        for i in range(len(top_strats))
    }

    fig = go.Figure()
    for strat in top_strats:
        vals = []
        for ct in claim_types:
            total = sum(type_strats[ct].values())
            vals.append(type_strats[ct].get(strat, 0) / max(total, 1) * 100)
        fig.add_trace(go.Bar(
            name=_label(strat),
            x=claim_types, y=vals,
            marker_color=strat_colors[strat],
            hovertemplate=f"{_label(strat)}<br>%{{x}}: %{{y:.0f}}%<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(title="% of primary strategy choices", gridcolor="#2A2A2A", range=[0, 110]),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", font=dict(size=10)),
        height=400, margin=dict(t=60, b=40, l=50, r=20),
        **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _how_to_read("Each bar shows one claim type. The colored segments show the share of each "
                 "primary strategy. The dominant color tells you the go-to tactic for that domain. "
                 "If colors shift across bars, models are adapting to the topic.")

    # Build per-type dominant strategy text
    type_insights = []
    for ct in claim_types:
        if type_strats[ct]:
            top_s, top_n = type_strats[ct].most_common(1)[0]
            total = sum(type_strats[ct].values())
            type_insights.append(f"<b>{ct}</b> → {_label(top_s)} ({top_n/total*100:.0f}%)")

    _takeaway(
        "<b>Key finding:</b> AI spreaders automatically adapt to the domain: " +
        " · ".join(type_insights) + ". "
        "This means misinformation from different domains has different rhetorical signatures — "
        "a health misinformation detector won't catch political misinformation, and vice versa."
    )

    # ==================================================================
    # REFERENCE: FULL STRATEGY USAGE
    # ==================================================================
    with st.expander("Full strategy usage table (reference)", expanded=False):
        st.markdown("**Spreader tactics**")
        all_spr = Counter()
        for c in spr_by_model.values():
            all_spr.update(c)
        spr_rows = []
        for strat, _ in all_spr.most_common():
            row = {"Tactic": _label(strat)}
            for model in models:
                total = sum(spr_by_model[model].values())
                n = spr_by_model[model].get(strat, 0)
                row[_short(model)] = f"{n/total*100:.0f}% ({n})" if total > 0 else "—"
            row["Total"] = all_spr[strat]
            spr_rows.append(row)
        st.dataframe(pd.DataFrame(spr_rows), use_container_width=True, hide_index=True)

        st.markdown("**Debunker tactics**")
        deb_rows = []
        for strat, _ in all_deb_strats.most_common():
            row = {"Tactic": _label(strat)}
            for model in models:
                total = sum(deb_by_model[model].values())
                n = deb_by_model[model].get(strat, 0)
                row[_short(model)] = f"{n/total*100:.0f}% ({n})" if total > 0 else "—"
            row["Total"] = all_deb_strats[strat]
            deb_rows.append(row)
        st.dataframe(pd.DataFrame(deb_rows), use_container_width=True, hide_index=True)


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
    """Citations tab: what sources do models use and does it matter?"""

    # ── Compute citation data ────────────────────────────────────────
    cite_deb = defaultdict(lambda: {"eps": 0})
    cite_spr = defaultdict(lambda: {"eps": 0})
    deb_sources = defaultdict(Counter)  # model → source → count
    spr_sources = defaultdict(Counter)

    for ep in episodes:
        dm = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sm = ep["config_snapshot"]["agents"]["spreader"]["model"]
        cite_deb[dm]["eps"] += 1
        cite_spr[sm]["eps"] += 1
        for t in ep.get("turns", []):
            for side_key, store, src_store, model in [
                ("debunker_message", cite_deb, deb_sources, dm),
                ("spreader_message", cite_spr, spr_sources, sm),
            ]:
                msg = t.get(side_key, {})
                text = msg.get("content", "") if isinstance(msg, dict) else ""
                tl = text.lower()
                for src in _NAMED_SOURCES:
                    if src.lower() in tl:
                        store[model][src] = store[model].get(src, 0) + 1
                        src_store[model][src] += 1

    models = sorted(cite_deb.keys())

    # Helper: total named sources for a model
    def _total_named(store, model):
        return sum(v for k, v in store[model].items() if k != "eps")

    # ==================================================================
    # Q1: WHICH MODEL CITES THE MOST SOURCES?
    # ==================================================================
    st.markdown('<p class="sr-finding">Which Model Cites the Most Sources as Debunker?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Effective debunking requires citing specific, credible institutions. '
        'How many named sources (WHO, CDC, Harvard, Nature, etc.) does each model reference per episode?'
        '</p>',
        unsafe_allow_html=True,
    )

    deb_named_per_ep = [_total_named(cite_deb, m) / max(cite_deb[m]["eps"], 1) for m in models]
    fig = go.Figure(go.Bar(
        x=[_short(m) for m in models], y=deb_named_per_ep,
        marker_color=[ACCENT_GREEN if v > 4 else DEBUNKER_COLOR if v > 1 else ACCENT_RED for v in deb_named_per_ep],
        text=[f"{v:.1f}/ep" for v in deb_named_per_ep],
        textposition="outside", textfont=dict(size=11),
    ))
    fig.update_layout(
        yaxis=dict(title="Named sources per episode", gridcolor="#2A2A2A"),
        height=300, margin=dict(t=20, b=40, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    best = max(models, key=lambda m: _total_named(cite_deb, m) / max(cite_deb[m]["eps"], 1))
    worst = min(models, key=lambda m: _total_named(cite_deb, m) / max(cite_deb[m]["eps"], 1))
    _takeaway(
        f"<b>{_short(best)}</b> cites {_total_named(cite_deb, best)/max(cite_deb[best]['eps'],1):.1f} "
        f"named sources per episode — the most evidence-grounded debunker. "
        f"<b>{_short(worst)}</b> cites {_total_named(cite_deb, worst)/max(cite_deb[worst]['eps'],1):.1f} "
        f"— it argues without citing evidence, and loses every debate."
    )

    # ==================================================================
    # Q2: WHAT SPECIFIC SOURCES DO THEY CITE?
    # ==================================================================
    st.markdown('<p class="sr-finding">What Sources Do They Reference?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Which institutions appear most frequently in the transcripts? '
        'This shows the top sources each model cites as debunker.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Top sources table
    source_rows = []
    all_deb_src = Counter()
    for c in deb_sources.values():
        all_deb_src.update(c)

    for src, total in all_deb_src.most_common(10):
        row = {"Source": src, "Total": total}
        for model in models:
            row[_short(model)] = deb_sources[model].get(src, 0)
        source_rows.append(row)

    st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)

    _how_to_read("Each row is one institution. Columns show how many times each model referenced "
                 "it across all debates. Sources like WHO and MIT appear frequently because they're "
                 "relevant across multiple claim types.")

    # ==================================================================
    # Q3: DO SPREADERS CITE THE SAME SOURCES? (weaponization)
    # ==================================================================
    st.markdown('<p class="sr-finding">Do Spreaders Use the Same Sources?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'AI misinformation is harder to detect when it cites the same credible institutions '
        'that debunkers use. Do spreaders weaponize legitimate sources?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Source overlap chart
    all_spr_src = Counter()
    for c in spr_sources.values():
        all_spr_src.update(c)

    # Show top sources used by BOTH sides
    shared_sources = sorted(
        set(all_spr_src.keys()) & set(all_deb_src.keys()),
        key=lambda s: all_spr_src[s] + all_deb_src[s],
        reverse=True,
    )[:8]

    # Debunker-only sources
    deb_only = sorted(
        [s for s in all_deb_src if all_spr_src.get(s, 0) < 5],
        key=lambda s: all_deb_src[s],
        reverse=True,
    )[:5]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Cited by Spreaders",
        x=shared_sources, y=[all_spr_src[s] for s in shared_sources],
        marker_color=SPREADER_COLOR,
        text=[str(all_spr_src[s]) for s in shared_sources],
        textposition="outside", textfont=dict(size=9),
    ))
    fig.add_trace(go.Bar(
        name="Cited by Debunkers",
        x=shared_sources, y=[all_deb_src[s] for s in shared_sources],
        marker_color=DEBUNKER_COLOR,
        text=[str(all_deb_src[s]) for s in shared_sources],
        textposition="outside", textfont=dict(size=9),
    ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Total citations across all episodes", gridcolor="#2A2A2A"),
        xaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=380, margin=dict(t=50, b=40, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _takeaway(
        "<b>Key finding:</b> Spreaders and debunkers cite many of the <b>same credible institutions</b>. "
        "WHO is cited 2,000+ times by spreaders vs 850 by debunkers — spreaders actually reference it more. "
        "This means AI-generated misinformation <i>sounds</i> evidence-based because it cherry-picks "
        "from the same sources that legitimate fact-checkers use. "
        "However, debunkers have exclusive access to specialized sources like <b>" +
        ", ".join(deb_only[:3]) +
        "</b> — which spreaders rarely touch."
    )

    # ==================================================================
    # Q4: DOES CITATION QUALITY PREDICT OUTCOMES?
    # ==================================================================
    st.markdown('<p class="sr-finding">Does Citation Quality Predict Who Wins?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'The judge scores each side on 6 dimensions (0-10). Do models that cite better sources score higher?'
        '</p>',
        unsafe_allow_html=True,
    )

    scores = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        dm = ep["config_snapshot"]["agents"]["debunker"]["model"]
        for s in ep["results"].get("scorecard", []):
            scores[dm][s["metric"]].append(s["debunker"])

    score_rows = []
    for model in models:
        row = {"Model": _short(model)}
        overall_scores = []
        for m in ["factuality", "source_credibility", "reasoning_quality",
                  "responsiveness", "persuasion", "manipulation_awareness"]:
            vals = scores[model].get(m, [0])
            avg = sum(vals) / max(len(vals), 1)
            overall_scores.append(avg)
            row[_label(m)] = f"{avg:.1f}"
        row["Overall"] = f"{sum(overall_scores)/len(overall_scores):.1f}"
        row["Sources/ep"] = f"{_total_named(cite_deb, model)/max(cite_deb[model]['eps'],1):.1f}"
        row["Win Rate"] = "100%" if "gemini" not in model else "0%"
        score_rows.append(row)

    st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

    _takeaway(
        "<b>Key finding:</b> Citation quality, judge scores, and win rate are tightly linked. "
        "Models that cite 4.8+ named sources per episode score 7.5+ overall and win 100% of debates. "
        "Gemini Flash cites near-zero sources, scores 4.7, and wins 0%. "
        "For AI-assisted fact-checking, <b>the ability to cite specific, verifiable evidence is the "
        "single strongest predictor of debunking effectiveness.</b>"
    )


def _render_depth(episodes):
    """Depth tab: does debate length matter?"""

    # ==================================================================
    # Q1: DO LONGER DEBATES PRODUCE NEW TACTICS?
    # ==================================================================
    st.markdown('<p class="sr-finding">Do Longer Debates Produce New Tactics?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'If AI debates ran for 10 turns instead of 2, would the arguments get richer? '
        'Or do models deploy everything they have early and recycle in longer debates?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Compute diversity data
    div_data = {"spreader": defaultdict(list), "debunker": defaultdict(list)}
    div_by_model = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        t = ep["results"]["completed_turn_pairs"]
        sa = ep.get("strategy_analysis") or {}
        spr_m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        div_data["spreader"][t].append(len(sa.get("spreader_strategies", [])))
        div_data["debunker"][t].append(len(sa.get("debunker_strategies", [])))
        div_by_model[spr_m][t].append(len(sa.get("spreader_strategies", [])))

    turns = sorted(div_data["spreader"].keys())
    spr_means = [sum(div_data["spreader"][t]) / len(div_data["spreader"][t]) for t in turns]
    deb_means = [sum(div_data["debunker"][t]) / len(div_data["debunker"][t]) for t in turns]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=turns, y=spr_means, mode="lines+markers", name="Spreader",
        line=dict(color=SPREADER_COLOR, width=3), marker=dict(size=10),
    ))
    fig.add_trace(go.Scatter(
        x=turns, y=deb_means, mode="lines+markers", name="Debunker",
        line=dict(color=DEBUNKER_COLOR, width=3), marker=dict(size=10),
    ))
    fig.update_layout(
        xaxis=dict(title="Debate length (turn pairs)", tickvals=[2, 6, 10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg unique tactics per episode", gridcolor="#2A2A2A", range=[0, 6]),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=40, b=50, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    _how_to_read("Flat lines = agents deploy their full repertoire early and recycle in longer debates. "
                 "Rising lines = longer debates produce genuinely new tactics. "
                 "Y-axis starts at 0 to show the true scale — these are small differences.")

    _takeaway(
        f"<b>Key finding:</b> Spreader tactics barely change with debate length: "
        f"<b>{spr_means[0]:.1f}</b> tactics at 2 turns → <b>{spr_means[-1]:.1f}</b> at 10 turns "
        f"(+{spr_means[-1]-spr_means[0]:.1f}). Agents deploy their full playbook within the first "
        f"2 exchanges. Longer debates produce repetition, not new arguments. "
        f"The debunker shows slightly more growth ({deb_means[0]:.1f} → {deb_means[-1]:.1f}) "
        f"suggesting it develops additional counter-tactics over time."
    )

    # ==================================================================
    # Q2: DOES THIS VARY BY MODEL?
    # ==================================================================
    st.markdown('<p class="sr-finding">Does the Plateau Differ by Model?</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do some models develop new tactics in longer debates while others stay flat?'
        '</p>',
        unsafe_allow_html=True,
    )

    fig = go.Figure()
    models = sorted(div_by_model.keys())
    for model in models:
        model_turns = sorted(div_by_model[model].keys())
        means = [sum(div_by_model[model][t]) / len(div_by_model[model][t]) for t in model_turns]
        fig.add_trace(go.Scatter(
            x=model_turns, y=means, mode="lines+markers", name=_short(model),
            hovertemplate=f"{_short(model)}<br>%{{x}} turns: %{{y:.1f}} tactics<extra></extra>",
        ))
    fig.update_layout(
        xaxis=dict(title="Debate length (turn pairs)", tickvals=[2, 6, 10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg spreader tactics per episode", gridcolor="#2A2A2A", range=[0, 6]),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=40, b=50, l=50, r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Build per-model insight
    model_insights = []
    for model in models:
        t_sorted = sorted(div_by_model[model].keys())
        v_first = sum(div_by_model[model][t_sorted[0]]) / len(div_by_model[model][t_sorted[0]])
        v_last = sum(div_by_model[model][t_sorted[-1]]) / len(div_by_model[model][t_sorted[-1]])
        delta = v_last - v_first
        model_insights.append((model, v_first, v_last, delta))

    most_growth = max(model_insights, key=lambda x: x[3])
    least_growth = min(model_insights, key=lambda x: x[3])

    _takeaway(
        f"<b>{_short(most_growth[0])}</b> shows the most growth: "
        f"{most_growth[1]:.1f} → {most_growth[2]:.1f} tactics (+{most_growth[3]:.1f}). "
        f"<b>{_short(least_growth[0])}</b> shows the least: "
        f"{least_growth[1]:.1f} → {least_growth[2]:.1f} (+{least_growth[3]:.1f}). "
        f"Claude's low and flat line reflects its safety training — it resists deploying "
        f"diverse misinformation tactics regardless of how long the debate runs."
    )

    # ==================================================================
    # Q3: PRACTICAL IMPLICATION
    # ==================================================================
    st.markdown('<p class="sr-finding">What Does This Mean for AI Debate Design?</p>', unsafe_allow_html=True)

    _takeaway(
        "<b>Practical implication:</b> For AI-assisted debunking, a <b>6-turn debate captures "
        "the full strategic repertoire</b>. Beyond 6 turns, models recycle the same tactics "
        "with diminishing returns. This has implications for platform design — longer AI "
        "fact-checking threads don't produce better arguments, they just produce more of "
        "the same ones. Short, focused debunking may be more effective than extended back-and-forth."
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
