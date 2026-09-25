from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class AInDisplayContentFormat(str, Enum):
    PLAIN_TEXT = "PLAIN_TEXT"
    MARKDOWN = "MARKDOWN"
    HTML = "HTML"
