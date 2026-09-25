from __future__ import annotations
from collections import defaultdict
from typing import Mapping
from eu.algites.frmw.aac.core.configuration.api import AInConfigurationValueSourceKind, AIcEffectiveConfiguration
from eu.algites.frmw.aac.core.descriptor.api import AIcProviderDefinitionDescriptor
from eu.algites.frmw.aac.core.readiness.api import (
    AInReadinessRequirementSource,
    AInReadinessState,
    AIcCapabilityReadiness,
    AIcComponentReadiness,
    AIcProviderReadiness,
    AIcReadinessReason,
    AIcReadinessResult,
)

from .aic_readiness_evaluator import AIcReadinessEvaluator

_RANK = {
    AInReadinessState.READY: 0,
    AInReadinessState.DEGRADED: 1,
    AInReadinessState.NOT_READY: 2,
}

def worst_readiness(*states: AInReadinessState) -> AInReadinessState:
    return max(states or (AInReadinessState.READY,), key=_RANK.__getitem__)

def _context_contains(context: Mapping[str, object], key: str) -> bool:
    current: object = context
    for part in key.split('.'):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return True
