"""
Citation extraction and credibility scoring from debate transcripts.

No LLM calls — purely regex and domain-based heuristics.
Identifies what each side cited, classifies the source type,
and assigns a credibility tier.

Credibility tiers
-----------------
  high         Named credible institution, government agency, or peer-reviewed journal.
  moderate     Named but less authoritative: major news organisations, .edu domains.
  questionable Vague attribution ("experts say", "studies show") or unsourced statistics.
  uncreditable No source attached to a specific factual claim, or known-bad framing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Full URLs
_URL_RE = re.compile(
    r"https?://[^\s<>\"'{}|\\^`\[\]]+|www\.[^\s<>\"'{}|\\^`\[\]]+",
    re.IGNORECASE,
)

# Named institutions / journals / agencies (must appear as a standalone proper noun)
_INSTITUTION_RE = re.compile(
    r"\b("
    r"CDC|WHO|NIH|FDA|USDA|EPA|NASA|NOAA|FEMA|HHS|NSF|"
    r"AMA|APA|ACS|AHA|AAP|ACOG|"
    r"Nature|Science|JAMA|Lancet|NEJM|BMJ|Cell|PNAS|"
    r"Harvard|Stanford|Oxford|Cambridge|MIT|Yale|Princeton|"
    r"Columbia|Duke|Johns Hopkins|Mayo Clinic|Cleveland Clinic|"
    r"Reuters|Associated Press|AP News|BBC|NPR|"
    r"Cochrane|PubMed|PLoS|"
    r"[A-Z][A-Za-z]+ University|[A-Z][A-Za-z]+ Institute|"
    r"[A-Z][A-Za-z]+ Foundation|[A-Z][A-Za-z]+ College"
    r")\b",
)

# "According to X" patterns
_ACCORDING_TO_RE = re.compile(
    r"according to (?:the )?([A-Z][A-Za-z\s&/\-]{2,50}?)(?:[,.\n]| report| study| data| research)",
    re.IGNORECASE,
)

# Vague attribution
_VAGUE_RE = re.compile(
    r"\b("
    r"experts? (?:say|agree|confirm|warn)|"
    r"scientists? (?:say|agree|confirm|warn|have found)|"
    r"researchers? (?:say|found|show|have found|confirm)|"
    r"studies show|study shows?|research shows?|data shows?|"
    r"it[' ]?s(?:\s+well)? known|many experts?|some experts?|most experts?|"
    r"reports suggest|evidence suggests?"
    r")\b",
    re.IGNORECASE,
)

# Specific numeric claims (used as a heuristic; context checked at extraction time)
_UNSOURCED_STAT_RE = re.compile(
    r"\b\d[\d,.]*\s*%|\b\d[\d,.]*\s*(?:million|billion|thousand)\b",
)


# ---------------------------------------------------------------------------
# Credibility classification
# ---------------------------------------------------------------------------

# Domain-level credibility for extracted URLs
_HIGH_CRED_DOMAINS = frozenset({
    ".gov", ".edu", "who.int", "cdc.gov", "nih.gov", "fda.gov",
    "pubmed.ncbi.nlm.nih.gov", "cochrane.org", "nature.com",
    "science.org", "nejm.org", "thelancet.com", "jamanetwork.com",
    "bmj.com", "pnas.org", "reuters.com", "apnews.com", "bbc.com",
    "bbc.co.uk", "npr.org",
})

_MODERATE_CRED_DOMAINS = frozenset({
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "economist.com", "bloomberg.com", "wsj.com", "ft.com",
    "sciencedaily.com", "medscape.com", "webmd.com", "healthline.com",
})

_LOW_CRED_DOMAINS = frozenset({
    "infowars.com", "naturalnews.com", "zerohedge.com",
    "beforeitsnews.com", "thegatewaypundit.com", "breitbart.com",
    "theonion.com",  # satire misused as fact
})


def _domain_credibility(url: str) -> tuple[str, str]:
    """Return (tier, reason) for a URL."""
    url_lower = url.lower()
    for dom in _HIGH_CRED_DOMAINS:
        if dom in url_lower:
            return "high", f"Recognised credible domain ({dom})"
    for dom in _LOW_CRED_DOMAINS:
        if dom in url_lower:
            return "uncreditable", f"Known low-credibility domain ({dom})"
    for dom in _MODERATE_CRED_DOMAINS:
        if dom in url_lower:
            return "moderate", f"Established news/reference outlet ({dom})"
    return "questionable", "URL from unclassified domain — verify independently"


def _institution_credibility(name: str) -> tuple[str, str]:
    HIGH = {
        "cdc", "who", "nih", "fda", "usda", "epa", "nasa", "noaa", "nsf",
        "nature", "science", "jama", "lancet", "nejm", "bmj", "cell", "pnas",
        "cochrane", "pubmed",
        "harvard", "stanford", "oxford", "cambridge", "mit", "yale", "princeton",
        "columbia", "duke", "johns hopkins", "mayo clinic", "cleveland clinic",
        "reuters", "associated press", "ap news", "bbc", "npr",
    }
    name_l = name.strip().lower()
    if name_l in HIGH or any(h in name_l for h in HIGH):
        return "high", f"Recognised high-credibility institution"
    if "university" in name_l or "institute" in name_l or "college" in name_l:
        return "moderate", "Academic institution — credibility depends on research quality"
    if "foundation" in name_l:
        return "moderate", "Foundation — verify independence and funding"
    return "questionable", "Named source not in verified institution list"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractedCitation:
    raw_text:   str
    source_type: str   # "url" | "institution" | "according_to" | "vague" | "statistic"
    credibility: str   # "high" | "moderate" | "questionable" | "uncreditable"
    reason:     str
    turn_index: int
    side:       str    # "spreader" | "debunker"


CREDIBILITY_ORDER = {"high": 0, "moderate": 1, "questionable": 2, "uncreditable": 3}
CREDIBILITY_LABELS = {
    "high":          "High credibility",
    "moderate":      "Moderate credibility",
    "questionable":  "Questionable",
    "uncreditable":  "Uncreditable",
}
CREDIBILITY_COLORS = {
    "high":          ("rgba(22,163,74,0.12)",  "#15803d"),
    "moderate":      ("rgba(132,204,22,0.12)", "#4d7c0f"),
    "questionable":  ("rgba(234,179,8,0.12)",  "#a16207"),
    "uncreditable":  ("rgba(220,38,38,0.10)",  "#b91c1c"),
}


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------

def extract_citations(
    turn_pairs: list[dict[str, Any]],
) -> dict[str, list[ExtractedCitation]]:
    """
    Extract citations from a list of turn-pair dicts (pair_idx, spreader_text, debunker_text).

    Returns ``{"spreader": [...], "debunker": [...]}``.
    """
    result: dict[str, list[ExtractedCitation]] = {"spreader": [], "debunker": []}

    for pair in turn_pairs:
        turn_idx = pair.get("pair_idx", 0)
        for side, text_key in (("spreader", "spreader_text"), ("debunker", "debunker_text")):
            text = (pair.get(text_key) or "").strip()
            if not text:
                continue
            seen_raw: set[str] = set()

            def _add(raw: str, stype: str, cred: str, reason: str) -> None:
                raw = raw.strip()[:200]
                if raw and raw not in seen_raw:
                    seen_raw.add(raw)
                    result[side].append(ExtractedCitation(
                        raw_text=raw,
                        source_type=stype,
                        credibility=cred,
                        reason=reason,
                        turn_index=turn_idx,
                        side=side,
                    ))

            # 1. URLs
            for m in _URL_RE.finditer(text):
                url = m.group()
                cred, reason = _domain_credibility(url)
                _add(url, "url", cred, reason)

            # 2. Named institutions
            for m in _INSTITUTION_RE.finditer(text):
                name = m.group()
                cred, reason = _institution_credibility(name)
                _add(name, "institution", cred, reason)

            # 3. "According to X" patterns
            for m in _ACCORDING_TO_RE.finditer(text):
                raw  = m.group().strip().rstrip(".,")
                name = m.group(1).strip()
                cred, reason = _institution_credibility(name)
                _add(raw, "according_to", cred, reason)

            # 4. Vague attributions
            for m in _VAGUE_RE.finditer(text):
                _add(
                    m.group(),
                    "vague",
                    "questionable",
                    "Unattributed claim — no specific source named",
                )

    return result


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------

def citation_summary(citations: list[ExtractedCitation]) -> dict[str, Any]:
    """Return counts-by-credibility-tier and an overall credibility score (0–1)."""
    counts: dict[str, int] = {"high": 0, "moderate": 0, "questionable": 0, "uncreditable": 0}
    for c in citations:
        counts[c.credibility] = counts.get(c.credibility, 0) + 1

    total = sum(counts.values())
    if total == 0:
        score = None
    else:
        # Weighted: high=1.0, moderate=0.65, questionable=0.3, uncreditable=0.0
        score = (
            counts["high"]          * 1.00 +
            counts["moderate"]      * 0.65 +
            counts["questionable"]  * 0.30 +
            counts["uncreditable"]  * 0.00
        ) / total

    return {"counts": counts, "total": total, "credibility_score": score}
