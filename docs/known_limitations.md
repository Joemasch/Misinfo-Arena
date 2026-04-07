# Known Limitations — Misinformation Arena v2

**Purpose:** Limitations to acknowledge in your thesis and account for in your analysis. Identified before experiment data collection.

---

## 1. Keyword-Based Concession Detection

**What:** Concessions are triggered when an agent says "I agree," "you're right," "I concede," etc. These are simple string matches, not semantic understanding.

**Risk:** LLMs are polite — they often say "you raise a good point" as a rhetorical transition, not a genuine concession. This produces false positive concessions, especially in longer debates where agents run out of novel arguments and default to polite acknowledgment.

**Impact on results:** Inflated concession rates, particularly at higher turn counts. Concession analysis may overstate how often agents actually give up.

**Mitigation:** Manually verify the first 10-15 concessions via the Replay tab. Report concession rates with a caveat. Focus on judge scores for primary findings; treat concession data as supplementary.

---

## 2. Claim-Agnostic Judge Rubric

**What:** The judge evaluates every claim with the same 6-dimension rubric. It cannot calibrate scoring to claim-specific ground truth — "factuality" for a vaccine claim (well-established science) is scored the same way as for an economic policy claim (genuinely uncertain).

**Risk:** The debunker systematically scores higher on factuality for claims with strong scientific consensus (health) and lower where evidence is genuinely contested (economic, political). Domain differences in results partially measure how settled the science is, not just argument quality.

**Impact on results:** Domain comparison findings (Experiment B) reflect a mix of agent performance AND real-world evidence availability. Health claims may show larger FC advantages because the evidence is clearer, not because the debunker argued better.

**Mitigation:** Report this explicitly: "The judge scores argument quality, not factual accuracy. Domain differences may reflect the availability and clarity of established evidence for each claim type."

---

## 3. Safety-Aligned Models Playing the Spreader

**What:** GPT-4o-mini, Claude Haiku, and Gemini Flash are all RLHF-trained to be helpful, harmless, and honest. When playing the spreader role, they must argue for misinformation — against their own training.

**Risk:** Model differences in spreader performance may reflect alignment strength rather than rhetorical capability. Claude has particularly strong refusal behaviors and may produce weaker misinformation arguments — not because it's less capable, but because it's more safety-aligned.

**Impact on results:** Cross-model comparisons of spreader effectiveness conflate alignment strictness with persuasive ability. A model that scores lower on persuasion as spreader might actually be the most capable model overall — it's just more reluctant to generate misinformation.

**Mitigation:** Report this explicitly: "Differences in spreader performance across models may reflect alignment strength rather than rhetorical capability. This is itself an interesting finding — it suggests that safety alignment affects the quality of adversarial argument generation."

---

## 4. Strategy Labeling by a Separate Model

**What:** After the judge scores, a separate gpt-4o-mini call labels which rhetorical strategies each side used (from the 20-label taxonomy). This analyst model is different from the model that generated the arguments.

**Risk:** The analyst may misread intent — labeling something as "emotional appeal" when the agent intended "anecdotal evidence." Strategy labels have noise from this interpretation gap.

**Impact on results:** Strategy-outcome correlations are weaker than the true relationship due to labeling error. Strategy frequency counts are approximate, not exact.

**Mitigation:** Use strategy data for descriptive analysis (frequency, distribution patterns) but do not over-claim causal relationships. Frame as: "Episodes labeled with emotional appeal tended to..." not "emotional appeal caused..."

---

## 5. No Absolute Quality Baseline

**What:** The 6 scoring dimensions are 0-10, but there is no external reference for what constitutes a "good" score. All scores are relative to other episodes in the dataset.

**Risk:** If all models are similarly mediocre, scores cluster around 5-7 and you cannot determine whether the arguments are objectively convincing — only that they are comparably convincing. A "persuasion score of 7.5" has no meaning outside the context of this dataset.

**Impact on results:** You can report relative differences ("Model A scored 1.2 points higher than Model B") but not absolute quality ("the debates were highly persuasive").

**Mitigation:** The human evaluation study (annotation page) is the external anchor. When human raters score transcripts, compare their ratings to the judge scores to establish what the numbers actually mean. Report human-judge correlation (Cohen's κ) alongside all score-based findings.

---

## 6. Non-Deterministic LLM Judge

**What:** The judge is an LLM (gpt-4o-mini by default). Running the same debate twice may produce different scores and even different winners.

**Risk:** Individual episode results have variance. Small score differences (< 0.5 points) may be noise, not signal.

**Impact on results:** Without reliability runs, you cannot distinguish real differences from LLM stochasticity.

**Mitigation:** Use reliability runs (3x or 5x in sidebar) for validation episodes. Report the standard deviation when available. For aggregate findings (mean across 30+ episodes), LLM noise averages out — individual episode results should not be over-interpreted.

---

## Summary Table

| Limitation | Affects | Severity | Mitigation available? |
|---|---|---|---|
| Keyword concession detection | Concession analysis | Medium | Manual verification |
| Claim-agnostic rubric | Domain comparisons | Medium | Acknowledge in reporting |
| Safety-aligned spreaders | Model comparisons | Medium | Report as finding |
| Separate strategy analyst | Strategy analysis | Low | Use descriptively only |
| No absolute quality baseline | All score-based findings | Medium | Human evaluation study |
| Non-deterministic judge | All findings | Low | Reliability runs + aggregation |

---

*Identified April 2026, before experiment data collection.*
