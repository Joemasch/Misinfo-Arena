# Experiment Proposal — Misinformation Arena v2

**Prepared for:** Advisor review and approval
**Prepared by:** Joe Mascher
**Date:** April 2026

---

## Research Questions

1. **RQ1:** How does conversation length affect the strategies AI agents use and the outcomes of adversarial misinformation debates?
2. **RQ2:** How do AI agents perform across different misinformation domains, and which claim types are hardest for the fact-checker to counter?
3. **RQ3:** Does the choice of LLM model (as spreader, debunker, or judge) affect debate outcomes?

---

## Constants (Held Fixed Across All Experiments)

| Parameter | Value | Justification |
|---|---|---|
| Spreader prompt | IME507 Research Default (3,022 chars) | Literature-grounded; 8 rhetorical strategies from inoculation/misinformation research |
| Debunker prompt | IME507 Research Default (4,178 chars) | 6-step response architecture based on inoculation theory |
| Judge rubric | v2 — 6 equal-weight dimensions | Grounded in Wachsmuth et al. (2017), D2D (EMNLP 2025), Roozenbeek & van der Linden (2022) |
| Spreader temperature | 0.85 | High creativity mirrors real misinformation variability |
| Debunker temperature | 0.40 | Low temperature for consistent, evidence-grounded responses |
| Judge temperature | 0.10 | Near-deterministic scoring |

---

## Models Under Test

| Model | Provider | Role in experiments |
|---|---|---|
| gpt-4o-mini | OpenAI | Spreader, Debunker, and Judge |
| claude-haiku-4-5 | Anthropic | Spreader and Debunker |
| gemini-2.0-flash | Google | Spreader and Debunker |

Three providers ensure genuine architectural diversity — different training data, alignment approaches, and safety philosophies.

---

## Judge Scoring Dimensions

| Dimension | Weight | Source |
|---|---|---|
| Factuality | 1/6 | D2D (EMNLP 2025) |
| Source Credibility | 1/6 | D2D (EMNLP 2025) |
| Reasoning Quality | 1/6 | Wachsmuth et al. (2017) — Cogency |
| Responsiveness | 1/6 | Wachsmuth et al. (2017) — Reasonableness |
| Persuasion | 1/6 | Wachsmuth et al. (2017) — Effectiveness |
| Manipulation Awareness | 1/6 | Inoculation theory (Roozenbeek & van der Linden, 2022) |

Equal weights per Wachsmuth's argument that fixed unequal weights introduce unjustified bias. The judge uses role-relative scoring: the spreader is evaluated on persuasive effectiveness, not factual accuracy.

---

## Experiment A — Conversation Length

### Purpose

Determine how debate length affects which strategies agents use, whether the spreader's persuasion advantage grows or shrinks over time, and whether longer debates produce more decisive outcomes.

### Design

- **Claims:** 30 (6 per domain × 5 domains)
- **Domains:** Health/Vaccine, Political/Election, Environmental, Economic, Institutional Conspiracy
- **Independent variable:** Max turns per episode (2, 4, 6, 8, 10)
- **Episodes per claim:** 5 (one per turn count)
- **Arena mode:** Single-claim (one claim per run, 5 episodes per run)

### Model Combinations

Each claim is tested across 9 model matchups (3 spreader × 3 debunker, fixed judge):

| Matchup | Spreader | Debunker | Judge |
|---|---|---|---|
| 1 | gpt-4o-mini | gpt-4o-mini | gpt-4o-mini |
| 2 | gpt-4o-mini | claude-haiku-4-5 | gpt-4o-mini |
| 3 | gpt-4o-mini | gemini-2.0-flash | gpt-4o-mini |
| 4 | claude-haiku-4-5 | gpt-4o-mini | gpt-4o-mini |
| 5 | claude-haiku-4-5 | claude-haiku-4-5 | gpt-4o-mini |
| 6 | claude-haiku-4-5 | gemini-2.0-flash | gpt-4o-mini |
| 7 | gemini-2.0-flash | gpt-4o-mini | gpt-4o-mini |
| 8 | gemini-2.0-flash | claude-haiku-4-5 | gpt-4o-mini |
| 9 | gemini-2.0-flash | gemini-2.0-flash | gpt-4o-mini |

### Execution

For each claim, 9 runs are created (one per matchup). Each run contains 5 episodes with staggered turn counts:

```
Run 1 (GPT vs GPT):    Claim A → 2 turns, 4 turns, 6 turns, 8 turns, 10 turns
Run 2 (GPT vs Claude): Claim A → 2 turns, 4 turns, 6 turns, 8 turns, 10 turns
...
Run 9 (Gemini vs Gemini): Claim A → 2 turns, 4 turns, 6 turns, 8 turns, 10 turns
```

Then repeat for all 30 claims.

### Total Episodes

30 claims × 9 matchups × 5 turn counts = **1,350 episodes**

### Estimated Cost

~$20–35

### Dependent Variables (what we measure)

- Winner (spreader, debunker, or draw)
- Score margin (debunker total − spreader total)
- Judge confidence (0–1)
- Per-dimension scores (6 dimensions × 2 sides = 12 scores)
- Strategy labels (from 20-label taxonomy per episode)
- Concession data (if early stop occurs: who conceded, at what turn)

### Analysis Plan

| Question | Statistical test | Tool |
|---|---|---|
| Does turn count affect win rate? | Chi-squared | Minitab |
| Does turn count affect score margin? | One-way ANOVA with Tukey post-hoc | Minitab |
| Does persuasion score change with debate length? | Linear regression | Minitab |
| Do strategy distributions shift with turn count? | Descriptive (frequency by turn count) | Arena app |
| Does the turn count effect differ by model? | Filtered turn sensitivity chart | Arena app |

---

## Experiment B — Domain Effects

### Purpose

Determine which misinformation domains are hardest for the fact-checker to counter, whether certain domains trigger different strategies, and whether model choice interacts with domain difficulty.

### Design

- **Claims:** 100 (20 per domain × 5 domains)
- **Domains:** Health/Vaccine, Political/Election, Environmental, Economic, Institutional Conspiracy
- **Independent variable:** Claim domain (claim_type)
- **Turn count:** Fixed at the optimal value determined by Experiment A results (likely 6)
- **Arena mode:** Multi-claim (all claims in one run per matchup)

### Model Combinations

Same 9 matchups as Experiment A. Each matchup processes all 100 claims in a single multi-claim run.

### Execution

```
Run 1 (GPT vs GPT):       100 claims × 6 turns each
Run 2 (GPT vs Claude):    100 claims × 6 turns each
...
Run 9 (Gemini vs Gemini): 100 claims × 6 turns each
```

### Total Episodes

100 claims × 9 matchups = **900 episodes**

### Estimated Cost

~$15–25

### Claim Set Requirements

Each domain's 20 claims should include:
- A range of complexity (simple factual claims, nuanced multi-part claims, conspiracy-level claims)
- Claims that a real person might share on social media
- Specific, falsifiable statements (not questions or opinions)
- No overlap with the 30 claims used in Experiment A (to avoid contamination)

### Analysis Plan

| Question | Statistical test | Tool |
|---|---|---|
| Does domain affect win rate? | Chi-squared | Minitab |
| Does domain affect score margin? | One-way ANOVA with Tukey post-hoc | Minitab |
| Does model choice interact with domain? | Two-way ANOVA (model × domain) | Minitab |
| Which model is the best spreader? | One-way ANOVA on persuasion score by spreader_model | Minitab |
| Which model is the best debunker? | One-way ANOVA on FC win rate by debunker_model | Minitab |
| Do strategy distributions differ by domain? | Descriptive (strategy × claim type heatmap) | Arena app |
| Which claims are hardest to debunk? | Claim difficulty index | Arena app |
| Are outcomes consistent across models for each claim? | Outcome consistency table | Arena app |

---

## Experiment Sequence

| Phase | What | When | Depends on |
|---|---|---|---|
| 1 | Prepare 30-claim set (Experiment A) | Day 1 | Nothing |
| 2 | Run Experiment A (1,350 episodes) | Day 1–2 | Phase 1 |
| 3 | Analyze Experiment A results | Day 2 | Phase 2 |
| 4 | Determine optimal turn count for Experiment B | Day 2 | Phase 3 |
| 5 | Prepare 100-claim set (Experiment B) | Day 2–3 | Nothing (can overlap with Phase 2) |
| 6 | Run Experiment B (900 episodes) | Day 3 | Phases 4 + 5 |
| 7 | Analyze Experiment B results | Day 3–4 | Phase 6 |
| 8 | Statistical significance testing in Minitab | Day 4 | Phases 3 + 7 |
| 9 | Human evaluation study (15–20 episodes) | Day 4–5 | Phases 2 + 6 |
| 10 | Write up findings | Day 5+ | All phases |

---

## Total Budget

| Experiment | Episodes | Estimated cost |
|---|---|---|
| Experiment A | 1,350 | $20–35 |
| Experiment B | 900 | $15–25 |
| **Total** | **2,250** | **$35–60** |

---

## Deliverables

Upon completion, the following will be available:

1. **Raw data:** 2,250 episode records in JSON v2 format with full transcripts, scorecards, and strategy labels
2. **Statistical exports:** 5 pre-formatted CSVs for Minitab (turn count, domain, model comparison, judge consistency, concession analysis)
3. **Human evaluation data:** 15–20 annotated episodes with human-AI agreement statistics
4. **Analytics dashboard:** All results viewable in the Misinformation Arena app across 7 tabs
5. **Known limitations:** Documented before data collection (see `docs/known_limitations.md`)

---

## Questions for Advisor

1. **Judge model:** Should the judge model (gpt-4o-mini) remain fixed, or should we vary it as a third independent variable? (See `docs/experiment_design_options.md` for full analysis of Options 1–3.)
2. **Claim sets:** Should the 30 + 100 claims be pre-registered before data collection?
3. **Experiment sequence:** Can Experiments A and B run in parallel, or should A complete first so its results inform B's turn count?
4. **Human evaluation:** Is 15–20 episodes sufficient for the human validation study, or should we aim for more?

---

*This proposal is based on the Misinformation Arena v2 platform. All features described are implemented and tested. The platform is ready for experiment execution.*
