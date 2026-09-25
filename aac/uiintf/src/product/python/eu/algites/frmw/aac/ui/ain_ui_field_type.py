from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from eu.algites.frmw.aac.core.presentation.api import (
    AIcDisplayContent,
    AIcDisplayText,
    normalize_display_content,
    normalize_display_text,
)

class AInUiFieldType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"
    MULTILINE = "MULTILINE"
    JSON = "JSON"
    SECRET_REFERENCE = "SECRET_REFERENCE"
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    INSTANCE_REFERENCE = "INSTANCE_REFERENCE"
    CAPABILITY_REFERENCE = "CAPABILITY_REFERENCE"
