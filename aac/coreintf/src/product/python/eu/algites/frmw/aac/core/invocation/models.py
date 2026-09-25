from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar

from .aic_invocation_input import AIcInvocationInput
from .aic_invocation_output import AIcInvocationOutput
from .ain_operation_completion_state import AInOperationCompletionState
from .aic_operation_completion import AIcOperationCompletion

AIcOperationSuccessT = TypeVar("AIcOperationSuccessT")

AIcOperationCancelledT = TypeVar("AIcOperationCancelledT")
