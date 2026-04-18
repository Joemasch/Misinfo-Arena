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

    st.markdown(
        '<div class="sr-insight"><b>Key finding:</b> The debunker wins 100% of debates '
        'in every matchup — except when <b>Gemini Flash</b> is the debunker (0% win rate). '
        'Every spreader win and draw in the dataset involves Gemini as the debunker.</div>',
        unsafe_allow_html=True,
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

    # ── Claim difficulty ─────────────────────────────────────────────
    st.markdown('<p class="sr-finding">Claim Difficulty Ranking</p>', unsafe_allow_html=True)
    st.markdown('<p class="sr-question">Which claims are hardest to debunk? Ranked by spreader win rate and score margin.</p>', unsafe_allow_html=True)

    claim_data = defaultdict(lambda: {"spr_wins": 0, "total": 0, "margins": []})
    for ep in episodes:
        claim = ep.get("claim", "?")
        claim_data[claim]["total"] += 1
        t = ep["results"].get("totals", {})
        if t.get("debunker") is not None and t.get("spreader") is not None:
            claim_data[claim]["margins"].append(t["debunker"] - t["spreader"])
        if ep["results"]["winner"] == "spreader":
            claim_data[claim]["spr_wins"] += 1

    claims_sorted = sorted(claim_data.keys(),
                          key=lambda c: claim_data[c]["spr_wins"]/max(claim_data[c]["total"],1),
                          reverse=True)
    claim_labels = [c[:40] + ("…" if len(c) > 40 else "") for c in claims_sorted]
    spr_rates = [claim_data[c]["spr_wins"]/max(claim_data[c]["total"],1)*100 for c in claims_sorted]
    avg_margins = [sum(claim_data[c]["margins"])/max(len(claim_data[c]["margins"]),1) for c in claims_sorted]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Spreader win %",
        x=claim_labels, y=spr_rates,
        marker_color=SPREADER_COLOR, opacity=0.85,
        text=[f"{r:.0f}% (n={claim_data[c]['total']})" for r,c in zip(spr_rates, claims_sorted)],
        textposition="outside", textfont=dict(size=9),
    ))
    fig.update_layout(
        yaxis=dict(title="Spreader win rate %", range=[0, 40], gridcolor="#2A2A2A"),
        xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
        height=350, margin=dict(t=20, b=120, l=50, r=20),
        **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_strategies(episodes):
    """Strategies tab: fingerprints + claim type adaptation."""
    # ── Finding 1: Fingerprints ──────────────────────────────────────
    st.markdown('<p class="sr-finding">Finding 1: Model Strategy Fingerprints</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Each model has a distinct rhetorical playbook. What tactics does each model '
        'default to as spreader and as debunker?'
        '</p>',
        unsafe_allow_html=True,
    )

    for role, side_key, color, strat_field in [
        ("As Spreader", "spreader", SPREADER_COLOR, "spreader_strategies"),
        ("As Debunker", "debunker", DEBUNKER_COLOR, "debunker_strategies"),
    ]:
        model_strats = defaultdict(Counter)
        model_eps = Counter()
        for ep in episodes:
            model = ep["config_snapshot"]["agents"][side_key]["model"]
            sa = ep.get("strategy_analysis") or {}
            for s in sa.get(strat_field, []):
                model_strats[model][s] += 1
            model_eps[model] += 1

        st.markdown(f"**{role}**")
        fig = go.Figure()
        for model in sorted(model_strats.keys()):
            counts = model_strats[model]
            total = sum(counts.values())
            top = counts.most_common(6)
            fig.add_trace(go.Bar(
                name=_short(model),
                x=[_label(s) for s, _ in top],
                y=[n/total*100 for _, n in top],
                text=[f"{n/total*100:.0f}%" for _, n in top],
                textposition="outside", textfont=dict(size=9),
            ))
        fig.update_layout(
            barmode="group",
            yaxis=dict(title="% of tactics", gridcolor="#2A2A2A", range=[0, 60]),
            xaxis=dict(tickfont=dict(size=10), tickangle=-25),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
            height=380, margin=dict(t=50, b=80, l=50, r=20), **_pb(),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Insight
    spr_by_model = defaultdict(Counter)
    for ep in episodes:
        m = ep["config_snapshot"]["agents"]["spreader"]["model"]
        sa = ep.get("strategy_analysis") or {}
        for s in sa.get("spreader_strategies", []):
            spr_by_model[m][s] += 1
    top_per = {m: c.most_common(1)[0] for m, c in spr_by_model.items() if c}
    st.markdown(
        '<div class="sr-insight"><b>Key insight:</b> ' +
        ". ".join(f'{_short(m)} leads with <b>{_label(s)}</b> ({n/sum(spr_by_model[m].values())*100:.0f}%)'
                  for m, (s, n) in sorted(top_per.items())) +
        '.</div>', unsafe_allow_html=True,
    )

    # ── Finding 2: Claim type adaptation ─────────────────────────────
    st.markdown('<p class="sr-finding">Finding 2: Strategy Adaptation by Claim Type</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do spreaders use different tactics for political claims vs health claims? '
        'This shows the primary strategy per claim type — aggregated across all models.'
        '</p>',
        unsafe_allow_html=True,
    )

    claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))

    # Primary strategy distribution by claim type (spreader)
    type_strats = defaultdict(Counter)
    for ep in episodes:
        ct = ep.get("claim_type", "?")
        sa = ep.get("strategy_analysis") or {}
        primary = sa.get("spreader_primary", "")
        if primary:
            type_strats[ct][primary] += 1

    fig = go.Figure()
    # Get top strategies across all types
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

    st.markdown(
        '<div class="sr-insight"><b>Key insight:</b> Spreader strategy adapts to the domain. '
        'Health claims trigger <b>anecdotal evidence</b>. Political claims trigger <b>emotional appeal</b>. '
        'Economic claims trigger <b>appeal to conspiracy</b>. '
        'This suggests AI models tailor their misinformation tactics to the topic.</div>',
        unsafe_allow_html=True,
    )


def _render_game_theory(episodes):
    """Game Theory tab: adaptation signals."""
    st.markdown('<p class="sr-finding">Finding 3: Strategic Adaptation</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'How do the agents influence each other? Does the debunker\'s tactic-naming '
        'cause the spreader to shift, and which model is best at disrupting the opponent?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Tactic-naming rate by debunker model
    st.markdown("**Tactic-naming rate by debunker model**")
    naming = defaultdict(lambda: {"names": 0, "total": 0})
    for ep in episodes:
        m = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        naming[m]["total"] += 1
        if any(s in sa.get("debunker_strategies", []) for s in ["logical_refutation", "contradiction_exposure"]):
            naming[m]["names"] += 1

    nm = sorted(naming.keys())
    rates = [naming[m]["names"]/max(naming[m]["total"],1)*100 for m in nm]
    fig = go.Figure(go.Bar(
        x=[_short(m) for m in nm], y=rates,
        marker_color=DEBUNKER_COLOR,
        text=[f"{r:.0f}%<br>n={naming[m]['total']}" for r,m in zip(rates,nm)],
        textposition="outside", textfont=dict(size=10),
    ))
    fig.update_layout(yaxis=dict(title="% of episodes", range=[0,120], gridcolor="#2A2A2A"),
                     height=300, margin=dict(t=15,b=40,l=50,r=10), **_pb())
    st.plotly_chart(fig, use_container_width=True)

    # Strategy diversity by model × turn length
    st.markdown("**Does strategic diversity increase with debate length?**")

    c1, c2 = st.columns(2)
    for col, role, side_key, strat_field, color in [
        (c1, "Spreader", "spreader", "spreader_strategies", SPREADER_COLOR),
        (c2, "Debunker", "debunker", "debunker_strategies", DEBUNKER_COLOR),
    ]:
        with col:
            st.markdown(f"**{role} tactics**")
            div = defaultdict(lambda: defaultdict(list))
            for ep in episodes:
                m = ep["config_snapshot"]["agents"][side_key]["model"]
                t = ep["results"]["completed_turn_pairs"]
                sa = ep.get("strategy_analysis") or {}
                div[m][t].append(len(sa.get(strat_field, [])))

            fig = go.Figure()
            for model in sorted(div.keys()):
                turns = sorted(div[model].keys())
                means = [sum(div[model][t])/len(div[model][t]) for t in turns]
                fig.add_trace(go.Scatter(
                    x=turns, y=means, mode="lines+markers", name=_short(model),
                    hovertemplate=f"{_short(model)}<br>%{{x}}t: %{{y:.1f}}<extra></extra>",
                ))
            fig.update_layout(
                xaxis=dict(title="Turns", tickvals=[2,6,10], gridcolor="#2A2A2A"),
                yaxis=dict(title="Avg tactics/ep", gridcolor="#2A2A2A"),
                legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", font=dict(size=10)),
                height=320, margin=dict(t=40,b=50,l=50,r=10), **_pb(),
            )
            st.plotly_chart(fig, use_container_width=True)


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
    st.markdown(
        f'<div class="sr-insight"><b>Key insight:</b> '
        f'<b>{_short(best[0])}</b> cites {best[1]["named"]/max(best[1]["eps"],1):.1f} named sources per episode. '
        f'<b>{_short(worst[0])}</b> cites only {worst[1]["named"]/max(worst[1]["eps"],1):.1f}. '
        f'This dramatically affects debunking credibility.</div>',
        unsafe_allow_html=True,
    )

    # Dimension scores by debunker model (explains WHY citation matters)
    st.markdown('<p class="sr-finding">Dimension Scores by Debunker Model</p>', unsafe_allow_html=True)
    st.markdown('<p class="sr-question">How does citation quality translate to judge scores?</p>', unsafe_allow_html=True)

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
        yaxis=dict(title="Avg unique tactics/ep", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350, margin=dict(t=40,b=50,l=50,r=20), **_pb(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per model
    st.markdown("**Per-model breakdown (spreader role)**")
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
        yaxis=dict(title="Avg spreader tactics", gridcolor="#2A2A2A"),
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
