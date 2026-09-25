from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

class AInCapabilityOperationInteractionKind(str, Enum):
    INPUT = "INPUT"
    RUNNING_COMPLETE_STATE_RESULT = "RUNNING_COMPLETE_STATE_RESULT"
    RUNNING_DELTA_STATE_RESULT = "RUNNING_DELTA_STATE_RESULT"
    FINAL_SUCCESS_STATE_RESULT = "FINAL_SUCCESS_STATE_RESULT"
    FINAL_CANCELLED_STATE_RESULT = "FINAL_CANCELLED_STATE_RESULT"
    FINAL_FAILED_STATE_RESULT_EXTENSION = "FINAL_FAILED_STATE_RESULT_EXTENSION"
