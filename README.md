# Misinformation Arena (Iteration 2)

A Streamlit-based debate simulation framework where misinformation spreaders battle fact-checkers in turn-based discussions. This iteration focuses on clean architecture, deterministic agent behavior, and comprehensive result persistence.

## 🎯 Features

- **Turn-based Debate System**: Structured exchanges between spreader and debunker agents
- **Multiple Agent Types**: Choose between deterministic Dummy agents or advanced OpenAI-powered agents
- **OpenAI Integration**: Uses OpenAI's Responses API for sophisticated language model agents
- **Interactive UI**: Chat-like interface with real-time debate execution
- **Comprehensive Analytics**: Performance visualization and trend analysis in dedicated Analytics tab
- **Automated Judging**: Heuristic judge system evaluating arguments across 6 dimensions
- **Result Persistence**: All matches saved to JSONL format in `runs/` directory
- **Early Stop Detection**: Debates end automatically when agents concede
- **Configurable Max Turns**: Slider control capped at 100 turns per debate
- **Agent Configuration**: Sidebar controls for model selection and temperature settings
- **Temporal Trend Analysis**: Rolling averages for win rates and judge confidence over time

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip for package management

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd misinfo_arena_v2
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Set up OpenAI API key:**
   ```bash
   # Get your API key from https://platform.openai.com/api-keys
   export OPENAI_API_KEY=your_api_key_here
   ```

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```

5. **Open your browser** to the provided localhost URL (typically `http://localhost:8501`)

## 📁 Project Structure

```
misinfo_arena_v2/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── app.py                       # Main Streamlit application
├── arena/                       # Core framework package
│   ├── __init__.py             # Package initialization and exports
│   ├── types.py                # Data models and type definitions
│   ├── agents.py               # Agent implementations (spreader/debunker)
│   ├── judge.py                # Judge evaluation system (stub)
│   ├── engine.py               # Debate execution engine
│   ├── storage.py              # JSONL persistence layer
│   └── analytics.py            # Analytics and reporting (stub)
└── runs/                       # Auto-created directory for match results
    └── matches.jsonl           # Persisted debate results
```

## 🎮 How to Use

### Basic Operation

1. **Navigate Tabs**: Use the tabs at the top to switch between "🏟️ Arena" and "📊 Analytics"
2. **Arena Tab - Run Debates**:
   - Configure Agents: Use the sidebar to select agent types (Dummy or OpenAI) for both spreader and debunker
   - Set OpenAI Options: If using OpenAI agents, configure model (e.g., "gpt-4") and temperature (0.0-2.0)
   - Configure Settings: Set maximum turns (1-100) and other debate parameters
   - Start Match: Click "🎯 Start New Match" to begin a debate
   - Execute Turns: Click "⏭️ Execute Next Turn" to advance the conversation
   - View Results: Completed matches show judge reports with winner and reasoning
3. **Analytics Tab - Analyze Performance**:
   - View overall win distributions and performance trends
   - Analyze rolling averages for win rates and judge confidence
   - Explore detailed scorecards and temporal patterns
   - Filter data (agent-specific filters coming in future versions)

### Understanding the Debate Flow

- **Turn Structure**: Each turn consists of one spreader message + one debunker response
- **Early Stopping**: Debates end if either agent uses concession phrases ("I agree", "you're right", etc.)
- **Deterministic Behavior**: Agents produce consistent responses based on conversation history
- **Result Persistence**: Every completed match is automatically saved to `runs/matches.jsonl`

### Agent Types

- **Dummy Agents** (Default):
  - **Spreader**: Promotes flat Earth conspiracy claims with defensive responses
  - **Debunker**: Provides scientific evidence and counters misinformation claims
  - **Deterministic**: Same responses given the same conversation history

- **OpenAI Agents** (Requires API key):
  - **Spreader**: Uses GPT models to generate persuasive misinformation arguments
  - **Debunker**: Uses GPT models to provide evidence-based fact-checking responses
  - **Configurable**: Model selection (gpt-4, gpt-3.5-turbo, etc.) and temperature control

- **Judge**: Stub implementation always returns "draw" with 0.5 confidence

## 🔧 Technical Details

### Agent Determinism

Agents use conversation history hashed with turn numbers to ensure repeatable responses:

```python
def _get_deterministic_seed(self, conversation_history, turn_number) -> str:
    # Creates consistent seed from debate state
    history_str = f"turn_{turn_number}_" + conversation_history_content
    return hashlib.sha256(history_str.encode()).hexdigest()[:8]
```

### OpenAI Integration

OpenAI agents use the Responses API for advanced language model capabilities:

```python
# Key implementation details:
response = client.responses.create(
    model=self.model,           # Configurable model (gpt-4, etc.)
    input=conversation_messages, # Formatted conversation history
    temperature=self.temperature  # Controls creativity (0.0-2.0)
)
generated_text = response.output_text  # Extract generated response
```

**Why Responses API?**
- Better conversation context management than Chat Completions
- Structured response handling for multi-turn debates
- Improved consistency in conversational AI behavior
- Enhanced control over conversation flow

**Fallback Handling:**
- API key missing → Show Streamlit error + fallback to Dummy agents
- API call failure → Return safe placeholder response
- Network issues → Graceful degradation with error logging

### Data Persistence

Matches are stored as JSONL (one JSON object per line) for efficient analysis:

```json
{"match_id": "uuid", "config": {...}, "turns": [...], "winner": "draw", ...}
{"match_id": "uuid", "config": {...}, "turns": [...], "winner": "draw", ...}
```

### Session State Management

The app safely uses `st.session_state` for:
- Debate engine and components
- Current match state and configuration
- UI flags for match completion and judge report visibility

## 🎯 Key Components

### Types System (`arena/types.py`)
- `Match`: Complete debate with configuration and results
- `Turn`: Single exchange (spreader + debunker messages)
- `AgentRole`: Enumeration for SPREADER/DEBUNKER
- `MatchResult`: Final outcome with judge decision

### Agent System (`arena/agents.py`)
- `SpreaderAgent`: Deterministic misinformation promoter
- `DebunkerAgent`: Deterministic fact-checker
- Both inherit from `BaseAgent` with conversation-aware responses

### Engine (`arena/engine.py`)
- `DebateEngine`: Coordinates debate execution
- Handles turn management, early stopping, and judge evaluation
- Supports both full matches and incremental turn execution

### Storage (`arena/storage.py`)
- `MatchStorage`: JSONL persistence with automatic directory creation
- Thread-safe append operations
- Structured data export for analysis

## 🔬 Research Applications

This framework enables:
- **Misinformation Pattern Analysis**: Study how false claims evolve in debate
- **Agent Behavior Research**: Compare different debate strategies
- **Fact-Checking Effectiveness**: Measure correction success rates
- **Conversation Dynamics**: Analyze turn-based interaction patterns

## 🚧 Current Limitations

- **Judge System**: Currently a stub (always returns draw)
- **Agent Intelligence**: Simple rule-based responses
- **Analytics**: Basic statistics only
- **Real-time Features**: No WebSocket support for live debates

## 🔄 Future Enhancements

- **Advanced Judge**: LLM-based evaluation of argument quality
- **Smarter Agents**: Integration with language models (GPT, Claude, etc.)
- **Analytics Dashboard**: Comprehensive statistics and visualizations
- **Multi-Agent Debates**: Support for multiple participants
- **Custom Topics**: User-defined debate subjects
- **Export Formats**: CSV, database integration

## 📊 Sample Output

After running several matches, `runs/matches.jsonl` contains:

```json
{
  "match_id": "550e8400-e29b-41d4-a716-446655440000",
  "config": {"max_turns": 10, "topic": "General misinformation debate"},
  "turns": [
    {
      "turn_number": 1,
      "spreader_message": {"role": "spreader", "content": "The Earth is flat and NASA is hiding this truth...", "timestamp": "2024-01-17T10:30:00"},
      "debunker_message": {"role": "debunker", "content": "The Earth is an oblate spheroid...", "timestamp": "2024-01-17T10:30:01"}
    }
  ],
  "winner": "draw",
  "confidence": 0.5,
  "reason": "stub",
  "early_stop": false,
  "created_at": "2024-01-17T10:30:02",
  "turn_count": 1
}
```

## 🤝 Contributing

This is iteration 2 of an ongoing research project. Future contributions should focus on:

1. Enhanced judge implementations
2. More sophisticated agent behaviors
3. Advanced analytics and visualization
4. Performance optimizations
5. Additional export formats

## 📄 License

This project is developed for research purposes. Please cite appropriately if used in academic work.

---

*Built with Streamlit and designed for misinformation research*
