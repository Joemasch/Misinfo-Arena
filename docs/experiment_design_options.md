# Experiment Design Options — Misinformation Arena v2

**Prepared for:** Advisor review
**Date:** April 2026
**Purpose:** Define the experimental structure before data collection begins.

---

## Research Questions

1. **RQ1 — Conversation Length:** How does debate length affect the strategies agents use and who wins?
2. **RQ2 — Domain Effects:** How do agents perform across different misinformation domains (health, political, environmental, economic, conspiracy)?
3. **RQ3 — Model Effects:** Does the choice of LLM model (as spreader, debunker, or judge) affect debate outcomes?

---

## Constants Across All Experiments

| Parameter | Value | Rationale |
|---|---|---|
| Spreader prompt | IME507 Research Default | Literature-grounded, held constant per advisor guidance |
| Debunker prompt | IME507 Research Default | Same |
| Judge rubric | v2 — 6 equal-weight dimensions | Grounded in Wachsmuth (2017), D2D (EMNLP 2025), inoculation theory |
| Temperature (spreader) | 0.85 | High creativity mirrors real misinformation variability |
| Temperature (debunker) | 0.40 | Low temperature for consistent, evidence-grounded responses |
| Judge temperature | 0.10 | Near-deterministic scoring |

---

## Models Under Test

| Model | Provider | Tier | Cost (per 1M tokens in/out) |
|---|---|---|---|
| gpt-4o-mini | OpenAI | Cheap | $0.15 / $0.60 |
| claude-haiku-4-5 | Anthropic | Mid | $0.80 / $4.00 |
| gemini-2.0-flash | Google | Cheap | $0.10 / $0.40 |

Three providers ensure genuine architectural diversity — different training data, alignment approaches, and safety philosophies.

---

## Experiment A — Conversation Length (Single-Claim Arena)

**Design:** One claim per run. Each run has 5 episodes at turn counts 2, 4, 6, 8, 10.

**Claims:** 30 total, 6 per domain.

**Independent variable:** Max turns per episode.

**Dependent variables:** Winner, score margin, persuasion score, manipulation_awareness score, strategy labels.

### The Judge Model Question

This is where advisor input is needed. Three options:

---

### Option 1 — Fixed Judge (Recommended)

**Judge model:** gpt-4o-mini for all episodes.

**Agent model combinations:** 3 spreader × 3 debunker = 9 matchups.

| Episodes | Calculation | Cost estimate |
|---|---|---|
| 9 matchups × 30 claims × 5 turn counts | 1,350 | ~$20–30 |

**Pros:**
- Cleanest design — the judge is not a variable, so any outcome differences are attributable to the agent models and turn count
- Smallest budget
- Easiest to analyze (two independent variables: model pair + turn count)

**Cons:**
- Cannot assess whether the judge model affects verdicts
- If gpt-4o-mini has systematic biases as a judge, all results inherit that bias

**Judge sensitivity check (add-on):** Re-judge 100 stored transcripts with gemini-flash and grok-mini judges. Compute inter-judge agreement. This costs ~$2 extra and answers "does the judge model matter?" without running 1,350 extra debates.

---

### Option 2 — Judge as Independent Variable

**Judge model:** Varies per run (gpt-4o-mini, gemini-flash, grok-mini).

**Agent model combinations:** 3 spreader × 3 debunker × 3 judge = 27 combinations.

| Episodes | Calculation | Cost estimate |
|---|---|---|
| 27 combos × 30 claims × 5 turn counts | 4,050 | ~$60–100 |

**Pros:**
- Full factorial design — can make claims about judge model effects with statistical power
- Can detect if certain judge models favor certain agent models (judge-agent interaction effects)

**Cons:**
- 3× the cost and runtime of Option 1
- Three independent variables (spreader model, debunker model, judge model, turn count) make analysis more complex
- May be overkill if the judge model has minimal effect (which the sensitivity check in Option 1 can determine first)

---

### Option 3 — Phased Approach (Compromise)

**Phase 1:** Run Option 1 (fixed judge, 1,350 episodes, ~$25).

**Phase 2:** Run the judge sensitivity check on stored transcripts (~$2).

**Phase 3:** If Phase 2 shows the judge model matters (inter-judge agreement < 0.8), expand to Option 2 for a subset of claims (e.g., 10 claims instead of 30 = 1,350 additional episodes).

| Total episodes | Worst case (judge matters) | Best case (judge doesn't matter) |
|---|---|---|
| Phase 1 | 1,350 | 1,350 |
| Phase 2 | ~100 re-judgings | ~100 re-judgings |
| Phase 3 | 1,350 more | 0 |
| **Total** | **2,800** | **1,450** |
| **Cost** | **~$45–70** | **~$22–30** |

**Pros:**
- Data-driven decision: only spend the extra budget if the judge model actually affects results
- Gets results faster (Phase 1 is complete before deciding on Phase 3)
- Defensible methodology: "We first established judge consistency, then expanded where needed"

**Cons:**
- Two-phase analysis is slightly more complex to report
- Phase 3 claims are a subset, not the full 30

---

## Experiment B — Domain Effects (Multi-Claim Arena)

**Design:** 100 claims across 5 domains (20 per domain), fixed turn count.

**Turn count:** Determined by Experiment A results (whichever turn count shows the most interesting strategy variation).

**Judge:** Same decision as Experiment A (fixed or variable).

| Option | Matchups | Episodes | Cost estimate |
|---|---|---|---|
| Fixed judge (9 matchups) | 9 × 100 claims | 900 | ~$15–25 |
| Variable judge (27 combos) | 27 × 100 claims | 2,700 | ~$45–70 |

---

## Summary for Advisor Decision

| | Option 1: Fixed Judge | Option 2: Full Factorial | Option 3: Phased |
|---|---|---|---|
| **Total episodes** | ~2,250 | ~6,750 | ~2,350–4,150 |
| **Total cost** | ~$35–55 | ~$105–170 | ~$37–100 |
| **Can claim judge effects?** | No (sensitivity check only) | Yes (full statistical power) | Conditionally |
| **Analysis complexity** | Low | High (3+ IVs) | Medium |
| **Time to first results** | Fast | Slow | Fast (Phase 1) |
| **Recommendation** | Best for thesis deadline | Best for publication | Best overall |

---

## Advisor Questions

1. Is the judge model an independent variable in the research design, or a methodological parameter to be validated?
2. If the judge sensitivity check (Option 1 add-on) shows high agreement across judge models (κ > 0.8), is that sufficient to report a fixed-judge design?
3. For the 30 single-claim claims — should they be pre-registered, or is the claim set itself exploratory?
4. Should Experiment A (turn length) complete before Experiment B (domains) starts, or can they run in parallel?

---

*Generated from Misinformation Arena v2 experiment planning session.*
