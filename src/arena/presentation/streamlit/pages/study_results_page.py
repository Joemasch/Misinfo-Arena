"""
Study Results Page — model-centered strategy and citation analysis.

Visualizes the 5 research findings from the unified experiment:
1. Model strategy fingerprints
2. Strategy × claim type adaptation
3. Game theory (strategic adaptation)
4. Citation quality by model
5. Strategy depth plateau with debate length
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

# Short display names for models
_MODEL_SHORT = {
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4-20250514": "Claude Sonnet",
    "claude-sonnet-4": "Claude Sonnet",
    "gemini-2.5-flash": "Gemini Flash",
}

# Named source keywords for citation extraction
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


def _plotly_base(**overrides) -> dict:
    base = {k: v for k, v in PLOTLY_LAYOUT.items()
            if k in ("paper_bgcolor", "plot_bgcolor", "font")}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_experiment_data(run_ids: tuple, runs_dir: str, token: float) -> list[dict]:
    """Load all successful experiment episodes as raw dicts."""
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


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

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
        font-size: 1.5rem; font-weight: 700;
        color: var(--color-text-primary, #E8E4D9);
        margin: 2.5rem 0 0.3rem 0; padding-bottom: 0.4rem;
        border-bottom: 3px solid var(--color-accent-red, #C9363E);
    }
    .sr-question {
        font-size: 0.95rem; color: var(--color-text-muted, #888);
        line-height: 1.6; margin-bottom: 1rem; max-width: 760px;
    }
    .sr-insight {
        background: rgba(74,127,165,0.08); border-left: 4px solid #4A7FA5;
        border-radius: 0 6px 6px 0; padding: 0.8rem 1.1rem;
        margin: 0.8rem 0 1.5rem 0; font-size: 0.95rem;
        color: var(--color-text-primary, #E8E4D9); line-height: 1.6;
    }
    .sr-kpi-grid {
        display: flex; gap: 1rem; margin: 1rem 0 1.5rem 0; flex-wrap: wrap;
    }
    .sr-kpi {
        flex: 1; min-width: 130px;
        background: var(--color-surface, #111); border: 1px solid var(--color-border, #2A2A2A);
        border-radius: 8px; padding: 0.8rem 1rem;
    }
    .sr-kpi-label {
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.07em; color: #9ca3af; margin-bottom: 0.15rem;
    }
    .sr-kpi-value {
        font-size: 1.6rem; font-weight: 700; color: var(--color-text-primary, #E8E4D9);
    }
    .sr-kpi-sub { font-size: 0.75rem; color: #9ca3af; }
    .sr-divider { border: none; border-top: 1px solid var(--color-border, #2A2A2A); margin: 2rem 0; }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_study_results_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    st.markdown('<p class="sr-title">Study Results</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-subtitle">'
        'Model-centered analysis of AI argumentation strategies and citation quality '
        'across 480 adversarial misinformation debates.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Load data ────────────────────────────────────────────────────────
    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None)

    if not run_ids:
        st.info("No experiment data. Run the experiment first.")
        return

    episodes = _load_experiment_data(tuple(run_ids), RUNS_DIR, token)

    if not episodes:
        st.info("No experiment episodes found. Upload and run `data/experiment_spec.csv` in Arena > Experiment.")
        return

    # ── Overview KPIs ────────────────────────────────────────────────────
    n_eps = len(episodes)
    winners = Counter(ep["results"]["winner"] for ep in episodes)
    deb_pct = winners.get("debunker", 0) / n_eps * 100
    spr_pct = winners.get("spreader", 0) / n_eps * 100
    draw_pct = winners.get("draw", 0) / n_eps * 100
    models = sorted(set(
        ep["config_snapshot"]["agents"]["spreader"]["model"] for ep in episodes
    ))

    st.markdown(
        f'<div class="sr-kpi-grid">'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Episodes</div>'
        f'<div class="sr-kpi-value">{n_eps}</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Debunker Wins</div>'
        f'<div class="sr-kpi-value" style="color:{DEBUNKER_COLOR}">{deb_pct:.0f}%</div>'
        f'<div class="sr-kpi-sub">{winners.get("debunker", 0)} episodes</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Spreader Wins</div>'
        f'<div class="sr-kpi-value" style="color:{SPREADER_COLOR}">{spr_pct:.0f}%</div>'
        f'<div class="sr-kpi-sub">{winners.get("spreader", 0)} episodes</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Draws</div>'
        f'<div class="sr-kpi-value">{draw_pct:.0f}%</div>'
        f'<div class="sr-kpi-sub">{winners.get("draw", 0)} episodes</div></div>'
        f'<div class="sr-kpi"><div class="sr-kpi-label">Models</div>'
        f'<div class="sr-kpi-value">{len(models)}</div>'
        f'<div class="sr-kpi-sub">{", ".join(_short(m) for m in models)}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ==================================================================
    # FINDING 1: MODEL STRATEGY FINGERPRINTS
    # ==================================================================
    st.markdown('<p class="sr-finding">Finding 1: Model Strategy Fingerprints</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Does each model have a distinct rhetorical playbook? When assigned the spreader role, '
        'which manipulation tactics does each model reach for first? As debunker, which '
        'counter-strategies dominate?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Build strategy counts per model per role
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
            labels = [_label(s) for s, _ in top]
            values = [n / total * 100 for _, n in top]

            fig.add_trace(go.Bar(
                name=_short(model),
                x=labels,
                y=values,
                text=[f"{v:.0f}%" for v in values],
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate=f"{_short(model)}<br>%{{x}}: %{{y:.1f}}%<extra></extra>",
            ))

        fig.update_layout(
            barmode="group",
            yaxis=dict(title="% of tactics used", gridcolor="#2A2A2A", range=[0, 60]),
            xaxis=dict(tickfont=dict(size=11), tickangle=-25),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
            height=400,
            margin=dict(t=50, b=80, l=50, r=20),
            **_plotly_base(),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Insight callout
    # Find the most distinctive model
    spr_by_model = defaultdict(Counter)
    for ep in episodes:
        model = ep["config_snapshot"]["agents"]["spreader"]["model"]
        sa = ep.get("strategy_analysis") or {}
        for s in sa.get("spreader_strategies", []):
            spr_by_model[model][s] += 1

    top_per_model = {m: c.most_common(1)[0] for m, c in spr_by_model.items() if c}
    st.markdown(
        '<div class="sr-insight">'
        '<b>Key insight:</b> ' +
        ". ".join(
            f'{_short(m)} leads with <b>{_label(s)}</b> ({n} times)'
            for m, (s, n) in sorted(top_per_model.items())
        ) +
        '.</div>',
        unsafe_allow_html=True,
    )

    # ==================================================================
    # FINDING 2: STRATEGY × CLAIM TYPE
    # ==================================================================
    st.markdown('<hr class="sr-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sr-finding">Finding 2: Strategy Adaptation by Claim Type</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do models change their tactics based on the claim domain? Does the spreader '
        'use conspiracy framing for political claims but anecdotal evidence for health claims?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Heatmap: model (as spreader) × claim type → dominant strategy
    claim_types = sorted(set(ep.get("claim_type", "?") for ep in episodes))

    for role, side_key, strat_field, colorscale in [
        ("Spreader", "spreader", "spreader_strategies", "Reds"),
        ("Debunker", "debunker", "debunker_strategies", "Blues"),
    ]:
        st.markdown(f"**{role} dominant strategy by claim type**")

        # Build: model × claim_type → most common strategy
        grid_data = {}
        for ep in episodes:
            model = _short(ep["config_snapshot"]["agents"][side_key]["model"])
            ct = ep.get("claim_type", "?")
            sa = ep.get("strategy_analysis") or {}
            primary = sa.get(f"{side_key}_primary", "")
            if primary:
                key = (model, ct)
                if key not in grid_data:
                    grid_data[key] = Counter()
                grid_data[key][primary] += 1

        model_names = sorted(set(k[0] for k in grid_data.keys()))
        z = []
        text = []
        for model in model_names:
            row_z = []
            row_text = []
            for ct in claim_types:
                counts = grid_data.get((model, ct), Counter())
                if counts:
                    top_strat, top_count = counts.most_common(1)[0]
                    total = sum(counts.values())
                    row_z.append(top_count / total * 100)
                    row_text.append(f"{_label(top_strat)}<br>{top_count}/{total}")
                else:
                    row_z.append(0)
                    row_text.append("—")
            z.append(row_z)
            text.append(row_text)

        fig = go.Figure(go.Heatmap(
            z=z,
            x=claim_types,
            y=model_names,
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=10),
            colorscale=colorscale,
            showscale=False,
            hovertemplate="%{y} on %{x}<br>%{text}<extra></extra>",
        ))
        fig.update_layout(
            xaxis=dict(tickfont=dict(size=11)),
            yaxis=dict(tickfont=dict(size=12), autorange="reversed"),
            height=250,
            margin=dict(t=10, b=40, l=120, r=20),
            **_plotly_base(),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ==================================================================
    # FINDING 3: GAME THEORY
    # ==================================================================
    st.markdown('<hr class="sr-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sr-finding">Finding 3: Strategic Adaptation</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Does the debunker\'s tactic-naming cause the spreader to shift strategies? '
        'Which model as debunker is most effective at disrupting the spreader\'s playbook?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Tactic-naming rate by debunker model
    naming_by_model = defaultdict(lambda: {"names": 0, "total": 0})
    for ep in episodes:
        model = ep["config_snapshot"]["agents"]["debunker"]["model"]
        sa = ep.get("strategy_analysis") or {}
        deb_strats = sa.get("debunker_strategies", [])
        naming_by_model[model]["total"] += 1
        # "logical_refutation" and "contradiction_exposure" are tactic-naming strategies
        if any(s in deb_strats for s in ["logical_refutation", "contradiction_exposure"]):
            naming_by_model[model]["names"] += 1

    naming_models = sorted(naming_by_model.keys())
    naming_rates = [naming_by_model[m]["names"] / max(naming_by_model[m]["total"], 1) * 100
                    for m in naming_models]

    fig = go.Figure(go.Bar(
        x=[_short(m) for m in naming_models],
        y=naming_rates,
        marker_color=DEBUNKER_COLOR,
        text=[f"{r:.0f}%" for r in naming_rates],
        textposition="outside",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        yaxis=dict(title="% of episodes with tactic-naming", range=[0, 110], gridcolor="#2A2A2A"),
        height=300,
        margin=dict(t=20, b=40, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Strategy diversity by model × turn length (adaptation proxy)
    st.markdown("**Strategy diversity by debate length (adaptation proxy)**")

    div_data = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        model = ep["config_snapshot"]["agents"]["spreader"]["model"]
        turns = ep["results"]["completed_turn_pairs"]
        sa = ep.get("strategy_analysis") or {}
        n_strats = len(sa.get("spreader_strategies", []))
        div_data[model][turns].append(n_strats)

    fig = go.Figure()
    for model in sorted(div_data.keys()):
        turn_vals = sorted(div_data[model].keys())
        means = [sum(div_data[model][t]) / len(div_data[model][t]) for t in turn_vals]
        fig.add_trace(go.Scatter(
            x=turn_vals, y=means,
            mode="lines+markers",
            name=_short(model),
            hovertemplate=f"{_short(model)}<br>%{{x}} turns: %{{y:.1f}} tactics<extra></extra>",
        ))

    fig.update_layout(
        xaxis=dict(title="Debate length (turns)", tickvals=[2, 6, 10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg unique tactics per episode", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350,
        margin=dict(t=40, b=50, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ==================================================================
    # FINDING 4: CITATION QUALITY
    # ==================================================================
    st.markdown('<hr class="sr-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sr-finding">Finding 4: Citation Quality by Model</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Which model produces the most trustworthy sources as debunker? '
        'Do some models cite named institutions while others rely on vague appeals?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Extract citation signals per episode
    cite_by_model = defaultdict(lambda: {"named": 0, "vague": 0, "urls": 0, "eps": 0})
    cite_by_model_type = defaultdict(lambda: defaultdict(lambda: {"named": 0, "eps": 0}))

    for ep in episodes:
        deb_model = ep["config_snapshot"]["agents"]["debunker"]["model"]
        ct = ep.get("claim_type", "?")
        cite_by_model[deb_model]["eps"] += 1
        cite_by_model_type[deb_model][ct]["eps"] += 1

        for t in ep.get("turns", []):
            d_msg = t.get("debunker_message", {})
            text = d_msg.get("content", "") if isinstance(d_msg, dict) else ""
            text_lower = text.lower()

            if "http" in text_lower:
                cite_by_model[deb_model]["urls"] += 1

            for src in _NAMED_SOURCES:
                if src.lower() in text_lower:
                    cite_by_model[deb_model]["named"] += 1
                    cite_by_model_type[deb_model][ct]["named"] += 1
                    break

            for kw in _VAGUE_KEYWORDS:
                if kw in text_lower:
                    cite_by_model[deb_model]["vague"] += 1
                    break

    # Bar chart: citation types by model
    cite_models = sorted(cite_by_model.keys())
    fig = go.Figure()

    for cite_type, label, color in [
        ("named", "Named Sources", DEBUNKER_COLOR),
        ("vague", "Vague Appeals", SPREADER_COLOR),
        ("urls", "URLs", ACCENT_GREEN),
    ]:
        values = [cite_by_model[m][cite_type] / max(cite_by_model[m]["eps"], 1) for m in cite_models]
        fig.add_trace(go.Bar(
            name=label,
            x=[_short(m) for m in cite_models],
            y=values,
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
            textfont=dict(size=10),
            marker_color=color,
            hovertemplate=f"{label}<br>%{{x}}: %{{y:.1f}} per episode<extra></extra>",
        ))

    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Citations per episode (avg)", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350,
        margin=dict(t=50, b=40, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Named sources by model × claim type
    st.markdown("**Named source density by model and claim type**")

    fig = go.Figure()
    for model in sorted(cite_by_model_type.keys()):
        types = sorted(cite_by_model_type[model].keys())
        vals = [cite_by_model_type[model][ct]["named"] / max(cite_by_model_type[model][ct]["eps"], 1)
                for ct in types]
        fig.add_trace(go.Bar(
            name=_short(model),
            x=types,
            y=vals,
            text=[f"{v:.1f}" for v in vals],
            textposition="outside",
            textfont=dict(size=10),
            hovertemplate=f"{_short(model)}<br>%{{x}}: %{{y:.1f}} per ep<extra></extra>",
        ))

    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Named sources per episode", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350,
        margin=dict(t=50, b=40, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Insight
    best_citer = max(cite_by_model.items(), key=lambda x: x[1]["named"] / max(x[1]["eps"], 1))
    worst_citer = min(cite_by_model.items(), key=lambda x: x[1]["named"] / max(x[1]["eps"], 1))
    st.markdown(
        f'<div class="sr-insight">'
        f'<b>Key insight:</b> <b>{_short(best_citer[0])}</b> cites '
        f'{best_citer[1]["named"] / max(best_citer[1]["eps"], 1):.1f} named sources per episode as debunker. '
        f'<b>{_short(worst_citer[0])}</b> cites only '
        f'{worst_citer[1]["named"] / max(worst_citer[1]["eps"], 1):.1f}. '
        f'</div>',
        unsafe_allow_html=True,
    )

    # ==================================================================
    # FINDING 5: STRATEGY DEPTH PLATEAU
    # ==================================================================
    st.markdown('<hr class="sr-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sr-finding">Finding 5: Strategy Depth Plateau</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sr-question">'
        'Do agents use more unique tactics in longer debates, or do they recycle the same ones? '
        'Is there an optimal debate length where strategic richness peaks?'
        '</p>',
        unsafe_allow_html=True,
    )

    # Strategy diversity: both spreader and debunker on same chart
    fig = go.Figure()

    for role, side_key, strat_field, color, dash in [
        ("Spreader", "spreader", "spreader_strategies", SPREADER_COLOR, "solid"),
        ("Debunker", "debunker", "debunker_strategies", DEBUNKER_COLOR, "solid"),
    ]:
        div_by_turns = defaultdict(list)
        for ep in episodes:
            turns = ep["results"]["completed_turn_pairs"]
            sa = ep.get("strategy_analysis") or {}
            n = len(sa.get(strat_field, []))
            div_by_turns[turns].append(n)

        turn_vals = sorted(div_by_turns.keys())
        means = [sum(div_by_turns[t]) / len(div_by_turns[t]) for t in turn_vals]

        fig.add_trace(go.Scatter(
            x=turn_vals, y=means,
            mode="lines+markers",
            name=role,
            line=dict(color=color, dash=dash, width=3),
            marker=dict(size=10),
            hovertemplate=f"{role}<br>%{{x}} turns: %{{y:.2f}} tactics<extra></extra>",
        ))

    fig.update_layout(
        xaxis=dict(title="Debate length (turns)", tickvals=[2, 6, 10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg unique tactics per episode", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350,
        margin=dict(t=40, b=50, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-model breakdown
    st.markdown("**Per-model plateau (spreader role)**")

    fig = go.Figure()
    spr_div = defaultdict(lambda: defaultdict(list))
    for ep in episodes:
        model = ep["config_snapshot"]["agents"]["spreader"]["model"]
        turns = ep["results"]["completed_turn_pairs"]
        sa = ep.get("strategy_analysis") or {}
        n = len(sa.get("spreader_strategies", []))
        spr_div[model][turns].append(n)

    for model in sorted(spr_div.keys()):
        turn_vals = sorted(spr_div[model].keys())
        means = [sum(spr_div[model][t]) / len(spr_div[model][t]) for t in turn_vals]
        fig.add_trace(go.Scatter(
            x=turn_vals, y=means,
            mode="lines+markers",
            name=_short(model),
            hovertemplate=f"{_short(model)}<br>%{{x}} turns: %{{y:.2f}} tactics<extra></extra>",
        ))

    fig.update_layout(
        xaxis=dict(title="Debate length (turns)", tickvals=[2, 6, 10], gridcolor="#2A2A2A"),
        yaxis=dict(title="Avg unique spreader tactics", gridcolor="#2A2A2A"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        height=350,
        margin=dict(t=40, b=50, l=50, r=20),
        **_plotly_base(),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary insight
    div_2 = [len(ep.get("strategy_analysis", {}).get("spreader_strategies", []))
             for ep in episodes if ep["results"]["completed_turn_pairs"] == 2]
    div_6 = [len(ep.get("strategy_analysis", {}).get("spreader_strategies", []))
             for ep in episodes if ep["results"]["completed_turn_pairs"] == 6]
    div_10 = [len(ep.get("strategy_analysis", {}).get("spreader_strategies", []))
              for ep in episodes if ep["results"]["completed_turn_pairs"] == 10]

    avg_2 = sum(div_2) / max(len(div_2), 1)
    avg_6 = sum(div_6) / max(len(div_6), 1)
    avg_10 = sum(div_10) / max(len(div_10), 1)
    jump_2_6 = avg_6 - avg_2
    jump_6_10 = avg_10 - avg_6

    st.markdown(
        f'<div class="sr-insight">'
        f'<b>Key insight:</b> Spreader strategy diversity: '
        f'<b>{avg_2:.1f}</b> tactics at 2 turns → '
        f'<b>{avg_6:.1f}</b> at 6 turns (Δ={jump_2_6:+.1f}) → '
        f'<b>{avg_10:.1f}</b> at 10 turns (Δ={jump_6_10:+.1f}). '
        f'{"Plateau detected — minimal gain beyond 6 turns." if abs(jump_6_10) < abs(jump_2_6) * 0.5 else "Diversity continues to grow with length."}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ==================================================================
    # FOOTER
    # ==================================================================
    st.markdown(
        '<p style="font-size:0.82rem;color:var(--color-text-muted,#888);margin-top:2rem;'
        'line-height:1.5;text-align:center">'
        f'{n_eps} episodes · {len(models)} models · Judge: GPT-4o (fixed) · '
        'Strategy labels assigned by AI analyst post-debate · '
        'Export per-test CSVs from Tools > Exports for Minitab analysis.'
        '</p>',
        unsafe_allow_html=True,
    )
