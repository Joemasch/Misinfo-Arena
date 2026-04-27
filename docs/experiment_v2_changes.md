# Experiment v2 Design Changes

> **Date:** 2026-04-27
> **Reason:** Post-advisor meeting redesign for stronger ecological validity and richer analysis

---

## Summary

| Aspect | v1 | v2 | Why changed |
|---|---|---|---|
| **Prompts** | Prescribed tactics (8 spreader, 6 debunker) | Free-will ("argue however you want") | Measures natural model behavior, not prompt adherence |
| **Judge model** | GPT-4o (also a debater) | Grok 3 (xAI, not a debater) | Removes provider bias |
| **Dimensions** | 6 (equal weight 0.167) | 8 (equal weight 0.125) | Adds source reputability, hallucination index, adaptability |
| **Claims** | 10 (2 per type, all misinfo) | 20 (3 misinfo + 1 true per type) | Within-type replication + true claim control |
| **Strategy labels** | Episode-level only | Episode-level + per-turn | Tracks tactical adaptation across exchanges |
| **Episodes** | 480 | 960 | More claims × same pairs × same turns |
| **New fields** | — | refusal detection, concession detection (true claims), per-turn response length, true_claim flag, per_turn_strategies | Richer data capture |
| **URL validation** | Not checked | Post-processing hallucination checker | Measures source validity |
| **Self-identification** | Not constrained | "Do not identify yourself as AI" | Ecological validity |

---

## Detailed Changes

### 1. Free-Will Prompts
**v1:** 3,022-char spreader prompt with 8 prescribed tactics + adaptation rules. 4,178-char debunker prompt with 6-step architecture.
**v2:** ~800-char prompts: "Argue in favor/against this claim. Use whatever approach you believe will be most effective."
**Impact:** Results now reflect what models naturally do, not what we told them to do.

### 2. Judge Model
**v1:** GPT-4o — same provider as 2 of 4 debater models (GPT-4o, GPT-4o-mini).
**v2:** Grok 3 — xAI, not used as any debater model.
**Impact:** Eliminates potential provider self-preference bias in scoring.

### 3. New Scoring Dimensions
**Added:**
- `source_reputability` (replaces `source_credibility`) — measures appropriateness of source usage, not just presence
- `hallucination_index` — measures apparent validity of cited evidence
- `adaptability` — measures tactical evolution across turns

**Removed:** None (6 original dimensions retained, 2 renamed/refined)

### 4. True Claims
**v1:** All 10 claims were misinformation.
**v2:** 15 misinformation + 5 factually true claims (1 per type).
**Impact:** Tests whether debunker refutes facts. Tests whether spreader concedes when arguing for truth. Creates a control condition.

### 5. Per-Turn Strategy Labels
**v1:** One set of labels per episode (episode-level analysis).
**v2:** Labels per turn pair + adaptation flags (did the model change tactics from previous turn?).
**Impact:** Enables game theory analysis — track how models adapt in real-time.

### 6. Refusal Detection
**v1:** Not tracked.
**v2:** Keyword detection for model refusal to engage ("I cannot argue for...", "as an AI...").
**Impact:** Captures safety-training effects, especially for Claude as spreader.

### 7. Per-Turn Response Length
**v1:** Not tracked at turn level.
**v2:** Character count per turn per side stored in episode data.
**Impact:** Free metric revealing behavioral differences (some models write paragraphs, others write sentences).

### 8. URL Hallucination Checking
**v1:** Not checked.
**v2:** Post-processing script checks if cited URLs actually resolve.
**Impact:** Quantifies how often models fabricate sources.

---

## Episode Count

| | v1 | v2 |
|---|---|---|
| Models | 4 | 4 (same) |
| Pairs | 16 | 16 (same) |
| Claims | 10 | 20 |
| Turn lengths | 3 (2,6,10) | 3 (same) |
| **Total episodes** | **480** | **960** |

## Estimated Cost & Time

| Provider | v2 Estimated |
|---|---|
| OpenAI | ~$30 |
| Anthropic | ~$25 |
| Google | ~$10 |
| xAI (Grok judge × 960) | ~$20 |
| **Total** | **~$85** |
| **Compute time** | ~60-70 hours |
