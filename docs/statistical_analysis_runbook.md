# Statistical Analysis Runbook

> **Framework:** Prof. RP's ANOVA & Regression methodology (IME 503)
> **Tool:** Minitab
> **LOS:** α = 0.05 unless stated otherwise
> **Data source:** Tools > Exports in the app
> **Last updated:** 2026-04-21

---

## Key Rules (Prof. RP)

1. **Decision Rule (D.R.):** Reject H₀ if P < α (LOS)
2. **Interaction first:** In multi-factor ANOVA, check the interaction term FIRST. If significant, it "explains the whole story" — do not interpret main effects separately. Generate an interaction plot.
3. **Follow-up tests:** If one-factor ANOVA rejects H₀, conduct Tukey's multiple comparisons to identify which pairs of means differ.
4. **Fixed effects:** All factors in this experiment are fixed effects (specific models chosen, not random).
5. **Practical significance:** A statistically significant result must also be practically meaningful. Report both.

---

## Test 1: Strategy Frequency by Model (Chi-Squared)

**Finding it supports:** Finding 1 — Model Strategy Fingerprints

**Purpose:** Do models use strategies at significantly different frequencies as spreader?

**Hypotheses:**
- H₀: Strategy frequency distribution is the same across all models
- Hₐ: At least one model's strategy distribution is significantly different

**Export:** `f1_strategy_by_model.csv`

**Data prep:** Filter to `side = spreader` only

**Minitab steps:**
1. File > Open Worksheet > `f1_strategy_by_model.csv`
2. Filter to rows where side = spreader
3. Stat > Tables > Cross Tabulation and Chi-Square
4. Rows: `model`
5. Columns: `strategy`
6. Check: Chi-Square test
7. Click OK

**D.R.:** Reject H₀ if P < 0.05

**Report template:** "A chi-squared test of independence was conducted to determine if strategy frequency distribution differs by model. χ²(df) = ___, P = ___. Since P [</>] α = 0.05, we [reject/FTR] H₀."

**If significant:** Look at observed vs expected counts to see which cells deviate most.

**Repeat for:** side = debunker

**Results:**
- Spreader: χ²(___) = ___, P = ___  → [Reject / FTR]
- Debunker: χ²(___) = ___, P = ___  → [Reject / FTR]

---

## Test 2.1: Strategy by Claim Type Within Model (Chi-Squared)

**Finding it supports:** Finding 2 — Strategy Adaptation by Claim Type

**Purpose:** Does a given model adapt its strategy based on claim type?

**Hypotheses:**
- H₀: The model uses the same strategy distribution regardless of claim type
- Hₐ: The strategy distribution differs significantly across claim types

**Export:** Same `f1_strategy_by_model.csv`

**Data prep:** Filter to one model + side = spreader

**Minitab steps:**
1. Filter to one model (e.g., gpt-4o-mini) AND side = spreader
2. Stat > Tables > Cross Tabulation and Chi-Square
3. Rows: `claim_type`
4. Columns: `strategy`
5. Check: Chi-Square test
6. Click OK

**D.R.:** Reject H₀ if P < 0.05

**Report template:** "For [model] as spreader, χ²(df) = ___, P = ___. Since P [</>] α, we [reject/FTR] H₀ and conclude that [model] [does/does not] adapt its strategy based on claim domain."

**Repeat for each model:**
- Claude Sonnet: χ²(___) = ___, P = ___  → [Reject / FTR]
- Gemini Flash:  χ²(___) = ___, P = ___  → [Reject / FTR]
- GPT-4o:        χ²(___) = ___, P = ___  → [Reject / FTR]
- GPT-4o-mini:   χ²(___) = ___, P = ___  → [Reject / FTR]

---

## Test 2.2: Model × Claim Type on Margin (Two-Factor ANOVA with Interaction)

**Finding it supports:** Finding 2 — Strategy Adaptation by Claim Type

**Purpose:** Do model matchup and claim type affect score margin, and is there an interaction?

**Hypotheses:**
- H₀(A): μ_margin is equal across all model matchups (αᵢ = 0 for all i)
- H₀(B): μ_margin is equal across all claim types (βⱼ = 0 for all j)
- H₀(AB): There is no interaction between model matchup and claim type (αβᵢⱼ = 0)
- Hₐ: At least one of the above is false

**Export:** `f2_model_x_claimtype_margin.csv`

**Minitab steps:**
1. File > Open Worksheet > `f2_model_x_claimtype_margin.csv`
2. Stat > ANOVA > General Linear Model > Fit General Linear Model
3. Response: `margin`
4. Factors: `model_matchup`, `claim_type`
5. Under Model tab: ensure interaction term `model_matchup*claim_type` is included
6. Click OK
7. If interaction significant: Stat > ANOVA > Interaction Plot

**D.R. (Prof. RP's interaction rule):**
- Check interaction FIRST
- If P(interaction) < 0.05: interaction explains the story — generate interaction plot
- If P(interaction) ≥ 0.05: check main effects individually

**Results:**
- Interaction (A×B): F = ___, P = ___  → [Significant / Not significant]
- Main effect A (model_matchup): F = ___, P = ___
- Main effect B (claim_type): F = ___, P = ___

**Interpretation:** ___

---

## Test 3.1: Tactic-Naming by Debunker Model (Chi-Squared)

**Finding it supports:** Finding 3 — Game Theory / Strategic Interaction

**Purpose:** Do debunker models name manipulation tactics at different rates?

**Hypotheses:**
- H₀: Tactic-naming rate is the same across all debunker models
- Hₐ: At least one model names tactics at a significantly different rate

**Export:** `f3_tactic_naming_by_model.csv`

**Minitab steps:**
1. File > Open Worksheet
2. Stat > Tables > Cross Tabulation and Chi-Square
3. Rows: `model_debunker`
4. Columns: `uses_tactic_naming`
5. Check: Chi-Square test
6. Click OK

**D.R.:** Reject H₀ if P < 0.05

**Note:** All models show near-100% tactic-naming. Expect P ≥ 0.05 (FTR). This confirms prompt adherence, not model differences.

**Results:** χ²(___) = ___, P = ___  → [Reject / FTR]

---

## Test 4.1: Citation Quality by Debunker Model (One-Factor ANOVA + Tukey's)

**Finding it supports:** Finding 4 — Citation Quality

**Purpose:** Does named source citation rate differ by debunker model?

**Hypotheses:**
- H₀: μ₁ = μ₂ = μ₃ = μ₄ (mean named sources/ep is equal across all debunker models)
- Hₐ: At least one pair of means is not equal

**Export:** `f4_citations_by_model.csv`

**Minitab steps:**
1. File > Open Worksheet > `f4_citations_by_model.csv`
2. Stat > ANOVA > One-Way
3. Select "Response data are in one column for all factor levels"
4. Response: `deb_named_sources`
5. Factor: `model_debunker`
6. Click Multiple Comparisons > select Tukey's
7. Click OK

**D.R.:** Reject H₀ if P < 0.05

**Report template:** "A one-factor completely randomized ANOVA model was applied. F(3, ___) = ___, P = ___. Since P < α = 0.05, we reject H₀ and conclude there is a significant difference in citation quality among debunker models."

**Tukey's follow-up (Prof. RP format):**
- For each pair, report if the C.I. covers zero (FTR) or does not cover zero (Reject)
- Expected: Gemini Flash differs from all others. Claude/GPT-4o/GPT-4o-mini not significantly different from each other.

**Results:**
- F(3, ___) = ___, P = ___  → [Reject / FTR]
- Tukey pairs:
  - Claude vs Gemini: [Significant / Not significant]
  - Claude vs GPT-4o: [Significant / Not significant]
  - Claude vs GPT-4o-mini: [Significant / Not significant]
  - Gemini vs GPT-4o: [Significant / Not significant]
  - Gemini vs GPT-4o-mini: [Significant / Not significant]
  - GPT-4o vs GPT-4o-mini: [Significant / Not significant]

---

## Test 4.2: Model × Claim Type on Citations (Two-Factor ANOVA with Interaction)

**Finding it supports:** Finding 4 — Citation Quality

**Purpose:** Does citation quality depend on both model and claim domain?

**Hypotheses:**
- H₀(A): μ_citations is equal across debunker models
- H₀(B): μ_citations is equal across claim types
- H₀(AB): No interaction
- Hₐ: At least one is false

**Export:** Same `f4_citations_by_model.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model > Fit General Linear Model
2. Response: `deb_named_sources`
3. Factors: `model_debunker`, `claim_type`
4. Include interaction: `model_debunker*claim_type`
5. Click OK

**D.R.:** Check interaction first (Prof. RP's rule).

**Results:**
- Interaction: F = ___, P = ___  → [Significant / Not significant]
- Main effect (model): F = ___, P = ___
- Main effect (claim_type): F = ___, P = ___

**Interpretation:** ___

---

## Test 5.1: Strategy Diversity by Turn Length (One-Factor ANOVA)

**Finding it supports:** Finding 5 — Strategy Depth Plateau

**Purpose:** Does strategy diversity (unique tactics per episode) differ by debate length?

**Hypotheses:**
- H₀: μ₂turns = μ₆turns = μ₁₀turns
- Hₐ: At least one pair of means is not equal

**Export:** `f5_diversity_by_turns.csv`

**Minitab steps:**
1. File > Open Worksheet > `f5_diversity_by_turns.csv`
2. Stat > ANOVA > One-Way
3. Response: `spr_strategy_count`
4. Factor: `max_turns`
5. Click Multiple Comparisons > Tukey's
6. Click OK

**D.R.:** Reject H₀ if P < 0.05

**Note:** Given small differences (3.47 → 3.62 → 3.71), this may NOT be significant. FTR is itself a finding: "Models deploy their full repertoire within the first 2 turns."

**Results:**
- F(2, ___) = ___, P = ___  → [Reject / FTR]

**Repeat for debunker:** Response: `deb_strategy_count`
- F(2, ___) = ___, P = ___  → [Reject / FTR]

---

## Test 5.2: Model × Turn Length on Diversity (Two-Factor ANOVA with Interaction)

**Finding it supports:** Finding 5 — Strategy Depth Plateau

**Purpose:** Does the diversity plateau differ by model?

**Hypotheses:**
- H₀(A): μ_diversity is equal across models
- H₀(B): μ_diversity is equal across turn lengths
- H₀(AB): No interaction
- Hₐ: At least one is false

**Export:** Same `f5_diversity_by_turns.csv`

**Minitab steps:**
1. Stat > ANOVA > General Linear Model > Fit General Linear Model
2. Response: `spr_strategy_count`
3. Factors: `model_spreader`, `max_turns`
4. Include interaction: `model_spreader*max_turns`
5. Click OK
6. If interaction significant: generate interaction plot

**D.R.:** Check interaction first.

**Expected:** Interaction may be significant because Claude is flat (~1.5) while Gemini grows (~2→5).

**Results:**
- Interaction: F = ___, P = ___  → [Significant / Not significant]
- Main effect (model): F = ___, P = ___
- Main effect (turns): F = ___, P = ___

**Interpretation:** ___

---

## Run Order

| # | Test | Est. Time | Priority |
|---|---|---|---|
| 1 | 4.1 Citation quality ANOVA + Tukey's | 5 min | Start here — cleanest finding |
| 2 | 5.1 Diversity by turns ANOVA | 3 min | Quick win |
| 3 | 1 Strategy by model Chi-squared | 5 min | Core finding |
| 4 | 2.2 Model × claim type ANOVA | 5 min | Interaction check |
| 5 | 5.2 Model × turns ANOVA | 5 min | Interaction check |
| 6 | 4.2 Model × claim type on citations | 5 min | Secondary |
| 7 | 2.1 Strategy by claim type (×4 models) | 15 min | Per-model |
| 8 | 3.1 Tactic-naming Chi-squared | 3 min | Likely FTR |

**Total estimated time: ~45-60 minutes**

---

## Results Summary (fill in as you go)

| Test | Statistic | P-value | Decision | Key finding |
|---|---|---|---|---|
| 1 (spr) | χ² = | P = | | |
| 1 (deb) | χ² = | P = | | |
| 2.1 Claude | χ² = | P = | | |
| 2.1 Gemini | χ² = | P = | | |
| 2.1 GPT-4o | χ² = | P = | | |
| 2.1 GPT-4o-mini | χ² = | P = | | |
| 2.2 | F(interaction) = | P = | | |
| 3.1 | χ² = | P = | | |
| 4.1 | F = | P = | | |
| 4.2 | F(interaction) = | P = | | |
| 5.1 (spr) | F = | P = | | |
| 5.1 (deb) | F = | P = | | |
| 5.2 | F(interaction) = | P = | | |
