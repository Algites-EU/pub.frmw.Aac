from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

class AInLifecycleStage(str, Enum):
    DISCOVER = "DISCOVER"
    VERIFY = "VERIFY"
    ADMIT_CONTRACTS = "ADMIT_CONTRACTS"
    PROVISION = "PROVISION"
    VALIDATE = "VALIDATE"
    EVALUATE_ENTITLEMENT = "EVALUATE_ENTITLEMENT"
    RESOLVE = "RESOLVE"
    INSTANTIATE = "INSTANTIATE"
    WIRE = "WIRE"
    ACTIVATABLE = "ACTIVATABLE"
    ACTIVATE = "ACTIVATE"
    SUSPEND = "SUSPEND"
    DEACTIVATE = "DEACTIVATE"
    UNPROVISION = "UNPROVISION"
