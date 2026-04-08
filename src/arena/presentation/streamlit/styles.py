"""
Global CSS and Plotly theme for Misinformation Arena v2.

Single source of truth for design tokens. Every page imports GLOBAL_CSS
and injects it via st.markdown() before any page-specific styles.

Design brief: docs/design-brief.md
"""

# ---------------------------------------------------------------------------
# Color constants (Python-side, for Plotly traces / inline styles)
# ---------------------------------------------------------------------------
SPREADER_COLOR = "#D4A843"   # Amber — spreader agent identity
DEBUNKER_COLOR = "#4A7FA5"   # Steel blue — fact-checker identity
DRAW_COLOR     = "#888888"   # Grey — draw / other outcome
ACCENT_RED     = "#C9363E"   # Primary accent — urgency, headers, stats
ACCENT_GREEN   = "#4CAF7D"   # Positive outcomes

# ---------------------------------------------------------------------------
# Plotly dark-theme layout (apply to every fig.update_layout)
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0A0A0A",
    plot_bgcolor="#111111",
    font=dict(family="IBM Plex Sans, sans-serif", color="#E8E4D9", size=13),
    xaxis=dict(gridcolor="#2A2A2A", zerolinecolor="#2A2A2A"),
    yaxis=dict(gridcolor="#2A2A2A", zerolinecolor="#2A2A2A"),
    colorway=["#4A7FA5", "#C9363E", "#D4A843", "#4CAF7D"],
    margin=dict(l=40, r=24, t=40, b=40),
    legend=dict(font=dict(color="#E8E4D9")),
)

# ---------------------------------------------------------------------------
# Global CSS — injected on every page
# ---------------------------------------------------------------------------
GLOBAL_CSS = """
/* ══════════════════════════════════════════════════════════════════════════
   Misinformation Arena — Global Design System
   docs/design-brief.md is the canonical reference.
   ══════════════════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500;700&display=swap');

/* ── CSS Custom Properties ── */
:root {
  --color-bg:           #0A0A0A;
  --color-surface:      #111111;
  --color-surface-alt:  #1A1A1A;
  --color-border:       #2A2A2A;

  --color-text-primary: #E8E4D9;
  --color-text-muted:   #888888;
  --color-text-faint:   #444444;

  --color-accent-red:   #C9363E;
  --color-accent-amber: #D4A843;
  --color-accent-blue:  #4A7FA5;
  --color-accent-green: #4CAF7D;
}

/* ── Streamlit layout overrides ── */
.main .block-container {
  max-width: 1100px;
  padding: 2rem 3rem;
}
[data-testid="stHorizontalBlock"] { width: 100%; }

/* ── Dark page background ── */
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.main,
.stApp {
  background-color: var(--color-bg) !important;
  color: var(--color-text-primary) !important;
}

/* ── Tab bar styling ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: transparent;
  border-bottom: 1px solid var(--color-border);
  gap: 0;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  font-weight: 400;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 0.6rem 1.2rem;
  transition: color 0.15s, border-color 0.15s;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
  color: var(--color-text-primary);
  border-bottom: 2px solid var(--color-accent-red);
  font-weight: 500;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
  color: var(--color-text-primary);
}
/* Hide Streamlit's default tab highlight bar */
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
  display: none;
}
/* Tab panel background */
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  background: transparent;
}

/* ── Typography resets ── */
h1, .stMarkdown h1 {
  font-family: 'Playfair Display', Georgia, serif !important;
  font-size: 2.6rem !important;
  font-weight: 700 !important;
  color: var(--color-text-primary) !important;
  letter-spacing: -0.5px !important;
  line-height: 1.15 !important;
}
h2, .stMarkdown h2 {
  font-family: 'Playfair Display', Georgia, serif !important;
  font-size: 1.6rem !important;
  font-weight: 400 !important;
  color: var(--color-accent-red) !important;
  line-height: 1.3 !important;
}
h3, .stMarkdown h3 {
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 2px !important;
  color: var(--color-text-muted) !important;
}

/* Body text */
p, li, span, div, label,
[data-testid="stAppViewContainer"] {
  font-family: 'IBM Plex Sans', sans-serif;
}

/* ── Body paragraph measure — centered 680px column, left-aligned text ── */
.main .block-container [data-testid="stMarkdownContainer"] p {
  line-height: 1.75;
}

/* ── Streamlit widget dark overrides ── */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stSlider"] label,
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stNumberInput"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {
  color: var(--color-text-muted) !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background-color: var(--color-surface) !important;
  color: var(--color-text-primary) !important;
  border-color: var(--color-border) !important;
}

/* Expanders */
[data-testid="stExpander"] {
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border) !important;
  border-radius: 4px !important;
}
[data-testid="stExpander"] summary span {
  color: var(--color-text-primary) !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  color: var(--color-text-primary) !important;
}

/* DataFrames */
[data-testid="stDataFrame"],
.stDataFrame {
  border: 1px solid var(--color-border) !important;
  border-radius: 4px !important;
}

/* st.caption */
.stCaption, [data-testid="stCaptionContainer"] {
  color: var(--color-text-muted) !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
}

/* ── Button overrides ── */
.stButton > button {
  background-color: var(--color-accent-red) !important;
  color: #fff !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
  border: none !important;
  border-radius: 2px !important;
  padding: 0.5rem 1.2rem !important;
  transition: filter 0.15s !important;
}
.stButton > button:hover {
  filter: brightness(1.15) !important;
  border: none !important;
}
.stButton > button:active {
  filter: brightness(0.95) !important;
}
/* Download buttons — same but with surface bg */
.stDownloadButton > button {
  background-color: var(--color-surface) !important;
  color: var(--color-text-primary) !important;
  border: 1px solid var(--color-border) !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-weight: 500 !important;
  border-radius: 2px !important;
}
.stDownloadButton > button:hover {
  background-color: var(--color-surface-alt) !important;
}

/* ── Stat card component (reusable) ── */
.ds-stat-row {
  display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.2rem 0;
}
.ds-stat {
  flex: 1; min-width: 180px;
  background: var(--color-surface);
  border-left: 3px solid var(--color-accent-red);
  border-radius: 4px;
  padding: 1.2rem 1.4rem;
}
.ds-stat-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 2.4rem; font-weight: 700;
  color: var(--color-accent-red);
  line-height: 1; margin-bottom: 0.3rem;
}
.ds-stat-label {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem; color: var(--color-text-muted);
  text-transform: uppercase; letter-spacing: 1.5px;
  line-height: 1.5;
}

/* ── Callout / quote blocks ── */
.ds-callout {
  border-left: 3px solid var(--color-accent-blue);
  background: rgba(74, 127, 165, 0.08);
  border-radius: 0 4px 4px 0;
  padding: 0.85rem 1.1rem;
  font-size: 0.95rem;
  color: var(--color-text-primary);
  margin: 0.75rem 0;
}
.ds-callout-red {
  border-left-color: var(--color-accent-red);
  background: rgba(201, 54, 62, 0.08);
}
.ds-quote {
  border-left: 3px solid var(--color-accent-red);
  background: rgba(201, 54, 62, 0.06);
  border-radius: 0 4px 4px 0;
  padding: 1.2rem 1.5rem;
  margin: 1.5rem 0;
}
.ds-quote-text {
  font-family: 'Playfair Display', Georgia, serif;
  font-style: italic; font-size: 1.1rem;
  color: var(--color-text-primary);
  line-height: 1.65;
}
.ds-quote-attr {
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 300; font-size: 0.82rem;
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

/* ── Badge system ── */
.ds-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.82rem; font-weight: 600;
  font-family: 'IBM Plex Sans', sans-serif;
  margin-right: 0.35rem; margin-bottom: 0.25rem;
}
.ds-badge-spreader {
  border: 1px solid rgba(212, 168, 67, 0.5);
  color: #D4A843;
  background: rgba(212, 168, 67, 0.1);
}
.ds-badge-debunker {
  border: 1px solid rgba(74, 127, 165, 0.5);
  color: #4A7FA5;
  background: rgba(74, 127, 165, 0.1);
}
.ds-badge-draw {
  border: 1px solid rgba(212, 168, 67, 0.5);
  color: #D4A843;
  background: rgba(212, 168, 67, 0.1);
}
.ds-badge-confidence {
  border: 1px solid rgba(74, 127, 165, 0.4);
  color: #4A7FA5;
}
.ds-badge-trigger {
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

/* ── Section dividers ── */
.ds-divider {
  height: 1px;
  background: var(--color-border);
  margin: 2rem 0;
}

/* ── Streamlit alerts → dark-themed ── */
[data-testid="stAlert"] {
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border) !important;
  color: var(--color-text-primary) !important;
  border-radius: 4px !important;
}

/* ── Sidebar (kept visible for now — Arena uses it) ── */
section[data-testid="stSidebar"] {
  background-color: var(--color-surface) !important;
}
section[data-testid="stSidebar"] * {
  color: var(--color-text-primary);
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color: var(--color-text-primary);
}

/* ── Footer ── */
footer { visibility: hidden; }
"""


def inject_global_css():
    """Inject GLOBAL_CSS into the current Streamlit page.

    Call at the top of every render_*_page() function:
        from arena.presentation.streamlit.styles import inject_global_css
        inject_global_css()
    """
    import streamlit as _st
    _st.markdown(f"<style>{GLOBAL_CSS}</style>", unsafe_allow_html=True)
