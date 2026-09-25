from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

class AInObservationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
