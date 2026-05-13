"""
Shared definition + institution-info lookups for the Atlas, Replay,
and any other surface that renders strategy or citation labels.

Lives outside the page modules so both atlas_page.py and explore_page.py
can import without creating a circular dependency.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional


# ── Where the LLM-backfilled definitions cache lives ──────────────────────
# scripts/backfill_strategy_definitions.py writes here. Re-run that script
# whenever new open-coded labels appear in your runs.
_STRATEGY_DEFINITIONS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "strategy_definitions.json"
)


# ── Institution metadata used by every "what does this source mean?" view ──
_INSTITUTION_INFO: dict[str, str] = {
    # Government agencies — US
    "CDC":  "Centers for Disease Control and Prevention. U.S. federal public-health agency under the Department of Health and Human Services. Monitors disease outbreaks, conducts epidemiological research, and issues clinical and public-health guidance.",
    "FDA":  "Food and Drug Administration. U.S. regulator for the safety and efficacy of food, prescription and over-the-counter drugs, vaccines, blood products, and medical devices. Reviews clinical-trial data and grants marketing authorization.",
    "EPA":  "Environmental Protection Agency. U.S. federal regulator for air, water, and land pollution. Sets and enforces environmental standards and conducts environmental risk assessments.",
    "NASA": "National Aeronautics and Space Administration. U.S. civilian space agency. Conducts space exploration, satellite earth observation, and atmospheric and climate research.",
    "NIH":  "National Institutes of Health. U.S. federal medical-research agency. The world's largest public funder of biomedical research; conducts and funds studies across 27 institutes.",
    "USDA": "United States Department of Agriculture. U.S. federal agency overseeing food, agriculture, nutrition, and rural development. Sets food-safety standards and administers nutrition programs.",
    "NOAA": "National Oceanic and Atmospheric Administration. U.S. federal agency monitoring oceanic and atmospheric conditions, weather forecasting, and climate science.",
    "NSF":  "National Science Foundation. U.S. federal agency funding non-medical basic research and education across the sciences and engineering.",

    # International / UN
    "WHO":                       "World Health Organization. UN agency for international public health. Sets global health standards, coordinates pandemic responses, and publishes guidance on disease prevention and treatment.",
    "World Health Organization": "World Health Organization. UN agency for international public health. Sets global health standards, coordinates pandemic responses, and publishes guidance on disease prevention and treatment.",
    "IPCC":                      "Intergovernmental Panel on Climate Change. UN body that synthesizes the published peer-reviewed science of climate change. Publishes consensus assessment reports cited by policymakers worldwide.",
    "United Nations":            "United Nations. Intergovernmental organization with 193 member states. Coordinates international cooperation on security, human rights, development, and humanitarian issues.",

    # Universities — known for major research output
    "Harvard":     "Harvard University. Private Ivy League research university in Cambridge, Massachusetts. Among the world's most-cited academic institutions, with major research output across medicine, law, public health, and the sciences.",
    "Stanford":    "Stanford University. Private research university in California. Major output across engineering, computer science, and medicine; influential in technology and biomedical research.",
    "MIT":         "Massachusetts Institute of Technology. Private research university in Cambridge, Massachusetts. Specializes in science, engineering, and economics, with leading research in computer science and physics.",
    "Oxford":      "University of Oxford. Ancient research university in England, in continuous operation since at least 1096. Major output across the humanities, social sciences, medicine, and natural sciences.",
    "Yale":        "Yale University. Private Ivy League research university in Connecticut. Strong output in medicine, law, and the humanities.",
    "Cambridge":   "University of Cambridge. Ancient research university in England. Major output across mathematics, the sciences, and engineering.",

    # Peer-reviewed journals
    "Nature":  "Nature. Weekly peer-reviewed scientific journal covering all natural sciences. One of the world's most cited and most prestigious science publications.",
    "Science": "Science. Weekly peer-reviewed general-science journal published by the American Association for the Advancement of Science. Among the most cited science journals globally.",
    "Lancet":  "The Lancet. Weekly peer-reviewed general-medicine journal, founded 1823. Publishes original research, reviews, and editorials with influence on clinical practice and public-health policy.",
    "JAMA":    "Journal of the American Medical Association. Peer-reviewed medical journal published by the American Medical Association. One of the highest-impact clinical-medicine journals worldwide.",
    "BMJ":     "The BMJ (formerly British Medical Journal). Peer-reviewed general-medicine journal, founded 1840. Publishes clinical research, reviews, and commentary.",
    "NEJM":    "New England Journal of Medicine. Weekly peer-reviewed medical journal, founded 1812. Among the highest-impact and most-cited medical journals in the world.",
    "Cell":    "Cell. Peer-reviewed biomedical journal focusing on molecular and cellular biology. High-impact venue for foundational life-sciences research.",
    "PNAS":    "Proceedings of the National Academy of Sciences. Peer-reviewed multidisciplinary scientific journal of the U.S. National Academy of Sciences.",

    # Polling / research orgs
    "Pew Research": "Pew Research Center. Nonpartisan U.S. fact-tank publishing public-opinion surveys, demographic data, and social-science analysis. Methodology is publicly documented.",
    "Gallup":       "Gallup. American analytics and advisory firm best known for long-running public-opinion polling on politics, the economy, and well-being.",

    # News agencies
    "Reuters":           "Reuters. International news agency, founded 1851. Wire-service reporting on global business, politics, and current events; known for strict sourcing standards.",
    "AP News":           "Associated Press. Independent, non-profit cooperative news agency, founded 1846. One of the largest and oldest wire services in the world.",
    "Associated Press":  "Associated Press. Independent, non-profit cooperative news agency, founded 1846. One of the largest and oldest wire services in the world.",
    "BBC":               "British Broadcasting Corporation. UK national public broadcaster, founded 1922. Operates global news, radio, and television services funded by a licence fee.",
    "NPR":               "National Public Radio. Privately and publicly funded U.S. nonprofit media organization producing news and cultural programming via member stations.",

    # Financial / economic bodies
    "Federal Reserve":             "Federal Reserve. Central banking system of the United States, founded 1913. Sets U.S. monetary policy, supervises banks, and acts as lender of last resort.",
    "World Bank":                  "World Bank. International financial institution providing loans, credits, and grants to developing countries for capital projects. Headquartered in Washington, D.C.",
    "IMF":                         "International Monetary Fund. Intergovernmental financial institution working to stabilize the international monetary system, with 190 member countries.",
    "Congressional Budget Office": "Congressional Budget Office. Non-partisan U.S. federal agency that produces economic analyses and budgetary cost estimates of legislation for Congress.",

    # NGOs / human rights
    "Amnesty International": "Amnesty International. Global non-governmental organization focused on human rights. Researches and campaigns against rights abuses worldwide; publishes country reports.",
    "Human Rights Watch":    "Human Rights Watch. International non-governmental organization that conducts research and advocacy on human-rights issues, publishing country reports and policy recommendations.",

    # Medical research / databases
    "Cochrane": "Cochrane. International non-profit producing systematic reviews of healthcare interventions. Cochrane Reviews are considered a gold standard for synthesising clinical-trial evidence.",
    "PubMed":   "PubMed. Free public database of biomedical literature maintained by the U.S. National Library of Medicine. Indexes more than 30 million peer-reviewed citations.",
    "PLoS":     "Public Library of Science. Non-profit open-access scientific publisher producing peer-reviewed journals including PLoS One and PLoS Medicine.",

    # Medical institutes
    "Mayo Clinic":      "Mayo Clinic. American non-profit academic medical centre with major hospitals in Minnesota, Arizona, and Florida. Known for integrated patient care, research, and education.",
    "Cleveland Clinic": "Cleveland Clinic. American non-profit academic medical centre headquartered in Ohio. Major centre for cardiac care, organ transplantation, and biomedical research.",

    # Medical associations
    "AMA":   "American Medical Association. Largest U.S. professional association for physicians; publishes JAMA and influences medical policy and licensing.",
    "APA":   "American Psychological Association. Largest U.S. professional organization for psychologists; publishes the DSM-style style guide and dozens of psychology journals.",
    "AAP":   "American Academy of Pediatrics. U.S. professional association of paediatricians; publishes clinical guidance on child health.",
    "ACOG":  "American College of Obstetricians and Gynecologists. U.S. professional association issuing clinical guidance in obstetrics and gynaecology.",
    "AHA":   "American Heart Association. U.S. non-profit funding cardiovascular research and publishing professional guidelines on heart disease and stroke.",
    "ACS":   "American Chemical Society. Professional society of chemists; publishes a wide portfolio of chemistry journals.",

    # Other US agencies
    "FEMA": "Federal Emergency Management Agency. U.S. federal agency coordinating disaster preparedness and response.",
    "HHS":  "Department of Health and Human Services. U.S. federal department overseeing health-care, public-health, and social-service agencies, including CDC, FDA, and NIH.",
}


def get_institution_info(name: str) -> str:
    """Return the descriptive blurb for a named institution, or an empty
    string if we don't recognise it. Names are matched case-sensitively
    against the canonical spelling (e.g. 'WHO', 'CDC')."""
    if not name:
        return ""
    return _INSTITUTION_INFO.get(name, "")


@lru_cache(maxsize=1)
def _load_cached_strategy_definitions() -> dict:
    """Load the LLM-backfilled strategy-definitions JSON once per process."""
    if not _STRATEGY_DEFINITIONS_PATH.exists():
        return {}
    try:
        return json.loads(_STRATEGY_DEFINITIONS_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _normalize_label(raw: str) -> str:
    """Match the same normalization the analyst and backfill use."""
    return (raw or "").strip().lower().replace(" ", "_")


def get_cached_strategy_definition(raw_label: str) -> Optional[str]:
    """Return the cached LLM-backfilled definition for a strategy label,
    or None if there isn't one. Keyed by snake_case label."""
    if not raw_label:
        return None
    cache = _load_cached_strategy_definitions()
    entry = cache.get(_normalize_label(raw_label))
    if not entry:
        return None
    desc = entry.get("definition", "")
    return desc.strip() or None


def resolve_strategy_description(
    raw_label: str,
    primary_lookup: Optional[dict] = None,
    episode_definitions: Optional[dict] = None,
) -> str:
    """Centralised resolution chain used by every surface that shows a
    strategy label.

    Order:
      1. ``primary_lookup`` — a hand-curated dict the caller cares about
         most (e.g. atlas_page._STRATEGY_CATALOG or explore_page._STRATEGY_CONTEXT).
         Both keys (lowercased-with-spaces and snake_case) are tried.
      2. ``episode_definitions`` — a per-episode label→definition map
         emitted by the strategy analyst, passed in by the caller.
      3. The LLM-backfilled cache (``strategy_definitions.json``).
      4. Empty string.
    """
    if not raw_label:
        return ""

    key_spaces = (raw_label or "").lower().replace("_", " ").strip()
    key_snake  = _normalize_label(raw_label)

    # 1) hand-curated primary lookup — accept either keying convention
    if primary_lookup:
        for k in (key_spaces, key_snake):
            v = primary_lookup.get(k)
            if isinstance(v, tuple):  # atlas-style (plain, desc, side)
                if len(v) > 1 and v[1]:
                    return str(v[1])
            elif isinstance(v, str) and v.strip():
                return v.strip()

    # 2) per-episode definitions (the analyst emits these inline now)
    if episode_definitions:
        v = episode_definitions.get(key_snake) or episode_definitions.get(key_spaces)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 3) LLM-backfilled cache
    cached = get_cached_strategy_definition(key_snake)
    if cached:
        return cached

    # 4) nothing — caller decides how to handle
    return ""
