# Statistical Analysis Guide — Misinformation Arena v2

**Purpose:** Step-by-step instructions for conducting statistical significance tests in Minitab using data exported from the arena. Each section maps to a specific research question, tells you which CSV export to use, and walks through the exact Minitab procedure.

---

## Prerequisites

1. Run your experiments (Experiment A: turn count, Experiment B: domains)
2. Go to **Tools → Exports** in the app
3. Download the 5 analysis-ready CSVs
4. Open each in Minitab

---

## Analysis 1 — Does Conversation Length Affect Outcomes?

**Research question:** RQ1 — As debates get longer, does the fact-checker's advantage grow or shrink?

**Export file:** `turn_count_analysis.csv`

**Columns:**
| Column | Description |
|---|---|
| claim | The misinformation claim text |
| claim_type | Domain category (Health / Vaccine, etc.) |
| max_turns | Turn count for this episode (2, 4, 6, 8, or 10) |
| winner | Who won: debunker, spreader, or draw |
| fc_win | 1 if debunker won, 0 otherwise (for regression) |
| margin | Score margin (debunker total − spreader total) |
| abs_margin | Absolute score margin |
| confidence | Judge confidence (0–1) |
| persuasion_spr | Spreader's persuasion score (0–10) |
| persuasion_deb | Debunker's persuasion score (0–10) |
| manipulation_spr | Spreader's manipulation_awareness score (0–10) |
| manipulation_deb | Debunker's manipulation_awareness score (0–10) |
| spreader_model | Which model played the spreader |
| debunker_model | Which model played the debunker |
| judge_model | Which model judged |

### Test 1a: Chi-squared — Does turn count affect win rate?

**Hypothesis:**
- H₀: Win rate is independent of turn count
- H₁: Win rate depends on turn count

**Minitab procedure:**
1. Open `turn_count_analysis.csv`
2. Go to **Stat → Tables → Cross Tabulation and Chi-Square**
3. Set Rows = `max_turns`, Columns = `winner`
4. Check "Chi-square test" and "Expected cell counts"
5. Click OK

**What to report:** χ² statistic, df, p-value. If p < 0.05, turn count significantly affects who wins.

**Follow-up if significant:** Look at the table of observed vs expected counts. Which turn count has the biggest deviation from expected? That's where the effect is strongest.

### Test 1b: One-way ANOVA — Does turn count affect score margin?

**Hypothesis:**
- H₀: Mean score margin is the same across all turn counts
- H₁: At least one turn count has a different mean margin

**Minitab procedure:**
1. Go to **Stat → ANOVA → One-Way**
2. Response = `margin`, Factor = `max_turns`
3. Click "Comparisons" and check "Tukey" for pairwise comparisons
4. Click "Graphs" and check "Boxplot of data" and "Residual plots"
5. Click OK

**What to report:** F-statistic, p-value, and Tukey pairwise results. The boxplot shows the spread at each turn count.

**What to look for:** If the margin increases with turn count, longer debates favor the debunker more (they have more time to build evidence). If it decreases, the spreader's persuasion tactics become more effective over time.

### Test 1c: Regression — Does persuasion score change with debate length?

**Minitab procedure:**
1. Go to **Stat → Regression → Regression → Fit Regression Model**
2. Response = `persuasion_spr`, Predictors = `max_turns`
3. Click OK

**What to report:** R², coefficient for max_turns, p-value. A positive coefficient means the spreader gets more persuasive in longer debates.

Repeat with `persuasion_deb` as the response to test whether the debunker also improves.

---

## Analysis 2 — Do Outcomes Differ Across Claim Domains?

**Research question:** RQ2 — Which misinformation domains are hardest to debunk?

**Export file:** `domain_analysis.csv`

**Columns:**
| Column | Description |
|---|---|
| claim | Claim text |
| claim_type | Domain (Health / Vaccine, Political / Election, etc.) |
| winner | Who won |
| fc_win | 1 if debunker won |
| margin | Score margin |
| abs_margin | Absolute margin |
| confidence | Judge confidence |
| spreader_model | Spreader model |
| debunker_model | Debunker model |
| judge_model | Judge model |

### Test 2a: Chi-squared — Does domain affect win rate?

**Minitab procedure:**
1. Open `domain_analysis.csv`
2. **Stat → Tables → Cross Tabulation and Chi-Square**
3. Rows = `claim_type`, Columns = `winner`
4. Check "Chi-square test"
5. Click OK

**What to report:** χ² statistic, df, p-value. If significant, some domains produce different outcomes than others.

### Test 2b: One-way ANOVA — Does domain affect score margin?

**Minitab procedure:**
1. **Stat → ANOVA → One-Way**
2. Response = `margin`, Factor = `claim_type`
3. Click "Comparisons" → Tukey
4. Click OK

**What to report:** F-statistic, p-value. Tukey results show which domain pairs differ significantly.

**What to look for:** Economic and Institutional Conspiracy claims may have smaller margins (harder to debunk) than Health / Vaccine claims (where evidence is clearest).

---

## Analysis 3 — Does Model Choice Affect Outcomes?

**Research question:** RQ3 — Do different LLM models produce different debate outcomes?

**Export file:** `model_comparison.csv`

**Columns:**
| Column | Description |
|---|---|
| spreader_model | Model playing spreader |
| debunker_model | Model playing debunker |
| judge_model | Model judging |
| model_matchup | Combined label: "spr_model vs deb_model" |
| winner | Who won |
| fc_win | 1 if debunker won |
| margin | Score margin |
| abs_margin | Absolute margin |
| confidence | Judge confidence |
| claim_type | Domain |
| persuasion_spr | Spreader persuasion score |

### Test 3a: Chi-squared — Does model matchup affect win rate?

**Minitab procedure:**
1. Open `model_comparison.csv`
2. **Stat → Tables → Cross Tabulation and Chi-Square**
3. Rows = `model_matchup`, Columns = `winner`
4. Check "Chi-square test"
5. Click OK

**What to report:** χ² statistic, p-value. If significant, some model pairings produce different outcomes.

### Test 3b: Two-way ANOVA — Model × Domain interaction

**Hypothesis:** Does the model effect depend on the domain? (e.g., Gemini might be better at health claims but worse at political claims)

**Minitab procedure:**
1. **Stat → ANOVA → General Linear Model → Fit General Linear Model**
2. Response = `margin`
3. Factors = `model_matchup`, `claim_type`
4. Under "Model", include the interaction term: `model_matchup * claim_type`
5. Click OK

**What to report:** Main effects (model_matchup, claim_type) and interaction effect. If the interaction is significant, the model's effectiveness depends on the domain.

### Test 3c: Which model is the best spreader?

**Minitab procedure:**
1. **Stat → ANOVA → One-Way**
2. Response = `persuasion_spr`, Factor = `spreader_model`
3. Click "Comparisons" → Tukey
4. Click OK

**What to report:** Which model has the highest mean persuasion score as spreader? Are the differences significant?

---

## Analysis 4 — Does the Judge Model Affect Verdicts?

**Research question:** Is the evaluation model-dependent?

**Export file:** `judge_consistency.csv`

**Columns:**
| Column | Description |
|---|---|
| run_id | Run identifier |
| episode_id | Episode identifier |
| claim | Claim text |
| judge_model | Which model judged |
| winner | Verdict |
| confidence | Judge confidence |
| factuality_spr | Spreader factuality score |
| factuality_deb | Debunker factuality score |
| source_credibility_spr | Spreader source credibility |
| source_credibility_deb | Debunker source credibility |
| reasoning_quality_spr | Spreader reasoning score |
| reasoning_quality_deb | Debunker reasoning score |
| responsiveness_spr | Spreader responsiveness |
| responsiveness_deb | Debunker responsiveness |
| persuasion_spr | Spreader persuasion |
| persuasion_deb | Debunker persuasion |
| manipulation_awareness_spr | Spreader manipulation score |
| manipulation_awareness_deb | Debunker manipulation score |
| margin | Score margin |

### Test 4a: Chi-squared — Do judge models produce different winners?

**Minitab procedure:**
1. Open `judge_consistency.csv`
2. **Stat → Tables → Cross Tabulation and Chi-Square**
3. Rows = `judge_model`, Columns = `winner`
4. Click OK

**What to report:** If p > 0.05, judge models agree on winners — your evaluation is robust. If p < 0.05, the judge model matters and you need to report results separately by judge.

### Test 4b: ANOVA — Do judge models produce different scores?

**Minitab procedure:**
1. **Stat → ANOVA → One-Way**
2. Response = `margin`, Factor = `judge_model`
3. Click OK

**What to report:** If not significant, different judges produce similar margins. If significant, some judges are systematically more or less generous.

### Test 4c: Correlation across judge models

For each metric (e.g., persuasion_spr), compare scores between pairs of judge models.

**Minitab procedure:**
1. Filter to episodes judged by gpt-4o-mini → save `persuasion_spr` as column A
2. Filter to same episodes judged by gemini-flash → save `persuasion_spr` as column B
3. **Stat → Basic Statistics → Correlation**
4. Variables = column A, column B
5. Click OK

**What to report:** Pearson r and p-value. r > 0.7 = good agreement. r < 0.5 = judges disagree meaningfully on that dimension.

*Note: This requires the same transcripts judged by multiple models. If you used Option 1 (fixed judge) from the experiment design, you'll need to re-judge a subset of transcripts with alternative models to run this analysis.*

---

## Analysis 5 — What Predicts Concession?

**Research question:** What factors make an agent concede?

**Export file:** `concession_analysis.csv`

**Columns:**
| Column | Description |
|---|---|
| claim | Claim text |
| claim_type | Domain |
| conceded | 1 if this episode had a concession, 0 if it hit max turns |
| conceded_by | Who conceded (spreader/debunker), or empty |
| concession_turn | Turn number when concession happened |
| max_turns | Planned max turns |
| spreader_model | Spreader model |
| debunker_model | Debunker model |
| judge_model | Judge model |
| margin | Final score margin |
| confidence | Judge confidence |
| persuasion_spr | Spreader persuasion |
| persuasion_deb | Debunker persuasion |

### Test 5a: Logistic regression — What predicts concession?

**Hypothesis:** Which factors predict whether a debate ends in concession?

**Minitab procedure:**
1. Open `concession_analysis.csv`
2. **Stat → Regression → Binary Logistic Regression → Fit Binary Logistic Regression**
3. Response = `conceded` (binary: 1/0)
4. Continuous predictors = `max_turns`, `persuasion_spr`, `persuasion_deb`
5. Categorical predictors = `claim_type`, `spreader_model`, `debunker_model`
6. Click OK

**What to report:** Odds ratios for each predictor. For example:
- If `max_turns` has OR > 1: longer debates → more concessions
- If `claim_type = Institutional Conspiracy` has OR > 1: conspiracy claims trigger more concessions
- If `spreader_model = gemini-flash` has OR > 1: Gemini concedes more as spreader

### Test 5b: Chi-squared — Does model choice affect concession rate?

**Minitab procedure:**
1. Filter to only rows where `conceded` = 1
2. **Stat → Tables → Cross Tabulation and Chi-Square**
3. Rows = `spreader_model`, Columns = `conceded_by`
4. Click OK

**What to report:** Do certain models concede more often when playing the spreader vs the debunker?

---

## Reporting Checklist

For each test in your thesis, report:

- [ ] The hypothesis (H₀ and H₁)
- [ ] Sample size (N episodes)
- [ ] Test statistic (χ², F, t, or OR)
- [ ] Degrees of freedom
- [ ] p-value
- [ ] Effect size (Cramér's V for χ², η² for ANOVA, OR for logistic)
- [ ] A plain-English interpretation
- [ ] The relevant figure or table from the app (screenshot)

---

## Quick Reference — Which Test for Which Question

| Question | Test | Export file |
|---|---|---|
| Does turn count affect win rate? | Chi-squared | turn_count_analysis.csv |
| Does turn count affect score margin? | One-way ANOVA + Tukey | turn_count_analysis.csv |
| Does domain affect win rate? | Chi-squared | domain_analysis.csv |
| Does domain affect score margin? | One-way ANOVA + Tukey | domain_analysis.csv |
| Does model choice affect outcomes? | Chi-squared + Two-way ANOVA | model_comparison.csv |
| Which model is best spreader? | One-way ANOVA + Tukey | model_comparison.csv |
| Do judge models agree? | Chi-squared + Correlation | judge_consistency.csv |
| What predicts concession? | Binary logistic regression | concession_analysis.csv |
| Does model affect concession? | Chi-squared | concession_analysis.csv |

---

*Export these CSVs from the Misinformation Arena → Tools → Exports tab.*
