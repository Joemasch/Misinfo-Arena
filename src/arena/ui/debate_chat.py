"""
Live Chat UI for Debate Arena

Provides a scrollable, iMessage-like conversation feed that updates in real-time
as the debate unfolds. Features typing indicators, smooth animations, and
paired-turn progression.
"""

import streamlit as st
import time
from typing import List, Dict, Any, Callable, Iterator, Union


def _arena_dbg(msg: str) -> None:
    """Lightweight debug log when arena_debug is enabled (server console only)."""
    if st.session_state.get("arena_debug", False):
        print(msg)


def inject_debate_chat_css():
    """Inject CSS for debate chat styling."""
    st.markdown(
        """
        <style>
          /* ---- Debate Chat Container ---- */
          .debate-chat-wrap {
            border: 1px solid rgba(0,0,0,0.08);
            border-radius: 14px;
            background: #ffffff;
            padding: 0;
            margin: 0;
          }

          .chat-scroll {
            height: 520px;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 14px;
            scroll-behavior: smooth;
          }

          /* ---- Bubble Rows ---- */
          .bubble-row {
            display: flex;
            margin: 8px 0;
            width: 100%;
          }

          .bubble-row.left { justify-content: flex-start; }
          .bubble-row.right { justify-content: flex-end; }

          /* ---- Bubbles ---- */
          .bubble {
            max-width: 76%;
            border-radius: 20px;
            padding: 10px 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
            line-height: 1.35;
            font-size: 0.95rem;
            white-space: pre-wrap;
            word-wrap: break-word;
          }

          .bubble.spreader {
            background: rgba(229,57,53,0.10);
            border: 1px solid rgba(229,57,53,0.25);
          }

          .bubble.debunker {
            background: rgba(33,150,243,0.08);
            border: 1px solid rgba(33,150,243,0.18);
          }

          /* ---- Structured content inside bubbles ---- */
          .bubble ul {
            margin: 0.3rem 0 0.3rem 1.2rem;
            padding: 0;
            list-style: disc;
          }
          .bubble li {
            margin-bottom: 0.25rem;
            line-height: 1.45;
          }
          .bubble b {
            font-weight: 700;
          }

          /* ---- Turn summary card ---- */
          .turn-summary {
            display: flex;
            gap: 0;
            margin: 18px 0 6px 0;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid rgba(0,0,0,0.08);
            background: #fff;
          }
          .turn-summary-header {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 6px 10px 2px 10px;
            color: #9ca3af;
          }
          .turn-summary-side {
            flex: 1;
            padding: 4px 12px 8px 12px;
            font-size: 0.82rem;
            line-height: 1.45;
            color: #374151;
          }
          .turn-summary-side.spr {
            border-right: 1px solid rgba(0,0,0,0.06);
            background: rgba(229,57,53,0.03);
          }
          .turn-summary-side.fc {
            background: rgba(33,150,243,0.03);
          }
          .turn-summary-side .ts-role {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
          }
          .turn-summary-side.spr .ts-role { color: #e53935; }
          .turn-summary-side.fc .ts-role { color: #1e88e5; }

          /* ---- Bubble Meta ---- */
          .bubble-meta {
            font-size: 0.75rem;
            opacity: 0.75;
            margin-bottom: 6px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }

          /* ---- Typing Indicator ---- */
          .typing {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            margin: 4px 0;
          }

          .dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: rgba(0,0,0,0.4);
            margin: 0 2px;
            animation: typing 1.4s infinite ease-in-out;
          }

          .dot:nth-child(1) { animation-delay: -0.32s; }
          .dot:nth-child(2) { animation-delay: -0.16s; }
          .dot:nth-child(3) { animation-delay: 0s; }

          @keyframes typing {
            0%, 80%, 100% {
              transform: scale(0.8);
              opacity: 0.5;
            }
            40% {
              transform: scale(1);
              opacity: 1;
            }
          }

          /* ---- Auto-scroll ---- */
          .chat-scroll::-webkit-scrollbar {
            width: 6px;
          }

          .chat-scroll::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.05);
            border-radius: 3px;
          }

          .chat-scroll::-webkit-scrollbar-thumb {
            background: rgba(0,0,0,0.2);
            border-radius: 3px;
          }

          .chat-scroll::-webkit-scrollbar-thumb:hover {
            background: rgba(0,0,0,0.3);
          }
        </style>
        """,
        unsafe_allow_html=True
    )


def init_debate_chat_state():
    """Initialize debate chat state variables."""
    st.session_state.setdefault("debate_messages", [])  # list of message dicts
    st.session_state.setdefault("debate_turn_idx", 1)   # 1-based paired turn counter
    st.session_state.setdefault("debate_phase", "spreader")  # "spreader" or "debunker"
    st.session_state.setdefault("debate_running", False)
    st.session_state.setdefault("debate_autoplay", True)
    st.session_state.setdefault("debate_generating", False)
    st.session_state.setdefault("debate_active_msg_id", None)

    # Cleanup safety: remove leftover typing messages (keep only the last one)
    msgs = st.session_state.debate_messages
    typing_idxs = [i for i, m in enumerate(msgs) if m.get("status") == "typing"]
    if len(typing_idxs) > 1:
        last = typing_idxs[-1]
        st.session_state.debate_messages = [m for i, m in enumerate(msgs) if i == last or m.get("status") != "typing"]


def _find_msg_index_by_id(messages, msg_id):
    """Find message index by ID."""
    for i, m in enumerate(messages):
        if m.get("id") == msg_id:
            return i
    return None

def html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))


def nl2br(text: str) -> str:
    """Convert newlines to <br> tags."""
    return text.replace("\n", "<br>")


import re as _re


def _format_for_display(raw: str) -> str:
    """
    Format raw agent text for readable display in chat bubbles.

    1. Bold the first sentence (the thesis / lead claim).
    2. Detect numbered or bulleted list patterns and render as <ul>/<li>.

    Full message is always shown — no truncation or collapsing.
    The raw text stored in session state and sent to the judge is never modified.
    """
    text = html_escape(raw).strip()
    if not text:
        return ""

    # ── Convert Markdown bold/italic to HTML ─────────────────────────────
    # **bold** → <b>bold</b>  (must come before single *)
    text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # *italic* → <i>italic</i>
    text = _re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # ── Split into paragraphs ────────────────────────────────────────────
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return nl2br(text)

    # ── Bold the first sentence of paragraph 1 ───────────────────────────
    first_para = paragraphs[0]
    _sent_match = _re.match(r'^(.+?[.!?])(\s|$)', first_para, _re.DOTALL)
    if _sent_match:
        first_sentence = _sent_match.group(1)
        rest_of_para = first_para[len(first_sentence):].strip()
        paragraphs[0] = f'<b>{first_sentence}</b> {rest_of_para}'.strip()
    else:
        if len(first_para) < 200:
            paragraphs[0] = f'<b>{first_para}</b>'

    # ── Detect and format list patterns ──────────────────────────────────
    formatted_paragraphs = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]

        list_items = []
        non_list_lines = []
        for line in lines:
            list_match = _re.match(r'^(?:\d+[.)]\s+|[-•*]\s+)(.+)', line)
            if list_match:
                list_items.append(list_match.group(1))
            else:
                if list_items:
                    items_html = "".join(f"<li>{item}</li>" for item in list_items)
                    non_list_lines.append(f'<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;list-style:disc;">{items_html}</ul>')
                    list_items = []
                non_list_lines.append(line)

        if list_items:
            items_html = "".join(f"<li>{item}</li>" for item in list_items)
            non_list_lines.append(f'<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;list-style:disc;">{items_html}</ul>')

        formatted_paragraphs.append("<br>".join(non_list_lines))

    return '<div style="margin-bottom:0.5rem"></div>'.join(formatted_paragraphs)


def _detect_tactics(content: str, role: str) -> str:
    """
    Detect rhetorical tactics in a message using regex (no API call).
    Returns a short human-readable label like "emotional appeal + vague sources".
    """
    if not content:
        return ""

    # Tactic patterns → human-readable labels (ordered by salience)
    _TACTIC_PATTERNS = [
        (_re.compile(r"\b(cover\s*up|hidden\s+truth|they\s+don'?t\s+want|mainstream\s+media|suppressed)\b", _re.I),
         "conspiracy framing"),
        (_re.compile(r"\b(fear|corrupt|agenda|dangerous|threat|protect|alarming|devastating)\b", _re.I),
         "emotional appeal"),
        (_re.compile(r"\b(experts\s+say|people\s+say|research\s+shows?|studies\s+show|it'?s\s+known)\b", _re.I),
         "vague sources"),
        (_re.compile(r"\b(CDC|WHO|NIH|FDA|according\s+to|journal|university|published)\b", _re.I),
         "named sources"),
        (_re.compile(r"\d+%|\d+\s*(?:million|billion|percent)", _re.I),
         "specific data"),
        (_re.compile(r"\b(claim\s+is\s+false|evidence\s+shows|in\s+fact|the\s+evidence|debunked)\b", _re.I),
         "direct refutation"),
        (_re.compile(r"\b(fallacy|logical\s+error|manipulation|tactic|technique|exploiting)\b", _re.I),
         "named manipulation tactic"),
        (_re.compile(r"\b(however|although|on\s+the\s+other\s+hand|that\s+said)\b", _re.I),
         "counterargument"),
        (_re.compile(r"\b(because|therefore|thus|leads?\s+to|result(s|ing)\s+in)\b", _re.I),
         "causal reasoning"),
    ]

    detected = []
    for pattern, label in _TACTIC_PATTERNS:
        if pattern.search(content):
            detected.append(label)
        if len(detected) >= 3:
            break

    if not detected:
        return ""
    return " + ".join(detected)


def _extract_key_move(content: str) -> str:
    """
    Extract the opening thesis / key move from a message for the turn summary.
    Returns the full first sentence — no truncation.
    """
    if not content:
        return ""
    text = content.strip()
    # Find first sentence boundary
    match = _re.match(r'^(.+?[.!?])(?:\s|$)', text, _re.DOTALL)
    if match:
        return html_escape(match.group(1).strip())
    # No sentence boundary found — use first 200 chars
    if len(text) > 200:
        trimmed = text[:200].rsplit(' ', 1)[0]
        return html_escape(trimmed) + "..."
    return html_escape(text)


def _build_chat_html(messages: List[Dict[str, Any]]) -> str:
    """Build HTML for debate chat with per-turn summary cards."""
    rows = []

    # Group messages into turn pairs for summary cards
    turn_pairs: dict[int, dict] = {}
    for msg in messages:
        turn = msg.get("turn", 1)
        speaker = msg.get("speaker", "").lower()
        if msg.get("status") == "typing":
            continue
        if turn not in turn_pairs:
            turn_pairs[turn] = {}
        turn_pairs[turn][speaker] = msg.get("content", "")

    rendered_summaries: set[int] = set()

    for msg in messages:
        speaker = msg.get("speaker", "").lower()
        content = msg.get("content", "")
        turn = msg.get("turn", 1)
        status = msg.get("status", "final")

        # Insert turn summary card before the first message of each turn pair
        # (only when both sides have spoken)
        if turn not in rendered_summaries and turn in turn_pairs:
            pair = turn_pairs[turn]
            spr_text = pair.get("spreader", "")
            fc_text = pair.get("debunker", "")
            if spr_text and fc_text:
                spr_move = _extract_key_move(spr_text)
                fc_move = _extract_key_move(fc_text)
                spr_tactics = _detect_tactics(spr_text, "spreader")
                fc_tactics = _detect_tactics(fc_text, "debunker")
                spr_tactic_html = f'<div style="font-size:0.72rem;color:#e53935;margin-top:3px;font-style:italic">{spr_tactics}</div>' if spr_tactics else ''
                fc_tactic_html = f'<div style="font-size:0.72rem;color:#1e88e5;margin-top:3px;font-style:italic">{fc_tactics}</div>' if fc_tactics else ''
                summary_html = (
                    f'<div class="turn-summary">'
                    f'<div class="turn-summary-side spr">'
                    f'<div class="turn-summary-header">Turn {turn}</div>'
                    f'<div class="ts-role">Spreader</div>'
                    f'{spr_move}'
                    f'{spr_tactic_html}'
                    f'</div>'
                    f'<div class="turn-summary-side fc">'
                    f'<div class="turn-summary-header">&nbsp;</div>'
                    f'<div class="ts-role">Fact-checker</div>'
                    f'{fc_move}'
                    f'{fc_tactic_html}'
                    f'</div>'
                    f'</div>'
                )
                rows.append(summary_html)
                rendered_summaries.add(turn)

        if speaker == "spreader":
            row_class = "bubble-row right"
            bubble_class = "bubble spreader"
            meta_text = f"Turn {turn} · SPREADER"
        else:
            row_class = "bubble-row left"
            bubble_class = "bubble debunker"
            meta_text = f"Turn {turn} · DEBUNKER"

        if status == "typing":
            bubble_html = '<div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>'
        else:
            formatted_content = _format_for_display(content)
            bubble_html = f'<div class="bubble-meta">{meta_text}</div><div>{formatted_content}</div>'

        rows.append(
            f'<div class="{row_class}"><div class="{bubble_class}">{bubble_html}</div></div>'
        )

    return f'<div class="debate-chat-wrap"><div class="chat-scroll">{"".join(rows)}</div></div>'


def render_debate_chat(messages: List[Dict[str, Any]]):
    """Render the debate chat as HTML bubbles."""
    html = _build_chat_html(messages)
    st.markdown(html, unsafe_allow_html=True)

    # Auto-scroll script
    st.markdown(
        """
        <script>
          setTimeout(() => {
            const scrolls = window.parent.document.querySelectorAll('.chat-scroll');
            const scroll = scrolls[scrolls.length - 1];
            if (scroll) { scroll.scrollTop = scroll.scrollHeight; }
          }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )


def render_debate_chat_into(container, messages: List[Dict[str, Any]]):
    """Render debate chat into a container/placeholder."""
    html = _build_chat_html(messages)
    container.markdown(html, unsafe_allow_html=True)


def render_debate_controls():
    """Render debate control buttons."""
    col_start, col_auto = st.columns([1, 1])

    with col_start:
        # Manual test: num_episodes=2, turn_plan [4,6] -> click Start -> expect 1/2, max_turns=4;
        # after ep1 completes -> chain to 2/2, max_turns=6, chat cleared; after ep2 -> run complete.
        if st.button("🎯 Start new match", use_container_width=True, key="debate_start_match_btn"):
            from app import get_ui_claim, arena_dbg
            ss = st.session_state

            if not ss.get("run_active", False):
                st.error("Start a new run first.")
                st.stop()

            # Block if the selected model's API key is missing
            from arena.utils.api_keys import get_key_status
            from arena.agents import is_anthropic_model, is_gemini_model, is_grok_model
            _key_status = get_key_status()
            for _role, _model_key in [("Spreader", "spreader_model"), ("Fact-checker", "debunker_model")]:
                _model = ss.get(_model_key, "gpt-4o-mini")
                if is_anthropic_model(_model) and not _key_status.get("anthropic", {}).get("set"):
                    st.error(f"**{_role} uses {_model} but ANTHROPIC_API_KEY is not set.** Paste it in the sidebar or add it to `.streamlit/secrets.toml`.")
                    st.stop()
                elif is_gemini_model(_model) and not _key_status.get("gemini", {}).get("set"):
                    st.error(f"**{_role} uses {_model} but GEMINI_API_KEY is not set.** Paste it in the sidebar or add it to `.streamlit/secrets.toml`.")
                    st.stop()
                elif is_grok_model(_model) and not _key_status.get("grok", {}).get("set") and not _key_status.get("xai", {}).get("set"):
                    st.error(f"**{_role} uses {_model} but XAI_API_KEY is not set.** Paste it in the sidebar or add it to `.streamlit/secrets.toml`.")
                    st.stop()
                elif not is_anthropic_model(_model) and not is_gemini_model(_model) and not is_grok_model(_model) and not _key_status.get("openai", {}).get("set"):
                    st.error(f"**{_role} uses {_model} but OPENAI_API_KEY is not set.** Paste it in the sidebar or add it to `.streamlit/secrets.toml`.")
                    st.stop()

            arena_mode = ss.get("arena_mode", "single_claim")
            if arena_mode == "multi_claim":
                claims_list = ss.get("claims_list", [])
                if not claims_list:
                    st.warning("Enter or upload at least one claim.")
                    st.stop()
                ui_claim = claims_list[0]
                ss["current_claim_index"] = 0
                ss["total_claims"] = len(claims_list)
                ss["max_turns"] = 10
                ss["num_episodes"] = len(claims_list)
            else:
                ui_claim = get_ui_claim()
                if not ui_claim:
                    st.warning("Please enter a claim to debate.")
                    st.stop()

            if ss.get("turn_plan_valid") is False:
                st.error("Fix the Run Plan (turn plan must be valid).")
                st.stop()

            if ss.get("match_in_progress", False):
                st.warning("A match is already in progress.")
                st.stop()

            if "episode_idx" not in ss:
                ss["episode_idx"] = 1

            ss["topic"] = ui_claim
            ss["current_claim"] = ui_claim
            ss["claim"] = ui_claim

            arena_dbg("MATCH_START_TOPIC",
                     ui_claim=(ui_claim or "")[:50],
                     ss_topic=(ss.get("topic") or "")[:50],
                     ss_current_claim=(ss.get("current_claim") or "")[:50],
                     ss_claim=(ss.get("claim") or "")[:50])

            ss["debate_messages"] = []
            ss["episode_transcript"] = []
            ss["completed_turn_pairs"] = 0
            ss["turn_idx"] = 0
            ss["debate_phase"] = "spreader"

            if arena_mode != "multi_claim":
                try:
                    from arena.ui.run_planner import apply_turn_plan_to_episode
                except ImportError:
                    import sys
                    sys.path.insert(0, "src")
                    from arena.ui.run_planner import apply_turn_plan_to_episode
                apply_turn_plan_to_episode(ss, ss.get("episode_idx", 1))

            _arena_dbg(f"[ARENA] Start new match: episode_idx={ss.get('episode_idx')} episodes_completed={ss.get('episodes_completed', 0)} max_turns={ss.get('max_turns')} run_active={ss.get('run_active')}")

            ss["match_in_progress"] = True
            ss["debate_running"] = True
            ss["debate_autoplay"] = True
            ss["match_id"] = f"match_{ss['episode_idx']}"

            arena_dbg("MATCH_START_RESET",
                     match_id=ss.get("match_id"),
                     episode_idx=ss.get("episode_idx"),
                     topic=(ss.get("topic") or "")[:50],
                     debate_messages_len=len(ss.get("debate_messages") or []),
                     episode_transcript_len=len(ss.get("episode_transcript") or []),
                     completed_turn_pairs=ss.get("completed_turn_pairs"),
                     debate_phase=ss.get("debate_phase"),
                     debate_running=ss.get("debate_running"),
                     match_in_progress=ss.get("match_in_progress"),
                     debate_autoplay=ss.get("debate_autoplay"))

            arena_dbg("RERUN_EXECUTED", reason="start_new_match")
            st.rerun()

    with col_auto:
        st.checkbox("Auto-play", value=st.session_state.debate_autoplay, key="debate_autoplay")


def run_debate_step(
    max_turns: int,
    generate_spreader_fn: Callable[[List[Dict]], Union[str, Iterator[str]]],
    generate_debunker_fn: Callable[[List[Dict]], Union[str, Iterator[str]]],
    build_context_fn: Callable[[List[Dict]], Any] = None
):
    """
    Generate exactly one message per call by delegating to execute_next_turn.

    Returns True if a message was completed, False if debate should stop.
    """
    ss = st.session_state

    # PHASE 2 (deferred chaining): consume pending chain at start so UI had one frame to show completed episode
    if ss.get("_pending_chain", False):
        next_idx = ss.get("_pending_chain_next_episode_idx")
        next_claim_idx = ss.get("_pending_chain_next_claim_index")
        arena_mode = ss.get("arena_mode", "single_claim")
        if next_idx is not None:
            ss["episode_idx"] = int(next_idx)
        if arena_mode == "multi_claim" and next_claim_idx is not None:
            claims_list = ss.get("claims_list", [])
            if 0 <= next_claim_idx < len(claims_list):
                claim_text = claims_list[next_claim_idx]
                ss["topic"] = claim_text
                ss["current_claim"] = claim_text
                ss["claim"] = claim_text
                ss["current_claim_index"] = next_claim_idx
                ss["max_turns"] = 10
        if ss.get("debug_mode", False):
            print(f"[ARENA] CONSUME pending_chain next_episode={ss.get('episode_idx')} len(debate_messages) BEFORE={len(ss.get('debate_messages', []))}")
        try:
            from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
        except ImportError:
            import sys
            sys.path.insert(0, "src")
            from arena.ui.run_planner import reset_episode_state_for_chaining, apply_turn_plan_to_episode
        reset_episode_state_for_chaining(ss)
        if arena_mode == "multi_claim":
            ss["topic"] = ss.get("current_claim", "")
            ss["max_turns"] = 10
        else:
            apply_turn_plan_to_episode(ss, ss.get("episode_idx", 1))
        if ss.get("debug_mode", False):
            print(f"[ARENA] CONSUME pending_chain len(debate_messages) AFTER={len(ss.get('debate_messages', []))}")
        ss["_pending_chain"] = False
        ss["_pending_chain_next_episode_idx"] = None
        ss["_pending_chain_next_claim_index"] = None
        ss["match_in_progress"] = True
        ss["debate_running"] = True
        return True

    from arena.application.use_cases.execute_next_turn import execute_next_turn

    # TEMPORARY DEBUG: Track call state (gated by DEBUG_DIAG)
    phase_before = st.session_state.get("debate_phase")
    pairs_before = st.session_state.get("completed_turn_pairs", 0)
    in_progress_before = st.session_state.get("match_in_progress", False)
    running_before = st.session_state.get("debate_running", False)

    try:
        from arena.app_config import DEBUG_DIAG
        if DEBUG_DIAG:
            print(f"TRACE run_debate_step START: phase={phase_before} pairs={pairs_before} max={max_turns} match_in_progress={in_progress_before} debate_running={running_before}")
    except ImportError:
        pass

    # Call the use case in single message mode
    result = execute_next_turn(st.session_state, single_message_mode=True)

    # TEMPORARY DEBUG: Track result
    phase_after = st.session_state.get("debate_phase")
    pairs_after = st.session_state.get("completed_turn_pairs", 0)
    in_progress_after = st.session_state.get("match_in_progress", False)
    running_after = st.session_state.get("debate_running", False)
    result_ok = result.get("ok", False)

    try:
        from arena.app_config import DEBUG_DIAG
        if DEBUG_DIAG:
            print(f"TRACE run_debate_step RESULT: phase={phase_after} pairs={pairs_after} match_in_progress={in_progress_after} debate_running={running_after} result_ok={result_ok}")
    except ImportError:
        pass

    # If match is no longer in progress, episode just completed: increment episodes_completed then chain or end run
    ss = st.session_state
    if not ss.get("match_in_progress", False):
        ss["episodes_completed"] = int(ss.get("episodes_completed", 0)) + 1
        current_episode = ss.get("episode_idx", 1)
        total_episodes = ss.get("num_episodes", 1)
        arena_mode = ss.get("arena_mode", "single_claim")
        if arena_mode == "multi_claim":
            current_claim_idx = ss.get("current_claim_index", 0)
            total_claims = ss.get("total_claims", 1)
            will_chain = (current_claim_idx + 1) < total_claims
            next_claim_idx = current_claim_idx + 1 if will_chain else None
        else:
            will_chain = current_episode < total_episodes
            next_claim_idx = None

        _arena_dbg(f"[ARENA] Episode completed: episode_idx={current_episode} episodes_completed={ss.get('episodes_completed')} will_chain={will_chain}")

        if will_chain:
            ss["_pending_chain"] = True
            ss["_pending_chain_next_episode_idx"] = current_episode + 1
            if arena_mode == "multi_claim":
                ss["_pending_chain_next_claim_index"] = next_claim_idx
            ss["debate_running"] = False
            ss["_arena_needs_final_rerun"] = True
            try:
                from arena.presentation.streamlit.state.runs_refresh import bump_runs_refresh_token
                bump_runs_refresh_token("episode_appended")
            except Exception:
                pass
            if ss.get("debug_mode", False):
                print(f"[ARENA] DEFER chain current_episode={current_episode} next_episode={current_episode + 1} len(debate_messages)={len(ss.get('debate_messages', []))}")
            return False
        else:
            try:
                from arena.app_config import DEBUG_DIAG
                if DEBUG_DIAG:
                    print(f"TRACE run_debate_step STOPPING: match_in_progress became False (run complete)")
            except ImportError:
                pass
            ss["debate_running"] = False
            ss["run_active"] = False
            try:
                from arena.presentation.streamlit.state.runs_refresh import bump_runs_refresh_token
                bump_runs_refresh_token("run_completed")
            except Exception:
                pass
            run_id = ss.get("run_id")
            if run_id:
                sel = st.session_state.get("analytics_selected_run_ids") or []
                if run_id not in sel:
                    st.session_state["analytics_selected_run_ids"] = sel + [run_id]
            ss["_arena_needs_final_rerun"] = True
            return False

    # Return success if we got a result (message was generated)
    return result.get("ok", False)
