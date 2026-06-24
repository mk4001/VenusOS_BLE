from __future__ import annotations

import re
from typing import Any


def clean_topic_part(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "device"


def flatten_payload(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        topic_key = clean_topic_part(key)
        full_key = f"{prefix}_{topic_key}" if prefix else topic_key
        if isinstance(value, dict):
            flattened.update(flatten_payload(value, full_key))
        elif isinstance(value, (str, int, float, bool)) or value is None:
            flattened[full_key] = value
    return flattened
