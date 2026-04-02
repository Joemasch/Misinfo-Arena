"""
Claim ingestion helpers for Multi-Claim Arena.

Parses claims from manual input or uploaded CSV/XLSX files.
"""

from __future__ import annotations

from typing import Tuple


def parse_claims_from_file(uploaded_file) -> Tuple[list[str], str | None]:
    """
    Parse claims from uploaded CSV or XLSX file.
    Requires column named 'claim' (case-insensitive).
    Returns (claims_list, error_message). error_message is None on success.
    """
    import io
    import pandas as pd

    if uploaded_file is None:
        return [], "No file uploaded"

    try:
        raw = uploaded_file.read()
    except Exception as e:
        return [], f"Could not read file: {e}"

    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw), encoding="utf-8")
        elif uploaded_file.name.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            return [], "File must be CSV or XLSX"
    except Exception as e:
        return [], f"Could not parse file: {e}"

    cols_lower = {c.strip().lower(): c for c in df.columns if isinstance(c, str)}
    if "claim" not in cols_lower:
        return [], f"File must have a 'claim' column. Found: {list(df.columns)}"

    claim_col = cols_lower["claim"]
    claims = df[claim_col].astype(str).str.strip()
    claims = [c for c in claims if c and c.lower() != "nan"]
    if not claims:
        return [], "No non-empty claims found in file"
    return claims, None
