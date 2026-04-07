"""
Automatic claim metadata inference for Misinfo Arena.

Two-tier classification:
1. Heuristic (regex/keyword) — fast, deterministic, zero cost
2. LLM fallback — used when heuristic returns "unknown" or confidence is low

Category names match the Arena UI dropdown exactly:
  Health / Vaccine, Political / Election, Institutional Conspiracy,
  Environmental, Economic, Hybrid
"""

from __future__ import annotations

import hashlib
import re

UNKNOWN = "unknown"

# ── Canonical categories (match UI dropdown) ──────────────────────────────
CLAIM_TYPE_CATEGORIES = [
    "Health / Vaccine",
    "Political / Election",
    "Institutional Conspiracy",
    "Environmental",
    "Economic",
    "Hybrid",
]

# ── Keyword → category mapping (lowercase keywords) ──────────────────────
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Health / Vaccine": [
        "vaccine", "vaccines", "vaccination", "covid", "virus", "pandemic",
        "infertility", "autism", "cancer", "disease", "medicine", "drug",
        "drugs", "doctor", "hospital", "pharma", "pharmaceutical", "injection",
        "side effect", "treatment", "cure", "flu", "health", "healthcare",
        "gmo", "genetically modified", "organic", "fluoride", "5g",
        "microchip", "dna", "mrna", "ivermectin", "hydroxychloroquine",
    ],
    "Political / Election": [
        "election", "elections", "vote", "votes", "ballot", "ballots",
        "fraud", "voter fraud", "rigged", "stolen", "recount",
        "president", "congress", "democrat", "republican", "immigration",
        "border", "deep state", "political", "politician",
    ],
    "Institutional Conspiracy": [
        "cover up", "cover-up", "coverup", "conspiracy", "they don't want",
        "secretly", "hoax", "false flag", "agenda", "plandemic",
        "big pharma", "elite", "establishment", "narrative", "suppressed",
        "suppression", "censored", "censorship", "hidden truth",
        "mainstream media", "controlled", "puppet", "new world order",
    ],
    "Environmental": [
        "climate", "climate change", "global warming", "warming", "pollution",
        "emissions", "carbon", "greenhouse", "extinction", "ecosystem",
        "renewable", "fossil fuel", "deforestation", "sea level",
        "environment", "environmental", "chemtrail",
    ],
    "Economic": [
        "inflation", "jobs", "job", "taxes", "tax", "unemployment",
        "recession", "economy", "economies", "wages", "wage",
        "market", "markets", "wealth", "poverty", "trade",
        "tariff", "debt", "deficit", "universal basic income",
        "automation", "replace", "replacing", "eliminate",
    ],
}

# Structural pattern keywords
_CAUSAL_PATTERNS = ["causes", "cause", "leads to", "results in", "makes", "creates", "because of", "due to"]
_PREDICTIVE_PATTERNS = ["will", "going to", "is about to", "soon"]
_DEFINITIONAL_PATTERNS = ["means", "defined as"]
_CONSPIRATORIAL_PATTERNS = [
    "cover up", "cover-up", "coverup", "they don't want you to know", "they don't want",
    "secretly", "hoax", "false flag", "agenda", "plandemic", "big pharma",
    "elite", "establishment", "narrative", "mainstream", "suppressed",
]


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


def _match_claim_type(text: str) -> tuple[str, float]:
    """
    Infer claim_type from keywords. Returns (category, confidence).
    Confidence: 1.0 = strong match, 0.5 = weak, 0.0 = unknown.
    """
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            scores[category] = count

    if not scores:
        return UNKNOWN, 0.0

    best = max(scores, key=scores.get)
    best_count = scores[best]

    # Check for hybrid (multiple categories with significant matches)
    significant = {k: v for k, v in scores.items() if v >= 2}
    if len(significant) >= 2:
        return "Hybrid", 0.7

    confidence = min(1.0, best_count / 3.0)  # 3+ keyword hits = full confidence
    return best, confidence


def classify_claim_llm(claim: str) -> str | None:
    """
    Classify a claim using a lightweight LLM call.
    Returns one of CLAIM_TYPE_CATEGORIES or None on failure.
    Used as fallback when heuristic returns unknown or low confidence.
    """
    try:
        from arena.utils.api_keys import get_openai_api_key
        api_key = get_openai_api_key()
        if not api_key:
            return None

        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        categories_str = ", ".join(CLAIM_TYPE_CATEGORIES)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    f"Classify the following misinformation claim into exactly one category: {categories_str}. "
                    "Respond with ONLY the category name, nothing else."
                )},
                {"role": "user", "content": claim},
            ],
            temperature=0.0,
            max_tokens=20,
        )
        result = response.choices[0].message.content.strip()
        # Validate it's one of our categories
        for cat in CLAIM_TYPE_CATEGORIES:
            if cat.lower() in result.lower():
                return cat
        return None
    except Exception:
        return None


def classify_claim(claim: str, use_llm_fallback: bool = True) -> tuple[str, str]:
    """
    Classify a claim into a canonical category.

    Returns (category, source) where source is "heuristic" or "llm".
    Falls back to LLM if heuristic is uncertain and use_llm_fallback is True.
    """
    norm = normalize_claim_text(claim)
    if not norm:
        return UNKNOWN, "none"

    category, confidence = _match_claim_type(norm)

    if category != UNKNOWN and confidence >= 0.5:
        return category, "heuristic"

    if use_llm_fallback:
        llm_result = classify_claim_llm(claim)
        if llm_result:
            return llm_result, "llm"

    return category if category != UNKNOWN else UNKNOWN, "heuristic"


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

        # claim_structure
        structure = _match_structure(norm)
        out["claim_structure"] = structure

        # claim_type (uses new canonical categories)
        ctype, _conf = _match_claim_type(norm)
        out["claim_type"] = ctype

        # claim_verifiability (depends on structure)
        out["claim_verifiability"] = _infer_verifiability(norm, structure)

        # claim_complexity
        out["claim_complexity"] = _infer_complexity(norm, structure)

        # claim_label_source
        out["claim_label_source"] = "heuristic"

        return out
    except Exception:
        return {}
