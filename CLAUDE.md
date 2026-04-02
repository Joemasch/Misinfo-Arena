# CLAUDE.md — Misinformation Arena v2: Full Project Audit

> **Purpose of this file:** This document is a complete technical audit of the Misinformation Arena v2 codebase. It is intended to give a Claude agent instant, authoritative context about how the project works, what has been built, what needs improvement, and what the owner's goals are — without needing to re-explore the codebase from scratch.

---

## Table of Contents

1. [Project Purpose](#1-project-purpose)
2. [Owner Goals & Improvement Directives](#2-owner-goals--improvement-directives)
3. [Technology Stack](#3-technology-stack)
4. [Folder & File Structure](#4-folder--file-structure)
5. [Core Data Models](#5-core-data-models)
6. [How a Debate Works End-to-End](#6-how-a-debate-works-end-to-end)
7. [The Judge System](#7-the-judge-system)
8. [Agent System](#8-agent-system)
9. [Storage & Persistence Layer](#9-storage--persistence-layer)
10. [UI Layer — Pages & Components](#10-ui-layer--pages--components)
11. [Analytics System](#11-analytics-system)
12. [Prompt Management System](#12-prompt-management-system)
13. [Configuration & Environment](#13-configuration--environment)
14. [State Management](#14-state-management)
15. [Current Project Status](#15-current-project-status)
16. [Known Issues & Technical Debt](#16-known-issues--technical-debt)
17. [Architectural Patterns & Conventions](#17-architectural-patterns--conventions)

---

## 1. Project Purpose

**Misinformation Arena v2** is a research tool for studying how misinformation spreads and how it can be countered through structured debate.

Two AI agents debate a user-supplied claim:
- **Spreader** — argues in favor of a misinformation claim using persuasion, emotional appeals, and selective evidence
- **Debunker** — argues against it using facts, citations, and logical reasoning

At the end of the debate, an **AI judge** (backed by an LLM) evaluates both sides across six dimensions and declares a winner. All results are persisted to disk for later analysis, replay, and research.

### Key Use Cases

| Use Case | Description |
|---|---|
| **Interactive Arena** | Run a single live debate in real time with chat-bubble UI |
| **Multi-Claim Batch** | Chain N claims back to back in one run |
| **Analytics** | Review aggregated metrics, win rates, strategy patterns across all runs |
| **Episode Replay** | Replay any past debate with full transcript, verdict, and scorecard |
| **Prompt Engineering** | Edit and compare agent + judge prompts to tune behavior |
| **Research Export** | Download episode data as CSV or JSON for external analysis |

---

## 2. Owner Goals & Improvement Directives

The owner (Joe) has installed Claude to improve the project. His explicit goals are:

1. **Better UI across the entire app** — the current interface lacks polish and professionalism
2. **Improved analytics graphs** — charts need to be clearer, more visually engaging, and easier to interpret for non-technical users
3. **The results of debates should be easy to understand** — users should be able to look at a finished debate and quickly grasp who won, why, and what the key moments were

When making changes, default to:
- Professional, clean visual design using Streamlit's native components where possible
- Clear labeling and plain-English explanations on all charts and data tables
- Consistent styling across all pages (colors, spacing, typography)
- Replacing raw matplotlib figures with styled alternatives where feasible
- Adding contextual "how to read this" captions and explainer text to all charts

---

## 3. Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| **Web UI** | Streamlit | ≥1.28.0 | All pages, charts, state |
| **LLM API** | OpenAI SDK | ≥1.0.0 | Agents, Judge, Insights |
| **Data** | Pandas | ≥2.0.0 | DataFrames for analytics |
| **Charts** | Matplotlib | installed | Currently used for radar, bar, scatter, box plots |
| **Language** | Python | 3.8–3.13 | Tested on 3.13 |
| **Packaging** | setuptools | ≥61.0 | `pyproject.toml` based |
| **Testing** | pytest | ≥7.0.0 | Suite lives in `tests/` |
| **Linting** | flake8 + black + mypy | dev deps | Code style enforcement |

**Key env vars:**

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API access for agents + judge | Required |
| `JUDGE_MODE` | `"agent"` (LLM) or `"heuristic"` | `"agent"` |
| `AGENT_JUDGE_MODEL` | Model for the AgentJudge | `"gpt-4o-mini"` |
| `DEBUG_ARENA` | Enable verbose console debug output | `"0"` |

**API key loading priority** (in `src/arena/utils/openai_config.py`):
1. `OPENAI_API_KEY` environment variable
2. `local_secrets.py` (dev-only, gitignored)
3. Streamlit session state (set via UI)

---

## 4. Folder & File Structure

```
misinfo_arena_v2/
│
├── app.py                          # Main Streamlit entry point (~3,341 lines)
├── pyproject.toml                  # Package config & dependencies
├── requirements.txt                # Pip dependencies
├── prompt_library.json             # Saved prompt variants (user-editable)
├── prompts.json                    # Active prompt references
├── local_secrets.py                # Dev API key injection [GITIGNORED]
├── CLAUDE.md                       # This file
│
├── src/arena/                      # PRIMARY APPLICATION PACKAGE
│   ├── types.py                    # Core data models (Message, Turn, JudgeDecision, etc.)
│   ├── config.py                   # Constants: models, defaults, system prompts
│   ├── app_config.py               # App-level paths and constants
│   ├── agents.py                   # DummyAgent + OpenAIAgent implementations
│   ├── judge.py                    # HeuristicJudge + AgentJudge (PRIMARY)
│   ├── judge_base.py               # Abstract BaseJudge interface
│   ├── judge_explain.py            # Judge explanation utilities
│   ├── factories.py                # Factory functions (create_agent, create_judge, etc.)
│   ├── compat.py                   # Compatibility shims for legacy imports
│   ├── state.py                    # Session state initialization
│   ├── concession.py               # Concession detection logic
│   ├── insights.py                 # InsightsAgent: AI-generated debate summary
│   ├── analytics.py                # Legacy analytics engine
│   ├── storage.py                  # Legacy MatchStorage (matches.jsonl)
│   ├── preflight.py                # Import health checks at startup
│   ├── strategy_analyst.py         # Post-judge LLM strategy labeler
│   ├── strategy_taxonomy.py        # Strategy label definitions
│   ├── claim_metadata.py           # Claim enrichment (category, domain, etc.)
│   ├── replay_summary_agent.py     # On-demand debate summary generator
│   │
│   ├── io/                         # Persistence I/O
│   │   ├── run_store.py            # JSONL append, run metadata writer
│   │   ├── run_store_v2_read.py    # JSON v2 reader (list_runs, load_episodes)
│   │   └── prompts_store.py        # Prompt file read/write
│   │
│   ├── analysis/                   # Analytics & data processing
│   │   ├── episode_dataset.py      # DataFrame builders from episodes.jsonl
│   │   ├── research_analytics.py   # Aggregated research metrics
│   │   ├── claim_analysis.py       # Claim-level breakdowns
│   │   ├── strategy_lens.py        # Regex strategy signal detection
│   │   ├── replay_summary.py       # Replay summary generation
│   │   ├── replay_summary_helper.py
│   │   └── anomaly_detection.py    # IQR + MAD outlier detection
│   │
│   ├── prompts/                    # Prompt management
│   │   ├── judge_static_prompt.py  # AgentJudge system prompt (editable)
│   │   └── prompt_library.py       # Prompt library CRUD
│   │
│   ├── application/                # Use-case layer (clean architecture)
│   │   ├── types.py
│   │   └── use_cases/
│   │       └── execute_next_turn.py  # Core debate turn pipeline
│   │
│   ├── presentation/               # UI layer
│   │   └── streamlit/
│   │       ├── pages/
│   │       │   ├── analytics_page.py          # Analytics dashboard
│   │       │   ├── replay_page.py             # Episode replay viewer
│   │       │   ├── claim_analysis_page.py     # Per-claim deep dive
│   │       │   ├── guide_page.py              # User guide
│   │       │   ├── prompts_page.py            # Prompt editor & library
│   │       │   └── strategy_leaderboard_page.py  # Strategy rankings
│   │       ├── components/
│   │       │   └── arena/
│   │       │       ├── judge_report.py        # Judge decision render component
│   │       │       ├── debate_insights.py     # Insights display component
│   │       │       └── replay_styles.py       # CSS injection + verdict card HTML
│   │       └── state/
│   │           └── runs_refresh.py            # Auto-load run IDs helper
│   │
│   ├── ui/                         # Older UI utilities (partially deprecated)
│   │   ├── debate_chat.py          # Live chat bubble renderer
│   │   ├── run_planner.py          # Multi-claim run scheduler UI
│   │   └── claim_ingest.py         # CSV/XLSX claim upload
│   │
│   └── utils/
│       ├── openai_config.py        # API key resolution
│       ├── serialization.py        # JSON/object serialization helpers
│       ├── transcript_conversion.py
│       └── normalize.py            # Text normalization
│
├── runs/                           # Auto-created run output directory
│   └── <run_id>/
│       ├── run.json                # Run-level metadata
│       └── episodes.jsonl          # One JSON line per completed episode
│
├── data/
│   ├── golden_set_v0.jsonl         # Validation benchmark v0
│   └── golden_set_v1.jsonl         # Validation benchmark v1
│
├── tests/                          # Pytest test suite
├── scripts/                        # Standalone research/evaluation scripts
├── tools/                          # Operational tools (cleanup, inspection)
├── docs/                           # Architecture docs and audit reports (56+ files)
└── artifacts/                      # Evaluation report outputs
```

---

## 5. Core Data Models

All defined in `src/arena/types.py` and `src/arena/judge.py`.

### `AgentRole` (Enum)
```python
SPREADER = "spreader"
DEBUNKER = "debunker"
```

### `Message`
The atomic unit of debate communication.
```python
role: AgentRole
content: str
citations: List[Citation]   # Structured evidence references (mostly empty today)
timestamp: datetime
```

### `Turn`
One exchange in the debate (one spreader message + one debunker message, keyed by `turn_index`).
```python
turn_index: int
spreader_message: Optional[Any]
debunker_message: Optional[Any]
meta: Optional[Dict]
```

### `JudgeDecision`
The output of a completed judge evaluation.
```python
winner: str               # "spreader", "debunker", or "draw"
confidence: float         # 0.0–1.0
reason: str               # Plain-English explanation
totals: Dict[str, float]  # {"spreader": X, "debunker": Y}
scorecard: List[MetricScore]  # Per-dimension scores
```

### `MetricScore`
One row of the scorecard.
```python
metric: str      # e.g. "evidence_quality"
spreader: float  # 0–10
debunker: float  # 0–10
weight: float    # contribution weight
```

### `MatchConfig` / `DebateConfig`
Controls how a debate runs (imported via `factories.py`):
- `max_turns` (default 5, configurable up to 10)
- `topic` — the claim being debated
- `concession_phrases` — keyword triggers for early stop

---

## 6. How a Debate Works End-to-End

### Flow Summary

```
User configures agents & selects claim
          ↓
   "Start Run" creates a run_id
          ↓
   Loop: execute_next_turn() called per turn
     ├── Active agent generates message (OpenAI API)
     ├── Message appended to session transcript
     ├── Concession check (keywords / max turns)
     └── If match over:
           ├── AgentJudge evaluates transcript → JudgeDecision
           │     (falls back to HeuristicJudge on failure)
           ├── StrategyAnalyst labels tactics used
           └── Episode persisted to runs/<run_id>/episodes.jsonl
          ↓
   Results displayed in Arena tab
   (judge report, insights, scorecard)
```

### `execute_next_turn.py` — The Core Pipeline

Located at `src/arena/application/use_cases/execute_next_turn.py`. This is the most critical file in the project. It:

1. Determines whose turn it is (spreader on odd indices, debunker on even)
2. Calls the correct `OpenAIAgent.generate()` with conversation history
3. Appends the new message to `st.session_state["messages"]` and `["turns"]`
4. Checks concession conditions
5. On match completion:
   - Tries `AgentJudge.evaluate_match()` first
   - Falls back to `HeuristicJudge.evaluate_match()` on failure
   - Runs `StrategyAnalyst` to label argument tactics
   - Calls `_persist_completed_match()` to write the episode to disk

### Multi-Claim Chaining

When multiple claims are queued (via the run planner), the app auto-advances: once an episode completes and persists, it resets the transcript and `turn_idx`, loads the next claim, and begins a new episode within the same `run_id`.

---

## 7. The Judge System

### AgentJudge (Primary)

**File:** `src/arena/judge.py` — class `AgentJudge`

The primary judge. Uses an LLM (`gpt-4o-mini` by default, configurable via `AGENT_JUDGE_MODEL`) to evaluate the full debate transcript and return structured JSON scores.

**Evaluation prompt** is loaded from `src/arena/prompts/judge_static_prompt.py`. This prompt is **user-editable** in the Prompts page of the UI — the active prompt is stored in `st.session_state["judge_static_prompt"]` and injected at judge call time.

**Output format** (parsed from LLM JSON response):
```json
{
  "winner": "debunker",
  "confidence": 0.78,
  "reason": "Debunker provided stronger evidence...",
  "totals": {"spreader": 4.2, "debunker": 6.1},
  "scorecard": [
    {"metric": "evidence_quality", "spreader": 4, "debunker": 8},
    ...
  ]
}
```

**Validation** (`_validate_judge_decision`): Enforces that the response contains exactly 6 expected metrics, scores are 0–10, and winner is a valid value. Raises `RuntimeError` on failure to trigger heuristic fallback.

### HeuristicJudge (Fallback)

**File:** `src/arena/judge.py` — class `HeuristicJudge`

Used when `JUDGE_MODE=heuristic` is set, or when `AgentJudge` fails. Uses regex pattern matching to score without any LLM call. Fast, deterministic, but less accurate.

### Judge Routing Logic

```python
# In execute_next_turn.py
judge_mode = os.getenv("JUDGE_MODE", "agent").lower()

if judge_mode == "agent":
    try:
        agent_judge = AgentJudge(model=agent_model, ...)
        decision = agent_judge.evaluate_match(turns, config)
        ss["judge_mode"] = "agent"
    except Exception:
        # Fallback to heuristic
        decision = ss["judge"].evaluate_match(turns, config)
        ss["judge_mode"] = "heuristic_fallback"
else:
    decision = ss["judge"].evaluate_match(turns, config)
    ss["judge_mode"] = "heuristic"
```

### The Six Scoring Dimensions

| Metric | Description | Weight |
|---|---|---|
| `truthfulness_proxy` | Factual grounding, avoidance of absolutist claims | 0.25 |
| `evidence_quality` | Use of citations, sources, concrete data | 0.20 |
| `reasoning_quality` | Logical structure, avoidance of fallacies | 0.20 |
| `responsiveness` | Directly addresses opponent's points | 0.15 |
| `persuasion` | Rhetorical strength and argumentative skill | 0.15 |
| `civility` | Professional tone, avoidance of personal attacks | 0.05 |

### Golden Sets

`data/golden_set_v0.jsonl` and `golden_set_v1.jsonl` are human-curated validation debates used to benchmark the AgentJudge. The eval harness in `scripts/judge_eval.py` runs the judge against these and reports accuracy/consistency. These were created *to test how well the AgentJudge performs*, not as training data.

---

## 8. Agent System

**File:** `src/arena/agents.py`

### `OpenAIAgent`

Used in production. Calls `client.chat.completions.create()` with:
- The agent's system prompt (role persona)
- The full conversation history formatted as OpenAI messages
- Configurable model and temperature

### `DummyAgent`

Used for testing only. Returns deterministic responses based on a hash of conversation history. No API calls. Fast and free.

### Agent Creation

Always via `factories.create_agent()`, never instantiated directly. The factory reads from session state to configure model, temperature, and system prompt.

---

## 9. Storage & Persistence Layer

### JSON v2 Format (Current)

Each run lives in `runs/<run_id>/`:

**`run.json`** — Run-level metadata:
```json
{
  "run_id": "20260312_150537_ebf9",
  "created_at": "2026-03-12T15:05:37",
  "claim_preview": "Vaccines cause autism",
  "episode_count": 3
}
```

**`episodes.jsonl`** — One JSON object per line, one line per completed episode:
```json
{
  "episode_id": 0,
  "claim": "Vaccines cause autism",
  "claim_index": 0,
  "total_claims": 1,
  "created_at": "...",
  "config_snapshot": { "planned_max_turns": 5, "model_spreader": "gpt-4o", ... },
  "results": {
    "winner": "debunker",
    "judge_confidence": 0.82,
    "completed_turn_pairs": 5,
    "totals": { "spreader": 3.9, "debunker": 6.4 },
    "scorecard": [ ... ],
    "reason": "..."
  },
  "concession": { "trigger": "max_turns", "early_stop": false },
  "summaries": { "abridged": "...", "full": "...", "version": "summary_v1" },
  "turns": [ ... ],
  "judge_audit": { "status": "success", "mode": "agent", "version": "v2" },
  "strategy_analysis": { "spreader_labels": [...], "debunker_labels": [...] }
}
```

### Key I/O Files

| File | Purpose |
|---|---|
| `src/arena/io/run_store.py` | Writes new episodes to `episodes.jsonl`, creates `run.json` |
| `src/arena/io/run_store_v2_read.py` | Reads runs: `list_runs()`, `load_episodes()` |
| `src/arena/io/prompts_store.py` | Reads/writes `prompts.json` |

### Legacy Storage

`runs/matches.jsonl` — An older single-file format. Still readable via the legacy expander on the Analytics page. Being phased out in favor of the per-run JSON v2 format.

---

## 10. UI Layer — Pages & Components

The app is launched as a multi-tab Streamlit app from `app.py`. Each tab renders a page module.

### Tab Structure

| Tab | Module | Description |
|---|---|---|
| **Arena** | Inline in `app.py` | Live debate setup, execution, and results |
| **Analytics** | `analytics_page.py` | Aggregated metrics, charts, anomaly explorer |
| **Episode Replay** | `replay_page.py` | Browse and replay any stored debate |
| **Claim Analysis** | `claim_analysis_page.py` | Per-claim breakdown and patterns |
| **Strategy Leaderboard** | `strategy_leaderboard_page.py` | Rankings by argument strategy |
| **Prompt Library** | `prompts_page.py` | Edit and manage agent/judge prompts |
| **Guide** | `guide_page.py` | User-facing documentation |

### Arena Tab (app.py)

The main interactive page. Handles:
- Agent model/temperature/prompt configuration in the sidebar
- Claim input (single or multi-claim via `run_planner.py`)
- Turn execution buttons and live chat display (via `debate_chat.py`)
- Judge report rendering (via `judge_report.py` component)
- Insights panel (via `debate_insights.py` component)

### Replay Tab (`replay_page.py`)

7-tab detail view for a selected episode:
1. **Summary** — AI-generated narrative overview (on demand via `replay_summary_agent`)
2. **Transcript** — Full turn-by-turn conversation (text areas, copyable)
3. **Verdict & Scorecard** — Winner card, scorecard table, top decision drivers bar chart
4. **Strategy Lens** — Regex-detected argument signals per side
5. **Audit** — Raw `judge_audit` JSON for debugging
6. **Config** — Stored `config_snapshot` for this episode
7. **Export** — Download episode JSON, raw JSONL, or full run

### Analytics Tab (`analytics_page.py`)

Sections:
1. **Dataset Overview** — Episode/run counts, win rate, avg confidence, error rate
2. **Research Analytics** — Filterable; strength fingerprint (radar + bar), episode trajectories
3. **Anomaly Explorer** — IQR/MAD outlier detection, box-whisker plot, scatter explorer, link to Replay

### Key Styling

CSS is injected via `src/arena/presentation/streamlit/components/replay_styles.py`. The verdict card uses custom HTML. Most charts use raw `matplotlib` rendered via `st.pyplot()`.

---

## 11. Analytics System

### Data Pipeline

```
runs/<run_id>/episodes.jsonl
      ↓
episode_dataset.py → build_episode_df()    → wide DataFrame (one row per episode)
                   → build_episode_long_df() → long DataFrame (one row per metric per episode)
      ↓
research_analytics.py → apply_research_filters()
                      → compute_strength_fingerprint()  → radar + bar chart data
                      → compute_episode_trajectory()    → line chart data
                      → compute_transparency_summary()  → count breakdowns
      ↓
anomaly_detection.py → compute_iqr_outliers() / compute_mad_outliers()
```

### Key DataFrame Columns (wide format)

| Column | Description |
|---|---|
| `run_id` | Which run the episode belongs to |
| `episode_id` | Sequential index within the run |
| `winner` | `"spreader"`, `"debunker"`, or `"draw"` |
| `judge_confidence` | Float 0–1 |
| `abs_margin` | Absolute score difference between sides |
| `completed_turn_pairs` | How many full turn pairs ran |
| `planned_max_turns` | What was configured |
| `end_trigger` | `"max_turns"`, `"concession"`, etc. |
| `error_flag` | Boolean, true if judge failed |
| `judge_mode` | `"agent"`, `"heuristic"`, `"heuristic_fallback"` |
| `model_spreader` | OpenAI model name used for spreader |
| `model_debunker` | OpenAI model name used for debunker |
| `metric_<name>_spreader` | Per-metric score for spreader |
| `metric_<name>_debunker` | Per-metric score for debunker |
| `metric_<name>_delta` | debunker − spreader for that metric |

### Current Chart Implementations

All charts currently use `matplotlib` via `st.pyplot()`:
- **Radar chart** — Strength fingerprint (polar projection, spreader red / debunker blue)
- **Bar chart** — Strength fingerprint side-by-side or delta view
- **Line chart** — Episode trajectories per metric
- **Box-and-whisker** — Anomaly explorer
- **Scatter plot** — abs_margin vs judge_confidence, colored by winner

---

## 12. Prompt Management System

### Agent Prompts

Default prompts for spreader and debunker are defined in `src/arena/config.py` as `SPREADER_SYSTEM_PROMPT` and `DEBUNKER_SYSTEM_PROMPT`.

Active prompts are stored in `st.session_state["spreader_prompt"]` and `st.session_state["debunker_prompt"]`.

### Judge Prompt

Defined in `src/arena/prompts/judge_static_prompt.py` via `get_judge_static_prompt()`. This returns the canonical system prompt used by `AgentJudge`. It includes a `<TRANSCRIPT_PLACEHOLDER>` that gets replaced at runtime with the formatted debate transcript.

The judge prompt is editable in the Prompts page. The active version is stored in `st.session_state["judge_static_prompt"]`. The app records whether a custom prompt was used via `ss["judge_prompt_customized"]`.

### Prompt Library

`prompt_library.json` stores named prompt variants per agent role. Users can:
- Save multiple named prompts per role
- Mark one as "active" (it gets injected into the agent/judge)
- Add notes/observations per prompt variant
- Delete old variants

CRUD operations in `src/arena/prompts/prompt_library.py`.

---

## 13. Configuration & Environment

### `pyproject.toml`

```toml
[project]
name = "misinfo-arena"
version = "2.0.0"
requires-python = ">=3.8"
dependencies = ["streamlit>=1.28.0", "pandas>=2.0.0", "openai>=1.0.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "black>=22.0.0", "flake8>=4.0.0", "mypy>=0.950"]
```

### `.streamlit/` Config

A `.streamlit/` directory exists (untracked). Likely contains `config.toml` for theme and server settings. Check this file when adjusting Streamlit theme colors.

### `app_config.py`

Defines key filesystem paths:
- `DEFAULT_MATCHES_PATH` — legacy `runs/matches.jsonl`
- `SPREADER_SYSTEM_PROMPT` / `DEBUNKER_SYSTEM_PROMPT` — default agent prompts
- `PROMPTS_PATH` — location of `prompts.json`

### `preflight.py`

Runs import health checks at startup. If key modules fail to import, it prints diagnostics rather than crashing silently. Called at the top of `app.py`.

---

## 14. State Management

All UI state is stored in `st.session_state`. Initialized in `src/arena/state.py` via `initialize_session_state()`.

### Key Session State Keys

| Key | Type | Purpose |
|---|---|---|
| `messages` | `List[dict]` | Chat messages for live debate display |
| `turns` | `List[Turn]` | Structured turn objects for judge |
| `turn_idx` | `int` | Current turn counter |
| `match_in_progress` | `bool` | Whether a debate is currently running |
| `claim_text` | `str` | The active debate topic/claim |
| `run_id` | `str` | Current run identifier |
| `judge_decision` | `JudgeDecision` | Result from last judge evaluation |
| `judge_mode` | `str` | `"agent"`, `"heuristic"`, `"heuristic_fallback"` |
| `judge_status` | `str` | `"success"`, `"error"` |
| `judge_error` | `str\|None` | Error message if judge failed |
| `judge_static_prompt` | `str` | Active judge prompt text |
| `judge_prompt_customized` | `bool` | Whether default was overridden |
| `spreader_prompt` | `str` | Active spreader system prompt |
| `debunker_prompt` | `str` | Active debunker system prompt |
| `spreader_agent` | `BaseAgent` | Instantiated spreader agent |
| `debunker_agent` | `BaseAgent` | Instantiated debunker agent |
| `judge` | `BaseJudge` | Instantiated fallback heuristic judge |
| `runs_refresh_token` | `float` | Cache-busting token for run list |
| `replay_target_run_id` | `str` | Handoff from Analytics → Replay |
| `replay_target_episode_id` | `str` | Handoff from Analytics → Replay |

---

## 15. Current Project Status

### What's Fully Built and Working

- End-to-end debate loop (single and multi-claim)
- AgentJudge with heuristic fallback
- JSON v2 storage format with full episode schema
- Episode replay with 7-tab detail view
- Analytics page with strength fingerprint, trajectories, anomaly explorer
- Prompt library with multi-variant management
- Strategy analysis (post-judge LLM labeling)
- Strategy leaderboard page
- Claim analysis page
- Golden set benchmarks and judge eval harness
- Anomaly detection (IQR + MAD)

### What Needs Improvement (Owner's Priority)

1. **UI polish across all pages** — inconsistent styling, dense layouts, no visual hierarchy
2. **Analytics charts** — raw matplotlib plots with minimal styling; need professional redesign
3. **Debate results clarity** — judge report and scorecard need cleaner presentation
4. **Arena tab** — debate setup and live view could be significantly more engaging
5. **General UX** — lack of clear navigation, confusing captions, no consistent color language

### Known Technical Debt

- `app.py` is ~3,341 lines — the Arena tab logic has not yet been fully extracted into `presentation/streamlit/pages/arena_page.py` (that file exists but is sparse)
- Duplicate `create_judge()` factory function defined twice in `judge.py` (lines 524 and 802)
- `src/arena/ui/` directory contains partially deprecated utilities (`debate_chat.py`, `run_planner.py`) that haven't been fully migrated to `presentation/`
- `src/arena/util/` (singular) and `src/arena/utils/` (plural) both exist — the singular one is legacy
- Legacy `matches.jsonl` format still supported via analytics expander
- Large volume of untracked audit/summary markdown files in project root and `docs/` — these can be ignored

---

## 16. Known Issues & Technical Debt

| Issue | Location | Severity |
|---|---|---|
| `create_judge()` defined twice | `judge.py` lines 524 + 802 | Low (no runtime impact, confusing) |
| `app.py` is a monolith | `app.py` | Medium (hard to navigate) |
| matplotlib charts lack styling | `analytics_page.py` | High (poor UX per owner goals) |
| Arena tab not extracted to page module | `app.py` | Medium |
| `util/` vs `utils/` namespace clash | `src/arena/` | Low |
| 56+ untracked markdown audit docs | `docs/`, project root | Low (clutter) |
| `debate_chat.py` partially superseded | `src/arena/ui/` | Low |

---

## 17. Architectural Patterns & Conventions

### Layered Architecture

```
Presentation   →  src/arena/presentation/streamlit/
Application    →  src/arena/application/use_cases/
Domain         →  src/arena/{types,agents,judge,concession,...}.py
I/O            →  src/arena/io/
```

### Factory Pattern

All major objects (`create_agent`, `create_judge`, `create_debate_engine`, `create_match_storage`) are created through `src/arena/factories.py`. Never instantiate these directly in UI code.

### Compatibility Layer

`src/arena/compat.py` provides shims so legacy import paths still work during migration. If an import fails elsewhere, check `compat.py` first.

### Caching

Analytics data is cached via `@st.cache_data` keyed by `(run_ids_tuple, runs_dir, refresh_token)`. The `refresh_token` is a float stored in session state and incremented to force cache invalidation when runs are added.

### Fail-Safe Persistence

Episode persistence (`_persist_completed_match`) is wrapped in try/except so a storage failure never crashes the debate UI. Strategy analysis is similarly optional — failures are logged but never block persistence.

### Naming Conventions

- Pages: `render_<page_name>_page()` functions
- Components: `render_<component_name>()` functions
- Use cases: `execute_<action_name>()` functions
- State keys: lowercase snake_case strings (`"judge_decision"`, `"run_id"`)
- Run IDs: `YYYYMMDD_HHMMSS_<4hex>` format

### Import Path

Always import from `arena.*` (not relative imports). `app.py` inserts `src/` into `sys.path[0]` at startup so `arena` resolves to `src/arena`.

---

*Last updated: 2026-03-30*
*Audited by Claude Sonnet 4.6 based on full codebase exploration.*
