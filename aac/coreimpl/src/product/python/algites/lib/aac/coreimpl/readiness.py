from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from algites.lib.aac.coreintf.configuration import AInConfigurationValueSourceKind, AIcEffectiveConfiguration
from algites.lib.aac.coreintf.descriptor import AIcProviderDefinitionDescriptor
from algites.lib.aac.coreintf.readiness import (
    AInReadinessRequirementSource,
    AInReadinessState,
    AIcCapabilityReadiness,
    AIcComponentReadiness,
    AIcProviderReadiness,
    AIcReadinessReason,
    AIcReadinessResult,
)


_RANK = {
    AInReadinessState.READY: 0,
    AInReadinessState.DEGRADED: 1,
    AInReadinessState.NOT_READY: 2,
}


def worst_readiness(*states: AInReadinessState) -> AInReadinessState:
    return max(states or (AInReadinessState.READY,), key=_RANK.__getitem__)


class AIcReadinessEvaluator:
    """Evaluate static AAC readiness requirements and aggregate runtime reports.

    Activation and readiness are intentionally distinct.  Missing runtime inputs never undo a
    successful component activation; they produce structured readiness state for the narrowest
    affected provider/capability instead.
    """

    @staticmethod
    def static_provider_readiness(
        application_scope_id: str,
        component_id: str,
        provider_instance_id: str,
        provider: AIcProviderDefinitionDescriptor,
        component_configuration: AIcEffectiveConfiguration,
        provider_configuration: AIcEffectiveConfiguration,
        context: Mapping[str, object],
        provider_local_configuration: Mapping[str, object] | None = None,
    ) -> AIcProviderReadiness:
        reasons: list[AIcReadinessReason] = []
        for requirement in provider.readiness_requirements:
            missing = False
            if requirement.source is AInReadinessRequirementSource.COMPONENT_CONFIGURATION:
                value = component_configuration.values.get(requirement.key)
                missing = value is None or value.source_kind is AInConfigurationValueSourceKind.UNDEFINED
                code = "CONFIGURATION_UNDEFINED"
            elif requirement.source is AInReadinessRequirementSource.PROVIDER_CONFIGURATION:
                value = provider_configuration.values.get(requirement.key)
                missing = value is None or value.source_kind is AInConfigurationValueSourceKind.UNDEFINED
                if missing and provider_local_configuration is not None and requirement.key in provider_local_configuration:
                    missing = False
                code = "CONFIGURATION_UNDEFINED"
            else:
                missing = not _context_contains(context, requirement.key)
                code = "CONTEXT_UNDEFINED"
            if missing:
                reasons.append(AIcReadinessReason(
                    code,
                    requirement.message or f"required {requirement.source.value.lower()} value {requirement.key!r} is unavailable",
                    requirement.missing_state,
                    requirement.id,
                    requirement.key,
                ))
        state = worst_readiness(*(item.state for item in reasons))
        return AIcProviderReadiness(
            application_scope_id,
            component_id,
            provider_instance_id,
            tuple(capability.id for capability in provider.capabilities),
            state,
            tuple(reasons),
        )

    @staticmethod
    def combine_runtime(static: AIcProviderReadiness, runtime: AIcReadinessResult) -> AIcProviderReadiness:
        return AIcProviderReadiness(
            static.application_scope_id,
            static.component_id,
            static.provider_instance_id,
            static.capability_ids,
            worst_readiness(static.state, runtime.state),
            static.reasons + runtime.reasons,
        )

    @staticmethod
    def component(application_scope_id: str, component_id: str, reports: tuple[AIcProviderReadiness, ...]) -> AIcComponentReadiness:
        if not reports:
            return AIcComponentReadiness(application_scope_id, component_id, AInReadinessState.READY)
        states = tuple(item.state for item in reports)
        if all(state is AInReadinessState.NOT_READY for state in states):
            state = AInReadinessState.NOT_READY
        elif any(state is not AInReadinessState.READY for state in states):
            state = AInReadinessState.DEGRADED
        else:
            state = AInReadinessState.READY
        return AIcComponentReadiness(
            application_scope_id, component_id, state,
            tuple(item.provider_instance_id for item in reports),
            tuple(reason for item in reports for reason in item.reasons),
        )

    @staticmethod
    def capabilities(application_scope_id: str, reports: tuple[AIcProviderReadiness, ...]) -> tuple[AIcCapabilityReadiness, ...]:
        grouped: dict[str, list[AIcProviderReadiness]] = defaultdict(list)
        for report in reports:
            for capability_id in report.capability_ids:
                grouped[capability_id].append(report)
        result = []
        for capability_id, values in sorted(grouped.items()):
            states = tuple(item.state for item in values)
            if any(state is AInReadinessState.READY for state in states):
                state = AInReadinessState.READY
            elif any(state is AInReadinessState.DEGRADED for state in states):
                state = AInReadinessState.DEGRADED
            else:
                state = AInReadinessState.NOT_READY
            result.append(AIcCapabilityReadiness(
                application_scope_id, capability_id, state,
                tuple(item.provider_instance_id for item in values),
                tuple(reason for item in values for reason in item.reasons),
            ))
        return tuple(result)


def _context_contains(context: Mapping[str, object], key: str) -> bool:
    current: object = context
    for part in key.split('.'):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return True
