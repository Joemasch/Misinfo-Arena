"""
Normalization utilities for Misinformation Arena v2.

Provides functions to normalize data structures and handle type conversions safely.
"""

import json
import math


def normalize_explanation(explanation):
    """
    Normalize explanation field to handle various input types safely.

    Converts explanation into either a dict or None, handling:
    - dict: returned as-is
    - pandas NaN (float): converted to None
    - None: returned as None
    - stringified JSON: parsed to dict if valid
    - other types: converted to None

    This prevents AttributeError when calling .get() on float/NaN values.
    """
    if explanation is None:
        return None
    if isinstance(explanation, float) and math.isnan(explanation):
        return None
    if isinstance(explanation, dict):
        return explanation
    if isinstance(explanation, str):
        s = explanation.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return None
    return None

