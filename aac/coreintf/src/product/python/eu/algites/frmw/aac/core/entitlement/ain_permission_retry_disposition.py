from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

class AInPermissionRetryDisposition(str, Enum):
    SAFE_AFTER_ENTITLEMENT_CHANGE = "SAFE_AFTER_ENTITLEMENT_CHANGE"
    DO_NOT_RETRY = "DO_NOT_RETRY"
