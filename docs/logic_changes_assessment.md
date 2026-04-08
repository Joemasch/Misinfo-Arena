# Logic Changes Assessment

> **Status:** Approved, pending implementation (after app restructure)
> **Last updated:** 2026-04-08
> **Context:** Honest assessment of logic changes needed to make the app's data output trustworthy for thesis experiments

---

## Changes to Make

### 1. Disable Silent Heuristic Fallback in Experiment Mode

**Problem:** When AgentJudge fails, it silently falls back to HeuristicJudge. The episode looks normal in the dataset but was scored by regex patterns, not an LLM. This contaminates research data — 95% LLM-scored and 5% regex-scored episodes are mixed together invisibly.

**Fix:** For experiment execution, a judge failure should produce an explicit error. Mark the episode as errored, skip it, log it. Report the failure rate in methodology. Keep the fallback only for casual Arena use.

**Files:** `execute_next_turn.py`, new experiment engine

---

### 2. Disable Concession Detection in Experiment Mode

**Problem:** Keyword-based detection ("I agree", "you're right") triggers false positives on rhetorical pivots like "You're right that this is complex, BUT...". A false early stop truncates the debate and corrupts the turn count variable — critical for Study 2 where turn length is the primary independent variable.

**Fix:** Disable concession detection entirely for experiment runs. All debates run to their planned max_turns. The independent variable stays clean.

**Files:** `execute_next_turn.py`, `concession.py`, new experiment engine

---

### 3. Extend Judge to Multi-Provider (Like Agents)

**Problem:** AgentJudge only uses the OpenAI SDK. The sidebar only offers gpt-4o-mini, gpt-4o, gpt-4-turbo as judge options. Study 1 requires claude-sonnet-4, gemini-2.5-flash, and grok-3-mini as judge candidates.

**Fix:** Apply the same multi-provider routing pattern that agents already use (model prefix detection → correct SDK). The agent code already solves this problem — the judge just needs to use the same pattern.

**Files:** `judge.py`, `config.py` (judge model list), sidebar in `arena_page.py`

---

### 4. Store Individual Consistency Run Results

**Problem:** When running 3 consistency runs, only the averaged result is stored. If 2 runs say "debunker" and 1 says "spreader," that disagreement is meaningful but gets hidden in the average.

**Fix:** Store all individual run results alongside the average in the episode's `judge_audit` field. Add a `judge_agreement` field: "unanimous" (3/3), "majority" (2/3), "split" (all different).

**Files:** `judge.py` (AgentJudge), episode builder

---

### 5. Add Symmetric Temperature Control Block

**Problem:** Spreader at 0.85, debunker at 0.40 is asymmetric by design. But this creates a confound: is the debunker winning because it argues better, or because lower temperature produces more coherent text? A committee may push on this.

**Fix:** Add a small symmetric baseline condition to Study 2: same 4 claims, one model pair, both at 0.70, 5 turn lengths = 20 extra episodes. This provides a control point to check whether the asymmetry drives the outcome.

**Files:** Study 2 spec generator script, no app code changes needed

---

### 6. Fix Turn Trajectory Chart Labeling

**Problem:** The Replay "Verdict & Scorecard" tab shows a line chart labeled as "argument strength" that actually plots regex signal counts per turn. Users (and committee members) would assume this represents judge scores when it's actually pattern match density. Conflates quantity with quality.

**Fix:** Either:
- Relabel as "Rhetorical signal density" with an explanatory caption
- Or remove it entirely and replace with something grounded in actual scoring

**Files:** `replay_page.py`

---

## What NOT to Change

| Component | Why it's correct |
|---|---|
| Equal weights (1/6 each) | Justified by Wachsmuth et al. (2017). Unequal weights require empirical justification. |
| Role-relative scoring | Spreader scored on persuasive execution, not factual accuracy. Methodologically sound. |
| Strategy analysis post-judge | Cannot influence scoring. Clean separation. |
| Fixed, read-only prompts | Correct for controlled experiments. Prompt variation is a confound. |
| Multi-provider agent routing | Clean model-prefix-based routing. Works as designed. |
| Episode schema structure | Comprehensive, stores full reproduction metadata. |
| Insights generation | Display feature only, doesn't affect research data. |
| Factory pattern | Centralized creation logic, prevents coupling. |
| Claim auto-classification | Fine for convenience. Experiment claims are pre-selected. |

---

## Implementation Priority

These changes should be implemented **after** the app restructure (UI reorganization) is complete, but **before** running any thesis experiments.

| Change | Effort | Priority |
|---|---|---|
| Disable heuristic fallback in experiments | Small | Must-have before Study 1 |
| Disable concession detection in experiments | Small | Must-have before Study 2 |
| Extend judge to multi-provider | Medium | Must-have before Study 1 |
| Store individual consistency results | Small | Should-have before Study 1 |
| Symmetric temperature control | Small (20 extra episodes) | Nice-to-have for Study 2 |
| Fix trajectory chart labeling | Small | Nice-to-have |

---

*Assessed: 2026-04-08*
