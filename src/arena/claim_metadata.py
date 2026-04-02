"""
Automatic claim metadata inference for Misinfo Arena.

Heuristic-based, deterministic inference from claim text.
Used at episode persistence to populate claim metadata for Claim Analysis.
"""

from __future__ import annotations

import hashlib
import re

UNKNOWN = "unknown"

# Domain keyword buckets (lowercase)
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "health": [
        "vaccine", "vaccines", "covid", "virus", "infertility", "autism", "cancer",
        "disease", "medicine", "drug", "drugs", "doctor", "doctors", "hospital",
        "pharma", "injection", "side effect", "treatment", "cure", "flu",
        "organic", "gmo", "genetically modified", "additive", "chemical",
    ],
    "politics": [
        "election", "elections", "vote", "votes", "ballot", "ballots", "fraud",
        "government", "president", "congress", "democrat", "republican",
        "stolen", "rigged", "voter", "recount",
    ],
    "science": [
        "evolution", "physics", "chemistry", "biology", "experiment",
        "study", "studies", "research", "scientific", "scientists",
        "peer review", "consensus",
    ],
    "environment": [
        "climate", "warming", "pollution", "emissions", "environment",
        "renewable", "carbon", "greenhouse", "extinction", "ecosystem",
    ],
    "economics": [
        "inflation", "jobs", "taxes", "unemployment", "recession",
        "economy", "economies", "wages", "market", "markets", "wealth",
    ],
    "technology": [
        "ai", "algorithm", "social media", "platform", "internet",
        "5g", "microchip", "microchips", "surveillance", "tracking",
    ],
    "society": [
        "conspiracy", "cover up", "hoax", "agenda", "culture",
        "media", "mainstream", "elite", "establishment",
    ],
}

# Structural pattern keywords
_CAUSAL_PATTERNS = ["causes", "cause", "leads to", "results in", "makes", "creates", "because of", "due to"]
_PREDICTIVE_PATTERNS = ["will", "going to", "is about to", "soon"]
_DEFINITIONAL_PATTERNS = ["means", "defined as"]
_CONSPIRATORIAL_PATTERNS = [
    "cover up", "cover-up", "coverup", "they don't want you to know", "they don't want",
    "secretly", "hoax", "false flag", "agenda", "plandemic", "big pharma",
    "elite", "establishment", "narrative", "mainstream",
]

# claim_type mapping (overlap with domain but emphasizes style)
_CLAIM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "scientific_medical": [
        "vaccine", "covid", "virus", "cancer", "disease", "medicine", "drug",
        "autism", "infertility", "study", "research", "scientific",
    ],
    "political": [
        "election", "vote", "fraud", "government", "president", "stolen",
    ],
    "conspiracy": [
        "cover up", "hoax", "false flag", "agenda", "plandemic", "elite",
        "establishment", "secret", "they don't want",
    ],
    "economic": [
        "inflation", "jobs", "taxes", "economy", "recession", "wages",
    ],
    "technological": [
        "ai", "algorithm", "5g", "microchip", "surveillance", "social media",
    ],
    "environmental": [
        "climate", "warming", "pollution", "emissions", "environment",
    ],
    "social": [
        "culture", "media", "society",
    ],
}


def normalize_claim_text(claim: str) -> str:
    """
    Normalize claim text for deterministic processing.

    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse repeated whitespace
    - Preserve substance of the claim
    """
    try:
        if claim is None:
            return ""
        s = str(claim).strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s.strip()
    except Exception:
        return ""


def build_claim_id(claim: str) -> str:
    """
    Generate a deterministic hash-based ID from normalized claim text.

    Same normalized claim always produces the same claim_id.
    Format: clm_<12 hex chars>
    """
    try:
        norm = normalize_claim_text(claim)
        if not norm:
            return ""
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
        return f"clm_{h}"
    except Exception:
        return ""


def _match_domain(text: str) -> str:
    """Infer claim_domain from keywords. Prefer specific matches."""
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return domain
    return UNKNOWN


def _match_structure(text: str) -> str:
    """Infer claim_structure. Prefer: conspiratorial > causal > predictive > correlational > definitional."""
    for kw in _CONSPIRATORIAL_PATTERNS:
        if kw in text:
            return "conspiratorial"
    for kw in _CAUSAL_PATTERNS:
        if kw in text:
            return "causal"
    for kw in _PREDICTIVE_PATTERNS:
        if kw in text:
            return "predictive"
    for kw in _DEFINITIONAL_PATTERNS:
        if kw in text:
            return "definitional"
    return UNKNOWN


def _match_claim_type(text: str) -> str:
    """Infer claim_type from keywords."""
    for ctype, keywords in _CLAIM_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return ctype
    return UNKNOWN


def _infer_verifiability(text: str, structure: str) -> str:
    """Infer claim_verifiability from structure and content."""
    if structure == "conspiratorial":
        return "difficult_to_verify"
    if structure in ("causal", "predictive"):
        return "partially_checkable"
    if structure == "definitional" or (len(text.split()) < 15 and " " in text):
        return "directly_checkable"
    return UNKNOWN


def _infer_complexity(text: str, structure: str) -> str:
    """Infer claim_complexity from word count and structure."""
    words = text.split()
    n = len(words)
    has_conspiracy = structure == "conspiratorial"
    multiple_clauses = text.count(",") + text.count(";") + text.count(" and ") >= 2

    if has_conspiracy or multiple_clauses or n > 20:
        return "complex"
    if n > 10 or structure in ("causal", "predictive"):
        return "moderate"
    if n <= 10 and structure != UNKNOWN:
        return "simple"
    if n <= 6:
        return "simple"
    return "moderate"


def infer_claim_metadata_from_text(claim: str) -> dict[str, str]:
    """
    Infer claim metadata from raw claim text.

    Pure, deterministic, never raises. Returns empty dict if claim is blank.
    Uses conservative heuristics; prefers "unknown" when uncertain.
    """
    try:
        norm = normalize_claim_text(claim)
        if not norm:
            return {}

        out: dict[str, str] = {}

        # claim_id - deterministic
        cid = build_claim_id(claim)
        if cid:
            out["claim_id"] = cid

        # claim_domain
        out["claim_domain"] = _match_domain(norm)

        # claim_structure
        structure = _match_structure(norm)
        out["claim_structure"] = structure

        # claim_type
        out["claim_type"] = _match_claim_type(norm)

        # claim_verifiability (depends on structure)
        out["claim_verifiability"] = _infer_verifiability(norm, structure)

        # claim_complexity
        out["claim_complexity"] = _infer_complexity(norm, structure)

        # claim_label_source
        out["claim_label_source"] = "heuristic"

        return out
    except Exception:
        return {}
