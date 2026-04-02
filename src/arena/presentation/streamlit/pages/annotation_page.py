"""
Human Annotation Page for Misinformation Arena v2.

Load any stored episode, read the full transcript, rate who won and
how convincing each side was, then save the annotation to
annotations/annotations.jsonl.

Computes human-AI agreement stats (simple % and Cohen's kappa) so
researchers can evaluate judge quality.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import streamlit as st

ANNOTATIONS_PATH = Path("annotations/annotations.jsonl")
RUNS_DIR = "runs"

SPREADER_COLOR = "#E8524A"
DEBUNKER_COLOR = "#3A7EC7"
DRAW_COLOR     = "#F0A500"


def _inject_styles():
    st.markdown("""
    <style>
    .an-page-title {
        font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em;
        color: #111; margin-bottom: 0.15rem;
    }
    .an-page-subtitle {
        font-size: 1rem; color: #555; margin-bottom: 1.5rem; line-height: 1.5;
    }
    .an-section {
        font-size: 1.35rem; font-weight: 700; color: #111;
        margin-top: 2rem; margin-bottom: 0.3rem;
        padding-bottom: 0.3rem; border-bottom: 2px solid #e8e8e8;
    }
    .an-prose {
        font-size: 0.95rem; color: #444; line-height: 1.65;
        margin-bottom: 1rem; max-width: 760px;
    }
    .an-metric-grid {
        display: flex; gap: 1rem; margin: 1rem 0 1.5rem 0; flex-wrap: wrap;
    }
    .an-metric-card {
        flex: 1; min-width: 130px;
        background: #fff; border: 1px solid #e4e4e4;
        border-radius: 8px; padding: 0.9rem 1.1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .an-metric-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.07em; color: #888; margin-bottom: 0.2rem;
    }
    .an-metric-value {
        font-size: 1.8rem; font-weight: 700; color: #111; line-height: 1.1;
    }
    .an-metric-sub { font-size: 0.78rem; color: #777; margin-top: 0.15rem; }
    .an-divider { border: none; border-top: 1px solid #e5e7eb; margin: 1.8rem 0; }
    .an-verdict-card {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 10px; padding: 1rem 1.3rem;
        margin: 0.8rem 0 1rem 0; background: transparent;
    }
    .an-claim-banner {
        border-left: 4px solid #3A7EC7;
        background: rgba(58,126,199,0.06);
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 1.1rem; margin-bottom: 1rem;
    }
    .an-turn-label {
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; color: #9ca3af;
        margin: 1.2rem 0 0.5rem 0;
    }
    .an-bubble {
        border-radius: 10px; padding: 0.8rem 1rem;
        margin-bottom: 0.5rem; line-height: 1.6; font-size: 0.93rem;
    }
    .an-bubble-spreader {
        background: rgba(232,82,74,0.05); border-left: 3px solid #E8524A;
    }
    .an-bubble-debunker {
        background: rgba(58,126,199,0.05); border-left: 3px solid #3A7EC7;
    }
    .an-bubble-role {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.07em; margin-bottom: 0.3rem;
    }
    .an-kappa-good { color: #16a34a; }
    .an-kappa-moderate { color: #d97706; }
    .an-kappa-poor { color: #dc2626; }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_annotations() -> list[dict]:
    if not ANNOTATIONS_PATH.exists():
        return []
    try:
        lines = ANNOTATIONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()]
    except Exception:
        return []


def _save_annotation(record: dict) -> None:
    ANNOTATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ANNOTATIONS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _list_runs() -> list[str]:
    from arena.io.run_store_v2_read import list_runs
    try:
        return [r["run_id"] for r in list_runs(RUNS_DIR)]
    except Exception:
        return []


def _load_episodes(run_id: str) -> list[dict]:
    from arena.io.run_store_v2_read import load_episodes
    try:
        result = load_episodes(run_id, RUNS_DIR)
        # load_episodes returns (episodes_list, warnings) tuple
        if isinstance(result, tuple):
            return result[0]
        return result
    except Exception:
        return []


def _fmt_claim(ep: dict) -> str:
    claim = ep.get("claim", ep.get("topic", "Unknown claim"))
    return (claim[:80] + "…") if len(claim) > 80 else claim


def _extract_turns(ep: dict) -> list[dict]:
    """Return list of {spreader, debunker} dicts."""
    raw = ep.get("turns", [])
    paired: list[dict] = []
    for t in raw:
        if isinstance(t, dict):
            s_msg = t.get("spreader_message", {})
            d_msg = t.get("debunker_message", {})
            s_text = s_msg.get("content", "") if isinstance(s_msg, dict) else str(s_msg)
            d_text = d_msg.get("content", "") if isinstance(d_msg, dict) else str(d_msg)
            if s_text or d_text:
                paired.append({"spreader": s_text, "debunker": d_text})
    return paired


# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------

def _cohens_kappa(human_labels: list[str], ai_labels: list[str]) -> float | None:
    """Simple Cohen's kappa for multi-class labels."""
    if not human_labels or len(human_labels) != len(ai_labels):
        return None
    n = len(human_labels)
    classes = sorted(set(human_labels) | set(ai_labels))
    # Observed agreement
    po = sum(1 for h, a in zip(human_labels, ai_labels) if h == a) / n
    # Expected agreement
    pe = 0.0
    for cls in classes:
        ph = human_labels.count(cls) / n
        pa = ai_labels.count(cls) / n
        pe += ph * pa
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


# ---------------------------------------------------------------------------
# Annotation stats
# ---------------------------------------------------------------------------

def _render_agreement_stats(annotations: list[dict]) -> None:
    """Show human-AI agreement metrics with styled KPI cards."""
    if len(annotations) < 2:
        st.caption("Annotate at least 2 episodes to see agreement stats.")
        return

    human = [a["human_winner"] for a in annotations]
    ai    = [a["ai_winner"]    for a in annotations]

    matches = sum(1 for h, a in zip(human, ai) if h == a)
    pct = matches / len(human)

    kappa = _cohens_kappa(human, ai)
    kappa_label = (
        "Excellent" if kappa and kappa > 0.8 else
        "Good"      if kappa and kappa > 0.6 else
        "Moderate"  if kappa and kappa > 0.4 else
        "Fair"      if kappa and kappa > 0.2 else
        "Poor"
    ) if kappa is not None else "—"
    kappa_class = (
        "an-kappa-good" if kappa and kappa > 0.6 else
        "an-kappa-moderate" if kappa and kappa > 0.2 else
        "an-kappa-poor"
    ) if kappa is not None else ""
    kappa_str = f"{kappa:.2f}" if kappa is not None else "—"

    st.markdown(
        f'<div class="an-metric-grid">'
        f'<div class="an-metric-card"><div class="an-metric-label">Annotations</div>'
        f'<div class="an-metric-value">{len(annotations)}</div></div>'
        f'<div class="an-metric-card"><div class="an-metric-label">Agreement with AI</div>'
        f'<div class="an-metric-value" style="color:{DEBUNKER_COLOR}">{pct:.0%}</div></div>'
        f'<div class="an-metric-card"><div class="an-metric-label">Cohen\'s κ</div>'
        f'<div class="an-metric-value {kappa_class}">{kappa_str}</div>'
        f'<div class="an-metric-sub">{kappa_label}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="an-prose">'
        '<b>Agreement %</b> = how often your winner matches the AI judge. '
        '<b>Cohen\'s κ</b> corrects for chance agreement — κ > 0.6 is generally considered good.'
        '</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------

def render_annotation_page():
    _inject_styles()

    st.markdown('<p class="an-page-title">Human Annotation</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="an-page-subtitle">'
        'Read a debate transcript and rate who won. '
        'Your ratings are saved and compared against the AI judge to measure human-AI agreement.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Agreement summary ─────────────────────────────────────────────────────
    all_annotations = _load_annotations()
    with st.expander(f"Agreement stats ({len(all_annotations)} annotations so far)", expanded=len(all_annotations) > 0):
        _render_agreement_stats(all_annotations)

    st.markdown('<hr class="an-divider">', unsafe_allow_html=True)

    # ── Episode selector ──────────────────────────────────────────────────────
    st.markdown('<p class="an-section">Select Episode</p>', unsafe_allow_html=True)
    runs = _list_runs()
    if not runs:
        st.info("No runs found. Complete some debates first, then come back to annotate them.")
        return

    selected_run = st.selectbox(
        "Run",
        options=runs,
        key="annot_run_id",
    )

    episodes = _load_episodes(selected_run) if selected_run else []
    if not episodes:
        st.info("No episodes found in this run.")
        return

    ep_labels = [f"Episode {i}: {_fmt_claim(ep)}" for i, ep in enumerate(episodes)]
    selected_ep_idx = st.selectbox(
        "Episode",
        options=list(range(len(episodes))),
        format_func=lambda i: ep_labels[i],
        key="annot_ep_idx",
    )
    ep = episodes[selected_ep_idx]

    # Check if already annotated
    ep_key = f"{selected_run}_{selected_ep_idx}"
    already_annotated = any(
        a.get("episode_key") == ep_key for a in all_annotations
    )

    # ── Transcript ────────────────────────────────────────────────────────────
    st.markdown('<hr class="an-divider">', unsafe_allow_html=True)
    st.markdown('<p class="an-section">Transcript</p>', unsafe_allow_html=True)
    claim = ep.get("claim", ep.get("topic", "—"))
    st.markdown(
        f'<div class="an-claim-banner">'
        f'<div class="an-bubble-role" style="color:{DEBUNKER_COLOR}">Claim</div>'
        f'<span style="font-weight:600;color:#1a1a2e">{claim}</span></div>',
        unsafe_allow_html=True,
    )

    turns = _extract_turns(ep)
    if not turns:
        st.warning("No transcript turns found in this episode.")
    else:
        for i, t in enumerate(turns):
            st.markdown(f'<div class="an-turn-label">Turn {i+1}</div>', unsafe_allow_html=True)
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                st.markdown(
                    f'<div class="an-bubble an-bubble-spreader">'
                    f'<div class="an-bubble-role" style="color:{SPREADER_COLOR}">Spreader</div>'
                    f'{t["spreader"]}</div>',
                    unsafe_allow_html=True,
                )
            with t_col2:
                st.markdown(
                    f'<div class="an-bubble an-bubble-debunker">'
                    f'<div class="an-bubble-role" style="color:{DEBUNKER_COLOR}">Fact-checker</div>'
                    f'{t["debunker"]}</div>',
                    unsafe_allow_html=True,
                )

    # AI verdict
    results = ep.get("results", {})
    ai_winner = results.get("winner", ep.get("winner", "unknown"))
    ai_conf   = results.get("judge_confidence", results.get("confidence", 0))
    ai_reason = results.get("reason", "")

    _verdict_border = DEBUNKER_COLOR if ai_winner == "debunker" else SPREADER_COLOR if ai_winner == "spreader" else DRAW_COLOR
    _reason_html = f'<br><span style="font-size:0.9rem;color:#555">{ai_reason[:200]}…</span>' if ai_reason else ""
    st.markdown(
        f'<div class="an-verdict-card" style="border-left:5px solid {_verdict_border}">'
        f'<div class="an-bubble-role" style="color:#b45309">AI Judge Verdict</div>'
        f'<b>{ai_winner.title()}</b> won · Confidence {float(ai_conf):.0%}'
        f'{_reason_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Annotation form ───────────────────────────────────────────────────────
    st.markdown('<hr class="an-divider">', unsafe_allow_html=True)
    if already_annotated:
        st.success("You have already annotated this episode.")
        if st.button("Annotate again (override)", key="annot_override"):
            pass  # allow re-annotation below
        else:
            return

    st.markdown('<p class="an-section">Your Rating</p>', unsafe_allow_html=True)

    winner_options = ["debunker", "spreader", "draw"]
    winner_labels  = {"debunker": "Fact-checker", "spreader": "Spreader", "draw": "Draw"}
    human_winner = st.radio(
        "Who won this debate?",
        options=winner_options,
        format_func=lambda x: winner_labels[x],
        horizontal=True,
        key="annot_winner",
    )

    rate_col1, rate_col2 = st.columns(2)
    with rate_col1:
        spr_conviction = st.slider(
            "Spreader conviction (1 = very weak, 5 = very convincing)",
            min_value=1, max_value=5, value=3, key="annot_spr_conv",
        )
    with rate_col2:
        deb_conviction = st.slider(
            "Fact-checker conviction (1 = very weak, 5 = very convincing)",
            min_value=1, max_value=5, value=3, key="annot_deb_conv",
        )

    notes = st.text_area(
        "Notes (optional)",
        placeholder="Any observations about the debate quality, tactics used, etc.",
        key="annot_notes",
        height=80,
    )

    if st.button("💾 Save Annotation", type="primary", key="annot_save_btn"):
        record = {
            "episode_key":     ep_key,
            "run_id":          selected_run,
            "episode_idx":     selected_ep_idx,
            "claim":           claim,
            "annotated_at":    datetime.now().isoformat(),
            "human_winner":    human_winner,
            "ai_winner":       ai_winner,
            "ai_confidence":   float(ai_conf),
            "spr_conviction":  spr_conviction,
            "deb_conviction":  deb_conviction,
            "notes":           notes,
            "agreement":       human_winner == ai_winner,
        }
        _save_annotation(record)
        st.toast("Annotation saved!", icon="✅")
        st.rerun()

    # ── Download all annotations ──────────────────────────────────────────────
    if all_annotations:
        st.markdown('<hr class="an-divider">', unsafe_allow_html=True)
        st.download_button(
            "⬇ Download all annotations as JSON",
            data=json.dumps(all_annotations, indent=2),
            file_name="annotations.json",
            mime="application/json",
        )
