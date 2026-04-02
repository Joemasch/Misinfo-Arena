"""
JSON serialization utilities for Arena.

Provides safe conversion of complex objects to JSON-serializable equivalents.
"""

from __future__ import annotations
from dataclasses import is_dataclass, asdict
from typing import Any
import json


def to_jsonable(obj: Any) -> Any:
    """
    Convert any object to a JSON-serializable equivalent.

    Handles:
    - Primitives (str, int, float, bool, None)
    - Lists and tuples (recursively processes elements)
    - Dicts (recursively processes values, converts keys to strings)
    - Dataclasses (converts to dict via asdict())
    - Pydantic models (v1 and v2)
    - Named tuples
    - Other objects (tries JSON serialization, falls back to string representation)

    Args:
        obj: Any object to make JSON-serializable

    Returns:
        JSON-serializable equivalent
    """
    # Fast path for primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Lists/tuples
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]

    # Dicts
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    # Dataclasses
    if is_dataclass(obj):
        return to_jsonable(asdict(obj))

    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return to_jsonable(obj.model_dump())
        except Exception:
            pass

    # Pydantic v1 or other dict() methods
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return to_jsonable(obj.dict())
        except Exception:
            pass

    # Namedtuple-like
    if hasattr(obj, "_asdict") and callable(getattr(obj, "_asdict")):
        try:
            return to_jsonable(obj._asdict())
        except Exception:
            pass

    # Fallback: try JSON serialization, else convert to string
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

