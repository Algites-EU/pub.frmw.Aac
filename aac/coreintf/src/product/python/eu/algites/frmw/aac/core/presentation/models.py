from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .aic_display_text import AIcDisplayText
from .ain_display_content_format import AInDisplayContentFormat
from .aic_display_content import AIcDisplayContent

def normalize_display_text(value: object | None) -> AIcDisplayText | None:
    """Normalize a descriptor/contract display-text value."""
    if value is None:
        return None
    if isinstance(value, AIcDisplayText):
        return value
    if isinstance(value, str):
        return AIcDisplayText(text=value)
    if isinstance(value, dict):
        return AIcDisplayText(
            text=str(value["text"]) if value.get("text") is not None else None,
            resource_key=str(value["resource_key"]) if value.get("resource_key") is not None else None,
        )
    raise TypeError("display text must be string, mapping, AIcDisplayText, or None")

def normalize_display_content(value: object | None) -> AIcDisplayContent | None:
    """Normalize display-content metadata without rendering it."""
    if value is None:
        return None
    if isinstance(value, AIcDisplayContent):
        return value
    if isinstance(value, str):
        return AIcDisplayContent(content=value)
    if isinstance(value, dict):
        return AIcDisplayContent(
            content=str(value["content"]) if value.get("content") is not None else None,
            resource_key=str(value["resource_key"]) if value.get("resource_key") is not None else None,
            format=AInDisplayContentFormat(str(value.get("format", "PLAIN_TEXT"))),
        )
    raise TypeError("display content must be string, mapping, AIcDisplayContent, or None")
