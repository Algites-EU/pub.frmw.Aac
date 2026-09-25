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
