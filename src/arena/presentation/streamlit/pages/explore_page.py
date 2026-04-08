"""
Explore Page for Misinformation Arena v2.

Merges the former Analytics and Claims tabs into a single exploratory
analytics hub with 6 sub-tabs: Overview & Scoring, Models, Strategy,
Claims, Citations, and Patterns.
"""

import streamlit as st

from arena.presentation.streamlit.pages.analytics_page import render_analytics_page
from arena.presentation.streamlit.pages.claim_analysis_page import render_claim_analysis_page


def render_explore_page():
    """Render the Explore tab — aggregate analytics across all runs.

    Currently delegates directly to the existing analytics page, which
    already contains Performance, Models, Strategy, Citations, Concessions,
    and Anomalies sub-tabs.  The Claims tab is rendered alongside via the
    top-level tab bar in app.py (now merged into Explore).

    As the Study Results page matures, study-specific analyses will migrate
    there and this page will remain the aggregate exploratory view.
    """
    # The analytics page already has its own sub-tabs and full data loading.
    # Rather than duplicating or splitting its internals, we render it as-is.
    # This is intentional: the analytics page works well, it just needed
    # to be in the right place in the tab hierarchy.
    render_analytics_page()
