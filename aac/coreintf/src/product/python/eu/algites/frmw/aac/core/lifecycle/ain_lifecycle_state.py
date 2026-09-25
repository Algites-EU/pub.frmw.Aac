from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

class AInLifecycleState(str, Enum):
    INSTALLED = "INSTALLED"
    VERIFIED = "VERIFIED"
    PROVISIONED_UNCONFIGURED = "PROVISIONED_UNCONFIGURED"
    PROVISIONED = "PROVISIONED"
    RESOLVED = "RESOLVED"
    INSTANTIATED = "INSTANTIATED"
    WIRED = "WIRED"
    ACTIVATABLE = "ACTIVATABLE"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    FAILED = "FAILED"
    DEACTIVATED = "DEACTIVATED"
