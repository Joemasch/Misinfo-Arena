"""
Execute Next Turn Use Case

Handles the debate turn-pair execution logic (spreader -> debunker -> completion checks).
Extracted from app.py to separate application logic from presentation concerns.
"""

import streamlit as st
import os  # NOTE: os must be imported at module scope. Do not import inside functions (causes UnboundLocalError in judge routing).

# Import required types and functions
from arena.factories import DebateConfig, Message, Turn, AgentRole
from arena.concession import should_concede, check_keyword_concession
from arena.state import is_concession
from arena.application.types import TurnPairResult
from arena.app_config import DEFAULT_MATCHES_PATH, DEBUG_DIAG
from arena.utils.transcript_conversion import to_paired_turns_for_judge

# Re-exported helpers (callers may import these from here)
from arena.application.use_cases.judge_helpers import (
    _jd_get,
    _jd_to_dict,
    _evaluate_judge,
    _make_judge_decision_safe,
    _infer_judge_status,
    _ensure_non_empty_scorecard,
)
from arena.application.use_cases.episode_builder import (
    _extract_claim_metadata,
    _build_episode_object,
    _build_run_object,
    _run_strategy_analysis,
)
from arena.application.use_cases.episode_persister import (
    _persist_completed_match,
    _convert_transcript_for_judge,
)


def generate_agent_message(agent, context):
    """
    Generate a message from an agent with the given context.
    """
    return agent.generate(context)


def execute_next_turn(state=None, single_message_mode=False) -> dict:
    """
    EXECUTE NEXT TURN - Generate both spreader and debunker messages.

    CHAT TURN PATTERN:
    ==================
    1. Generate spreader message based on topic and conversation history
    2. Generate debunker message in response to spreader
    3. Add both messages to chat transcript immediately
    4. Check for completion conditions
    5. If complete, run judge evaluation

    WHY TWO MESSAGES PER TURN?
    ==========================
    - Matches real debate flow: spreader argues, debunker responds
    - Each button click advances the conversation meaningfully
    - Users see both sides of the exchange at once
    """
    # Use provided state or default to streamlit session_state
    ss = state if state is not None else st.session_state

    # ===================================================================
    # TRANSCRIPT KEY BRIDGING - Ensure UI and persistence use same transcript
    # ===================================================================
    # The Arena UI renders from debate_messages, but persistence expects episode_transcript
    # Bridge them so both keys contain the same data
    if "debate_messages" in ss and "episode_transcript" not in ss:
        ss["episode_transcript"] = ss["debate_messages"]
    elif "episode_transcript" in ss and "debate_messages" not in ss:
        ss["debate_messages"] = ss["episode_transcript"]

    # Create result object to track turn execution
    result = TurnPairResult(ok=True, debug={})

    # TEMPORARY DEBUG: Entry state (gated by DEBUG_DIAG for production experimentation)
    if DEBUG_DIAG:
        print(f"TRACE execute_next_turn ENTRY: single_mode={single_message_mode} phase={ss.get('debate_phase')} pairs={ss.get('completed_turn_pairs', 0)} max={ss.get('max_turns', 5)} match_in_progress={ss.get('match_in_progress', False)}")

    # A) STEP_ENTRY at function entry
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("STEP_ENTRY",
                     phase=ss.get('debate_phase'),
                     completed_turn_pairs=ss.get('completed_turn_pairs', 0),
                     match_in_progress=ss.get('match_in_progress', False),
                     debate_running=ss.get('debate_running', False))
        except ImportError:
            pass

    # Initialize message variables to avoid UnboundLocalError
    spreader_message = None
    debunker_message = None

    # ===================================================================
    # GUARD: Check if match is in progress
    # ===================================================================
    if not ss.get("match_in_progress", False):
        st.warning("No active match to continue - start a new match first")
        result.ok = False
        result.completion_reason = "No active match"
        return result.to_dict()

    # Completion check moved to after message generation

    turn_idx = ss["turn_idx"]
    topic = ss.get("topic", "")

    # Track turn index in result
    result.turn_idx = turn_idx

    # ===================================================================
    # PHASE 2A: CONCESSION STATE MANAGEMENT
    # ===================================================================
    # Initialize or get rolling concession state for evidence-driven concessions
    if "concession_state" not in ss:
        ss["concession_state"] = {"consecutive": 0, "last_advantaged": None}

    if single_message_mode:
        # ===================================================================
        # SINGLE MESSAGE MODE - Generate one message per call (for UI rolling chat)
        # ===================================================================
        # Determine current speaker from debate_phase (default to spreader for first message)
        current_phase = ss.get("debate_phase", "spreader")
        debate_messages = ss.get("debate_messages", [])

        # Get context from debate_messages instead of messages
        last_spreader_content = ""
        last_debunker_content = ""
        for msg in reversed(debate_messages):
            if msg.get("status") == "final":  # Only consider finalized messages
                if msg.get("speaker") == "spreader":
                    last_spreader_content = msg.get("content", "")
                    break
                elif msg.get("speaker") == "debunker":
                    last_debunker_content = msg.get("content", "")
                    break

        # Build context for current speaker
        if current_phase == "spreader":
            context = {
                "topic": topic,
                "turn_idx": turn_idx,
                "last_opponent_text": last_debunker_content,
                "system_prompt": ss.get("spreader_prompt", ""),
            }
            agent = ss["spreader_agent"]
            speaker_name = "spreader"
            result.spreader_text = None  # Will be set after generation
        else:  # debunker
            context = {
                "topic": topic,
                "turn_idx": turn_idx,
                "last_opponent_text": last_spreader_content,
                "system_prompt": ss.get("debunker_prompt", ""),
            }
            agent = ss["debunker_agent"]
            speaker_name = "debunker"
            result.debunker_text = None  # Will be set after generation

        try:
            message_content = generate_agent_message(agent, context)
        except Exception as e:
            error_msg = f"{speaker_name.title()} generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = f"{speaker_name} generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # Add message to debate_messages (UI transcript)
        import time
        message_record = {
            "id": f"turn_{turn_idx}_{speaker_name}_{time.time()}",
            "turn": turn_idx,
            "speaker": speaker_name,
            "content": message_content,
            "status": "final",
            "ts": time.time(),
        }
        debate_messages.append(message_record)

        # APPEND: Track message append (transcript duplication detection)
        if hasattr(ss, 'arena_dbg'):  # Import debug function if available
            try:
                from app import arena_dbg
                arena_dbg("APPEND", speaker=speaker_name, turn=turn_idx,
                         debate_msgs_count=len(debate_messages),
                         episode_transcript_count=len(episode_transcript),
                         message_id=message_record.get("id", ""),
                         content_len=len(message_content))
            except ImportError:
                pass

        # Also add to episode_transcript for persistence (bridge the keys)
        episode_transcript = ss.get("episode_transcript", [])
        transcript_record = {
            "message_id": message_record["id"],
            "episode_index": ss.get("episode_idx", 1),
            "turn_index": turn_idx,
            "role": "user" if speaker_name == "spreader" else "assistant",
            "name": speaker_name,
            "content": message_content,
            "timestamp": message_record["ts"],
        }
        episode_transcript.append(transcript_record)

        # D) MSG_GENERATED immediately after message creation but before completion logic
        if hasattr(ss, 'arena_dbg'):
            try:
                from app import arena_dbg
                arena_dbg("MSG_GENERATED",
                         phase=ss.get('debate_phase'),
                         speaker=message_record.get("speaker"),
                         turn=message_record.get("turn"),
                         debate_messages_len=len(debate_messages),
                         episode_transcript_len=len(episode_transcript),
                         completed_turn_pairs=ss.get('completed_turn_pairs', 0))
            except ImportError:
                pass

        # Update result
        if speaker_name == "spreader":
            result.spreader_text = message_content
        else:
            result.debunker_text = message_content

        # Count full pair only after debunker responds
        if current_phase == "debunker":
            before = ss.get("completed_turn_pairs", 0)
            ss["completed_turn_pairs"] = before + 1
            if hasattr(ss, 'arena_dbg'):
                try:
                    from app import arena_dbg
                    arena_dbg(
                        "PAIRS_INC_AFTER_DEBUNK",
                        before=before,
                        after=ss["completed_turn_pairs"],
                        turn=transcript_record.get("turn_index"),
                        name=transcript_record.get("name"),
                    )
                except ImportError:
                    pass

        # Advance phase for next call
        if current_phase == "spreader":
            ss["debate_phase"] = "debunker"
        else:
            ss["debate_phase"] = "spreader"

    else:
        # ===================================================================
        # PAIR MODE - Generate both messages (original logic for backward compatibility)
        # ===================================================================
        # Find the last message from each debater for context
        messages = ss["messages"]

        # Find the last spreader message (for debunker context)
        last_spreader_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user" or msg.get("name") == "spreader":
                last_spreader_content = msg.get("content", "")
                break

        # Find the last debunker message (for spreader context)
        last_debunker_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" or msg.get("name") == "debunker":
                last_debunker_content = msg.get("content", "")
                break

        # ===================================================================
        # GENERATE SPREADER MESSAGE
        # ===================================================================
        spreader_context = {
            "topic": topic,
            "turn_idx": turn_idx,
            "last_opponent_text": last_debunker_content,
            "system_prompt": ss.get("spreader_prompt", ""),
        }

        try:
            spreader_message = generate_agent_message(ss["spreader_agent"], spreader_context)
        except Exception as e:
            error_msg = f"Spreader generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = "Spreader generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # ===================================================================
        # GENERATE DEBUNKER MESSAGE
        # ===================================================================
        debunker_context = {
            "topic": topic,
            "turn_idx": turn_idx,
            "last_opponent_text": spreader_message,
            "system_prompt": ss.get("debunker_prompt", ""),
        }

        try:
            debunker_message = generate_agent_message(ss["debunker_agent"], debunker_context)
        except Exception as e:
            error_msg = f"Debunker generation failed: {str(e)}"
            ss["error"] = error_msg
            ss["match_in_progress"] = False
            ss["stop_reason"] = "error"
            st.error(f"❌ {error_msg}")
            result.ok = False
            result.completion_reason = "Debunker generation error"
            result.last_openai_error = error_msg
            return result.to_dict()

        # Set result fields for pair mode
        result.spreader_text = str(spreader_message) if spreader_message is not None else ""
        result.debunker_text = str(debunker_message) if debunker_message is not None else ""

    # For single message mode, result fields are already set in the respective branches

    if not single_message_mode:
        # ===================================================================
        # PAIR MODE - Add both messages to transcripts
        # ===================================================================

        # Add to episode transcript (structured for judge/analysis)
        import datetime
        message_records = [
            {
                "message_id": f"ep{ss.get('episode_idx', 1)}_turn{turn_idx}_spreader",
                "episode_index": ss.get("episode_idx", 1),
                "turn_index": turn_idx,
                "role": "spreader",
                "name": "spreader",
                "content": str(spreader_message),
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "message_id": f"ep{ss.get('episode_idx', 1)}_turn{turn_idx}_debunker",
                "episode_index": ss.get("episode_idx", 1),
                "turn_index": turn_idx,
                "role": "debunker",
                "name": "debunker",
                "content": str(debunker_message),
                "created_at": datetime.datetime.now().isoformat()
            }
        ]

        if "episode_transcript" not in ss:
            ss["episode_transcript"] = []
        ss["episode_transcript"].extend(message_records)

        # Add to flat messages (for UI compatibility)
        ss["messages"].extend([
            {
                "role": "user",
                "name": "spreader",
                "content": spreader_message
            },
            {
                "role": "assistant",
                "name": "debunker",
                "content": debunker_message
            }
        ])

    if single_message_mode:
        # In single message mode, counters are updated incrementally above
        # Only increment turn_idx when completing a full pair (debunker turn)
        if current_phase == "debunker":  # Just completed a full turn
            ss["turn_idx"] += 1
    else:
        # ===================================================================
        # PAIR MODE - Update structured turns and counters (original logic)
        # ===================================================================
        if "turns" not in ss:
            ss["turns"] = []

        ss["turns"].append({
            "turn_idx": turn_idx,
            "spreader_text": spreader_message,
            "debunker_text": debunker_message
        })

        # ===================================================================
        # UPDATE COUNTERS
        # ===================================================================
        ss["turn_idx"] += 1
        ss["completed_turn_pairs"] = min(
            ss.get("spreader_msgs_count", 0) + 1,
            ss.get("debunker_msgs_count", 0) + 1
        )
        ss["spreader_msgs_count"] = ss.get("spreader_msgs_count", 0) + 1
        ss["debunker_msgs_count"] = ss.get("debunker_msgs_count", 0) + 1
        ss["current_turn_idx"] = ss["completed_turn_pairs"]

    # ===================================================================
    # CHECK COMPLETION CONDITIONS
    # ===================================================================
    max_turns = ss.get("max_turns", 5)

    # TURN_STATE: Track completion check
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg("TURN_STATE", completed_turn_pairs=ss.get('completed_turn_pairs', 0),
                     max_turns=max_turns,
                     match_in_progress=ss.get('match_in_progress', False),
                     will_complete=(ss.get('completed_turn_pairs', 0) >= max_turns))
        except ImportError:
            pass
    else:
        # Fallback to existing logging (gated by DEBUG_DIAG for production experimentation)
        if DEBUG_DIAG:
            print(f"TRACE execute_next_turn CHECK_COMPLETION: pairs={ss.get('completed_turn_pairs', 0)} >= max={max_turns} ? {ss.get('completed_turn_pairs', 0) >= max_turns}")

    # CHECK_COMPLETION_POST_APPEND immediately before completion logic
    if hasattr(ss, 'arena_dbg'):
        try:
            from app import arena_dbg
            arena_dbg(
                "CHECK_COMPLETION_POST_APPEND",
                phase=ss.get('debate_phase'),
                pairs=ss.get("completed_turn_pairs", 0),
                max_turns=max_turns,
                debate_messages_len=len(debate_messages),
                transcript_len=len(episode_transcript),
            )
        except ImportError:
            pass

    # Check for completion after phase advancement (ensures final debunker generates)
    if ss.get("completed_turn_pairs", 0) >= max_turns:
        ss["match_in_progress"] = False
        if hasattr(ss, 'arena_dbg'):
            try:
                from app import arena_dbg
                arena_dbg(
                    "COMPLETION_TRIGGERED",
                    pairs=ss["completed_turn_pairs"],
                    max_turns=max_turns,
                )
            except ImportError:
                pass
        elif DEBUG_DIAG:
            print(f"TRACE execute_next_turn COMPLETING: setting match_in_progress=False")
        ss["early_stop_reason"] = f"Reached maximum turn pairs ({max_turns})"
        ss["stop_reason"] = "max_turns"
        _persist_completed_match(ss)
        st.success(f"✅ Debate completed: Reached maximum turns ({max_turns})")
        result.completion_reason = "Max turns reached"
        result.match_completed = True
        result.early_stop_reason = ss["early_stop_reason"]
        result.debug["persisted"] = True
        result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
        return result.to_dict()

    if single_message_mode:
        # ===================================================================
        # SINGLE MESSAGE MODE - Check concession on the message just generated
        # ===================================================================
        just_generated_message = message_content
        speaker_who_spoke = speaker_name

        # Check if the message just generated contains a concession
        conceded = is_concession(just_generated_message)

        if conceded:
            # Set up concession data
            ss["concession_data"] = {
                "early_stop_reason": "concession_keyword",
                "conceded_by": speaker_who_spoke,
                "concession_method": "keyword",
                "concession_turn": turn_idx,
                "concession_strength": 1.0,
                "concession_reason": f"Keyword concession detected: '{just_generated_message[:50]}...'"
            }

            ss["match_in_progress"] = False
            ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
            ss["stop_reason"] = "concession_keyword"

            _persist_completed_match(ss)

            st.success(f"🎉 **{speaker_who_spoke.title()} conceded!** Debate completed via keyword concession.")

            result.completion_reason = "Keyword concession"
            result.match_completed = True
            result.early_stop_reason = ss["early_stop_reason"]
            if speaker_who_spoke == "spreader":
                result.spreader_conceded = True
            else:
                result.debunker_conceded = True
            result.debug["persisted"] = True
            result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
            return result.to_dict()
    else:
        # ===================================================================
        # PAIR MODE - Check concessions on both messages (original logic)
        # ===================================================================
        # Check for keyword concessions
        spreader_conceded = is_concession(spreader_message)
        debunker_conceded = is_concession(debunker_message)

        # Add concession results to result
        result.spreader_conceded = spreader_conceded
        result.debunker_conceded = debunker_conceded

        if spreader_conceded or debunker_conceded:
            # Set up concession data
            conceder = "spreader" if spreader_conceded else "debunker"
            concession_text = spreader_message if spreader_conceded else debunker_message

            ss["concession_data"] = {
                "early_stop_reason": "concession_keyword",
                "conceded_by": conceder,
                "concession_method": "keyword",
                "concession_turn": turn_idx,
                "concession_strength": 1.0,
                "concession_reason": f"Keyword concession detected: '{concession_text[:50]}...'"
            }

            ss["match_in_progress"] = False
            ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
            ss["stop_reason"] = "concession_keyword"

            _persist_completed_match(ss)

            st.success(f"🎉 **{conceder.title()} conceded!** Debate completed via keyword concession.")

            result.completion_reason = "Keyword concession"
            result.match_completed = True
            result.early_stop_reason = ss["early_stop_reason"]
            result.debug["persisted"] = True
            result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
            return result.to_dict()

    # Check for model-based concessions (evidence-driven)
    if len(ss.get("turns", [])) >= 2:  # Need at least 1 full exchange for meaningful evaluation
        try:
            raw_for_concession = ss.get("episode_transcript") or ss.get("debate_messages") or []
            paired_for_concession = to_paired_turns_for_judge(raw_for_concession)
            config = DebateConfig(max_turns=max_turns, topic=topic)
            result.judge_ran = True
            model_concession = should_concede(
                ss["judge"],
                paired_for_concession,
                config,
                ss["concession_state"]
            )

            if model_concession and model_concession["recommend"]:
                conceder = model_concession["conceder"]
                ss["concession_data"] = {
                    "early_stop_reason": "concession_model",
                    "conceded_by": conceder,
                    "concession_method": "model",
                    "concession_turn": turn_idx,
                    "concession_strength": model_concession["strength"],
                    "concession_reason": model_concession["reason"]
                }

                ss["match_in_progress"] = False
                ss["early_stop_reason"] = ss["concession_data"]["early_stop_reason"]
                ss["stop_reason"] = "concession_model"

                _persist_completed_match(ss)

                st.success(f"🎯 **{conceder.title()} conceded!** Debate completed via evidence-driven concession.")

                result.completion_reason = "Model concession"
                result.match_completed = True
                result.judge_ran = True
                result.early_stop_reason = ss["early_stop_reason"]
                result.debug["persisted"] = True
                result.debug["persisted_path"] = str(DEFAULT_MATCHES_PATH)
                return result.to_dict()

        except Exception as e:
            if DEBUG_DIAG:
                print(f"CONCESSION_ERROR: {str(e)}")
            # Continue without model concession check

    # ===================================================================
    # CONTINUE DEBATE
    # ===================================================================
    st.success(f"✅ Turn {turn_idx + 1} completed. Ready for next turn.")

    return result.to_dict()
