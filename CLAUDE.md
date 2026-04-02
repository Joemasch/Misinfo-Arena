# CLAUDE.md — Misinformation Arena v2

> **Purpose:** Complete technical context for any Claude agent working on this codebase. Read this before exploring files.

---

## 1. Project Purpose

Research platform for studying how misinformation spreads and how it can be countered through structured adversarial AI debate. Built for the IME 507 graduate research project.

- **Spreader agent** argues in favor of a misinformation claim using persuasion tactics
- **Debunker agent** counters with evidence-based reasoning and inoculation techniques
- **AI judge** scores both sides across 6 literature-grounded dimensions
- **Analytics** track outcomes across runs, claims, models, and prompt variants

### Key Use Cases

| Use Case | Description |
|---|---|
| **Interactive Arena** | Run a single live debate with chat-bubble UI |
| **Multi-Claim Batch** | Chain N claims in one run |
| **Batch Experiment** | N prompt variants x M prompt variants x C claims grid |
| **Analytics** | 11 analytics sections across win rates, model comparison, strategy taxonomy, etc. |
| **Episode Replay** | Replay any past debate with full transcript, verdict, and scorecard |
| **Human Annotation** | Rate transcripts, compute Cohen's kappa for judge validation |
| **Prompt Engineering** | Edit and compare agent + judge prompts via prompt library |

---

## 2. Owner Goals

Joe is a graduate student researcher. His priorities:

1. **Research credibility** — literature-grounded scoring, pre-registerable experiment design
2. **Professional UI** — clean dashboard aesthetic, readable debate transcripts
3. **Experiment efficiency** — CSV import, batch runs, multi-provider model comparison

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| **Web UI** | Streamlit >=1.28.0 |
| **LLM Providers** | OpenAI, Anthropic, Google GenAI, xAI (Grok) |
| **Charts** | Plotly |
| **Data** | Pandas |
| **Language** | Python 3.8–3.13 |
| **Testing** | pytest (47 tests) |

### API Key Resolution (priority order)

1. `.streamlit/secrets.toml`
2. Environment variables
3. Sidebar paste (session only)

Managed centrally in `src/arena/utils/api_keys.py`.

---

## 4. Folder Structure

```
misinfo_arena_v2/
├── app.py                          # Entry point (1,416 lines)
├── pyproject.toml
├── CLAUDE.md                       # This file
├── README.md
│
├── src/arena/                      # Application package
│   ├── types.py                    #   Canonical types: JudgeDecision, MetricScore, Turn, Message
│   ├── config.py                   #   11 models, temperature presets, IME507 system prompts
│   ├── agents.py                   #   5 agent classes: OpenAI, Anthropic, Gemini, Grok, Dummy
│   ├── judge.py                    #   HeuristicJudge + AgentJudge (with consistency runs)
│   ├── judge_base.py               #   Abstract BaseJudge interface
│   ├── batch_runner.py             #   N×M×C experiment grid engine
│   ├── state.py                    #   Session state initialization
│   ├── factories.py                #   Object creation (create_agent, create_judge)
│   ├── concession.py               #   Early-stop detection
│   ├── insights.py                 #   AI debate summary generation
│   ├── strategy_analyst.py         #   Post-judge LLM strategy labeler
│   ├── strategy_taxonomy.py        #   20-label strategy taxonomy (10 spr + 10 deb)
│   ├── claim_metadata.py           #   Claim enrichment (type, domain, complexity)
│   ├── compat.py                   #   Legacy import shims
│   ├── app_config.py               #   App-level paths and constants
│   │
│   ├── prompts/
│   │   ├── judge_static_prompt.py  #   Judge rubric v2 (Wachsmuth 2017, D2D 2025, inoculation theory)
│   │   └── prompt_library.py       #   Named prompt variant CRUD
│   │
│   ├── analysis/
│   │   ├── episode_dataset.py      #   DataFrame builders (wide + long + strategy long)
│   │   ├── research_analytics.py   #   Filterable research metrics
│   │   ├── anomaly_detection.py    #   IQR + MAD outlier detection
│   │   ├── claim_analysis.py       #   Claim difficulty index, turn sensitivity
│   │   ├── strategy_lens.py        #   Regex-based per-turn tactic detection
│   │   └── citation_tracker.py     #   Citation credibility analysis
│   │
│   ├── application/use_cases/
│   │   └── execute_next_turn.py    #   Core debate pipeline (judge → strategy → persist)
│   │
│   ├── presentation/streamlit/
│   │   ├── pages/
│   │   │   ├── arena_page.py       #   Live debate UI (extracted from app.py)
│   │   │   ├── analytics_page.py   #   11-section analytics dashboard
│   │   │   ├── replay_page.py      #   7-tab episode replay viewer
│   │   │   ├── claim_analysis_page.py
│   │   │   ├── strategy_leaderboard_page.py
│   │   │   ├── citation_page.py
│   │   │   ├── prompts_page.py
│   │   │   ├── experiment_page.py  #   Batch experiment UI with CSV import
│   │   │   ├── annotation_page.py  #   Human annotation with Cohen's kappa
│   │   │   └── guide_page.py
│   │   └── components/arena/
│   │       ├── judge_report.py     #   Styled verdict card + scorecard
│   │       └── debate_insights.py  #   AI-generated strategic analysis
│   │
│   ├── io/
│   │   ├── run_store.py            #   JSONL append, run metadata writer
│   │   ├── run_store_v2_read.py    #   JSON v2 reader (list_runs, load_episodes)
│   │   └── prompts_store.py        #   Prompt file read/write
│   │
│   ├── ui/
│   │   ├── debate_chat.py          #   Live chat bubbles + turn summary cards + tactic detection
│   │   ├── run_planner.py          #   Multi-episode turn scheduler
│   │   └── claim_ingest.py         #   CSV/XLSX claim upload
│   │
│   └── utils/
│       ├── api_keys.py             #   4-provider centralized key management
│       ├── openai_config.py        #   Backward compat shim → api_keys.py
│       ├── serialization.py        #   JSON serialization helpers
│       ├── transcript_conversion.py
│       └── normalize.py
│
├── tests/                          # 47 tests, 15 files
├── scripts/                        # Dev tools, golden set evaluation (21 files)
├── data/                           # Golden set benchmarks (v0, v1)
├── runs/                           # Runtime episode output (gitignored)
└── runs_archive/                   # Archived test/pilot runs (gitignored)
```

---

## 5. Core Data Models

All canonical definitions in `src/arena/types.py`:

- **`JudgeDecision`** — winner, confidence, reason, totals dict, scorecard (List[MetricScore])
- **`MetricScore`** — metric name, spreader score, debunker score, weight
- **`Turn`** — turn_index, spreader_message, debunker_message, meta
- **`Message`** — role (AgentRole), content, citations, timestamp
- **`MatchConfig`** — max_turns, topic, concession_phrases, judge_weights

Types are defined once in `types.py` and imported everywhere. `judge.py` imports from `types.py`, not vice versa.

---

## 6. Judge System (v2)

### Scoring Dimensions (equal weights, 1/6 each)

| Dimension | Source | Measures |
|---|---|---|
| `factuality` | D2D (EMNLP 2025) | Narrative consistency (spr) / factual grounding (deb) |
| `source_credibility` | D2D (EMNLP 2025) | Specificity and checkability of sources |
| `reasoning_quality` | Wachsmuth 2017 — Cogency | Logical structure |
| `responsiveness` | Wachsmuth 2017 — Reasonableness | Direct engagement with opponent |
| `persuasion` | Wachsmuth 2017 — Effectiveness | Convincingness to uncommitted reader |
| `manipulation_awareness` | Inoculation theory | Penalizes manipulation (spr) / rewards naming tactics (deb) |

### Key Design Choices

- **Role-relative scoring** — spreader scored on persuasive execution, not factual accuracy
- **Equal weights** — per Wachsmuth's argument that fixed unequal weights are unjustified
- **Consistency runs** — AgentJudge can run N times and average scores (configurable in sidebar)
- **Heuristic fallback** — if AgentJudge fails, HeuristicJudge provides regex-based scores (excluded from research analytics by default)
- **Prompt version**: `judge_static_v2` (defined in `prompts/judge_static_prompt.py`)

### AgentJudge flow

```
AgentJudge.evaluate_match(turns, config)
  → _build_evaluation_prompt(turns)  # insert transcript into rubric
  → _call_llm(prompt)                # system=rubric, user=transcript
  → _parse_agent_judgment(response)  # JSON → JudgeDecision
  → _validate_judge_decision()       # 6 metrics, 0-10, valid winner
  (repeat N times if consistency_runs > 1, then average)
```

---

## 7. Agent System

### 5 Agent Classes (all in `agents.py`)

| Class | Provider | Notes |
|---|---|---|
| `OpenAIAgent` | OpenAI | GPT-4o, GPT-4o-mini, etc. |
| `AnthropicAgent` | Anthropic | Claude Sonnet, Claude Haiku |
| `GeminiAgent` | Google | Gemini 2.0 Flash, 2.5 Pro/Flash |
| `GrokAgent` | xAI | Grok 3, Grok 3 Mini (OpenAI-compatible API) |
| `DummyAgent` | None | Deterministic testing, blocked in production |

### Model Routing

Factory auto-routes by model name prefix:
- `claude-*` → AnthropicAgent
- `gemini-*` → GeminiAgent
- `grok-*` → GrokAgent
- everything else → OpenAIAgent

### 11 Available Models

Tier 1 (cheap): `gemini-2.0-flash`, `gpt-4o-mini`, `grok-3-mini`
Tier 2 (mid): `claude-haiku-4-5`, `gemini-2.5-flash`
Tier 3 (premium): `gpt-4o`, `gemini-2.5-pro`, `claude-sonnet-4`, `grok-3`

### Role-Specific User Prompts

Spreader gets: "You are arguing IN FAVOR of this claim: {topic}"
Debunker gets: "You are arguing AGAINST this claim: {topic}"

This prevents GPT-4o from defaulting to the factually correct position regardless of role.

---

## 8. Storage

### JSON v2 Format (current, canonical)

Each run: `runs/<run_id>/run.json` + `runs/<run_id>/episodes.jsonl`

Episode fields: schema_version, run_id, episode_id, claim, claim_index, config_snapshot (agents, weights, prompts), results (winner, confidence, totals, scorecard), concession, turns, judge_audit, strategy_analysis, claim metadata.

### Legacy Format

`runs/matches.jsonl` — **off by default** (`WRITE_LEGACY_MATCHES=0`). Can be re-enabled with env var.

---

## 9. UI — 10 Tabs

| Tab | Module | Description |
|---|---|---|
| Home | `guide_page.py` | User guide with research context |
| Arena | `arena_page.py` | Live debate: config → claim → debate → results |
| Analytics | `analytics_page.py` | 11-section dashboard (Parts I–XI) |
| Run Replay | `replay_page.py` | 7-tab episode detail viewer |
| Claim Analysis | `claim_analysis_page.py` | Per-claim breakdown, difficulty index |
| Strategy Leaderboard | `strategy_leaderboard_page.py` | Strategy frequency, win rates, co-occurrence |
| Citation Tracker | `citation_page.py` | Citation credibility analysis |
| Prompts | `prompts_page.py` | Prompt editor + library |
| Experiment | `experiment_page.py` | Batch grid with CSV import |
| Annotate | `annotation_page.py` | Human rating + Cohen's kappa |

### Analytics Sections (Parts I–XI)

I: Win distribution, II: Metric performance, III: Anomaly detection, IV: Claim difficulty, V: Strategy×outcome, VI: Model comparison, VII: Prompt A/B, VIII: Concession analysis, IX: Response length, X: Longitudinal trends, XI: Judge calibration

---

## 10. Experiment Design

### CSV Formats

**Single-claim Arena:**
```csv
claim,run,claim_type,max_turns
Vaccines cause autism,1,Health / Vaccine,2
Vaccines cause autism,1,Health / Vaccine,4
```

**Multi-claim Arena:**
```csv
claim,run,claim_type
Vaccines cause autism,1,Health / Vaccine
Climate change is a hoax,2,Environmental
```

**Experiment prompts:**
```csv
name,role,prompt_text
IME507 Spreader,spreader,"You are a misinformation spreader agent..."
```

---

## 11. Architectural Patterns

- **All 10 tabs** delegate to a single `render_*_page()` function
- **Factory pattern** for agents, judges, storage (`factories.py`)
- **Types defined once** in `types.py`, imported everywhere
- **API keys** resolved centrally in `utils/api_keys.py` (secrets → env → session)
- **Episode persistence** decomposed: `_evaluate_judge()`, `_run_strategy_analysis()`, `_build_episode_object()`, `_build_run_object()` in `execute_next_turn.py`
- **Caching** via `@st.cache_data` keyed by `(run_ids, runs_dir, refresh_token)`
- **Import path**: `app.py` inserts `src/` into `sys.path[0]`, so `arena.*` resolves to `src/arena/*`

### Naming Conventions

- Pages: `render_<page_name>_page()`
- Components: `render_<component_name>()`
- Use cases: `execute_<action_name>()`
- State keys: lowercase snake_case (`"judge_decision"`, `"run_id"`)
- Run IDs: `YYYYMMDD_HHMMSS_<4hex>`
- Run labels: `"Claim preview... (Apr 2)"` for human display

---

## 12. Known Limitations (as of April 2026)

- Debunker wins 100% of episodes so far — this is a finding, not a bug
- Judge confidence clusters at 0.9 — needs investigation with consistency_runs > 1
- Strategy taxonomy is not explicitly cited to published literature
- No human evaluation baseline yet (annotation page built, study not conducted)
- `execute_next_turn.py` is still ~1,100 lines — persistence logic decomposed into sub-functions but not yet extracted to a separate module

---

*Last updated: 2026-04-02*
