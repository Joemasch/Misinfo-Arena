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

    tab_about, tab_how, tab_research = st.tabs(["About", "How to use it", "Research design"])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — ABOUT
    # ════════════════════════════════════════════════════════════════════════
    with tab_about:
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
                <div class="gp-stat-num" style="color:#ef4444;">6&times;</div>
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
            'Two AI agents debate a claim. A third AI judges. Every argument, every score, '
            'every strategy is recorded.'
            '</p>',
            unsafe_allow_html=True,
        )

        cols_why = st.columns(3)
        with cols_why[0]:
            st.markdown("**Simulate the exchange**")
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
            st.markdown("**Test at scale**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Import hundreds of claims via CSV, use auto-run to execute them '
                'back-to-back, and generate thousands of episodes without manual '
                'intervention. The analytics layer turns individual debates into a '
                'research dataset.'
                '</p>',
                unsafe_allow_html=True,
            )

        st.markdown('<hr class="gp-divider">', unsafe_allow_html=True)
        st.markdown(
            '<p class="gp-ref">'
            'Vosoughi, S., Roy, D., &amp; Aral, S. (2018). The spread of true and false news online. '
            '<em>Science, 359</em>(6380), 1146&ndash;1151. &middot; '
            'Nyhan, B., &amp; Reifler, J. (2010). When corrections fail: The persistence of political '
            'misperceptions. <em>Political Behavior, 32</em>(2), 303&ndash;330. &middot; '
            'Gallup (2023). Media trust at all-time low. &middot; '
            'M&eacute;di&egrave;s, A. et al. (2020). Economic burden of health misinformation. JHSPH.'
            '</p>',
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — HOW TO USE IT
    # ════════════════════════════════════════════════════════════════════════
    with tab_how:
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
                <div class="gp-step-title">Enter a claim or upload CSV</div>
                <div class="gp-step-body">Type a single claim directly, or import a CSV/XLSX file with many claims to run them as a batch experiment.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">3</div>
                <div class="gp-step-title">Start the debate</div>
                <div class="gp-step-body">Click "Start debate." Watch the exchange unfold turn by turn in real time. Each agent responds to the other directly.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">4</div>
                <div class="gp-step-title">Read the verdict</div>
                <div class="gp-step-body">When the debate ends, the judge scores both sides across six dimensions and declares a winner. The scorecard shows exactly why.</div>
            </div>
            <div class="gp-step">
                <div class="gp-step-num">5</div>
                <div class="gp-step-title">Explore the data</div>
                <div class="gp-step-body">Use the 7 tabs — Arena, Analytics, Replay, Claim Analysis, Strategy Leaderboard, Prompt Library, and Guide — to dig into results from every angle.</div>
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
                    Uses the IME507 research prompt with 8 rhetorical strategies — appeals to
                    lived experience, selective statistics, narrative framing, Socratic doubt,
                    and more. <strong>Not crude dismissals</strong> — sophisticated, adaptive
                    persuasion grounded in misinformation research literature.
                </div>
            </div>
            <div class="gp-role-card" style="background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.2);">
                <div class="gp-role-title" style="color:#2563eb;">The Fact-checker</div>
                <div class="gp-role-body">
                    Uses the IME507 6-step response architecture — identify the core falsehood,
                    provide the factual alternative, explain the fallacy, cite credible sources,
                    address the emotional appeal, and inoculate against future variants.
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
            'The AI judge evaluates the debate across six dimensions, scored 0&ndash;10 for each side. '
            'All dimensions are weighted equally (1/6 each). The judge is <strong>role-aware</strong>: '
            'it scores the Spreader on how effectively it executes the spreader\'s role, not on '
            'factual accuracy. This allows meaningful competition across all six metrics.'
            '</p>',
            unsafe_allow_html=True,
        )

        metric_data = [
            ("Factuality", "1/6",
             "Narrative consistency (spreader) / factual grounding (debunker). "
             "D2D, EMNLP 2025."),
            ("Source Credibility", "1/6",
             "Specificity and checkability of cited sources. "
             "D2D, EMNLP 2025."),
            ("Reasoning Quality", "1/6",
             "Logical structure and avoidance of fallacies. "
             "Wachsmuth et al. 2017 — Cogency."),
            ("Responsiveness", "1/6",
             "Direct engagement with the opponent's specific points. "
             "Wachsmuth et al. 2017 — Reasonableness."),
            ("Persuasion", "1/6",
             "Convincingness to an uncommitted reader. "
             "Wachsmuth et al. 2017 — Effectiveness."),
            ("Manipulation Awareness", "1/6",
             "Penalizes manipulation (spreader) / rewards naming tactics (debunker). "
             "Inoculation theory."),
        ]
        for name, weight, desc in metric_data:
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:0.8rem;'
                f'padding:0.55rem 0.8rem;margin-bottom:0.4rem;'
                f'background:#f9fafb;border-radius:8px;border:1px solid #f3f4f6;">'
                f'<div style="min-width:160px;font-weight:700;font-size:0.9rem;'
                f'color:#111;padding-top:0.05rem;">{name}</div>'
                f'<div style="min-width:40px;font-size:0.8rem;font-weight:700;'
                f'color:#6366f1;padding-top:0.1rem;">{weight}</div>'
                f'<div style="font-size:0.85rem;color:#4b5563;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p class="gp-prose" style="margin-top:1rem;">'
            '<strong>Why equal weights?</strong> '
            'Per Wachsmuth et al. (2017), fixed unequal weights introduce unjustified bias. '
            'Argument quality is context-dependent, and no single dimension should dominate '
            'scoring a priori.'
            '</p>'
            '<p class="gp-prose">'
            '<strong>Why role-relative scoring?</strong> '
            'The spreader is scored on persuasive effectiveness, not factual accuracy. '
            'This allows meaningful competition and prevents the debunker from winning by '
            'default on every dimension.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="gp-section">Navigating the app</p>',
            unsafe_allow_html=True,
        )
        nav_cards = [
            ("Arena", "Run a live debate. Single claim or CSV batch. Watch it unfold in real time."),
            ("Analytics", "Aggregate metrics across all runs — win rates, score distributions, anomaly detection."),
            ("Replay", "Replay any past debate with full transcript, verdict, scorecard, strategy lens, and export."),
            ("Strategy", "Which rhetorical tactics appear most often, and which ones actually win?"),
            ("Claim Analysis", "Deep dive into a specific claim — see how it performs across runs and model configurations."),
            ("Prompt Library", "View active agent and judge prompts. Save named variants for reference."),
            ("Guide", "You are here. Research motivation, system overview, and design rationale."),
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
            st.markdown("**Use CSV import for systematic experiments**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Prepare a spreadsheet of claims organized by topic, domain, or difficulty. '
                'Upload via CSV and run them as a batch to generate a structured dataset '
                'in one session.'
                '</p>',
                unsafe_allow_html=True,
            )
            st.markdown("**Run the same claim multiple times**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'LLM outputs are stochastic. A single debate is an observation, not a '
                'finding. Run 5&ndash;10 episodes of the same claim to see how much variance '
                'exists — that variance is itself a data point.'
                '</p>',
                unsafe_allow_html=True,
            )
        with cols_tips[1]:
            st.markdown("**Compare models across providers**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'Try the same claim with GPT-4o on both sides, then swap in a different '
                'model as the spreader or debunker. Does better reasoning always win? '
                'The answer may surprise you.'
                '</p>',
                unsafe_allow_html=True,
            )
            st.markdown("**Use the auto-run feature for batch experiments**")
            st.markdown(
                '<p style="font-size:0.88rem;color:#4b5563;">'
                'When running multiple claims, enable auto-run to execute all episodes '
                'back-to-back without manual intervention. This is the fastest way to '
                'build a large dataset for analysis.'
                '</p>',
                unsafe_allow_html=True,
            )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — RESEARCH DESIGN
    # ════════════════════════════════════════════════════════════════════════
    with tab_research:
        st.markdown(
            '<p class="gp-section">Why are certain things fixed?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'Misinformation Arena holds several parameters constant by design. Each '
            'fixed variable eliminates a confound and makes cross-run comparisons meaningful.'
            '</p>',
            unsafe_allow_html=True,
        )

        # --- Fixed prompts ---
        st.markdown("**Prompts are fixed**")
        st.markdown(
            '<p class="gp-prose">'
            'The IME507 prompts are grounded in misinformation research literature. '
            'Varying prompts would make it impossible to isolate whether outcome '
            'differences come from the prompt or the model. Per advisor guidance, '
            'prompts are held constant so that model capability is the independent variable.'
            '</p>',
            unsafe_allow_html=True,
        )

        # --- Fixed temperatures ---
        st.markdown("**Temperatures are fixed**")
        st.markdown(
            '<p class="gp-prose">'
            'Spreader 0.85 (high creativity mirrors real misinformation variability), '
            'Debunker 0.40 (consistent, evidence-grounded responses), '
            'Judge 0.10 (near-deterministic scoring). '
            'Varying temperature would introduce an uncontrolled variable that '
            'confounds model-level comparisons.'
            '</p>',
            unsafe_allow_html=True,
        )

        # --- Equal weights ---
        st.markdown("**Equal weights**")
        st.markdown(
            '<p class="gp-prose">'
            'Per Wachsmuth et al. (2017), fixed unequal weights introduce unjustified '
            'bias. A sensitivity analysis showed zero outcome flips across 7 different '
            'weight schemes — the weights do not matter because the score gaps are '
            'large enough to be robust.'
            '</p>',
            unsafe_allow_html=True,
        )

        # --- Role-relative scoring ---
        st.markdown("**Role-relative scoring**")
        st.markdown(
            '<p class="gp-prose">'
            'The spreader is evaluated on persuasive execution, not factual accuracy. '
            'Without this, the debunker wins by default on every dimension — which '
            'tells you nothing about how misinformation actually works. Role-relative '
            'scoring is what makes the competition informative.'
            '</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="gp-divider">', unsafe_allow_html=True)

        # --- Literature grounding ---
        st.markdown(
            '<p class="gp-section">Literature grounding</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'Key citations that inform the system design:'
            '</p>',
            unsafe_allow_html=True,
        )
        st.markdown("""
- **Wachsmuth et al. (2017)** — Computational argumentation quality assessment. Defines cogency, reasonableness, and effectiveness as top-level quality dimensions. Basis for our scoring rubric.
- **D2D / Debate-to-Detect (EMNLP 2025)** — Adversarial debate framework for misinformation detection. Informs our factuality and source credibility dimensions.
- **Cook & Lewandowsky (2020)** — The FLICC taxonomy of science denial techniques. Basis for strategy labels applied to spreader arguments.
- **SemEval-2023 Task 3** — Persuasion technique detection in news articles. Informs our manipulation awareness dimension.
- **Roozenbeek & van der Linden (2022)** — Inoculation theory applied to misinformation resistance. Underpins the manipulation awareness scoring for debunkers.
- **Cook et al. (2017)** — Neutralizing misinformation through inoculation. Informs the debunker prompt architecture.
        """)

        st.markdown('<hr class="gp-divider">', unsafe_allow_html=True)

        # --- Known limitations ---
        st.markdown(
            '<p class="gp-section">Known limitations</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gp-prose">'
            'A detailed discussion lives in <code>docs/known_limitations.md</code>. '
            'Key limitations in brief:'
            '</p>',
            unsafe_allow_html=True,
        )
        st.markdown("""
- **Keyword-based concession detection** — concession is detected via keyword matching, which can produce false positives on nuanced language.
- **Safety-aligned models playing spreader** — models with strong safety training may refuse or soften the spreader role, reducing ecological validity.
- **No absolute quality baseline** — scores are relative within a debate, not calibrated against an external ground truth.
- **Non-deterministic judge** — even at temperature 0.10, the judge produces slight scoring variance across repeated evaluations of the same transcript.
        """)
