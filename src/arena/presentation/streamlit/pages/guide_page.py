"""
Home / Guide Page for Misinformation Arena v2.

Serves as the landing page for the app. Explains the research motivation,
how the system works, and how to navigate each section.
"""

import streamlit as st


def _inject_styles() -> None:
    st.markdown("""
    <style>
    .gp-hero-title {
        font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em;
        line-height: 1.15; margin: 0 0 0.5rem 0; color: #111;
    }
    .gp-hero-sub {
        font-size: 1.15rem; color: #4b5563; line-height: 1.7;
        max-width: 720px; margin: 0 0 1.8rem 0;
    }
    .gp-section {
        font-size: 1.5rem; font-weight: 700; color: #111;
        margin: 2.5rem 0 0.4rem 0;
        padding-bottom: 0.35rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .gp-prose {
        font-size: 0.97rem; color: #374151; line-height: 1.75;
        max-width: 760px; margin-bottom: 1rem;
    }
    .gp-pull-quote {
        font-size: 1.1rem; font-style: italic; color: #1d4ed8;
        border-left: 4px solid #3b82f6;
        padding: 0.75rem 1.25rem; margin: 1.5rem 0;
        background: rgba(59,130,246,0.05); border-radius: 0 8px 8px 0;
        max-width: 720px;
    }
    .gp-stat-row {
        display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.5rem 0;
    }
    .gp-stat {
        flex: 1; min-width: 160px;
        background: #fff; border: 1px solid #e5e7eb;
        border-radius: 12px; padding: 1rem 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .gp-stat-num {
        font-size: 2rem; font-weight: 800; line-height: 1;
        margin-bottom: 0.25rem;
    }
    .gp-stat-label {
        font-size: 0.8rem; color: #6b7280; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.06em;
    }
    .gp-step-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 1.2rem 0; }
    .gp-step {
        flex: 1; min-width: 160px;
        background: #f9fafb; border: 1px solid #e5e7eb;
        border-radius: 10px; padding: 0.9rem 1rem;
    }
    .gp-step-num {
        font-size: 1.5rem; font-weight: 800; color: #6366f1;
        margin-bottom: 0.2rem;
    }
    .gp-step-title {
        font-size: 0.88rem; font-weight: 700; color: #111; margin-bottom: 0.2rem;
    }
    .gp-step-body { font-size: 0.82rem; color: #6b7280; line-height: 1.5; }
    .gp-role-card {
        flex: 1; min-width: 200px; border-radius: 12px;
        padding: 1.1rem 1.3rem;
    }
    .gp-role-title {
        font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem;
    }
    .gp-role-body { font-size: 0.85rem; line-height: 1.6; }
    .gp-nav-card {
        flex: 1; min-width: 180px;
        background: #fff; border: 1px solid #e5e7eb;
        border-radius: 10px; padding: 0.9rem 1.1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .gp-nav-title {
        font-size: 0.92rem; font-weight: 700; color: #111; margin-bottom: 0.25rem;
    }
    .gp-nav-body { font-size: 0.8rem; color: #6b7280; line-height: 1.5; }
    .gp-ref {
        font-size: 0.8rem; color: #9ca3af; line-height: 1.6;
        border-top: 1px solid #f3f4f6; padding-top: 0.75rem; margin-top: 1rem;
    }
    .gp-divider { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
    .gp-badge {
        display: inline-block; font-size: 0.72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em;
        padding: 0.2rem 0.55rem; border-radius: 999px; margin-right: 0.4rem;
    }
    </style>
    """, unsafe_allow_html=True)


def render_guide_page():
    _inject_styles()

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        '<p class="gp-hero-title">Misinformation Arena</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="gp-hero-sub">'
        'A research platform for studying how false narratives compete with facts — '
        'and why the outcome is rarely as simple as "truth wins."'
        '</p>',
        unsafe_allow_html=True,
    )

    sub_home, sub_how, sub_about = st.tabs(["Why this exists", "How to use it", "Research context"])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — WHY THIS EXISTS
    # ════════════════════════════════════════════════════════════════════════
    with sub_home:
        st.markdown(
            '<p class="gp-section">We are living through an information crisis</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'Skepticism toward the sources we rely on — news media, government agencies, '
            'scientific institutions — has reached levels that would have seemed extreme '
            'a generation ago. A 2023 Gallup poll found that trust in mass media hit an '
            'all-time low, with only 32% of Americans reporting a "great deal" or "fair '
            'amount" of trust. Similar trends appear across Europe, Latin America, and '
            'Southeast Asia. We are not just disagreeing about facts — we are disagreeing '
            'about who gets to establish them.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="gp-stat-row">
            <div class="gp-stat">
                <div class="gp-stat-num" style="color:#ef4444;">6×</div>
                <div class="gp-stat-label">Faster spread of false news vs. true news on social media <em>(Science, 2018)</em></div>
            </div>
            <div class="gp-stat">
                <div class="gp-stat-num" style="color:#f59e0b;">32%</div>
                <div class="gp-stat-label">Americans who trust mass media "a great deal" or "fair amount" <em>(Gallup, 2023)</em></div>
            </div>
            <div class="gp-stat">
                <div class="gp-stat-num" style="color:#6366f1;">$78B</div>
                <div class="gp-stat-label">Estimated annual economic cost of health misinformation in the US <em>(JHSPH, 2020)</em></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="gp-pull-quote">'
            '"False news is more novel than true news, which suggests it is the novelty of '
            'false news that attracts human attention and encourages sharing, not its '
            'accuracy." — Vosoughi, Roy &amp; Aral, <em>Science</em>, 2018'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="gp-section">The problem with fact-checking alone</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'The standard response to misinformation has been to fact-check it — label a '
            'claim as true or false, attach a correction, and move on. Research has '
            'repeatedly shown this is insufficient. Corrections often reach only a fraction '
            'of the original audience. They can trigger a "backfire effect" in deeply '
            'committed believers, hardening existing views rather than updating them. And '
            'they treat misinformation as a static object rather than a dynamic, adaptive '
            'process that evolves in response to challenge.'
            '</p>'
            '<p class="gp-prose">'
            'Misinformation succeeds because it tells stories. It exploits real '
            'uncertainties in complex topics. It speaks to genuine anxieties. '
            'It builds community around shared skepticism. Understanding <em>how</em> it '
            'persuades — not just <em>that</em> it is false — is the key to countering it.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="gp-section">What Misinformation Arena does differently</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'This platform simulates the debate that happens in the real world, but under '
            'controlled conditions where we can observe, measure, and replay every move. '
            'Two AI agents argue a claim from opposing positions. A third AI evaluates the '
            'exchange across six rhetorical dimensions. Every turn, every score, every '
            'strategy label is recorded.'
            '</p>',
            unsafe_allow_html=True,
        )

        cols_why = st.columns(3)
        with cols_why[0]:
            st.markdown("**Simulate, not just label**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'We model the actual argumentative exchange — how a spreader responds to '
                'pushback, how a debunker adapts when emotional appeals land. Labels don\'t '
                'capture this; debates do.'
                '</p>',
                unsafe_allow_html=True,
            )
        with cols_why[1]:
            st.markdown("**Measure persuasion, not just truth**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'The judge scores evidence quality, reasoning, responsiveness, and '
                'persuasive impact — because a claim can be false and still win '
                'rhetorically. That gap is the problem we are studying.'
                '</p>',
                unsafe_allow_html=True,
            )
        with cols_why[2]:
            st.markdown("**Accumulate evidence across claims**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Run the same claim dozens of times to study variance. Run many different '
                'claims to study patterns. The analytics layer turns individual debates '
                'into a research dataset.'
                '</p>',
                unsafe_allow_html=True,
            )

        st.markdown('<hr class="gp-divider">', unsafe_allow_html=True)
        st.markdown(
            '<p class="gp-ref">'
            'Vosoughi, S., Roy, D., &amp; Aral, S. (2018). The spread of true and false news online. '
            '<em>Science, 359</em>(6380), 1146–1151. · '
            'Nyhan, B., &amp; Reifler, J. (2010). When corrections fail: The persistence of political '
            'misperceptions. <em>Political Behavior, 32</em>(2), 303–330. · '
            'Gallup (2023). Media trust at all-time low. · '
            'Médiès, A. et al. (2020). Economic burden of health misinformation. JHSPH.'
            '</p>',
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — HOW TO USE IT
    # ════════════════════════════════════════════════════════════════════════
    with sub_how:
        st.markdown(
            '<p class="gp-section">Getting started in 3 minutes</p>',
            unsafe_allow_html=True,
        )
        st.markdown("""
        <div class="gp-step-row">
            <div class="gp-step">
                <div class="gp-step-num">1</div>
                <div class="gp-step-title">Open the Arena tab</div>
                <div class="gp-step-body">Type any claim you want to test — a health myth, a political narrative, a historical revisionism. Keep it to one clear, debatable statement.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">2</div>
                <div class="gp-step-title">Configure (optional)</div>
                <div class="gp-step-body">In the sidebar, adjust the number of turns, AI models, and whether you want a single claim or a batch of claims run back-to-back.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">3</div>
                <div class="gp-step-title">Start the debate</div>
                <div class="gp-step-body">Click "Start Debate." Watch the exchange unfold turn by turn in real time. Each agent responds to the other directly.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">4</div>
                <div class="gp-step-title">Read the verdict</div>
                <div class="gp-step-body">When debate ends, the judge scores both sides across six dimensions and declares a winner. The scorecard shows exactly why.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">5</div>
                <div class="gp-step-title">Explore the data</div>
                <div class="gp-step-body">Replay past debates, view analytics across all runs, or browse the strategy leaderboard to see which tactics win most often.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<p class="gp-section">The two agents</p>',
            unsafe_allow_html=True,
        )
        st.markdown("""
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem;">
            <div class="gp-role-card" style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.2);">
                <div class="gp-role-title" style="color:#dc2626;">The Spreader</div>
                <div class="gp-role-body">
                    Argues in favour of the claim using the tactics real misinformation uses —
                    appeals to lived experience, selective statistics, narrative framing, and
                    Socratic doubt. <strong>Not crude "fake news" dismissals</strong> — sophisticated,
                    adaptive persuasion that mirrors how misinformation actually behaves in the wild.
                </div>
            </div>
            <div class="gp-role-card" style="background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.2);">
                <div class="gp-role-title" style="color:#2563eb;">The Fact-checker</div>
                <div class="gp-role-body">
                    Counters with evidence, cites credible sources, identifies logical fallacies,
                    and addresses the emotional core of the claim — not just the factual errors.
                    Effective debunking requires understanding <em>why</em> the original claim
                    is persuasive, not just that it is false.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<p class="gp-section">The judge</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'The AI judge evaluates the debate across six dimensions, scored 0–10 for each side. '
            'Crucially, the judge is <strong>role-aware</strong>: it scores the Spreader on how '
            'effectively it executes the spreader\'s role (credibility of narrative, emotional '
            'resonance, adaptability under pressure), not on factual accuracy. This allows '
            'meaningful competition across all six metrics.'
            '</p>',
            unsafe_allow_html=True,
        )

        metric_data = [
            ("Truthfulness proxy", "0.25", "How internally consistent and credible does each side's case appear?"),
            ("Evidence quality", "0.20", "Concrete citations, data, and sourcing to support claims."),
            ("Reasoning quality", "0.20", "Logical structure, avoidance of fallacies, clear argumentation."),
            ("Responsiveness", "0.15", "Direct engagement with the opponent's specific points."),
            ("Persuasion", "0.15", "Rhetorical effectiveness — how compelling is the overall case?"),
            ("Civility", "0.05", "Professional, respectful tone throughout the exchange."),
        ]
        for name, weight, desc in metric_data:
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:0.8rem;'
                f'padding:0.55rem 0.8rem;margin-bottom:0.4rem;'
                f'background:#f9fafb;border-radius:8px;border:1px solid #f3f4f6;">'
                f'<div style="min-width:130px;font-weight:700;font-size:0.9rem;'
                f'color:#111;padding-top:0.05rem;">{name}</div>'
                f'<div style="min-width:52px;font-size:0.8rem;font-weight:700;'
                f'color:#6366f1;padding-top:0.1rem;">×{weight}</div>'
                f'<div style="font-size:0.85rem;color:#4b5563;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p class="gp-section">Navigating the app</p>',
            unsafe_allow_html=True,
        )
        nav_cards = [
            ("🏟️ Arena", "Run a live debate. Single claim or multi-claim batch. Watch it unfold in real time."),
            ("📊 Analytics", "Aggregate metrics across all runs — win rates, score distributions, anomaly detection, claim difficulty, strategy × outcome correlation."),
            ("🎬 Run Replay", "Replay any past debate with full transcript, verdict, momentum chart, strategy lens, and citation audit."),
            ("📋 Claim Analysis", "Deep dive into a specific claim — see how it performs across many runs and model configurations."),
            ("🏆 Strategy Leaderboard", "Which rhetorical tactics appear most often, and which ones actually win? Includes emergent patterns not in the taxonomy."),
            ("📚 Citation Tracker", "Aggregates citation behaviour across all episodes — credibility scoring, source types, temporal patterns."),
            ("🎭 Prompts", "Edit agent and judge prompts to run experiments. Save named variants and compare outcomes."),
        ]
        nav_html = '<div class="gp-step-row">'
        for title, body in nav_cards:
            nav_html += (
                f'<div class="gp-nav-card">'
                f'<div class="gp-nav-title">{title}</div>'
                f'<div class="gp-nav-body">{body}</div>'
                f'</div>'
            )
        nav_html += '</div>'
        st.markdown(nav_html, unsafe_allow_html=True)

        st.markdown(
            '<p class="gp-section">Tips for meaningful results</p>',
            unsafe_allow_html=True,
        )
        cols_tips = st.columns(2)
        with cols_tips[0]:
            st.markdown("**Choose claims with genuine complexity**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Claims that are unambiguously false (e.g. "the Earth is flat") produce '
                'predictable outcomes. Claims with real uncertainty, competing evidence, '
                'or emotionally charged context produce the most interesting debates.'
                '</p>',
                unsafe_allow_html=True,
            )
            st.markdown("**Run the same claim multiple times**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'LLM outputs are stochastic. A single debate is an observation, not a '
                'finding. Run 5–10 episodes of the same claim to see how much variance '
                'exists — that variance is itself a data point.'
                '</p>',
                unsafe_allow_html=True,
            )
        with cols_tips[1]:
            st.markdown("**Compare models**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Try the same claim with GPT-4o on both sides, then with a weaker model '
                'as the spreader. Does better reasoning always win? The answer may '
                'surprise you.'
                '</p>',
                unsafe_allow_html=True,
            )
            st.markdown("**Use the Prompt Library**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Experiment with different agent personas. A subtler, more sophisticated '
                'spreader prompt — one that uses partial truths and narrative framing '
                'rather than crude dismissals — will produce very different outcomes.'
                '</p>',
                unsafe_allow_html=True,
            )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — RESEARCH CONTEXT
    # ════════════════════════════════════════════════════════════════════════
    with sub_about:
        st.markdown(
            '<p class="gp-section">Theoretical grounding</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'Misinformation Arena draws on three intersecting bodies of research: the '
            'psychology of belief formation, the sociology of information diffusion, and '
            'the rhetoric of persuasion.'
            '</p>',
            unsafe_allow_html=True,
        )

        with st.expander("Psychology: why people believe false things"):
            st.markdown("""
**Dual-process theory** (Kahneman, 2011) distinguishes fast intuitive reasoning (System 1)
from slow analytical reasoning (System 2). Misinformation exploits System 1 — it is vivid,
emotionally resonant, and cognitively easy to process. Corrections require System 2
activation, which is effortful and easily bypassed.

**The illusory truth effect** (Hasher et al., 1977; Pennycook et al., 2018): repeated
exposure to a claim increases its perceived truth, regardless of its actual accuracy.
Repetition in the spreader's arguments is not accidental — it is strategic.

**Motivated reasoning** (Kunda, 1990): people evaluate evidence in ways that support
conclusions they are already motivated to reach. A claim that validates existing anxieties
or group identity is processed very differently from one that challenges them.

**The backfire effect** (Nyhan & Reifler, 2010): in some contexts, corrections that
directly contradict a person's identity-linked beliefs can strengthen those beliefs.
This is why the debunker's strategy matters as much as its content.
            """)

        with st.expander("Sociology: how misinformation spreads"):
            st.markdown("""
**Network amplification**: Vosoughi, Roy & Aral (2018) showed false news travels faster,
farther, and deeper through social networks than true news — driven by novelty and
emotional arousal, not bot activity.

**Epistemic communities**: people increasingly rely on trusted in-group sources over
institutional media. This creates segmented information environments where corrections
from "outsiders" carry no weight regardless of their accuracy.

**Platform incentive structures**: engagement-maximising algorithms preferentially surface
emotionally arousing content. Outrage and anxiety drive clicks; careful corrections do not.

**The liar's dividend**: widespread awareness of deepfakes and AI-generated content has
created a climate where any inconvenient evidence can be dismissed as fabricated — even
when it is real. This asymmetry benefits misinformation producers.
            """)

        with st.expander("Rhetoric: what makes misinformation persuasive"):
            st.markdown("""
Effective misinformation is not simply false — it is strategically constructed.
Key rhetorical mechanisms include:

- **Anchoring to partial truths**: building a false narrative on a true foundation
  makes the whole more credible and harder to refute cleanly.
- **Socratic doubt**: "just asking questions" creates uncertainty without requiring
  the spreader to assert anything falsifiable.
- **Narrative framing**: embedding a claim in a story activates empathy and
  identification; abstract statistics rarely compete.
- **Authority laundering**: citing real institutions out of context, or citing
  fringe experts within real fields, borrows credibility selectively.
- **Inoculation resistance**: misinformation that anticipates counter-arguments
  and pre-emptively dismisses them is significantly harder to correct.

Misinformation Arena models these mechanisms. The spreader agent uses them.
Understanding how they perform — which claims they win on and which they don't —
is the central research question.
            """)

        st.markdown(
            '<p class="gp-section">What this system is — and is not</p>',
            unsafe_allow_html=True,
        )
        cols_is = st.columns(2)
        with cols_is[0]:
            st.success("**This system studies** argument competition in controlled, repeatable conditions.")
            st.success("**This system produces** data on persuasive strategy effectiveness across claim types.")
            st.success("**This system enables** controlled experiments on model, prompt, and claim variables.")
        with cols_is[1]:
            st.error("**This system does not** fact-check claims or declare truth.")
            st.error("**This system does not** recommend content moderation or policy.")
            st.error("**This system does not** perfectly simulate human psychology — AI agents are proxies.")

        st.markdown(
            '<p class="gp-section">Full reference list</p>',
            unsafe_allow_html=True,
        )
        st.markdown("""
- Brady, W. J., Wills, J. A., Jost, J. T., Tucker, J. A., & Van Bavel, J. J. (2017). Emotion shapes the diffusion of moralized content in social networks. *PNAS, 114*(28), 7313–7318.
- Hasher, L., Goldstein, D., & Toppino, T. (1977). Frequency and the conference of referential validity. *Journal of Verbal Learning and Verbal Behavior, 16*(1), 107–112.
- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux.
- Kunda, Z. (1990). The case for motivated reasoning. *Psychological Bulletin, 108*(3), 480–498.
- Nyhan, B., & Reifler, J. (2010). When corrections fail: The persistence of political misperceptions. *Political Behavior, 32*(2), 303–330.
- Pennycook, G., Cannon, T. D., & Rand, D. G. (2018). Prior exposure increases perceived accuracy of fake news. *Journal of Experimental Psychology: General, 147*(12), 1865–1880.
- Pennycook, G., & Rand, D. G. (2020). Who falls for fake news? The roles of bullshit receptivity, overclaiming, familiarity, and analytic thinking. *Journal of Personality, 88*(2), 185–200.
- Vosoughi, S., Roy, D., & Aral, S. (2018). The spread of true and false news online. *Science, 359*(6380), 1146–1151.
        """)
