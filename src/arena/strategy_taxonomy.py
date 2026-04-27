"""
Strategy taxonomy for Strategy Analyst.

V2: Open-coding approach — analyst generates labels from observation rather
than selecting from a fixed list. This follows established qualitative
research methodology:

Methodology grounding:
- Grounded Theory (Glaser & Strauss, 1967; Corbin & Strauss, 2015):
  Inductive coding where categories emerge from data rather than being
  predetermined. The "open coding" phase identifies concepts directly
  from observed behavior.
- Qualitative Content Analysis (Krippendorff, 2018):
  Systematic coding of communicative content where categories can be
  developed inductively from the material.
- Computational Grounded Theory (Nelson, 2020, Sociological Methods & Research):
  Using computational tools (including LLMs) to assist with pattern
  discovery in large text corpora while maintaining interpretive rigor.
- LLM-assisted Qualitative Coding (Xiao et al., 2023; Tai et al., 2024):
  Recent studies showing LLMs can perform open coding tasks comparable
  to human coders when given appropriate instructions.

The v1 fixed taxonomy (FLICC, SemEval-2023, Cook et al.) is preserved
below as a REFERENCE for post-hoc comparison, but is no longer used to
constrain the analyst's output.

Post-experiment workflow:
1. Analyst generates free-form labels per episode and per turn
2. All unique labels are collected across the dataset
3. Similar labels are clustered into canonical groups (axial coding)
4. Groups are compared against v1 taxonomy to identify overlap and novelty
5. Statistical tests use the clustered groups, not raw labels
"""

from __future__ import annotations

STRATEGY_ANALYSIS_VERSION = "strategy_v3_open"
STRATEGY_TAXONOMY_VERSION = "v3_open_coding"

# ═══════════════════════════════════════════════════════════════════
# V1 REFERENCE TAXONOMY (preserved for post-hoc comparison)
# Not used to constrain analyst output in v2 experiments.
# ═══════════════════════════════════════════════════════════════════

# Spreader strategies (misinformation-promoting rhetorical tactics)
V1_SPREADER_STRATEGIES = [
    "appeal_to_conspiracy",       # FLICC: Conspiracy theories
    "false_certainty",            # FLICC: Impossible expectations
    "anecdotal_evidence",         # FLICC: Logical fallacy (anecdote)
    "cherry_picking",             # FLICC: Cherry picking
    "authority_misuse",           # FLICC: Fake experts
    "emotional_appeal",           # FLICC: Appeal to emotion
    "burden_shift",               # FLICC: Logical fallacy
    "repetition",                 # SemEval: Repetition
    "pseudo_scientific_framing",  # Extension of FLICC Fake experts
    "uncertainty_exploitation",   # FLICC: Impossible expectations
]

# Debunker strategies (fact-checking and correction tactics)
V1_DEBUNKER_STRATEGIES = [
    "evidence_citation",          # Cook et al. 2017
    "source_quality_emphasis",    # Lewandowsky 2020
    "logical_refutation",         # Cook et al. 2017
    "mechanism_explanation",      # Lewandowsky 2020
    "uncertainty_calibration",    # Cook et al. 2017
    "contradiction_exposure",     # Cook et al. 2017
    "alternative_explanation",    # Lewandowsky 2020
    "precision_correction",       # Cook et al. 2017
    "consensus_grounding",        # Cook et al. 2017
    "burden_reversal",            # Inoculation theory
]

# Legacy aliases for backward compatibility with v1 data
SPREADER_STRATEGIES = V1_SPREADER_STRATEGIES
DEBUNKER_STRATEGIES = V1_DEBUNKER_STRATEGIES
SPREADER_SET = frozenset(V1_SPREADER_STRATEGIES)
DEBUNKER_SET = frozenset(V1_DEBUNKER_STRATEGIES)


def get_spreader_strategy_labels() -> list[str]:
    """Return v1 spreader labels (used as reference, not constraint in v2)."""
    return list(V1_SPREADER_STRATEGIES)


def get_debunker_strategy_labels() -> list[str]:
    """Return v1 debunker labels (used as reference, not constraint in v2)."""
    return list(V1_DEBUNKER_STRATEGIES)


def get_v1_all_labels() -> set[str]:
    """Return all v1 taxonomy labels for post-hoc comparison."""
    return set(V1_SPREADER_STRATEGIES) | set(V1_DEBUNKER_STRATEGIES)


def is_valid_spreader_strategy(label: str) -> bool:
    """Check if label is in v1 spreader taxonomy."""
    return label in SPREADER_SET


def is_valid_debunker_strategy(label: str) -> bool:
    """Check if label is in v1 debunker taxonomy."""
    return label in DEBUNKER_SET


def is_v1_label(label: str) -> bool:
    """Check if a label matches any v1 taxonomy label."""
    return label in SPREADER_SET or label in DEBUNKER_SET
