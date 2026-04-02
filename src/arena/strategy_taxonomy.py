"""
Strategy taxonomy for Strategy Analyst.

Canonical labels for spreader and debunker rhetorical strategies.
Used to constrain LLM output and enable leaderboard aggregation.

Literature grounding:
- FLICC taxonomy (Cook & Lewandowsky, 2020): Fake experts, Logical
  fallacies, Impossible expectations, Cherry picking, Conspiracy theories
- SemEval-2023 Task 3 (Piskorski et al., 2023): 23 persuasion techniques
  for propaganda detection in online news
- Cook et al. (2017) "Neutralizing misinformation through inoculation" (PLOS ONE)
- Lewandowsky et al. (2020) "The Debunking Handbook 2020"

Each label below includes its literature source in the comment.
"""

from __future__ import annotations

STRATEGY_ANALYSIS_VERSION = "strategy_v2"
STRATEGY_TAXONOMY_VERSION = "v2"

# Spreader strategies (misinformation-promoting rhetorical tactics)
SPREADER_STRATEGIES = [
    "appeal_to_conspiracy",       # FLICC: Conspiracy theories; SemEval: Conspiracy theory
    "false_certainty",            # FLICC: Impossible expectations (partial); SemEval: Loaded language
    "anecdotal_evidence",         # FLICC: Logical fallacy (anecdote); SemEval: Anecdote
    "cherry_picking",             # FLICC: Cherry picking; SemEval: Cherry picking data
    "authority_misuse",           # FLICC: Fake experts; SemEval: Appeal to authority
    "emotional_appeal",           # FLICC: Logical fallacy (appeal to emotion); SemEval: Appeal to emotion
    "burden_shift",               # FLICC: Logical fallacy; SemEval: Doubt / Questioning
    "repetition",                 # SemEval: Repetition
    "pseudo_scientific_framing",  # Extension of FLICC Fake experts — scientific-sounding claims without rigor
    "uncertainty_exploitation",   # FLICC: Impossible expectations — exploiting genuine uncertainty to cast doubt
]

# Debunker strategies (fact-checking and correction tactics)
DEBUNKER_STRATEGIES = [
    "evidence_citation",          # Cook et al. 2017: providing specific verifiable evidence
    "source_quality_emphasis",    # Lewandowsky 2020: highlighting source credibility
    "logical_refutation",         # Cook et al. 2017: identifying logical fallacies
    "mechanism_explanation",      # Lewandowsky 2020: explaining the causal mechanism
    "uncertainty_calibration",    # Cook et al. 2017: honest uncertainty communication
    "contradiction_exposure",     # Cook et al. 2017: exposing internal contradictions
    "alternative_explanation",    # Lewandowsky 2020: providing alternative narrative (truth sandwich)
    "precision_correction",       # Cook et al. 2017: correcting specific false claims with specific facts
    "consensus_grounding",        # Cook et al. 2017: referencing scientific consensus
    "burden_reversal",            # Inoculation theory: shifting burden of proof back to the claimant
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
