"""
Tests for runs_refresh_token bump logic.
"""

import streamlit as st
import pytest

from arena.presentation.streamlit.state.runs_refresh import bump_runs_refresh_token


def test_bump_runs_refresh_token_increments():
    """bump_runs_refresh_token increments correctly."""
    st.session_state.clear()
    assert bump_runs_refresh_token() == 1
    assert bump_runs_refresh_token() == 2
    assert st.session_state["runs_refresh_token"] == 2


def test_bump_initializes_to_one_if_missing():
    """Token initializes (via get) and first bump returns 1."""
    st.session_state.clear()
    assert "runs_refresh_token" not in st.session_state
    result = bump_runs_refresh_token()
    assert result == 1
    assert st.session_state["runs_refresh_token"] == 1


def test_multiple_bumps_increment_sequentially():
    """Multiple bumps increment sequentially."""
    st.session_state.clear()
    for i in range(1, 6):
        assert bump_runs_refresh_token() == i
    assert st.session_state["runs_refresh_token"] == 5


def test_bump_with_reason_stores_reason():
    """Optional reason is stored in session_state."""
    st.session_state.clear()
    bump_runs_refresh_token(reason="episode_appended")
    assert st.session_state.get("runs_refresh_reason") == "episode_appended"


def test_bump_handles_non_numeric_token():
    """If token is non-numeric, treat as 0 and bump to 1."""
    st.session_state.clear()
    st.session_state["runs_refresh_token"] = "invalid"
    result = bump_runs_refresh_token()
    assert result == 1
