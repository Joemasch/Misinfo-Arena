# Phase 7: Study Results Visualizations

> **Status:** Planned — build after experiment data exists
> **Last updated:** 2026-04-09

---

## Design Principle

Every chart must tell its story in 30 seconds on a presentation slide. Joe's deliverable is a 15-16 minute presentation, not a paper. Visualizations should be self-explanatory with minimal labels.

---

## Study 1: Judge Validation

| Visualization | What it shows | Chart type |
|---|---|---|
| Judge agreement comparison | Kappa + winner agreement % for each of the 4 judge candidates | Grouped bar (4 judges, 2 metrics) |
| Per-dimension correlation | Spearman ρ for each judge × each of the 6 dimensions | Heatmap (4 judges × 6 dimensions) |
| Consistency comparison | Coefficient of variation per judge | Horizontal bar (lower = better) |
| Confidence discrimination | Distribution of confidence scores per judge | Overlaid box plots or violin plots |
| Verdict card | "Selected judge: X — kappa=Y, CV=Z" | Styled callout |

---

## Study 2: Conversation Length Effects

| Visualization | What it shows | Chart type |
|---|---|---|
| Win rate by turn length | Debunker win % at 2, 4, 6, 8, 10 turns | Line chart with confidence band |
| Score margin by turn length | Mean margin at each turn count | Line chart (single line, clear trend) |
| Model × length interaction | Score margin by turn length, one line per model pair (or grouped by tier) | Multi-line chart with tier toggle |
| Easy vs hard claims × length | Win rate by turn length, split by difficulty | Faceted line chart (2 panels) |
| Same-model vs cross-model by length | Margin curves for diagonal vs off-diagonal pairs | Two-line comparison |
| Side-by-side comparison | Pick 2 model pairs, synced length curves | Two-panel layout |

### Strategy visualizations (Study 2 specific)
| Visualization | What it shows | Chart type |
|---|---|---|
| Strategy diversity by length | Avg unique strategies per episode at each turn count | Line chart (one per side) |
| Strategy profile by model | Which strategies each model favors as spreader/debunker | Grouped bar or small multiples |

---

## Study 3: Claim Type Effects

| Visualization | What it shows | Chart type |
|---|---|---|
| Win rate by claim type | Debunker win % per type | Horizontal bar (5 types) |
| Score margin by claim type | Mean margin per type with variance | Box plots (5 types) |
| Difficulty index per claim | All 25 claims as dots, grouped by type | Strip plot within type groups |
| Model × claim type interaction | Performance per model pair across types | Heatmap (16 pairs × 5 types) |
| Within-type variance | How consistent is each type? | Box plots showing spread |
| Per-dimension breakdown by type | Which scoring dimensions drive outcomes per type | Grouped bar (6 dims × 5 types) |
| Side-by-side comparison | Pick 2 claim types, compare all metrics | Two-panel layout |

### Strategy visualizations (Study 3 specific)
| Visualization | What it shows | Chart type |
|---|---|---|
| Strategy mix by claim type | Do agents adapt tactics to the domain? | Heatmap (already in Explore, replicated filtered to Study 3 data) |
| Close vs decisive strategy mix | What's different about hard-fought debates? | Side-by-side frequency bars split by margin threshold |

---

## Cross-Study: Model Comparison

| Visualization | What it shows | Chart type |
|---|---|---|
| Model effectiveness by role | Best spreader / best debunker rankings | Horizontal bar (margin by model, one chart per role) |
| Matchup heatmap | FC win % for each of the 16 pairs | Heatmap with cell annotations |
| Tier comparison | Budget vs premium performance | Grouped bar |
| Cross-provider vs within-provider | Does provider diversity affect outcomes? | Two-group comparison bar |
| Strategy profile by model | Which strategies each model defaults to | Small multiples (one per model) |

---

## Implementation Notes

- All charts use Plotly (consistent with existing app)
- Side-by-side comparisons use `st.columns(2)` with synced axes
- Study picker at top of page (selectbox from study_id values)
- Charts should work at presentation resolution (large fonts, minimal gridlines)
- Color scheme: spreader amber (#D4A843), debunker blue (#4A7FA5), consistent throughout
