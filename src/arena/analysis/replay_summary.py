# Replay Summary: on-demand summary generation for Episode Replay tab (Phase 1).
# Uses InsightsAgent; caches in st.session_state. Does not persist.

from __future__ import annotations

import streamlit as st


def get_replay_summary(run_id: str, episode: dict) -> dict | None:
    """
    Return a generated summary for the episode, or None if unavailable.
    Uses session_state cache keyed by (run_id, episode_id). Never raises.
    """
    claim = episode.get("claim")
    transcript = episode.get("turns")
    verdict = episode.get("results")

    if claim is None or transcript is None or verdict is None:
        return None

    cache_name = "replay_summary_cache"
    if cache_name not in st.session_state:
        st.session_state[cache_name] = {}

    key = (run_id, episode.get("episode_id"))
    if key in st.session_state[cache_name]:
        return st.session_state[cache_name][key]

    try:
        from arena.insights import get_insights_agent

        agent = get_insights_agent()
        insights = agent.generate_insights(
            claim=claim,
            transcript=transcript,
            judge_verdict=verdict,
        )
        if insights is None:
            return None

        result = {
            "tldr": insights.tldr,
            "full": insights.strategic_dynamics,
            "model": insights.model,
        }
        st.session_state[cache_name][key] = result
        return result
    except Exception:
        return None
