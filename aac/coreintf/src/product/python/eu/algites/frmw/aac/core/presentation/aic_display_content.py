from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .ain_display_content_format import AInDisplayContentFormat

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
