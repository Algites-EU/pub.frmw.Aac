from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AIcDisplayText:
    """Technology-neutral user-visible text metadata.

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


def normalize_display_text(value: object | None) -> AIcDisplayText | None:
    """Normalize a descriptor/contract display-text value.

    Accepted forms are a plain string or a mapping with `text` and/or
    `resource_key`. Kept as a function rather than an implicit parser so
    technology bindings can use the same model without a localization engine.
    """
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
