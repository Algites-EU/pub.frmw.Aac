from __future__ import annotations
import copy
from dataclasses import replace
from threading import Condition, RLock
from typing import Callable
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationExecutionState,
    AInOperationInteractionDetailLevel,
    AInOperationInteractionFailureDetailLevel,
    AInOperationInteractionMode,
    AInStateResultDeliveryMode,
    AIcOperationInteractionCallerToProviderMessage,
    AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures,
    AIcOperationInteractionProviderToCallerMessage,
    AIiOperationInteractionCallerToProvider,
    AIiOperationFailureExceptionFactory,
    AIxCapabilityOperationFailed,
)

from .aic_operation_interaction_controller import AIcOperationInteractionController
