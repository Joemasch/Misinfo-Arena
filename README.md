# Misinformation Arena v2

A research platform for studying how misinformation spreads and how it can be countered through structured adversarial AI debate. Two AI agents argue opposing sides of a claim while an LLM judge evaluates the exchange across six literature-grounded dimensions.

Built for the IME 507 graduate research project at [your university].

## What It Does

- **Spreader agent** argues in favor of a misinformation claim using persuasion tactics (emotional appeals, selective evidence, conspiratorial framing)
- **Debunker agent** counters with evidence-based reasoning, source citations, and inoculation techniques
- **AI judge** scores both sides across 6 dimensions derived from Wachsmuth et al. (2017) and D2D (EMNLP 2025)
- **Analytics** track outcomes across runs, claims, models, and prompt variants

## Key Features

| Feature | Description |
|---|---|
| **4-provider agent support** | OpenAI, Anthropic (Claude), Google (Gemini), xAI (Grok) — 11 models |
| **Literature-grounded judge** | 6 dimensions with equal weights: factuality, source credibility, reasoning quality, responsiveness, persuasion, manipulation awareness |
| **Batch experiment engine** | Run N prompt variants x M prompt variants x C claims in one go |
| **Human annotation** | Rate transcripts, compute Cohen's kappa for human-AI judge agreement |
| **CSV import** | Upload claim sets and prompt variants for systematic experiments |
| **11 analytics sections** | Win rates, model comparison, prompt A/B, concession patterns, response length, longitudinal trends, judge calibration, strategy taxonomy, claim difficulty, anomaly detection |
| **Judge consistency mode** | Run the judge N times per episode and average scores to measure reliability |
| **Role-relative scoring** | The spreader is scored on persuasive effectiveness, not factual accuracy |

## Quick Start

### Prerequisites
- Python 3.8+
- At least one API key (OpenAI, Anthropic, Google, or xAI)

### Installation

```bash
git clone https://github.com/Joemasch/Misinfo-Arena.git
cd Misinfo-Arena
pip install -e .
```

### Set up API keys

Create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-..."
ANTHROPIC_API_KEY = ""
GEMINI_API_KEY = ""
XAI_API_KEY = ""
```

Or paste keys in the sidebar when the app is running.

### Run

```bash
streamlit run app.py
```

## Project Structure

```
misinfo_arena_v2/
├── app.py                          # Streamlit entry point
├── src/arena/                      # Application package
│   ├── agents.py                   #   5 agent classes (OpenAI, Anthropic, Gemini, Grok, Dummy)
│   ├── judge.py                    #   HeuristicJudge + AgentJudge with consistency runs
│   ├── types.py                    #   Core data models (JudgeDecision, MetricScore, Turn, etc.)
│   ├── config.py                   #   11 models, temperature presets, system prompts
│   ├── batch_runner.py             #   N×M×C experiment grid engine
│   ├── prompts/
│   │   ├── judge_static_prompt.py  #   Judge rubric (v2, literature-grounded)
│   │   └── prompt_library.py       #   Named prompt variant CRUD
│   ├── analysis/                   #   Episode datasets, research analytics, anomaly detection
│   ├── application/use_cases/      #   Core debate pipeline (execute_next_turn)
│   ├── presentation/streamlit/     #   All 10 page modules + components
│   ├── io/                         #   Episode persistence (JSON v2)
│   └── utils/api_keys.py           #   Centralized 4-provider key management
├── tests/                          #   47 tests
├── scripts/                        #   Dev tools, golden set evaluation
└── data/                           #   Golden set benchmarks (v0, v1)
```

## Scoring Dimensions

The judge evaluates each side on 6 equally-weighted dimensions:

| Dimension | Source | What it measures |
|---|---|---|
| **Factuality** | D2D (EMNLP 2025) | Narrative consistency (spreader) / factual grounding (debunker) |
| **Source Credibility** | D2D (EMNLP 2025) | Specificity and checkability of cited sources |
| **Reasoning Quality** | Wachsmuth et al. (2017) — Cogency | Logical structure, premise-to-conclusion coherence |
| **Responsiveness** | Wachsmuth et al. (2017) — Reasonableness | Direct engagement with opponent's strongest point |
| **Persuasion** | Wachsmuth et al. (2017) — Effectiveness | Overall convincingness to an uncommitted reader |
| **Manipulation Awareness** | Inoculation theory (Roozenbeek & van der Linden, 2022) | Penalizes manipulation tactics (spreader) / rewards naming them (debunker) |

## Experiment Design

### Single-claim experiment

Upload a CSV to test one claim at different debate lengths:

```csv
claim,run,claim_type,max_turns
Vaccines cause autism,1,Health / Vaccine,2
Vaccines cause autism,1,Health / Vaccine,4
Vaccines cause autism,1,Health / Vaccine,6
Vaccines cause autism,1,Health / Vaccine,8
Vaccines cause autism,1,Health / Vaccine,10
```

### Multi-claim experiment

Upload a CSV to test many claims across domains:

```csv
claim,run,claim_type
Vaccines cause autism,1,Health / Vaccine
5G towers spread COVID,1,Health / Vaccine
Climate change is a hoax,2,Environmental
The 2020 election was stolen,2,Political / Election
```

### Batch experiment (Experiment tab)

Compare prompt variants systematically:

```csv
name,role,prompt_text
IME507 Spreader,spreader,"You are a misinformation spreader agent..."
Naive Spreader,spreader,"You are a misinformation spreader in a debate..."
IME507 Debunker,debunker,"You are a fact-checking debunker agent..."
```

## References

- Wachsmuth, H., et al. (2017). "Argumentation Quality Assessment: Theory vs. Practice." ACL.
- D2D: Debate-to-Detect (EMNLP 2025). Multi-dimensional evaluation rubric for adversarial misinformation debate.
- Roozenbeek, J., & van der Linden, S. (2022). "Inoculation theory and misinformation." Cambridge Handbook.
- Cook, J., et al. (2017). "Neutralizing misinformation through inoculation." PLOS ONE.

## License

This project is developed for academic research purposes. Please cite appropriately if used in academic work.

---

*Built with Streamlit, OpenAI, Anthropic, and Google GenAI SDKs.*
