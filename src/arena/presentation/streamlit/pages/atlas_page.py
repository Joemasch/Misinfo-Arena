"""
Atlas — Debate Reference Library.

A glossary-style reference library covering both the rhetorical strategies
AND the institutions cited in debates. Each entry shows a definition plus
a live index of which of the user's debates featured it.

Strategies (Section 1):
  • Plain-English name + raw open-coded label
  • Literature-grounded description
  • Spreader-leaning vs Fact-checker-leaning side coloring on the label
  • Per-side breakdown of episodes where the strategy appeared

Citations / institutions (Section 2):
  • Institution name with green coloring on the label
  • One-line "what they are" definition
  • Per-side breakdown of episodes where the institution was cited

If an entry hasn't appeared yet in the user's debates, the entry still
shows the definition — the Atlas works as a learning tool from day one.
"""

import json
import re
from pathlib import Path

import streamlit as st

from arena.io.run_store_v2_read import load_episodes
from arena.presentation.streamlit.state.runs_refresh import get_auto_run_ids
from arena.presentation.streamlit.data.definitions import (
    _INSTITUTION_INFO,
    get_cached_strategy_definition,
    resolve_strategy_description,
)
from arena.presentation.streamlit.pages.explore_page import (
    _NAMED_SOURCES,
    _SOURCE_PATTERNS,
    _canonical_source,
    _normalize_turn_pairs,
)


SPREADER_COLOR = "#D4A843"
DEBUNKER_COLOR = "#4A7FA5"

RUNS_DIR = "runs"


# ── Strategy catalogue ─────────────────────────────────────────────────────
# Each entry: raw_label -> (plain_name, description, canonical_side)
# canonical_side ∈ {"spreader", "debunker"} — used to color the expander label.
#
# Definitions are written to stand alone — what the tactic IS and how it
# works — followed (where useful) by a one-line research note about its
# role in our 960-episode study.
_STRATEGY_CATALOG = {
    # ── Spreader-leaning tactics ──
    "appeal to (dis)trust": (
        "Attacks Credibility",
        "Undermines the credibility of institutions, experts, or sources rather "
        "than engaging with the claims those sources make. The implicit logic is "
        "\"you can't trust the messenger, so you can ignore the message\" — bypassing "
        "the evidence by attacking its origin. "
        "Research note: Claude's signature spreader tactic on unfalsifiable claims.",
        "spreader",
    ),
    "anecdotal evidence": (
        "Personal Stories",
        "Uses individual stories or single examples as evidence for a general claim, "
        "in place of systematic data, studies, or population-level statistics. The "
        "vividness of the anecdote often substitutes for its representativeness. "
        "Research note: GPT-4o-mini's default spreader tactic, especially on Health claims.",
        "spreader",
    ),
    "pseudo-scientific claim": (
        "Pseudo-Science",
        "Presents non-scientific or unsupported claims using scientific-sounding "
        "terminology, technical formatting, or surface markers of expertise — without "
        "the underlying methodology, peer review, or replicability. The form of "
        "science is borrowed; the substance is not. "
        "Research note: Gemini's signature spreader tactic.",
        "spreader",
    ),
    "source weaponization": (
        "Misused Sources",
        "Cites real, credible institutions but misrepresents what they actually said. "
        "Three common mechanisms: selective excerpting (quote a finding, omit the "
        "conclusion), authority transfer (use the name, attach a different claim), "
        "and scope manipulation (one report becomes \"documented concerns\"). "
        "Research note: rises sharply on unfalsifiable claims across every model.",
        "spreader",
    ),
    "conspiracy theory": (
        "Conspiracy Framing",
        "Frames a pattern as the deliberate, coordinated action of a hidden powerful "
        "group. A self-sealing structure: counter-evidence is treated as further proof "
        "of the cover-up, and the absence of evidence is treated as suppression. "
        "Research note: triggers reliably when debunkers demand verification.",
        "spreader",
    ),
    "historical revisionism": (
        "Rewrites History",
        "Reinterprets, downplays, or denies established historical events to support a "
        "present-day claim. Selectively highlights, distorts, or fabricates past "
        "evidence to construct an alternative timeline that fits the desired conclusion. "
        "Research note: dominant Environmental spreader tactic in our study.",
        "spreader",
    ),
    "appeal to emotion": (
        "Emotional Appeal",
        "Uses fear, alarm, outrage, sympathy, or moral urgency to drive belief — "
        "displacing reason and evidence with affect. Effective because emotional "
        "responses are faster and stickier than analytical ones. "
        "Research note: dominant on Political and Technology claims.",
        "spreader",
    ),
    "cherry picking": (
        "Selective Evidence",
        "Presents only the data, sources, or examples that support a position while "
        "ignoring or omitting contradicting evidence that is equally available. "
        "Differs from honest summarization in that the omitted material would change "
        "the conclusion if included.",
        "spreader",
    ),
    "impossible expectations": (
        "Impossible Standards",
        "Sets a standard of proof that no realistic evidence could ever meet, then "
        "dismisses existing evidence for failing to meet it. Often takes the form of "
        "\"but you can't prove X with 100% certainty\" or \"you'd need to control for "
        "every conceivable variable.\"",
        "spreader",
    ),

    # ── Fact-checker-leaning tactics ──
    "evidence citation": (
        "Cites Research",
        "Supports a claim by referring to specific, named studies, datasets, or "
        "peer-reviewed publications that the audience could in principle look up and "
        "verify. The strength of the tactic depends on the specificity and "
        "checkability of the citation, not just the prestige of the source. "
        "Research note: the universal debunker tactic on falsifiable claims.",
        "debunker",
    ),
    "scientific consensus": (
        "Cites Consensus",
        "Appeals to the established agreement among qualified experts or major "
        "scientific bodies as evidence that a claim is accurate. Works as a shortcut "
        "when an audience can't independently evaluate the underlying methods. "
        "Research note: drops to ~0% on unfalsifiable claims, where no formal "
        "consensus exists to cite.",
        "debunker",
    ),
    "logical refutation": (
        "Logical Counter",
        "Exposes flaws in the opponent's reasoning — invalid inferences, "
        "contradictions, named fallacies, or unstated assumptions — without "
        "necessarily disputing the factual content. The argument loses on form, not "
        "(only) on facts.",
        "debunker",
    ),
    "contextual analysis": (
        "Adds Nuance",
        "Argues that the opponent's claim is technically defensible but oversimplifies "
        "a more complex situation, introducing additional factors, qualifiers, or "
        "trade-offs that change the bottom line. Often phrased as \"it's more "
        "complicated than that.\" "
        "Research note: the default fallback when direct evidence fails — wins only "
        "35% of the time.",
        "debunker",
    ),
    "mechanism explanation": (
        "Explains How It Works",
        "Explains the underlying causal process or system that produces an observed "
        "phenomenon, so the audience can evaluate the claim against how things "
        "actually function in the world. Effective when evidence is sparse but "
        "domain understanding is shared. "
        "Research note: Claude's unique tactic on unfalsifiable claims, where it "
        "achieves a 95% win rate.",
        "debunker",
    ),
    "technical correction": (
        "Corrects Data",
        "Identifies and corrects specific factual errors in the opponent's claim — "
        "wrong numbers, misattributed quotes, mistaken dates, conflated definitions — "
        "and replaces them with precise, verifiable values. Narrow and surgical "
        "compared to broader argumentative tactics.",
        "debunker",
    ),
    "verification": (
        "Demands Verification",
        "Asks the opponent to provide checkable sources, methodology, or independent "
        "confirmation for their claims rather than accepting unsupported assertions. "
        "Shifts the burden of proof back onto the asserting side. "
        "Research note: triggers a conspiracy-framing pivot from spreaders in ~17% of cases.",
        "debunker",
    ),
    "public safety": (
        "Safety Appeal",
        "Frames the dispute in terms of the direct or indirect harm that accepting the "
        "misinformation would cause — health risk, institutional erosion, social "
        "trust, vulnerable populations. Argues the stakes, not (just) the facts.",
        "debunker",
    ),
}

# ── Institution dictionary ────────────────────────────────────────────────
# What each named source is and what they do. Used in the Atlas citations
# section. Descriptions are factual and brand-neutral.
# Institution metadata moved to data/definitions.py and imported above.


def _plain_name_for(raw_label: str) -> str:
    """Look up a label in the catalogue. Fall back to a Title Case variant."""
    if not raw_label:
        return ""
    key = raw_label.lower().replace("_", " ").strip()
    if key in _STRATEGY_CATALOG:
        return _STRATEGY_CATALOG[key][0]
    return key.title()


def _side_for(plain_name: str, raw_label: str, data: dict | None = None) -> str:
    """Return the canonical side ('spreader' or 'debunker') for a strategy.

    Resolution order:
      1. Raw label is in the catalogue → use catalogue side
      2. Plain name matches a catalogue entry → use that entry's side
      3. ``data`` provided → classify by which side actually used it
         (open-coded labels from the LLM analyst end up here)
      4. Fall back to 'spreader' only as a last resort
    """
    key = (raw_label or "").lower().replace("_", " ").strip()
    if key in _STRATEGY_CATALOG:
        return _STRATEGY_CATALOG[key][2]
    for _raw, (plain, _desc, side) in _STRATEGY_CATALOG.items():
        if plain == plain_name:
            return side
    if data is not None:
        n_spr = len(data.get("spreader") or [])
        n_deb = len(data.get("debunker") or [])
        if n_deb > n_spr:
            return "debunker"
        if n_spr > n_deb:
            return "spreader"
    return "spreader"


def _short_model(model: str) -> str:
    """Trim model identifier to something friendlier."""
    if not model:
        return "?"
    aliases = {
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o-mini",
        "claude-sonnet-4-20250514": "Claude Sonnet",
        "claude-haiku-4-5-20251001": "Claude Haiku",
        "gemini-2.5-flash": "Gemini Flash",
        "gemini-2.5-flash-lite-preview-06-17": "Gemini Flash",
        "grok-3": "Grok-3",
    }
    return aliases.get(model, model[:20])


@st.cache_data(show_spinner=False)
def _scan_strategy_index(run_ids: tuple, runs_dir: str, refresh_token: float) -> dict:
    """Aggregate per-strategy episode index across all the user's runs.

    Returns a dict shaped like::

        {
            <plain_name>: {
                "raw_label":     str,
                "spreader":      [ {"run_id","episode_id","claim","spr_model",
                                    "deb_model","turns":[1,3]}, ... ],
                "debunker":      [ ... same shape ... ],
            },
            ...
        }
    """
    index = {}
    # episode-emitted definitions keyed by normalized raw label
    episode_definitions: dict[str, str] = {}

    def _ensure(plain, raw):
        if plain not in index:
            index[plain] = {"raw_label": raw, "spreader": [], "debunker": []}
        return index[plain]

    for run_id in run_ids:
        try:
            eps, _ = load_episodes(run_id, runs_dir, refresh_token)
        except Exception:
            continue
        for ep in eps:
            # Collect definitions emitted by this episode's strategy analyst
            for k, v in (ep.get("strategy_definitions") or {}).items():
                norm = (k or "").strip().lower().replace(" ", "_")
                if norm and v and norm not in episode_definitions:
                    episode_definitions[norm] = v
            pts = ep.get("per_turn_strategies") or []
            if not pts:
                continue
            cfg = ep.get("config_snapshot", {}).get("agents", {}) or {}
            spr_model = _short_model((cfg.get("spreader") or {}).get("model", ""))
            deb_model = _short_model((cfg.get("debunker") or {}).get("model", ""))
            claim = ep.get("claim", "")
            claim_type = ep.get("claim_type", "")
            ep_id = ep.get("episode_id", 0)

            spr_turns_by_label = {}
            deb_turns_by_label = {}
            for t in pts:
                turn_num = t.get("turn") or 0
                for s in (t.get("spreader_strategies") or []):
                    plain = _plain_name_for(s)
                    spr_turns_by_label.setdefault(plain, []).append(turn_num)
                for s in (t.get("debunker_strategies") or []):
                    plain = _plain_name_for(s)
                    deb_turns_by_label.setdefault(plain, []).append(turn_num)

            for plain, turns in spr_turns_by_label.items():
                raw = next(
                    (s for t in pts for s in (t.get("spreader_strategies") or [])
                     if _plain_name_for(s) == plain),
                    plain.lower().replace(" ", "_"),
                )
                _ensure(plain, raw)["spreader"].append({
                    "run_id":     run_id,
                    "episode_id": ep_id,
                    "claim":      claim,
                    "claim_type": claim_type,
                    "spr_model":  spr_model,
                    "deb_model":  deb_model,
                    "turns":      sorted(set(turns)),
                })
            for plain, turns in deb_turns_by_label.items():
                raw = next(
                    (s for t in pts for s in (t.get("debunker_strategies") or [])
                     if _plain_name_for(s) == plain),
                    plain.lower().replace(" ", "_"),
                )
                _ensure(plain, raw)["debunker"].append({
                    "run_id":     run_id,
                    "episode_id": ep_id,
                    "claim":      claim,
                    "claim_type": claim_type,
                    "spr_model":  spr_model,
                    "deb_model":  deb_model,
                    "turns":      sorted(set(turns)),
                })
    # Attach episode-emitted definitions to each tactic entry so the
    # description resolver can find them without re-scanning runs.
    for plain, entry in index.items():
        norm = (entry.get("raw_label") or "").strip().lower().replace(" ", "_")
        if norm in episode_definitions:
            entry["episode_definition"] = episode_definitions[norm]
    return index


def _seed_catalogue(index: dict) -> dict:
    """Ensure every catalogued strategy appears in the index (even if 0 uses)."""
    for raw, (plain, _desc, _side) in _STRATEGY_CATALOG.items():
        if plain not in index:
            index[plain] = {"raw_label": raw, "spreader": [], "debunker": []}
    return index


def _description_for(plain_name: str, raw_label: str, data: dict | None = None) -> str:
    """Resolve a description via the shared resolver in data/definitions.py.
    Order: hand-curated catalogue → per-episode definition → backfilled cache
    → soft fallback."""
    # The catalogue is keyed by lowercased-with-spaces. The shared resolver
    # accepts both keying conventions and will also match by plain name.
    desc = resolve_strategy_description(
        raw_label,
        primary_lookup=_STRATEGY_CATALOG,
        episode_definitions=({(raw_label or "").strip().lower().replace(" ", "_"):
                              (data or {}).get("episode_definition")}
                             if data and (data or {}).get("episode_definition") else None),
    )
    if desc:
        return desc
    # Plain-name match against the catalogue (covers cases where the raw
    # label differs from the catalogue key but the plain title matches).
    for _raw, (plain, cat_desc, _side) in _STRATEGY_CATALOG.items():
        if plain == plain_name and cat_desc:
            return cat_desc
    return (
        "Open-coded label from the LLM strategy analyst. No definition has been "
        "cached for this tactic yet — re-run scripts/backfill_strategy_definitions.py."
    )


@st.cache_data(show_spinner=False)
def _scan_citation_index(run_ids: tuple, runs_dir: str, refresh_token: float) -> dict:
    """Aggregate per-institution episode index across all the user's runs.

    Returns a dict shaped like::

        {
            <institution>: {
                "spreader":  [ {run_id, episode_id, claim, spr_model, deb_model,
                                turns: [1,3]}, ... ],
                "debunker":  [ ... ],
            },
            ...
        }
    """
    index = {}
    for run_id in run_ids:
        try:
            eps, _ = load_episodes(run_id, runs_dir, refresh_token)
        except Exception:
            continue
        for ep in eps:
            pairs = _normalize_turn_pairs(ep)
            if not pairs:
                continue
            cfg = ep.get("config_snapshot", {}).get("agents", {}) or {}
            spr_model = _short_model((cfg.get("spreader") or {}).get("model", ""))
            deb_model = _short_model((cfg.get("debunker") or {}).get("model", ""))
            claim = ep.get("claim", "")
            claim_type = ep.get("claim_type", "")
            ep_id = ep.get("episode_id", 0)

            # Per side: institution -> set of turns. We canonicalize the
            # institution name so "WHO" and "World Health Organization"
            # aggregate into a single Atlas entry.
            spr_turns = {}
            deb_turns = {}
            for i, p in enumerate(pairs):
                turn_num = p.get("pair_idx", i + 1)
                spr_text = (p.get("spreader_text") or "")
                deb_text = (p.get("debunker_text") or "")
                for src, pat in _SOURCE_PATTERNS.items():
                    canon = _canonical_source(src)
                    if pat.search(spr_text):
                        if turn_num not in spr_turns.setdefault(canon, []):
                            spr_turns[canon].append(turn_num)
                    if pat.search(deb_text):
                        if turn_num not in deb_turns.setdefault(canon, []):
                            deb_turns[canon].append(turn_num)

            for src, turns in spr_turns.items():
                index.setdefault(src, {"spreader": [], "debunker": []})["spreader"].append({
                    "run_id":     run_id,
                    "episode_id": ep_id,
                    "claim":      claim,
                    "claim_type": claim_type,
                    "spr_model":  spr_model,
                    "deb_model":  deb_model,
                    "turns":      sorted(set(turns)),
                })
            for src, turns in deb_turns.items():
                index.setdefault(src, {"spreader": [], "debunker": []})["debunker"].append({
                    "run_id":     run_id,
                    "episode_id": ep_id,
                    "claim":      claim,
                    "claim_type": claim_type,
                    "spr_model":  spr_model,
                    "deb_model":  deb_model,
                    "turns":      sorted(set(turns)),
                })
    return index


def _seed_citations(index: dict) -> dict:
    """Ensure every known institution appears in the index (even if 0 uses).

    Canonicalises aliased keys so e.g. "World Health Organization" doesn't
    seed a second empty entry alongside the canonical "WHO".
    """
    for src in _INSTITUTION_INFO.keys():
        canon = _canonical_source(src)
        if canon not in index:
            index[canon] = {"spreader": [], "debunker": []}
    return index


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str, min_len: int = 30, max_len: int = 280) -> list[str]:
    """Split a turn text into reasonable-length sentences."""
    if not text:
        return []
    out = []
    for s in _SENT_SPLIT_RE.split(text):
        s = s.strip()
        if min_len <= len(s) <= max_len:
            out.append(s)
    return out


def _extract_examples(events: list, side: str, runs_dir: str, max_n: int = 2) -> list[dict]:
    """Pull up to max_n example sentences for this tactic from the actual debate
    transcripts. Returns list of dicts: {sentence, turn, claim, run_id, spr_model, deb_model}."""
    out: list[dict] = []
    seen_runs: set[str] = set()
    for ev in events or []:
        if len(out) >= max_n:
            break
        run_id = ev.get("run_id")
        if not run_id:
            continue
        # Cap to one example per run for diversity
        if run_id in seen_runs and len(events) > 1:
            continue
        try:
            eps, _ = load_episodes(run_id, runs_dir, 0)
        except Exception:
            continue
        ep_id = ev.get("episode_id", 0)
        target_ep = next((e for e in eps if e.get("episode_id") == ep_id), None) or (eps[0] if eps else None)
        if not target_ep:
            continue
        # Index turns by turn number for the side we care about
        side_text_by_turn: dict[int, str] = {}
        for i, t in enumerate(target_ep.get("turns") or []):
            name = (t.get("name") or t.get("role") or "").lower()
            ti = t.get("turn_index")
            if ti is None:
                ti = i // 2
            tnum = int(ti) + 1
            if side == "spreader" and "spread" in name:
                side_text_by_turn[tnum] = t.get("content") or ""
            elif side == "debunker" and ("debunk" in name or "fact" in name):
                side_text_by_turn[tnum] = t.get("content") or ""
            # Legacy structured format
            if side == "spreader" and "spreader_message" in t:
                sm = t.get("spreader_message") or {}
                side_text_by_turn[tnum] = sm.get("content", "") if isinstance(sm, dict) else ""
            if side == "debunker" and "debunker_message" in t:
                dm = t.get("debunker_message") or {}
                side_text_by_turn[tnum] = dm.get("content", "") if isinstance(dm, dict) else ""

        for tnum in (ev.get("turns") or []):
            text = side_text_by_turn.get(int(tnum), "")
            sents = _sentences(text)
            if sents:
                out.append({
                    "sentence": sents[0],
                    "turn":     int(tnum),
                    "claim":    ev.get("claim", ""),
                    "run_id":   run_id,
                    "spr_model": ev.get("spr_model", ""),
                    "deb_model": ev.get("deb_model", ""),
                })
                seen_runs.add(run_id)
                break
        if len(out) >= max_n:
            break
    return out


def _render_examples(spreader_events: list, debunker_events: list, runs_dir: str) -> None:
    """Render a small 'Examples from your debates' block under the definition.
    Pulls 1-2 sentences per side from real transcripts. Silent if none found."""
    spr_ex = _extract_examples(spreader_events, "spreader", runs_dir, max_n=2)
    deb_ex = _extract_examples(debunker_events, "debunker", runs_dir, max_n=2)
    if not spr_ex and not deb_ex:
        return

    st.markdown(
        '<div style="font-size:0.66rem;text-transform:uppercase;letter-spacing:0.08em;'
        'color:#9ca3af;font-weight:700;margin:0.5rem 0 0.35rem 0">'
        'Examples from your debates</div>',
        unsafe_allow_html=True,
    )

    def _block(ex: dict, color: str, role: str) -> str:
        rgb = _hex_to_rgb(color)
        attribution = (
            f'{role} · turn {ex["turn"]} · '
            f'<em>"{(ex["claim"] or "")[:60]}{"…" if len(ex.get("claim") or "") > 60 else ""}"</em>'
        )
        return (
            f'<div style="background:rgba({rgb},0.05);border-left:3px solid {color};'
            f'border-radius:0 4px 4px 0;padding:0.5rem 0.7rem;margin:0.25rem 0;'
            f'font-size:0.85rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;'
            f'color:#9ca3af;margin-bottom:0.25rem;text-transform:uppercase;letter-spacing:0.05em">'
            f'{attribution}</div>'
            f'<div style="font-style:italic">&ldquo;{ex["sentence"]}&rdquo;</div>'
            f'</div>'
        )

    html = ""
    for ex in spr_ex:
        html += _block(ex, SPREADER_COLOR, "Spreader")
    for ex in deb_ex:
        html += _block(ex, DEBUNKER_COLOR, "Fact-checker")
    st.markdown(html, unsafe_allow_html=True)


def _render_episode_chip_list(events: list, color: str, role_label: str) -> None:
    """Render a list of episode chips for one side of a strategy entry."""
    rgb = _hex_to_rgb(color)
    if not events:
        st.markdown(
            f'<div style="font-size:0.82rem;color:#6b7280;font-style:italic;margin:0.4rem 0">'
            f'— not yet seen on the {role_label.lower()} side —</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div style="font-size:0.72rem;color:{color};font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.07em;margin:0.4rem 0 0.3rem 0;'
        f'padding-bottom:0.2rem;border-bottom:1px solid rgba({rgb},0.25)">'
        f'{role_label} · {len(events)} episode{"s" if len(events) != 1 else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    for ev in events:
        claim_short = (ev["claim"] or "")[:70]
        turns_str = ", ".join(f"T{n}" for n in ev["turns"])
        st.markdown(
            f'<div style="background:rgba({rgb},0.04);border-left:3px solid {color};'
            f'border-radius:0 4px 4px 0;padding:0.45rem 0.7rem;margin:0.3rem 0;'
            f'font-size:0.86rem;color:var(--color-text-primary,#E8E4D9)">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.72rem;'
            f'color:#9ca3af;margin-bottom:0.2rem">{ev["spr_model"]} vs {ev["deb_model"]} · '
            f'used in {turns_str}</div>'
            f'<div style="font-style:italic">&ldquo;{claim_short}'
            f'{"…" if len(ev["claim"]) > 70 else ""}&rdquo;</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_domain_footer(events: list) -> None:
    """Render a small 'Seen in: <domain chips with counts>' footer for an entry.

    Aggregates the claim_type field across the supplied event list. Silent
    if no events have a recorded claim_type.
    """
    if not events:
        return
    from arena.claim_metadata import domain_badge_html
    from collections import Counter as _Ctr
    counts = _Ctr()
    for ev in events:
        ct = (ev.get("claim_type") or "").strip()
        if ct:
            counts[ct] += 1
    if not counts:
        return
    chips = ""
    for ct, n in counts.most_common():
        chips += (
            f'<span style="margin-right:0.4rem;display:inline-block;line-height:1.6">'
            f'{domain_badge_html(ct, size="sm")} '
            f'<span style="color:#9ca3af;font-family:\'IBM Plex Mono\',monospace;font-size:0.74rem;'
            f'margin-left:0.15rem">× {n}</span>'
            f'</span>'
        )
    st.markdown(
        f'<div style="margin:0.6rem 0 0 0;padding-top:0.4rem;'
        f'border-top:1px solid var(--color-border,#2A2A2A)">'
        f'<span style="font-size:0.66rem;text-transform:uppercase;letter-spacing:0.07em;'
        f'color:#9ca3af;font-weight:700;margin-right:0.4rem">Seen in:</span>'
        f'{chips}</div>',
        unsafe_allow_html=True,
    )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    try:
        r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
    except ValueError:
        return "128,128,128"
    return f"{r},{g},{b}"


def render_atlas_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()

    st.markdown(
        '<h1 style="font-family:\'Playfair Display\',Georgia,serif;'
        'font-size:2.2rem;font-weight:700;letter-spacing:-0.02em;margin:0 0 0.3rem 0">'
        'Atlas</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.95rem;color:#9ca3af;margin:0 0 1.5rem 0;line-height:1.5">'
        'A reference library for the strategies and citations behind every AI debate. '
        'Strategy labels are colored by which side leans on them '
        '(<span style="color:#D4A843;font-weight:600">amber = spreader</span>, '
        '<span style="color:#4A7FA5;font-weight:600">blue = fact-checker</span>); '
        'institution labels are <span style="color:#16a34a;font-weight:600">green</span>. '
        'Expand any entry to see what it means and which of your debates featured it.'
        '</p>',
        unsafe_allow_html=True,
    )

    if "runs_refresh_token" not in st.session_state:
        st.session_state["runs_refresh_token"] = 0
    token = st.session_state["runs_refresh_token"]
    run_ids = get_auto_run_ids(RUNS_DIR, refresh_token=token, limit=None) or []

    # Usage-driven — Atlas only surfaces strategies and citations that
    # have actually appeared in the user's runs. The catalogue and
    # institution dictionaries still power descriptions and metadata,
    # but they no longer seed empty rows.
    strategy_index = _scan_strategy_index(tuple(run_ids), RUNS_DIR, token)
    citation_index = _scan_citation_index(tuple(run_ids), RUNS_DIR, token)

    # ── Empty state: no runs yet ─────────────────────────────────────────
    if not run_ids:
        st.markdown(
            '<div style="background:var(--color-surface,#111);'
            'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
            'padding:1.4rem 1.6rem;text-align:center;color:#9ca3af;font-size:0.95rem;'
            'line-height:1.65;margin-top:0.8rem">'
            '<div style="font-size:1.05rem;color:var(--color-text-primary,#E8E4D9);'
            'margin-bottom:0.4rem;font-weight:600">Nothing in the Atlas yet</div>'
            'Run a debate in the <strong>Arena</strong> tab — strategies and citations '
            'will populate here as they appear, with links back to the turns where they '
            'were used.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Summary row ──────────────────────────────────────────────────────
    strats_seen = len(strategy_index)
    cites_seen = len(citation_index)
    total_strat_uses = sum(len(v["spreader"]) + len(v["debunker"]) for v in strategy_index.values())
    total_cite_uses = sum(len(v["spreader"]) + len(v["debunker"]) for v in citation_index.values())

    _summary_card = (
        '<div style="flex:1;background:var(--color-surface,#111);'
        'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;padding:0.7rem 1rem">'
        '<div style="font-size:0.7rem;color:#9ca3af;text-transform:uppercase;letter-spacing:0.07em;'
        'font-weight:700">{title}</div>'
        '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:1.4rem;font-weight:700;'
        'color:var(--color-text-primary,#E8E4D9)">{value}</div>'
        '</div>'
    )
    st.markdown(
        '<div style="display:flex;gap:1rem;margin-bottom:1.2rem">'
        + _summary_card.format(title="Runs scanned", value=len(run_ids))
        + _summary_card.format(title="Unique strategies observed", value=strats_seen)
        + _summary_card.format(title="Unique citations observed", value=cites_seen)
        + '</div>',
        unsafe_allow_html=True,
    )

    # ── Sort control (applies to both sections) ──────────────────────────
    sort_mode = st.radio(
        "Sort",
        options=["By use count", "Alphabetical"],
        index=0,
        horizontal=True,
        key="atlas_sort_mode",
        label_visibility="collapsed",
    )

    # ────────────────────────────────────────────────────────────────────
    # Section 1 — Strategies (split by canonical side: spreader / fact-checker)
    # ────────────────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="font-family:\'Playfair Display\',Georgia,serif;font-size:1.4rem;'
        'font-weight:700;margin:1.5rem 0 0.4rem 0">Strategies</h2>'
        '<p style="font-size:0.85rem;color:#9ca3af;margin:0 0 0.8rem 0">'
        'Rhetorical tactics observed in your debates, grouped by '
        '<span style="color:#D4A843;font-weight:600">dominant spreader use</span> or '
        '<span style="color:#4A7FA5;font-weight:600">dominant fact-checker use</span>. '
        'Tactics with at least 25% balance between sides are marked '
        '<span style="color:#16a34a;font-weight:600">↔ used by both</span>.'
        '</p>',
        unsafe_allow_html=True,
    )

    def _strat_sort_key(item):
        plain, data = item
        n_uses = len(data["spreader"]) + len(data["debunker"])
        if sort_mode == "Alphabetical":
            return (plain.lower(), 0)
        return (-n_uses, plain.lower())

    # Two-bucket layout. Every tactic goes into its dominant side. A tactic
    # is flagged "shared" if the minor side has ≥25% of the major side's
    # usage — that catches genuine cross-side patterns and excludes the
    # statistical-noise cases (e.g. emotional_appeal at 5% balance).
    SHARED_THRESHOLD = 0.25
    BOTH_COLOR = "#16a34a"

    strat_items = sorted(strategy_index.items(), key=_strat_sort_key)
    strat_by_bucket: dict[str, list] = {"spreader": [], "debunker": []}
    for plain, data in strat_items:
        n_spr = len(data["spreader"])
        n_deb = len(data["debunker"])
        if n_spr == 0 and n_deb == 0:
            # No usage yet — fall back to the catalogue's canonical side
            bucket = _side_for(plain, data.get("raw_label", ""), data)
            if bucket == "both":
                bucket = "spreader"  # arbitrary default — only happens for unused catalogue entries
            data["_is_shared"] = False
            data["_n_spr"] = n_spr
            data["_n_deb"] = n_deb
        else:
            bucket = "spreader" if n_spr >= n_deb else "debunker"
            major = max(n_spr, n_deb)
            minor = min(n_spr, n_deb)
            data["_is_shared"] = bool(major > 0 and (minor / major) >= SHARED_THRESHOLD and minor > 0)
            data["_n_spr"] = n_spr
            data["_n_deb"] = n_deb
        strat_by_bucket[bucket].append((plain, data))

    def _render_strategy_column(entries, header_label, color_tag, accent_color, empty_msg):
        accent_rgb = _hex_to_rgb(accent_color)
        both_rgb = _hex_to_rgb(BOTH_COLOR)
        # Header — show how many of the entries are shared
        n_shared = sum(1 for _, d in entries if d.get("_is_shared"))
        shared_suffix = (
            f' · <span style="color:{BOTH_COLOR}">{n_shared} shared</span>'
            if n_shared else ""
        )
        st.markdown(
            f'<div style="font-size:0.72rem;color:{accent_color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin:0.2rem 0 0.5rem 0;'
            f'padding-bottom:0.35rem;border-bottom:2px solid rgba({accent_rgb},0.4)">'
            f'{header_label} · {len(entries)}{shared_suffix}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if not entries:
            st.caption(empty_msg)
            return
        for plain, data in entries:
            raw = data.get("raw_label", "")
            desc = _description_for(plain, raw, data)
            n_spr = data.get("_n_spr", len(data["spreader"]))
            n_deb = data.get("_n_deb", len(data["debunker"]))
            n_total = n_spr + n_deb
            is_shared = bool(data.get("_is_shared"))

            # Header label — color-coded green when shared, native side color otherwise.
            color_for_header = "green" if is_shared else color_tag
            marker = " ↔" if is_shared else ""
            header = f":{color_for_header}[**{plain}{marker}**] · {n_total} ep{'s' if n_total != 1 else ''}"

            with st.expander(header):
                # Shared-tactic banner with the per-side balance
                if is_shared:
                    balance_pct = (
                        round(min(n_spr, n_deb) / max(n_spr, n_deb) * 100)
                        if max(n_spr, n_deb) else 0
                    )
                    st.markdown(
                        f'<div style="background:rgba({both_rgb},0.10);border:1px solid rgba({both_rgb},0.45);'
                        f'border-radius:6px;padding:0.45rem 0.7rem;margin:0.1rem 0 0.6rem 0;'
                        f'font-size:0.82rem;color:#C8C4B9">'
                        f'<span style="color:{BOTH_COLOR};font-weight:700;letter-spacing:0.04em;'
                        f'text-transform:uppercase;font-size:0.7rem">↔ used by both sides</span>'
                        f' &middot; '
                        f'Spreader <strong>{n_spr}</strong> ep · '
                        f'Fact-checker <strong>{n_deb}</strong> ep · '
                        f'<span style="color:#9ca3af">balance {balance_pct}%</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Prominent "About this tactic" definition section
                st.markdown(
                    f'<div style="background:var(--color-surface-alt,#1A1A1A);'
                    f'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
                    f'padding:0.6rem 0.8rem;margin:0.2rem 0 0.6rem 0">'
                    f'<div style="font-size:0.66rem;text-transform:uppercase;letter-spacing:0.08em;'
                    f'color:#9ca3af;font-weight:700;margin-bottom:0.3rem">About this tactic</div>'
                    f'<div style="font-size:0.92rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">'
                    f'{desc}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Examples pulled live from real debate transcripts
                _render_examples(data["spreader"], data["debunker"], RUNS_DIR)
                _render_episode_chip_list(data["spreader"], SPREADER_COLOR, "Spreader")
                _render_episode_chip_list(data["debunker"], DEBUNKER_COLOR, "Fact-checker")
                _render_domain_footer(data["spreader"] + data["debunker"])
                st.markdown(
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;'
                    f'color:#6b7280;margin-top:0.5rem;text-align:right">raw label: {raw}</div>',
                    unsafe_allow_html=True,
                )

    _sc1, _sc2 = st.columns(2)
    with _sc1:
        _render_strategy_column(
            strat_by_bucket["spreader"],
            "Spreader tactics", "orange", SPREADER_COLOR,
            "— no tactics dominantly used by the spreader yet —",
        )
    with _sc2:
        _render_strategy_column(
            strat_by_bucket["debunker"],
            "Fact-checker tactics", "blue", DEBUNKER_COLOR,
            "— no tactics dominantly used by the fact-checker yet —",
        )

    # ────────────────────────────────────────────────────────────────────
    # Section 2 — Citations (split by usage side: cited by spreader / fact-checker)
    # ────────────────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="font-family:\'Playfair Display\',Georgia,serif;font-size:1.4rem;'
        'font-weight:700;margin:2rem 0 0.4rem 0">Citations</h2>'
        '<p style="font-size:0.85rem;color:#9ca3af;margin:0 0 0.8rem 0">'
        'Institutions cited in your debates, grouped by which side cited them. '
        'An institution may appear in both columns if both sides cited it.'
        '</p>',
        unsafe_allow_html=True,
    )

    def _cite_sort_key_for(side_key):
        def keyfn(item):
            src, data = item
            n_uses_side = len(data[side_key])
            if sort_mode == "Alphabetical":
                return (src.lower(), 0)
            return (-n_uses_side, src.lower())
        return keyfn

    def _render_citation_column(side_key, side_label, accent_color):
        accent_rgb = _hex_to_rgb(accent_color)
        # Only institutions this side actually cited in the user's runs.
        items = [
            (src, data) for src, data in citation_index.items()
            if data[side_key]
        ]
        items.sort(key=_cite_sort_key_for(side_key))

        st.markdown(
            f'<div style="font-size:0.72rem;color:{accent_color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.07em;margin:0.2rem 0 0.5rem 0;'
            f'padding-bottom:0.35rem;border-bottom:2px solid rgba({accent_rgb},0.4)">'
            f'Cited by {side_label} · {len(items)}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if not items:
            st.caption(f"— no citations from the {side_label.lower()} yet —")
            return

        for src, data in items:
            n_this_side = len(data[side_key])
            info = _INSTITUTION_INFO.get(src, "Institution recognised by the citation detector.")
            header = f":green[**{src}**] · {n_this_side} ep{'s' if n_this_side != 1 else ''}"
            with st.expander(header):
                # Prominent "About this institution" definition section
                st.markdown(
                    f'<div style="background:var(--color-surface-alt,#1A1A1A);'
                    f'border:1px solid var(--color-border,#2A2A2A);border-radius:6px;'
                    f'padding:0.6rem 0.8rem;margin:0.2rem 0 0.6rem 0">'
                    f'<div style="font-size:0.66rem;text-transform:uppercase;letter-spacing:0.08em;'
                    f'color:#9ca3af;font-weight:700;margin-bottom:0.3rem">About this institution</div>'
                    f'<div style="font-size:0.92rem;line-height:1.55;color:var(--color-text-primary,#E8E4D9)">'
                    f'{info}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                _render_episode_chip_list(data[side_key], accent_color, side_label)
                _render_domain_footer(data[side_key])

    _cc1, _cc2 = st.columns(2)
    with _cc1:
        _render_citation_column("spreader", "Spreader", SPREADER_COLOR)
    with _cc2:
        _render_citation_column("debunker", "Fact-checker", DEBUNKER_COLOR)
