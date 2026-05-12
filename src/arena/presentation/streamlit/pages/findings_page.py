"""
Findings Page — Conference demo research findings with embedded SVG visualizations.
5 sub-tabs: Falsifiability | Fingerprints | Game Theory | Source Weaponization | Adaptability
"""

import streamlit as st
from pathlib import Path

SVG_DIR = Path(__file__).resolve().parents[5] / "exports" / "svg"


def _inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;800&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500;700&display=swap');

    .fn-container { padding: 1rem 0; }
    .fn-headline {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.8rem; font-weight: 700;
        color: var(--color-text-primary, #E8E4D9);
        line-height: 1.2; margin: 0 0 0.5rem 0;
    }
    .fn-stat {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.4rem; font-weight: 700;
        color: var(--color-accent-red, #C9363E);
        margin: 0.3rem 0 1rem 0;
    }
    .fn-prose {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.95rem; color: #C8C4B9;
        line-height: 1.7; margin: 0 0 1.2rem 0;
    }
    .fn-prose strong { color: var(--color-text-primary, #E8E4D9); }
    .fn-section-label {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.75rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 2px;
        color: var(--color-text-muted, #888);
        margin: 2rem 0 0.5rem 0;
    }
    .fn-svg-wrap { margin: 1rem 0; text-align: center; }
    .fn-svg-wrap svg { max-width: 100%; height: auto; }
    .fn-divider {
        border: none; border-top: 1px solid var(--color-border, #2A2A4A);
        margin: 2rem 0;
    }
    .fn-callout {
        background: var(--color-surface, #1A1A2E);
        border-left: 3px solid var(--color-accent-red, #C9363E);
        border-radius: 4px; padding: 1rem 1.4rem; margin: 1rem 0;
    }
    .fn-callout p {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.93rem; color: #C8C4B9;
        line-height: 1.6; margin: 0;
    }
    .fn-callout strong { color: var(--color-text-primary, #E8E4D9); }
    .fn-key-insight {
        background: rgba(46, 204, 113, 0.08);
        border-left: 3px solid #2ECC71;
        border-radius: 4px; padding: 0.8rem 1.2rem; margin: 1rem 0;
    }
    .fn-key-insight p {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.9rem; color: #C8C4B9; line-height: 1.6; margin: 0;
    }
    .fn-key-insight strong { color: #2ECC71; }
    </style>
    """, unsafe_allow_html=True)


def _svg(filename: str) -> None:
    path = SVG_DIR / filename
    if not path.exists():
        st.caption(f"Visual not available: {filename}")
        return
    svg = path.read_text(encoding="utf-8")
    st.markdown(f'<div class="fn-svg-wrap">{svg}</div>', unsafe_allow_html=True)


def _headline(text): st.markdown(f'<div class="fn-headline">{text}</div>', unsafe_allow_html=True)
def _stat(text): st.markdown(f'<div class="fn-stat">{text}</div>', unsafe_allow_html=True)
def _prose(text): st.markdown(f'<div class="fn-prose">{text}</div>', unsafe_allow_html=True)
def _label(text): st.markdown(f'<div class="fn-section-label">{text}</div>', unsafe_allow_html=True)
def _callout(text): st.markdown(f'<div class="fn-callout"><p>{text}</p></div>', unsafe_allow_html=True)
def _insight(text): st.markdown(f'<div class="fn-key-insight"><p>{text}</p></div>', unsafe_allow_html=True)
def _divider(): st.markdown('<hr class="fn-divider">', unsafe_allow_html=True)


def _plain_stat(stat_html: str, plain: str):
    """Render an academic stat line followed by a plain-English subtitle.

    The stat (e.g. 'η² = 0.369 (Large)') sits on top in monospace.
    The plain line below restates it for a casual reader.
    """
    st.markdown(
        f'<div class="fn-stat">{stat_html}</div>'
        f'<div style="font-size:0.92rem;color:#9ca3af;margin:-0.3rem 0 0.8rem 0;'
        f'font-style:italic;line-height:1.5;">{plain}</div>',
        unsafe_allow_html=True,
    )


# ─── F1: Falsifiability ─────────────────────────────────────────
def _render_falsifiability():
    _headline("Falsifiability Is the Dividing Line")
    _plain_stat(
        "η² = 0.369 (Large) — the single largest effect in the study",
        "In plain English: whether a claim can be disproven by evidence explains "
        "about 37% of who wins — more than which model you pick, or how many turns "
        "the debate runs."
    )

    _prose(
        "Whether a claim can be disproven with empirical evidence is the strongest predictor "
        "of debate outcome. On <strong>falsifiable claims</strong>, debunkers win 95% — "
        "model choice barely matters (η² = 0.051). On <strong>unfalsifiable claims</strong>, "
        "win rate drops to 53% and model identity becomes <strong>7.2x more important</strong> (η² = 0.369)."
    )

    _callout(
        "<strong>Within-domain proof:</strong> In Political, <strong>'the 2020 election was stolen'</strong> "
        "(falsifiable — court records exist) → 0% spreader wins. <strong>'A deep state secretly "
        "controls policy'</strong> (unfalsifiable — any counter-evidence is proof of the cover-up) "
        "→ 50% spreader wins. Same domain. The falsifiability changed."
    )

    _label("Win rate: Falsifiable vs Unfalsifiable")
    _svg("pv5_falsifiability.svg")

    _divider()
    _label("Both sides reorganize their tactics")
    _prose(
        "On falsifiable claims, <strong>debunkers converge</strong> — all models cite evidence (45-98% Evidence Citation). "
        "<strong>Spreaders diverge by domain</strong> — Health triggers anecdotes (72%), Environmental triggers "
        "revisionism (78%), Political triggers emotion (91%). But all spreader tactics are answerable with data."
    )
    _prose(
        "On unfalsifiable claims, it <strong>reverses</strong>. <strong>Spreaders converge</strong> on "
        "institutional attacks — Source Weaponization, Appeal to (Dis)trust, and Conspiracy Theory rise "
        "across all models. <strong>Debunkers diverge by model</strong> — Claude explains mechanisms (52%), "
        "GPT-4o demands verification (66%), Mini defaults to 'it's more complex' (34-76%)."
    )

    _insight(
        "<strong>The convergence/divergence reversal:</strong> When evidence exists, debunkers all do the same thing "
        "and spreaders get creative per domain. When evidence fails, spreaders all attack institutions "
        "and debunkers reveal their training-specific defaults. This reversal is why model identity "
        "suddenly matters on hard claims."
    )

    _divider()
    _label("Debunker advantage collapses across every dimension")
    _prose(
        "Every evidence-based scoring dimension shrinks on unfalsifiable claims. Source reputability "
        "drops from +4.2 to +0.7. Hallucination index from +3.8 to +0.8. <strong>Persuasion</strong> and "
        "<strong>manipulation awareness</strong> actually flip in the spreader's favor — a confident "
        "narrative ('the revolving door between government and industry') beats a vague 'it's more complex.'"
    )
    _svg("pv_falsifiability_gaps.svg")

    _divider()
    _label("Model capability only reveals itself on hard claims")
    _prose(
        "On falsifiable claims, Claude wins 100% and GPT-4o-mini wins 89% — a 11-point gap. "
        "On unfalsifiable claims, Claude wins 95% and GPT-4o-mini wins 29% — a <strong>66-point gap</strong>. "
        "Claude survives because it uses <strong>mechanism explanation</strong> — explaining how institutions "
        "actually work rather than citing evidence that doesn't exist. The other models default to "
        "'it's more complex than that,' which wins only 35% of the time."
    )

    col1, col2 = st.columns(2)
    with col1:
        _svg("pv_fals_unf_winrate.svg")
    with col2:
        _svg("pv_fals_fal_winrate.svg")

    _divider()
    _label("Why it matters")
    _callout(
        "AI can only debunk what humans have already settled. Current fact-checking systems are built "
        "around evidence retrieval — that works on 95% of falsifiable claims. But the misinformation "
        "that spreads fastest (conspiracies, economic theories, AI fears) is <strong>unfalsifiable by design</strong>. "
        "For these claims, systems need to be trained on <strong>mechanism explanation</strong>, not evidence retrieval."
    )


# ─── F2: Fingerprints ───────────────────────────────────────────
def _render_fingerprints():
    _headline("Models Have Detectable Rhetorical Fingerprints")
    _plain_stat(
        "η² = 0.130 (Medium) — classifier accuracy 44% vs 25% baseline",
        "In plain English: each AI model has a signature style of arguing. We trained a "
        "classifier to guess which model wrote a turn just from the tactics it used — "
        "it got 44% right (random guessing would be 25%)."
    )

    _prose(
        "With no instructions on how to argue (~180 char free-will prompts), each model develops a distinct "
        "rhetorical pattern from training alone. All models draw from the <strong>same tactical vocabulary</strong> — "
        "the fingerprint is in the <strong>frequency distribution</strong>, not unique tactics."
    )

    _callout(
        "<strong>Why this is valid:</strong> In v1, we prescribed tactics and got artifacts — "
        "Fake Expert and Logical Fallacy appeared frequently. In v2 with free-will prompts, those two "
        "tactics <strong>never appeared once</strong> across 931 episodes. Everything here is genuine model behavior."
    )

    _label("What each model defaults to")
    _prose(
        "<strong>Claude</strong> → Institutional distrust &amp; structural framing. Smallest repertoire (8.3 unique tactics). "
        "Most identifiable model.<br>"
        "<strong>GPT-4o-mini</strong> → Personal stories &amp; anecdotal evidence. 72% on Health claims.<br>"
        "<strong>GPT-4o</strong> → Balanced mix across tactics. Most versatile, least distinctive.<br>"
        "<strong>Gemini</strong> → Pseudo-scientific framing. 72.7% neutral citation framing — barely engages "
        "with institutions. Least identifiable (3% recall)."
    )

    _label("Spreader strategy distribution by model")
    _svg("pv4_spr_stacked.svg")

    _divider()
    _label("Detection results")
    _prose(
        "A Random Forest classifier identifies the source model at <strong>44.3%</strong> accuracy "
        "from strategy counts alone — nearly double the 25% baseline. The classifier used raw tactic "
        "counts per episode with stratified k-fold cross-validation."
    )

    col1, col2 = st.columns(2)
    with col1:
        _svg("s2f_accuracy_comparison.svg")
    with col2:
        _svg("s2f_feature_importance.svg")

    _prose(
        "<strong>Binary Claude vs Others:</strong> 81% accuracy. Claude's institutional distrust pattern "
        "makes it distinctive by a wide margin.<br>"
        "<strong>Provider-level:</strong> GPT-4o and GPT-4o-mini are nearly indistinguishable (56 cross-misclassifications) "
        "but collectively identifiable as OpenAI at 86% recall. Fingerprints operate at the provider level."
    )

    _insight(
        "<strong>Spreader fingerprints are stronger than debunker</strong> (44% vs 36%, 8.8-point gap). "
        "Debunking is formulaic — everyone cites evidence. Spreading misinformation requires creativity, "
        "and that creativity reveals identity."
    )

    _divider()
    _label("Strategy clusters: domain drives grouping, model is secondary")
    _prose(
        "t-SNE embedding of strategy features shows <strong>claim domain</strong> creates the tightest "
        "clusters — all Health claims group together regardless of model. Within each cluster, "
        "model colors show secondary separation. This is the hierarchy: domain determines <em>which</em> "
        "tactic region you land in, model determines <em>how likely</em> you are to land there."
    )

    tsne_choice = st.radio(
        "Color by:",
        ["Claim Type", "Spreader Model", "Debunker Model"],
        horizontal=True,
        key="tsne_radio",
    )
    tsne_map = {
        "Claim Type": "s2d_tsne_claimtype.svg",
        "Spreader Model": "s2d_tsne_spreader.svg",
        "Debunker Model": "s2d_tsne_debunker.svg",
    }
    _svg(tsne_map[tsne_choice])

    _divider()
    _label("Comparison to published work")
    _prose(
        "Prior systems (DetectGPT, GLTR) achieve 70-95% using <strong>lexical features</strong> — "
        "how a model writes. Our classifier uses <strong>rhetorical strategy</strong> — what a model argues. "
        "Lower accuracy (44%) but a fundamentally different signal. You can paraphrase text to beat "
        "stylometric detection. You can't paraphrase a model's tendency to default to institutional distrust."
    )


# ─── F3: Game Theory ─────────────────────────────────────────────
def _render_game_theory():
    _headline("Fixed Playbooks, Real-Time Reactions")
    _plain_stat(
        "η² = 0.001 (Null: opponent) → V = 0.17 (Medium: tactic reactivity)",
        "In plain English: no model changes its overall playbook based on WHO it's facing "
        "— but every model reacts to WHAT was just said. Each move provokes a specific counter, "
        "and those counter-patterns are highly predictable."
    )

    _prose(
        "No model changes strategy based on <strong>who</strong> it faces — all P values above 0.85. "
        "But both sides react to <strong>what was just said</strong> — χ² = 991, P &lt; 0.001. "
        "The playbook is fixed; the execution is real-time."
    )

    _label("The null result: opponent blindness")
    _callout(
        "<strong>Claude:</strong> P = 0.964 · <strong>GPT-4o:</strong> P = 0.965 · "
        "<strong>GPT-4o-mini:</strong> P = 0.986 · <strong>Gemini:</strong> P = 0.9996<br><br>"
        "These are the strongest null results in the study. Gemini's strategy is virtually identical "
        "regardless of opponent. We also tested whether models deploy more tactics against weaker "
        "opponents — they don't (F = 0.26, P = 0.857, η² = 0.001)."
    )

    _label("The discovery: tactic-level reactivity")
    _prose(
        "Within a debate, both sides respond to the opponent's tactic. Debunker reacts to spreader: "
        "χ² = 991, V = 0.17. Spreader reacts to debunker: χ² = 794, V = 0.17. Both medium effects. "
        "Knowing the opponent's tactic gives moderate predictive power over the response."
    )
    _svg("s5d_reactivity_chi2.svg")

    _divider()
    _label("Specific counter-patterns")
    _prose(
        "<strong>Emotional appeal</strong> → debunker counters with Evidence Citation 48%, Logical Refutation 30%<br>"
        "<strong>Source Weaponization</strong> → debunker attacks from multiple angles (evidence, consensus, logic equally)<br>"
        "<strong>Technical Correction</strong> by debunker → spreader pivots to Pseudo-Science 35% (abandons corrected ground)<br>"
        "<strong>Scientific Consensus</strong> by debunker → spreader shifts to Historical Revisionism 21% + Anecdotes 15%<br>"
        "<strong>Verification demand</strong> by debunker → spreader pivots to Conspiracy 17% (demand for proof becomes proof of cover-up)"
    )

    _divider()
    _label("Counter-strategy flows by domain")
    _prose(
        "Select a domain to see how tactics flow between sides. Each domain has distinct counter-patterns — "
        "Health pseudo-science gets a safety counter, Political claims trigger verification demands, "
        "Economic claims produce the most uncategorizable responses."
    )

    domain = st.selectbox(
        "Domain:",
        ["All (Aggregated)", "Health", "Technology", "Political", "Environmental", "Economic"],
        key="sankey_domain",
    )
    slug_map = {
        "All (Aggregated)": "", "Health": "_health", "Technology": "_technology",
        "Political": "_political", "Environmental": "_environmental", "Economic": "_economic",
    }
    slug = slug_map[domain]

    col1, col2 = st.columns(2)
    with col1:
        _svg(f"s5d_sankey_spr_to_deb{slug}.svg")
    with col2:
        _svg(f"s5d_sankey_deb_to_spr{slug}.svg")

    _divider()
    _label("Why it matters")
    _insight(
        "<strong>AI misinformation is predictable.</strong> If you know the model and the domain, you know the playbook. "
        "If the spreader uses emotional appeal, the debunker will cite evidence 48% of the time. "
        "If the debunker corrects data, the spreader will pivot to pseudo-science 35%. "
        "A counter-system can anticipate the next move before it happens."
    )


# ─── F4: Source Weaponization ────────────────────────────────────
def _render_source_weaponization():
    _headline("The Danger Isn't Fabrication, It's Framing")
    _plain_stat(
        "V = 0.169 (Medium) — r² = 0.98 (citation quality predicts outcomes)",
        "In plain English: across 9,050 citations, zero were fabricated. Both sides cite "
        "the same institutions — the difference is HOW they frame them. Citation quality "
        "alone predicts the winner with near-perfect accuracy across all 5 domains."
    )

    _prose(
        "Across <strong>9,050 citations</strong> from 931 episodes, <strong>zero were fabricated</strong>. "
        "Both sides cite the same institutions — WHO, CDC, Nature, Federal Reserve. "
        "The difference is framing: spreaders <strong>hedge 2.4x more</strong> than debunkers "
        "(χ² = 258, P &lt; 0.001)."
    )

    _label("Both sides cite the same institutions")
    _svg("s8c_weaponization.svg")

    _divider()
    _label("Three framing mechanisms")
    _prose(
        "<strong>Selective excerpt:</strong> Cite a real finding, omit the institution's conclusion. "
        "The spreader cites WHO's adverse event database; the debunker cites WHO's statement that those "
        "reports don't establish causation. Both factually accurate.<br><br>"
        "<strong>Authority transfer:</strong> Use the institution's name for credibility, then attach a "
        "conclusion it doesn't endorse. 'According to NASA...' followed by a claim NASA hasn't made.<br><br>"
        "<strong>Scope manipulation:</strong> Cite a narrow finding as the institution's overall position. "
        "One adverse event report becomes 'WHO has documented concerns.'"
    )

    _callout(
        "<strong>Spreader:</strong> \"WHO's VigiAccess database has recorded over 4.5 million "
        "adverse event reports...\"<br>"
        "<strong>Debunker:</strong> \"WHO explicitly states that reports in VigiAccess do not "
        "establish causation — they are raw signals for investigation...\"<br><br>"
        "Same database. Same institution. The misinformation lives in what's omitted, not what's stated."
    )

    _divider()
    _label("Framing differs systematically by role")
    _prose(
        "<strong>Hedging:</strong> Spreaders hedge 17.1% vs debunkers 7.2% — 'some studies suggest,' "
        "'there are concerns.' Plants doubt without committing to a falsifiable position.<br>"
        "<strong>Definitive:</strong> Debunkers assert 5.5% vs spreaders 2.8% — 'the evidence conclusively shows.'<br>"
        "<strong>Conspiratorial:</strong> Debunkers actually use conspiratorial framing more (9.4% vs 5.6%) — "
        "but in the opposite direction: 'conspiracy theorists claim X, but...' vs 'what they don't want you to know.'"
    )
    _svg("s8d_framing.svg")

    _divider()
    _label("Citation quality predicts debate outcomes")
    _prose(
        "Domains where authoritative institutions have published definitive positions produce higher-quality "
        "citations and higher debunker win rates. The relationship is nearly perfect across 5 domains."
    )
    _svg("pv2_citation_vs_winrate.svg")

    _prose(
        "<strong>Health</strong> (~7.3 reputability) → 96% debunker wins · "
        "<strong>Environmental</strong> (~6.0) → 85% · "
        "<strong>Technology</strong> (~5.5) → 80% · "
        "<strong>Political</strong> (~5.4) → 75% · "
        "<strong>Economic</strong> (~3.8) → 50%"
    )

    _insight(
        "This connects directly to Finding 1: citation quality is high when evidence exists (falsifiable) "
        "and collapses when it doesn't (unfalsifiable). The r = 0.99 is the citation-level expression "
        "of the falsifiability finding."
    )

    _divider()
    _label("Model differences in framing")
    _prose(
        "<strong>Claude:</strong> Frames structurally — explains how the institution works, selects which "
        "operational detail to highlight. Most sophisticated framing. Never fabricates.<br>"
        "<strong>GPT-4o:</strong> Frames rhetorically — leads with the institution's name for authority, then pivots.<br>"
        "<strong>GPT-4o-mini:</strong> Over-cites — stacks multiple institutions for volume over depth.<br>"
        "<strong>Gemini:</strong> Under-cites — 72.7% neutral framing. Barely engages with institutions."
    )

    _divider()
    _label("Why it matters")
    _callout(
        "Traditional fact-checking asks 'is this citation real?' For AI misinformation, the answer is "
        "almost always yes. The real question is <strong>'does this citation support the conclusion being drawn?'</strong> "
        "— that's a framing question, not a factual one. Detection must analyze which facts were selected "
        "and which were omitted, not whether the facts themselves are true."
    )


# ─── F5: Adaptability ───────────────────────────────────────────
def _render_adaptability():
    _headline("The Best Debater Doesn't Switch Tactics, It Deepens Arguments")
    _plain_stat(
        "r = 0.753 (Strong) — adaptability is the #1 predictor of who wins",
        "In plain English: the winning side is usually the one that deepens a single coherent "
        "argument across challenges, not the one that hops between tactics. Of every dimension "
        "we measured, this correlation is the strongest. Bottom-quartile adaptability wins 28% "
        "of debates; everyone else wins 100%."
    )

    _prose(
        "We ranked all 8 scoring dimensions by point-biserial correlation with outcome. "
        "<strong>Adaptability</strong> leads at r = 0.753, followed by reasoning quality (0.733), "
        "responsiveness (0.721), and factuality (0.703). The top four are all 'Strong' predictors."
    )

    _prose(
        "<strong>Manipulation awareness</strong> — the dimension designed to penalize manipulation — "
        "is the <strong>weakest predictor</strong> (r = 0.401). Detecting manipulation doesn't determine "
        "outcomes. Adapting your argument does."
    )

    _label("Dimension predictor ranking")
    _svg("s8b_predictor_ranking.svg")

    _divider()
    _label("Adaptability gap determines outcomes")
    _prose(
        "When the debunker's adaptability advantage falls to the bottom quartile, win rate drops "
        "from <strong>100% to 28%</strong> (n=140). Adaptability isn't just correlated — it's nearly a binary switch."
    )
    _svg("s8b_adapt_quartiles.svg")

    _divider()
    _label("The paradox: fewer label changes = higher adaptability score")
    _prose(
        "<strong>Claude</strong> changes tactic labels only 84% of turns — the least of any model. "
        "Yet it scores <strong>highest on adaptability</strong> (5.71). <strong>GPT-4o-mini</strong> changes labels "
        "98% of turns but scores lowest (5.10). The model that looks most adaptive by surface metrics "
        "is actually the least adaptive by judge assessment."
    )

    _callout(
        "<strong>GPT-4o-mini</strong> debunking the Federal Reserve claim opens every turn with "
        "'The assertion that the Federal Reserve is a private scam...' — relabels from 'essential_role' "
        "to 'critical_role' to 'independence' to 'hybrid_organization' but restates the same sentence. "
        "Four different labels, one argument.<br><br>"
        "<strong>Claude</strong> opens with 'This claim fundamentally misunderstands the structure' then "
        "shifts to addressing transparency concerns, then explains oversight mechanisms. Fewer label changes, "
        "but each turn builds on the last."
    )

    _insight(
        "<strong>The distinction is relabeling vs advancing.</strong> Models that relabel restart their "
        "argument every turn with new framing but the same content. Models that advance maintain their "
        "framework but deepen it. The judge rewards depth over breadth."
    )

    _divider()
    _label("Why adaptability and reasoning quality are linked")
    _prose(
        "The top two predictors measure the same skill from different angles. <strong>Reasoning quality</strong> "
        "captures how well arguments are structured. <strong>Adaptability</strong> captures how well arguments "
        "respond to challenges. A model that deepens its reasoning in response to opponents scores high on both."
    )

    _prose(
        "From the gap analysis, debunker adaptation rate increases with turn length (η² = 0.178, Large). "
        "Longer debates give debunkers more room to build cumulative cases — which is why adaptability "
        "becomes the decisive factor."
    )

    _divider()
    _label("Why it matters")
    _callout(
        "The most dangerous AI communicator isn't the one with the most tricks — it's the one that can "
        "take a <strong>single misleading frame and deepen it across every challenge</strong>. That's harder "
        "to detect and harder to counter than surface-level tactic switching. For counter-misinformation, "
        "the winning strategy is the same on both sides: depth over breadth, persistence over agility."
    )


# ─── Main Entry Point ───────────────────────────────────────────
def render_findings_page():
    _inject_styles()

    st.markdown('<div class="fn-container">', unsafe_allow_html=True)

    _prose(
        "<strong>960 adversarial AI debates</strong> across 4 models, 20 claims, 5 domains, "
        "and 3 turn lengths — judged independently by Grok-3. These five findings are ordered "
        "by causal logic and account for every source of variance above η² = 0.05 in the dataset."
    )

    _insight(
        "<strong>The narrative:</strong> The claim sets the difficulty (F1). Each model brings a fixed toolkit (F2). "
        "Interactions are reactive but predictable (F3). Evidence quality varies by domain (F4). "
        "And the side that deepens its argument wins (F5)."
    )

    f1, f2, f3, f4, f5 = st.tabs([
        "Falsifiability",
        "Fingerprints",
        "Game Theory",
        "Source Weaponization",
        "Adaptability",
    ])

    with f1:
        _render_falsifiability()
    with f2:
        _render_fingerprints()
    with f3:
        _render_game_theory()
    with f4:
        _render_source_weaponization()
    with f5:
        _render_adaptability()

    st.markdown('</div>', unsafe_allow_html=True)
