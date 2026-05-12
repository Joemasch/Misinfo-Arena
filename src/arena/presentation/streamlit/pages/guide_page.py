"""
Home / Guide Page for Misinformation Arena v2.

Editorial dark-mode design scoped to the Home tab only.
Uses Playfair Display for headers, IBM Plex Sans for body, IBM Plex Mono for data.
"""

import streamlit as st


def _inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,800;1,400;1,700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&display=swap');

    /* ── Scoped dark container ── */
    .hp-dark {
        background: var(--color-bg);
        color: var(--color-text-primary);
        padding: 2.5rem 0;
        border-radius: 4px;
        width: 100%;
    }

    /* ── Typography ── */
    .hp-dark h1, .hp-h1 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.6rem; font-weight: 700;
        color: var(--color-text-primary); letter-spacing: -0.5px;
        line-height: 1.15; margin: 0 0 0.5rem 0;
        text-align: center;
    }
    .hp-dark h2, .hp-h2 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.6rem; font-weight: 400;
        color: var(--color-accent-red); margin: 2.5rem 0 0.5rem 0;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid var(--color-border);
        text-align: center;
    }
    .hp-dark h3, .hp-h3 {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.8rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 2px;
        color: var(--color-text-muted); margin: 2rem 0 0.6rem 0;
        text-align: center;
    }
    .hp-prose {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.97rem; color: #C8C4B9;
        line-height: 1.78;
        margin: 0 0 1rem 0;
        text-align: center;
    }
    .hp-prose strong { color: var(--color-text-primary); }
    .hp-prose em { color: #999; }

    /* ── Stat cards ── */
    .hp-stat-row {
        display: flex; gap: 1rem; flex-wrap: wrap;
        margin: 1.8rem 0;
    }
    .hp-stat {
        flex: 1; min-width: 220px;
        background: var(--color-surface);
        border-left: 3px solid var(--color-accent-red);
        border-radius: 4px;
        padding: 1.2rem 1.4rem;
        text-align: center;
    }
    .hp-stat-num {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 3rem; font-weight: 700;
        color: var(--color-accent-red); line-height: 1;
        margin-bottom: 0.3rem;
    }
    .hp-stat-label {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.75rem; color: var(--color-text-muted);
        text-transform: uppercase; letter-spacing: 1.5px;
        line-height: 1.5;
    }

    /* ── Pull quote ── */
    .hp-quote {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.1rem; font-style: italic;
        color: var(--color-text-primary);
        border-left: 3px solid var(--color-accent-red);
        padding: 0.8rem 1.3rem;
        margin: 1.8rem auto;
        background: rgba(201,54,62,0.06);
        border-radius: 0 4px 4px 0;
        max-width: 780px;
        line-height: 1.65;
    }
    .hp-quote-cite {
        font-style: normal; font-size: 0.85rem;
        color: var(--color-text-muted); display: block; margin-top: 0.4rem;
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* ── Agent cards ── */
    .hp-agents-row {
        display: flex; gap: 1rem; flex-wrap: wrap;
        margin: 1.2rem 0;
    }
    .hp-agent-card {
        flex: 1; min-width: 280px;
        background: var(--color-surface);
        padding: 1.5rem;
        border-radius: 4px;
    }
    .hp-agent-card.spreader { border-left: 3px solid var(--color-accent-amber); }
    .hp-agent-card.factchecker { border-left: 3px solid var(--color-accent-blue); }
    .hp-agent-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.15rem; font-weight: 700;
        font-style: italic; margin-bottom: 0.6rem;
    }
    .hp-agent-title.spreader { color: var(--color-accent-amber); }
    .hp-agent-title.factchecker { color: var(--color-accent-blue); }
    .hp-agent-body {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.88rem; color: #999;
        line-height: 1.65;
    }

    /* ── Scoring table ── */
    .hp-score-table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    .hp-score-table td {
        padding: 0.6rem 0.8rem;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.88rem; color: #C8C4B9;
        border-bottom: 1px solid #1A1A1A;
    }
    .hp-score-table tr:nth-child(odd) td { background: #0F0F0F; }
    .hp-score-table tr:nth-child(even) td { background: #141414; }
    .hp-score-name { font-weight: 500; color: #E8E4D9; min-width: 170px; }
    .hp-score-weight {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem; font-weight: 500;
        color: #666; background: #1E1E1E;
        padding: 0.15rem 0.5rem; border-radius: 999px;
        display: inline-block;
    }
    .hp-score-cite {
        font-size: 0.78rem; color: #555; font-style: italic;
    }

    /* ── Three-column features ── */
    .hp-features-row {
        display: flex; gap: 1rem; flex-wrap: wrap;
        margin: 1.2rem 0;
    }
    .hp-feature {
        flex: 1; min-width: 200px;
        background: #111; border-radius: 4px;
        padding: 1.2rem;
        border-top: 2px solid #C9363E;
    }
    .hp-feature-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.9rem; font-weight: 700;
        color: #E8E4D9; margin-bottom: 0.4rem;
    }
    .hp-feature-body {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.82rem; color: #888;
        line-height: 1.6;
    }

    /* ── Fixed parameter cards ── */
    .hp-fixed-row {
        display: flex; gap: 1rem; flex-wrap: wrap;
        margin: 1rem 0;
    }
    .hp-fixed {
        flex: 1; min-width: 240px;
        background: #111; border-radius: 4px;
        padding: 1.1rem 1.3rem;
        border-left: 2px solid #333;
    }
    .hp-fixed-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.85rem; font-weight: 700;
        color: #E8E4D9; margin-bottom: 0.3rem;
    }
    .hp-fixed-body {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.82rem; color: #888;
        line-height: 1.6;
    }
    .hp-fixed-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem; color: #C9363E;
        margin-top: 0.2rem;
    }

    /* ── References ── */
    .hp-ref {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.78rem; color: #555;
        line-height: 1.65;
        border-top: 1px solid #1A1A1A;
        padding-top: 0.8rem; margin-top: 1.5rem;
    }

    /* ── Divider ── */
    .hp-divider {
        border: none; border-top: 1px solid #1A1A1A;
        margin: 2rem 0;
    }

    /* ── Nav cards ── */
    .hp-nav-row {
        display: flex; gap: 0.75rem; flex-wrap: wrap;
        margin: 1rem 0;
    }
    .hp-nav-card {
        flex: 1; min-width: 170px;
        background: #111; border: 1px solid #1A1A1A;
        border-radius: 4px; padding: 0.9rem 1rem;
    }
    .hp-nav-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.88rem; font-weight: 700;
        color: #E8E4D9; margin-bottom: 0.25rem;
    }
    .hp-nav-body {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.78rem; color: #666; line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)


def render_guide_page():
    from arena.presentation.streamlit.styles import inject_global_css
    inject_global_css()
    _inject_styles()

    # Everything wrapped in the dark container
    st.markdown('<div class="hp-dark">', unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────
    st.markdown(
        '<h1 class="hp-h1">Misinformation Arena</h1>'
        '<p class="hp-prose" style="font-size:1.1rem;color:#999;max-width:720px;margin:0 auto 0.7rem auto;text-align:center;">'
        'Watch two AI models debate a misinformation claim live. See who wins, why, '
        'and what each side did. Every debate teaches you something the research found '
        'across 960 episodes — embedded in the experience, not buried in a paper.'
        '</p>',
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # Sub-tabs (outside dark container so Streamlit tab styling works)
    tab_about, tab_how, tab_research = st.tabs(["About", "How to use it", "Research design"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — ABOUT
    # ══════════════════════════════════════════════════════════════════════
    with tab_about:
        st.markdown('<div class="hp-dark">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">We are living through an information crisis</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'Skepticism toward the sources we rely on — news media, government agencies, '
            'scientific institutions — has reached levels that would have seemed extreme '
            'a generation ago. A 2023 Gallup poll found that trust in mass media hit an '
            'all-time low, with only 32% of Americans reporting a &ldquo;great deal&rdquo; or '
            '&ldquo;fair amount&rdquo; of trust. We are not just disagreeing about facts — '
            'we are disagreeing about who gets to establish them.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-stat-row">
            <div class="hp-stat">
                <div class="hp-stat-num">6&times;</div>
                <div class="hp-stat-label">Faster spread of false news vs. true news on social media (Science, 2018)</div>
            </div>
            <div class="hp-stat">
                <div class="hp-stat-num" style="color:#D4A843;">32%</div>
                <div class="hp-stat-label">Americans who trust mass media &ldquo;a great deal&rdquo; or &ldquo;fair amount&rdquo; (Gallup, 2023)</div>
            </div>
            <div class="hp-stat">
                <div class="hp-stat-num" style="color:#4A7FA5;">$78B</div>
                <div class="hp-stat-label">Estimated annual economic cost of health misinformation in the US (JHSPH, 2020)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="hp-quote">'
            '&ldquo;False news is more novel than true news, which suggests it is the novelty of '
            'false news that attracts human attention and encourages sharing, not its accuracy.&rdquo;'
            '<span class="hp-quote-cite">Vosoughi, Roy &amp; Aral, Science, 2018</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<h2 class="hp-h2">The problem with fact-checking alone</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'The standard response to misinformation has been to fact-check it — label a '
            'claim as true or false, attach a correction, and move on. Research has '
            'repeatedly shown this is insufficient. Corrections often reach only a fraction '
            'of the original audience. They can trigger a &ldquo;backfire effect&rdquo; in deeply '
            'committed believers. And they treat misinformation as a static object rather '
            'than a dynamic, adaptive process that evolves in response to challenge.'
            '</p>'
            '<p class="hp-prose">'
            'Misinformation succeeds because it tells stories. It exploits real '
            'uncertainties in complex topics. It speaks to genuine anxieties. '
            'Understanding <strong>how</strong> it persuades — not just <em>that</em> '
            'it is false — is the key to countering it.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<h2 class="hp-h2">What this platform does differently</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'Two AI models debate a misinformation claim. A third AI judges. Every argument, '
            'every citation, every rhetorical tactic is captured — and surfaced back to you '
            'as the debate unfolds.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-features-row">
            <div class="hp-feature">
                <div class="hp-feature-title">Simulate the exchange</div>
                <div class="hp-feature-body">
                    Run a real argumentative back-and-forth — see how a spreader responds to
                    pushback, how a fact-checker adapts when emotional appeals land. Five
                    exchanges by default, configurable per episode.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">Measure persuasion, not just truth</div>
                <div class="hp-feature-body">
                    The judge scores eight dimensions, equally weighted — factuality,
                    source reputability, hallucination index, reasoning, responsiveness, persuasion,
                    manipulation awareness, and adaptability. A claim can be false and still win rhetorically.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">Learn while you watch</div>
                <div class="hp-feature-body">
                    Citation toasts and strategy chips pop up live during each turn. After
                    the verdict, a plain-English explainer ties the outcome to specific
                    findings from our 960-episode study.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<p class="hp-ref">'
            'Vosoughi, S., Roy, D., &amp; Aral, S. (2018). The spread of true and false news online. '
            '<em>Science, 359</em>(6380), 1146&ndash;1151. &middot; '
            'Nyhan, B., &amp; Reifler, J. (2010). When corrections fail. '
            '<em>Political Behavior, 32</em>(2), 303&ndash;330. &middot; '
            'Gallup (2023). Media trust at all-time low. &middot; '
            'JHSPH (2020). Economic burden of health misinformation.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — HOW TO USE IT
    # ══════════════════════════════════════════════════════════════════════
    with tab_how:
        st.markdown('<div class="hp-dark">', unsafe_allow_html=True)

        # ── User flow walkthrough ─────────────────────────────────────────
        st.markdown('<h2 class="hp-h2">Run your first debate</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'The app is built around a single magic moment: watching two AI models actually argue. '
            'Everything else exists to make that moment more meaningful.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-features-row">
            <div class="hp-feature">
                <div class="hp-feature-title">1. Pick a claim</div>
                <div class="hp-feature-body">
                    Click a <strong>Quickstart</strong> chip on the Arena tab, or type your own claim.
                    The app auto-detects the domain (Health, Political, Tech, Environmental, Economic)
                    and shows a <strong>Falsifiable / Unfalsifiable</strong> badge so you know what
                    kind of debate to expect.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">2. Configure models</div>
                <div class="hp-feature-body">
                    Each episode has its own row: choose a spreader model, a fact-checker model, and
                    how many exchanges to run. Want to run two episodes with the same models in
                    swapped roles? Add a second row and flip them.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">3. Start &mdash; or Showdown</div>
                <div class="hp-feature-body">
                    <strong>Start Debate</strong> runs your configured episodes back-to-back.
                    <strong>Run Showdown</strong> queues four model matchups on the same claim
                    in one click &mdash; the fastest way to see how different models argue the same thing.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="hp-features-row">
            <div class="hp-feature">
                <div class="hp-feature-title">4. Watch live</div>
                <div class="hp-feature-body">
                    Messages stream turn by turn. The progress bar shows
                    <em>Episode X/N &middot; Exchange Y/M &middot; current phase</em>.
                    Citation and strategy toasts pop up the moment something interesting happens
                    &mdash; <em>WHO cited by Fact-checker (Turn 2)</em>, <em>Spreader used: Conspiracy Framing (Turn 3)</em>.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">5. Read the verdict</div>
                <div class="hp-feature-body">
                    The verdict card explains who won and <strong>why</strong> in plain English &mdash;
                    citing falsifiability dynamics, hedge ratios, or tactic diversity from our study.
                    Then a <strong>&ldquo;What to try next&rdquo;</strong> panel suggests a context-aware
                    next debate, never repeating what you just did.
                </div>
            </div>
            <div class="hp-feature">
                <div class="hp-feature-title">6. Dig deeper</div>
                <div class="hp-feature-body">
                    Open the <strong>Replay</strong> tab. The Strategy sub-tab shows a swimlane of
                    every tactic by turn. Citations shows how each side framed its sources.
                    Compare puts two episodes side-by-side and adapts based on whether you picked
                    same-claim or same-domain candidates.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        # ── The agents — what they actually are ──────────────────────────
        st.markdown('<h2 class="hp-h2">The two agents</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'Both agents receive minimal instructions &mdash; roughly 180 characters each. '
            'No predefined tactics. No strategy lists. The only directive is which side to argue. '
            'Everything you see &mdash; the conspiratorial framing, the institutional distrust, '
            'the evidence citation, the mechanism explanation &mdash; emerges from the model&rsquo;s '
            'training, not from prompt engineering.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-agents-row">
            <div class="hp-agent-card spreader">
                <div class="hp-agent-title spreader">The Spreader</div>
                <div class="hp-agent-body">
                    Argues <strong>in favor</strong> of the claim. With free-will prompting,
                    we observe what tactics the model actually defaults to &mdash; the rhetorical
                    fingerprint of its training, not the engineer&rsquo;s preferences.
                </div>
            </div>
            <div class="hp-agent-card factchecker">
                <div class="hp-agent-title factchecker">The Fact-Checker</div>
                <div class="hp-agent-body">
                    Argues <strong>against</strong> the claim. Same minimal prompt structure.
                    On falsifiable claims, models converge on evidence citation; on unfalsifiable
                    ones, they diverge by training lineage.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">The judge</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'An AI judge evaluates the debate across eight dimensions, scored 0&ndash;10 for each side. '
            'All dimensions are weighted equally. The judge uses <strong>role-relative scoring</strong>: '
            'the spreader is scored on persuasive effectiveness, not factual accuracy.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <table class="hp-score-table">
            <tr>
                <td class="hp-score-name">Factuality</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Narrative consistency (spreader) / factual grounding (fact-checker)</td>
                <td class="hp-score-cite">D2D, EMNLP 2025</td>
            </tr>
            <tr>
                <td class="hp-score-name">Source Reputability</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Specificity and authority of cited sources</td>
                <td class="hp-score-cite">D2D, EMNLP 2025</td>
            </tr>
            <tr>
                <td class="hp-score-name">Hallucination Index</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Apparent validity of cited evidence; penalizes fabricated-sounding sources</td>
                <td class="hp-score-cite">LLM-as-judge</td>
            </tr>
            <tr>
                <td class="hp-score-name">Reasoning Quality</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Logical structure, avoidance of fallacies</td>
                <td class="hp-score-cite">Wachsmuth 2017 &mdash; Cogency</td>
            </tr>
            <tr>
                <td class="hp-score-name">Responsiveness</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Direct engagement with opponent&rsquo;s strongest point</td>
                <td class="hp-score-cite">Wachsmuth 2017 &mdash; Reasonableness</td>
            </tr>
            <tr>
                <td class="hp-score-name">Persuasion</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Convincingness to an uncommitted reader</td>
                <td class="hp-score-cite">Wachsmuth 2017 &mdash; Effectiveness</td>
            </tr>
            <tr>
                <td class="hp-score-name">Manipulation Awareness</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Penalizes manipulation (spreader) / rewards naming tactics (fact-checker)</td>
                <td class="hp-score-cite">Inoculation theory</td>
            </tr>
            <tr>
                <td class="hp-score-name">Adaptability</td>
                <td><span class="hp-score-weight">1/8</span></td>
                <td>Tactical evolution across turns; rewards introducing new angles over repetition</td>
                <td class="hp-score-cite">Argumentation dynamics</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown(
            '<p class="hp-prose">'
            '<strong>Why equal weights?</strong> '
            'Per Wachsmuth et al. (2017), fixed unequal weights introduce unjustified bias. '
            'A sensitivity analysis showed zero outcome flips across 7 weight schemes.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">Navigating the app</h2>', unsafe_allow_html=True)
        st.markdown("""
        <div class="hp-nav-row">
            <div class="hp-nav-card">
                <div class="hp-nav-title">Home</div>
                <div class="hp-nav-body">You&rsquo;re here. Context for the platform and a walkthrough of the user flow.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">Arena</div>
                <div class="hp-nav-body">Run a debate. Quickstart claims, per-episode model rows, Showdown mode, live citation &amp; strategy toasts.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">Replay</div>
                <div class="hp-nav-body">
                    Browse past episodes (with domain &amp; falsifiability columns) and drill into any one
                    via five sub-tabs: <em>Verdict</em>, <em>Transcript</em>, <em>Strategy</em>,
                    <em>Citations</em>, <em>Compare</em>.
                </div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">Atlas</div>
                <div class="hp-nav-body">
                    Reference library for the strategies and citations you encounter. Each entry has
                    a definition and shows which of your debates featured it. Three columns: spreader-leaning,
                    used by both, fact-checker-leaning.
                </div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">Findings</div>
                <div class="hp-nav-body">
                    The five findings from the 960-episode study, each with effect sizes, supporting visuals,
                    and a plain-English interpretation.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        # ── Features you might miss ──────────────────────────────────────
        st.markdown('<h3 class="hp-h3">Small things that change the experience</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose" style="font-size:0.9rem;">'
            '<strong>Domain badges</strong> appear on every episode card &mdash; coloured per domain '
            '(Health pink, Political purple, Tech cyan, Environmental lime, Economic orange, Conspiracy amber). '
            '<strong>Falsifiability badges</strong> sit next to claims everywhere they appear &mdash; green '
            'for falsifiable, amber for unfalsifiable. <strong>Cross-domain Compare is intentionally disabled</strong> '
            '&mdash; comparing two claims from different domains confounds the model and the topic, so the '
            'Compare tab only surfaces same-claim or same-domain candidates. <strong>The Compare tab adapts</strong> '
            'based on which candidate you pick: same-claim shows model fingerprints; same-domain shows tactic '
            'consistency, citation continuity, and per-side behavioural metrics.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — RESEARCH DESIGN
    # ══════════════════════════════════════════════════════════════════════
    with tab_research:
        st.markdown('<div class="hp-dark">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">What we tested</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'The findings surfaced in this app come from a fully-crossed factorial experiment of '
            '<strong>960 adversarial AI debates</strong>. Every cell of the design grid was run, '
            'with each debate judged by an independent model (<strong>Grok-3</strong>) to avoid '
            'in-family judge bias.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-stat-row">
            <div class="hp-stat">
                <div class="hp-stat-num">4</div>
                <div class="hp-stat-label">Models tested as spreader &amp; fact-checker (GPT-4o-mini, Claude Haiku 4.5, Gemini 2.5 Flash, Grok-3 Mini)</div>
            </div>
            <div class="hp-stat">
                <div class="hp-stat-num" style="color:#D4A843;">20</div>
                <div class="hp-stat-label">Misinformation claims spanning Health, Political, Tech, Environmental, Conspiracy</div>
            </div>
            <div class="hp-stat">
                <div class="hp-stat-num" style="color:#4A7FA5;">5</div>
                <div class="hp-stat-label">Domains for cross-topic comparison</div>
            </div>
            <div class="hp-stat">
                <div class="hp-stat-num" style="color:#7BAF6D;">3</div>
                <div class="hp-stat-label">Turn lengths (2, 4, 6 exchanges) to capture short and long debate dynamics</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<p class="hp-prose" style="font-size:0.92rem;">'
            '4 spreaders &times; 4 fact-checkers &times; 20 claims &times; 3 turn lengths = '
            '<strong>960 episodes</strong>. Each episode produces a structured judge verdict, '
            'a per-turn strategy trace, and a citation log &mdash; the raw material for every '
            'finding and every analytics view in this platform.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">The five findings</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'Ordered by causal logic. The claim sets the difficulty &rarr; each model brings a fixed toolkit '
            '&rarr; interactions are reactive but predictable &rarr; evidence quality varies by domain &rarr; '
            'the side that deepens its argument wins.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-nav-row">
            <div class="hp-nav-card">
                <div class="hp-nav-title">F1 &mdash; Falsifiability</div>
                <div class="hp-nav-body">Falsifiable claims collapse for spreaders; unfalsifiable claims stay competitive. The single biggest determinant of who wins.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">F2 &mdash; Fingerprints</div>
                <div class="hp-nav-body">Each model has a signature tactic mix. Claude leans on appeal-to-trust; GPT-4o-mini on emotional framing; Gemini on mechanism.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">F3 &mdash; Game Theory</div>
                <div class="hp-nav-body">Strategy choice is reactive to the opponent&rsquo;s last turn. Co-occurrence and lag-1 transitions are highly structured.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">F4 &mdash; Source Weaponization</div>
                <div class="hp-nav-body">9,050 citations, 0 fabricated. Both sides cite the same institutions &mdash; spreaders just hedge 2.4&times; more.</div>
            </div>
            <div class="hp-nav-card">
                <div class="hp-nav-title">F5 &mdash; Adaptability</div>
                <div class="hp-nav-body">Tactical evolution across turns is the strongest predictor of winning (r = 0.753). Bottom-quartile adaptability wins only 28% of the time.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">Why are certain things fixed?</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            'This platform holds several parameters constant by design. Each fixed variable '
            'eliminates a confound and makes cross-run comparisons meaningful.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="hp-fixed-row">
            <div class="hp-fixed">
                <div class="hp-fixed-title">Free-will prompts</div>
                <div class="hp-fixed-body">
                    Both agents receive roughly 180 characters of instruction &mdash; just the
                    role assignment. No prescribed tactics, no strategy lists. This is a
                    deliberate methodological choice: rhetorical patterns we observe come from
                    the model&rsquo;s training, not from prompt engineering by the researcher.
                </div>
                <div class="hp-fixed-value">~180 chars each &middot; identical structure for both sides</div>
            </div>
            <div class="hp-fixed">
                <div class="hp-fixed-title">Temperatures are fixed</div>
                <div class="hp-fixed-body">
                    Same temperature on both sides keeps the playing field even. The judge runs
                    near-zero to minimise scoring noise across repeated evaluations.
                </div>
                <div class="hp-fixed-value">Spreader 0.85 &middot; Fact-checker 0.40 &middot; Judge 0.10</div>
            </div>
        </div>
        <div class="hp-fixed-row">
            <div class="hp-fixed">
                <div class="hp-fixed-title">Equal weights</div>
                <div class="hp-fixed-body">
                    Per Wachsmuth et al. (2017), fixed unequal weights introduce unjustified bias.
                    A sensitivity analysis showed zero outcome flips across 7 different weight
                    schemes &mdash; the score gaps are large enough to be robust.
                </div>
                <div class="hp-fixed-value">All 8 dimensions &times; 1/8 weight</div>
            </div>
            <div class="hp-fixed">
                <div class="hp-fixed-title">Role-relative scoring</div>
                <div class="hp-fixed-body">
                    The spreader is evaluated on persuasive execution, not factual accuracy.
                    Without this, the fact-checker wins by default on every dimension &mdash;
                    which tells you nothing about how misinformation actually works.
                </div>
                <div class="hp-fixed-value">Spreader scored on persuasion &middot; Fact-checker scored on evidence</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        st.markdown('<h2 class="hp-h2">Literature grounding</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose">'
            '<strong>Scoring dimensions (Wachsmuth axes):</strong> Wachsmuth et al. (2017) &ldquo;Argumentation Quality Assessment&rdquo; (ACL) '
            '&mdash; cogency, reasonableness, effectiveness'
            '</p>'
            '<p class="hp-prose">'
            '<strong>Factuality, source reputability, hallucination index:</strong> D2D &mdash; Debate-to-Detect (EMNLP 2025) '
            '&middot; LLM-as-judge literature (Zheng et al. 2023)'
            '</p>'
            '<p class="hp-prose">'
            '<strong>Manipulation awareness:</strong> Inoculation theory &mdash; Roozenbeek &amp; van der Linden (2022) '
            '&middot; Cook et al. (2017) &ldquo;Neutralizing misinformation through inoculation&rdquo; (PLOS ONE)'
            '</p>'
            '<p class="hp-prose">'
            '<strong>Strategy taxonomy:</strong> FLICC &mdash; Cook &amp; Lewandowsky (2020) '
            '&middot; SemEval-2023 Task 3 &mdash; persuasion technique detection'
            '</p>'
            '<p class="hp-prose">'
            '<strong>Open-coded labels:</strong> Grounded Theory &mdash; Glaser &amp; Strauss (1967). '
            'Strategy labels are emergent from the debates themselves, not assigned from a fixed list.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="hp-divider">', unsafe_allow_html=True)

        st.markdown('<h3 class="hp-h3">Known limitations</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hp-prose" style="font-size:0.88rem;">'
            'Safety-aligned models may soften the spreader role &middot; '
            'No absolute quality baseline (scores are relative within each debate) &middot; '
            'Non-deterministic judge (slight variance across repeated evaluations) &middot; '
            'Findings are LLM-on-LLM &mdash; human-evaluation baseline not yet conducted &middot; '
            'English-language claims only'
            '</p>'
            '<p class="hp-prose" style="font-size:0.82rem;color:#555;">'
            'Full discussion: docs/known_limitations.md'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)
