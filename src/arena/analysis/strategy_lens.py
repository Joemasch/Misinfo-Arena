"""
Deterministic strategy signal extraction from turn pairs (regex only).

Used by Run Replay Strategy Lens tab. No agents, no ML.
"""

import re
from typing import Any

MAX_SNIPPETS_PER_SIGNAL = 2
MAX_SNIPPET_LEN = 180

# Patterns (compiled once)
CITATION_LIKE = re.compile(
    r"\b(https?://|www\.|#|according to|study|studies|report|journal|CDC|WHO|NIH|FDA)\b",
    re.IGNORECASE,
)
NUMERIC_SPECIFICITY = re.compile(r"\d+%|\d+\s*(?:years?|percent|million|billion)|%\s*\d+")
CAUSAL_MARKERS = re.compile(
    r"\b(because|therefore|thus|implies?|leads?\s+to|result(s|ing)\s+in)\b",
    re.IGNORECASE,
)
COUNTERARGUMENT = re.compile(
    r"\b(however|although|though|some\s+argue|on\s+the\s+other\s+hand|that\s+said)\b",
    re.IGNORECASE,
)
RHETORICAL_QUESTIONS = re.compile(r"\?")
EMOTIONAL_FRAMING = re.compile(
    r"\b(fear|corrupt|agenda|dangerous|protect|protecting|threat|conspiracy|trust)\b",
    re.IGNORECASE,
)
CONSPIRACY_FRAMING = re.compile(
    r"\b(cover\s*up|hidden\s+truth|they\s+don\'?t\s+want\s+you\s+to\s+know|mainstream\s+media)\b",
    re.IGNORECASE,
)
VAGUE_SOURCES = re.compile(
    r"\b(experts\s+say|people\s+say|it\'?s\s+known|research\s+shows?|studies\s+show)\b",
    re.IGNORECASE,
)
REFUTATION_STRUCTURE = re.compile(
    r"\b(claim\s+is\s+false|evidence\s+shows|the\s+evidence|instead[,.]?|in\s+fact)\b",
    re.IGNORECASE,
)
UNCERTAINTY_CALIBRATION = re.compile(
    r"\b(likely|unlikely|uncertain|we\s+don\'?t\s+know|based\s+on\s+evidence)\b",
    re.IGNORECASE,
)

SIGNAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("citation_like", CITATION_LIKE),
    ("numeric_specificity", NUMERIC_SPECIFICITY),
    ("causal_markers", CAUSAL_MARKERS),
    ("counterargument", COUNTERARGUMENT),
    ("rhetorical_questions", RHETORICAL_QUESTIONS),
    ("emotional_framing", EMOTIONAL_FRAMING),
    ("conspiracy_framing", CONSPIRACY_FRAMING),
    ("vague_sources", VAGUE_SOURCES),
    ("refutation_structure", REFUTATION_STRUCTURE),
    ("uncertainty_calibration", UNCERTAINTY_CALIBRATION),
]


def _extract_snippet(text: str, match: re.Match[str]) -> str:
    start = max(0, match.start() - 40)
    end = min(len(text), match.end() + 140)
    snippet = text[start:end].strip()
    if len(snippet) > MAX_SNIPPET_LEN:
        snippet = snippet[: MAX_SNIPPET_LEN - 3] + "..."
    return snippet


def _count_and_sample(text: str, role: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for signal_name, pattern in SIGNAL_PATTERNS:
        if signal_name == "rhetorical_questions":
            matches = list(pattern.finditer(text))
        else:
            matches = list(pattern.finditer(text))
        count = len(matches)
        counts[signal_name] = count
        if count > 0:
            snippets: list[str] = []
            for m in matches[:MAX_SNIPPETS_PER_SIGNAL]:
                snip = _extract_snippet(text, m)
                if snip and snip not in snippets:
                    snippets.append(snip)
            if snippets:
                examples[signal_name] = snippets
    return counts, examples


def extract_strategy_signals(
    turn_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Extract deterministic strategy signals from turn pairs.

    turn_pairs: list of { pair_idx, spreader_text, debunker_text } (from normalize_turn_pairs).

    Returns:
      - spreader: { signal: count }
      - debunker: { signal: count }
      - examples: { spreader: { signal: [snippet, ...] }, debunker: { ... } }
    """
    spreader_counts: dict[str, int] = {}
    debunker_counts: dict[str, int] = {}
    spreader_examples: dict[str, list[str]] = {}
    debunker_examples: dict[str, list[str]] = {}

    for sig_name, _ in SIGNAL_PATTERNS:
        spreader_counts[sig_name] = 0
        debunker_counts[sig_name] = 0

    for pair in turn_pairs:
        s_text = (pair.get("spreader_text") or "").strip()
        d_text = (pair.get("debunker_text") or "").strip()
        sc, se = _count_and_sample(s_text, "spreader")
        dc, de = _count_and_sample(d_text, "debunker")
        for k, v in sc.items():
            spreader_counts[k] = spreader_counts.get(k, 0) + v
        for k, v in dc.items():
            debunker_counts[k] = debunker_counts.get(k, 0) + v
        for k, snippets in se.items():
            spreader_examples.setdefault(k, [])
            for sn in snippets:
                if sn not in spreader_examples[k] and len(spreader_examples[k]) < MAX_SNIPPETS_PER_SIGNAL:
                    spreader_examples[k].append(sn)
        for k, snippets in de.items():
            debunker_examples.setdefault(k, [])
            for sn in snippets:
                if sn not in debunker_examples[k] and len(debunker_examples[k]) < MAX_SNIPPETS_PER_SIGNAL:
                    debunker_examples[k].append(sn)

    return {
        "spreader": spreader_counts,
        "debunker": debunker_counts,
        "examples": {
            "spreader": spreader_examples,
            "debunker": debunker_examples,
        },
    }
