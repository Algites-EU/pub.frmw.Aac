from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class AIcDisplayText:
    """Technology-neutral user-visible short text metadata.

    `text` is the immediate/fallback rendering. `resource_key` is an opaque
    localization key for a future/product-provided localization engine.
    AAC Core does not resolve resource keys itself.
    """

    text: str | None = None
    resource_key: str | None = None

    def __post_init__(self) -> None:
        if self.text is not None and not self.text:
            raise ValueError("display text must not be empty")
        if self.resource_key is not None and not self.resource_key:
            raise ValueError("display resource_key must not be empty")
        if self.text is None and self.resource_key is None:
            raise ValueError("display text requires text and/or resource_key")

    @property
    def fallback(self) -> str:
        return self.text or self.resource_key or ""


class AInDisplayContentFormat(str, Enum):
    PLAIN_TEXT = "PLAIN_TEXT"
    MARKDOWN = "MARKDOWN"
    HTML = "HTML"


@dataclass(frozen=True, slots=True)
class AIcDisplayContent:
    """Technology-neutral multi-line or formatted display content.

    Renderers decide how MARKDOWN and HTML are presented. HTML is content, not
    executable UI; host policy is responsible for sanitization and active-content restrictions.
    """

    content: str | None = None
    resource_key: str | None = None
    format: AInDisplayContentFormat = AInDisplayContentFormat.PLAIN_TEXT

    def __post_init__(self) -> None:
        if self.content is not None and not self.content:
            raise ValueError("display content must not be empty")
        if self.resource_key is not None and not self.resource_key:
            raise ValueError("display content resource_key must not be empty")
        if self.content is None and self.resource_key is None:
            raise ValueError("display content requires content and/or resource_key")

    @property
    def fallback(self) -> str:
        return self.content or self.resource_key or ""


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
