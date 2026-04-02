"""
Strategy taxonomy for Strategy Analyst (Phase 1).

Canonical labels for spreader and debunker rhetorical strategies.
Used to constrain LLM output and enable leaderboard aggregation.
"""

from __future__ import annotations

STRATEGY_ANALYSIS_VERSION = "strategy_v1"
STRATEGY_TAXONOMY_VERSION = "v1"

# Spreader strategies (misinformation-promoting rhetorical tactics)
SPREADER_STRATEGIES = [
    "appeal_to_conspiracy",
    "false_certainty",
    "anecdotal_evidence",
    "cherry_picking",
    "authority_misuse",
    "emotional_appeal",
    "burden_shift",
    "repetition",
    "pseudo_scientific_framing",
    "uncertainty_exploitation",
]

# Debunker strategies (fact-checking and correction tactics)
DEBUNKER_STRATEGIES = [
    "evidence_citation",
    "source_quality_emphasis",
    "logical_refutation",
    "mechanism_explanation",
    "uncertainty_calibration",
    "contradiction_exposure",
    "alternative_explanation",
    "precision_correction",
    "consensus_grounding",
    "burden_reversal",
]

SPREADER_SET = frozenset(SPREADER_STRATEGIES)
DEBUNKER_SET = frozenset(DEBUNKER_STRATEGIES)


def get_spreader_strategy_labels() -> list[str]:
    """Return canonical list of spreader strategy labels."""
    return list(SPREADER_STRATEGIES)


def get_debunker_strategy_labels() -> list[str]:
    """Return canonical list of debunker strategy labels."""
    return list(DEBUNKER_STRATEGIES)


def is_valid_spreader_strategy(label: str) -> bool:
    """Check if label is in spreader taxonomy."""
    return label in SPREADER_SET


def is_valid_debunker_strategy(label: str) -> bool:
    """Check if label is in debunker taxonomy."""
    return label in DEBUNKER_SET
