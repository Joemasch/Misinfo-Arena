# Statistical Testing Guide — Misinformation Arena v2

> **Purpose:** Step-by-step instructions for every statistical test in the thesis.
> **Tools:** Minitab, SPSS, or R. Instructions written for Minitab; adapt as needed.
> **Last updated:** 2026-04-09

---

## How to Use This Guide

1. Go to **Tools > Exports** in the app
2. Download the CSV for the specific test you want to run
3. Open it in Minitab (File > Open Worksheet)
4. Follow the instructions below

Each test has:
- **What it answers** — the research question
- **Export file** — which CSV to download
- **Columns used** — what's in the CSV
- **Minitab steps** — where to click
- **How to interpret** — what the output means

---

## Study 1: Judge Validation

### Test 1.1: Cohen's Kappa (Winner Agreement)

**What it answers:** Do the AI judge and human rater agree on who won?

**Data needed:** Human annotations (from Annotate page) + judge verdicts. The app computes this automatically in the Annotate tab — no manual export needed.

**How to interpret:**
- κ > 0.80 = almost perfect agreement
- κ 0.60–0.80 = substantial agreement
- κ 0.40–0.60 = moderate agreement
- κ < 0.40 = poor — consider a different judge model

### Test 1.2: Spearman Rank Correlation (Per-Dimension Scores)

**What it answers:** Does the judge rank episodes similarly to the human on each dimension?

**Export:** `judge_validation.csv`

**Procedure (per judge model, per dimension):**
1. Filter to one judge model
2. Pair each episode's judge score with your human annotation score
3. In Minitab: Stat > Basic Statistics > Correlation
4. Select the two score columns
5. Check "Spearman" (not Pearson — scores are ordinal)

**How to interpret:**
- ρ > 0.70 = strong agreement on this dimension
- ρ 0.50–0.70 = moderate — judge partially captures your reasoning
- ρ < 0.50 = weak — judge evaluates this dimension differently than you

**Do this for all 6 dimensions × all 4 judge candidates = 24 correlations.**

### Test 1.3: Consistency (Coefficient of Variation)

**What it answers:** Does the judge give the same scores when re-evaluating the same transcript?

**Export:** `judge_validation.csv` (with consistency_n and consistency_std columns)

**Procedure:**
1. For each judge model, compute: CV = consistency_std / mean(confidence)
2. Lower CV = more consistent
3. In Minitab: Stat > Basic Statistics > Display Descriptive Statistics on confidence, grouped by judge_model

**How to interpret:**
- CV < 0.05 = highly consistent
- CV 0.05–0.10 = acceptable
- CV > 0.10 = too variable for research use

### Test 1.4: Confidence Discrimination

**What it answers:** Does the judge use the full confidence range, or cluster at one value?

**Procedure:**
1. In Minitab: Stat > Basic Statistics > Display Descriptive Statistics on confidence, grouped by judge_model
2. Look at the standard deviation

**How to interpret:**
- StDev > 0.10 = good discrimination (the judge distinguishes close calls from blowouts)
- StDev < 0.05 = poor — judge defaults to similar confidence regardless of debate quality

---

## Study 2: Conversation Length Effects

### Test 2.1: One-Way ANOVA — Turn Count → Score Margin

**What it answers:** Does debate length affect the score gap between sides?

**Export:** `study2_anova_turns_margin.csv`

**Minitab steps:**
1. Stat > ANOVA > One-Way
2. Response: `margin`
3. Factor: `max_turns`
4. Click OK

**How to interpret:**
- p < 0.05 = debate length significantly affects score margin
- Look at the means plot: does margin increase or decrease with more turns?
- If debunker margin grows with length → longer debates favor debunkers

### Test 2.2: Chi-Squared — Turn Count → Win Rate

**What it answers:** Does debate length affect who wins?

**Export:** `study2_chi2_turns_winner.csv`

**Minitab steps:**
1. Stat > Tables > Cross Tabulation and Chi-Square
2. Rows: `max_turns`
3. Columns: `winner`
4. Check "Chi-Square test"

**How to interpret:**
- p < 0.05 = win distribution differs significantly across turn lengths
- Look at the table: does debunker win rate increase with more turns?

### Test 2.3: Two-Way ANOVA — Model × Turn Count on Margin

**What it answers:** Do some models improve more with debate length than others?

**Export:** `study2_anova_model_turns.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model > Fit General Linear Model
2. Response: `margin`
3. Factors: `model_matchup`, `max_turns`
4. Under Model: include the interaction term (model_matchup × max_turns)

**How to interpret:**
- Main effect of max_turns: does length matter overall?
- Main effect of model_matchup: do some pairs produce different margins?
- **Interaction p < 0.05** = the effect of length depends on which models are debating — this is the key finding

### Test 2.4: T-Test — Same-Model vs Cross-Model Pairs

**What it answers:** Do mirror matchups (GPT vs GPT) behave differently than cross-model matchups?

**Export:** `study2_ttest_same_model.csv`

**Minitab steps:**
1. Stat > Basic Statistics > 2-Sample t
2. Sample 1: margin where same_model = 1
3. Sample 2: margin where same_model = 0

**How to interpret:**
- p < 0.05 = mirror matchups produce significantly different margins
- Compare means: are mirror matchups closer (smaller margin) or more decisive?

### Test 2.5: Two-Way ANOVA — Tier × Turn Count

**What it answers:** Do budget models respond differently to debate length than premium models?

**Export:** `study2_anova_tier_turns.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model
2. Response: `margin`
3. Factors: `debunker_tier`, `max_turns`
4. Include interaction

**How to interpret:**
- Interaction p < 0.05 = budget and premium models have different length-sensitivity curves
- If premium debunkers improve more with length → capability matters more in longer debates

### Test 2.6: Length × Difficulty Interaction

**What it answers:** Does debate length matter more for hard claims?

**Export:** `study2_anova_turns_margin.csv` (includes claim column — classify as easy/hard)

**Minitab steps:**
1. Create a new column: "difficulty" = "easy" for C1/C2, "hard" for C3/C4
2. Stat > ANOVA > General Linear Model
3. Response: `margin`
4. Factors: `difficulty`, `max_turns`
5. Include interaction

---

## Study 3: Claim Type Effects

### Test 3.1: One-Way ANOVA — Claim Type → Score Margin

**What it answers:** Are some claim types harder to debunk?

**Export:** `study3_anova_type_margin.csv`

**Minitab steps:**
1. Stat > ANOVA > One-Way
2. Response: `margin`
3. Factor: `claim_type`

**How to interpret:**
- p < 0.05 = claim type significantly affects score margin
- Post-hoc (Tukey's): which types differ from each other?

### Test 3.2: Chi-Squared — Claim Type → Win Rate

**What it answers:** Does claim type affect who wins?

**Export:** `study3_chi2_type_winner.csv`

**Minitab steps:**
1. Stat > Tables > Cross Tabulation and Chi-Square
2. Rows: `claim_type`
3. Columns: `winner`

### Test 3.3: Two-Way ANOVA — Model × Claim Type

**What it answers:** Do models specialize by claim domain?

**Export:** `study3_anova_model_type.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model
2. Response: `margin`
3. Factors: `model_matchup`, `claim_type`
4. Include interaction

**How to interpret:**
- **Interaction p < 0.05** = the best model depends on the claim type
- This is a key Study 3 finding

### Test 3.4: Two-Way ANOVA — Tier × Claim Type

**What it answers:** Do budget models struggle more on certain claim types?

**Export:** `study3_anova_tier_type.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model
2. Response: `margin`
3. Factors: `debunker_tier`, `claim_type`
4. Include interaction

---

## Cross-Study: Model Comparison

### Test 4.1: One-Way ANOVA — Best Spreader Model

**What it answers:** Which model is the most effective spreader?

**Export:** `model_best_spreader.csv`

**Minitab steps:**
1. Stat > ANOVA > One-Way
2. Response: `margin`
3. Factor: `model_spreader`

**How to interpret:**
- Lower margin = better spreader (closer to winning)
- Post-hoc (Tukey's): which spreaders differ significantly?

### Test 4.2: One-Way ANOVA — Best Debunker Model

**What it answers:** Which model is the most effective debunker?

**Export:** `model_best_debunker.csv`

**Minitab steps:**
1. Stat > ANOVA > One-Way
2. Response: `margin`
3. Factor: `model_debunker`

**How to interpret:**
- Higher margin = better debunker (larger gap over spreader)

### Test 4.3: Two-Way ANOVA — Spreader × Debunker Model

**What it answers:** Do specific matchups produce results that can't be predicted from individual model effects?

**Export:** `model_interaction.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model
2. Response: `margin`
3. Factors: `model_spreader`, `model_debunker`
4. Include interaction

**How to interpret:**
- Interaction p < 0.05 = certain pairings produce unexpected results
- Example: Claude might be a strong debunker overall but weaker specifically against Gemini

### Test 4.4: T-Test — Cross-Provider vs Within-Provider

**What it answers:** Do debates between models from different providers play out differently?

**Export:** `model_cross_provider.csv`

**Minitab steps:**
1. Stat > Basic Statistics > 2-Sample t
2. Group by: `cross_provider`
3. Response: `margin`

---

## Quick Reference

| Test | Type | Export File |
|---|---|---|
| 1.1 Kappa | Cohen's kappa | (computed in app) |
| 1.2 Dimension correlation | Spearman | judge_validation.csv |
| 1.3 Consistency | Descriptive stats | judge_validation.csv |
| 1.4 Confidence discrimination | Descriptive stats | judge_validation.csv |
| 2.1 Turns → margin | One-way ANOVA | study2_anova_turns_margin.csv |
| 2.2 Turns → winner | Chi-squared | study2_chi2_turns_winner.csv |
| 2.3 Model × turns | Two-way ANOVA | study2_anova_model_turns.csv |
| 2.4 Same vs cross model | 2-sample t-test | study2_ttest_same_model.csv |
| 2.5 Tier × turns | Two-way ANOVA | study2_anova_tier_turns.csv |
| 2.6 Turns × difficulty | Two-way ANOVA | study2_anova_turns_margin.csv + manual difficulty tag |
| 3.1 Type → margin | One-way ANOVA | study3_anova_type_margin.csv |
| 3.2 Type → winner | Chi-squared | study3_chi2_type_winner.csv |
| 3.3 Model × type | Two-way ANOVA | study3_anova_model_type.csv |
| 3.4 Tier × type | Two-way ANOVA | study3_anova_tier_type.csv |
| 4.1 Best spreader | One-way ANOVA | model_best_spreader.csv |
| 4.2 Best debunker | One-way ANOVA | model_best_debunker.csv |
| 4.3 Spreader × debunker | Two-way ANOVA | model_interaction.csv |
| 4.4 Cross vs within provider | 2-sample t-test | model_cross_provider.csv |

---

*Each export CSV contains exactly the columns needed for that test — no filtering required. Download, open in Minitab, run the test.*
