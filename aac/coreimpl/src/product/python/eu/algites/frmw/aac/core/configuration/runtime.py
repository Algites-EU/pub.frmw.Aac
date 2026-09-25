from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationPolicyMode,
    AInConfigurationProviderCapability,
    AInConfigurationValueSourceKind,
    AIcConfigurationChangeSet,
    AIcConfigurationProviderAccess,
    AIcConfigurationContribution,
    AIcConfigurationMutationResult,
    AIcConfigurationTarget,
    AIcConfigurationContributionProvenance,
    AIcConfigurationProfile,
    AIcConfigurationProviderRequest,
    AIcConfigurationScopeResolutionRequest,
    AIcEffectiveConfiguration,
    AIcEffectiveConfigurationPolicy,
    AIcEffectiveConfigurationValue,
    AIcResolvedConfigurationScope,
    AIiConfigurationMutationAuthorizer,
    AIiConfigurationProvider,
    AIiConfigurationScopeResolver,
)
from eu.algites.frmw.aac.core.context.api import AIcConfigurationScope
from eu.algites.frmw.aac.core.migration.api import AInSchemaRuntimeInterpretation
from eu.algites.frmw.aac.core.persistence.api import AInPersistenceCapability
from eu.algites.frmw.aac.core.implementation.errors import AIxConfigurationConflictError, AIxConfigurationPolicyError

from .aic_configuration_provider_registry import AIcConfigurationProviderRegistry
from .aic_configuration_scope_resolver_registry import AIcConfigurationScopeResolverRegistry
from .aic_static_configuration_scope_resolver import AIcStaticConfigurationScopeResolver
from .aic_static_configuration_provider import AIcStaticConfigurationProvider
from .aic_allow_own_namespace_configuration_mutation_authorizer import AIcAllowOwnNamespaceConfigurationMutationAuthorizer
from .aic_configuration_mutation_service import AIcConfigurationMutationService
from .aic_configuration_provider_read_result import AIcConfigurationProviderReadResult
from .aic_configuration_read_service import AIcConfigurationReadService
from .aic_configuration_context_resolver import AIcConfigurationContextResolver
from .aic_configuration_contribution_record import AIcConfigurationContributionRecord
from .aic_configuration_resolver import AIcConfigurationResolver

def _compose_policy(property_id: str, records: list[AIcConfigurationContributionRecord]) -> AIcEffectiveConfigurationPolicy:
    minimum: object | None = None
    maximum: object | None = None
    in_set: list[object] | None = None
    not_in_set: list[object] = []
    lock: object | None = None
    has_lock = False
    provenance: list[tuple[object, AIcConfigurationContributionProvenance]] = []

    for record in records:
        for policy in record.contribution.policy_modes:
            provenance.append((policy, record.provenance))
            if policy.mode is AInConfigurationPolicyMode.DEFAULT:
                continue
            if policy.mode is AInConfigurationPolicyMode.LOCK:
                if has_lock and not _equal(lock, policy.value):
                    raise AIxConfigurationPolicyError(f"conflicting LOCK policies for property {property_id!r}")
                lock, has_lock = policy.value, True
            elif policy.mode is AInConfigurationPolicyMode.MIN:
                if minimum is None or _compare(policy.value, minimum) > 0:
                    minimum = policy.value
            elif policy.mode is AInConfigurationPolicyMode.MAX:
                if maximum is None or _compare(policy.value, maximum) < 0:
                    maximum = policy.value
            elif policy.mode is AInConfigurationPolicyMode.IN_SET:
                incoming = _as_values(policy.value, property_id, "IN_SET")
                in_set = incoming if in_set is None else [value for value in in_set if _contains(incoming, value)]
            elif policy.mode is AInConfigurationPolicyMode.NOT_IN_SET:
                for value in _as_values(policy.value, property_id, "NOT_IN_SET"):
                    if not _contains(not_in_set, value):
                        not_in_set.append(value)

    result = AIcEffectiveConfigurationPolicy(
        lock=lock,
        has_lock=has_lock,
        minimum=minimum,
        maximum=maximum,
        in_set=tuple(in_set) if in_set is not None else None,
        not_in_set=tuple(not_in_set),
        provenance=tuple(provenance),  # type: ignore[arg-type]
    )
    if minimum is not None and maximum is not None and _compare(minimum, maximum) > 0:
        raise AIxConfigurationPolicyError(f"effective MIN exceeds MAX for property {property_id!r}")
    if result.in_set is not None:
        candidates = [value for value in result.in_set if _allows(result, value)]
        if not candidates:
            raise AIxConfigurationPolicyError(f"effective policy has an empty allowed set for property {property_id!r}")
    if has_lock and not _allows(result, lock):
        raise AIxConfigurationPolicyError(f"LOCK value violates combined policy for property {property_id!r}")
    return result

def _select_explicit(
    property_id: str,
    records: list[AIcConfigurationContributionRecord],
    scope_order: Mapping[str, int],
) -> tuple[AIcConfigurationContributionRecord | None, list[AIcConfigurationContributionProvenance]]:
    if not records:
        return None, []
    first = records[0]
    first_scope_index = scope_order[first.provenance.configuration_scope.key]
    first_priority = first.provenance.configuration_provider_priority
    same_precedence = [
        item for item in records
        if scope_order[item.provenance.configuration_scope.key] == first_scope_index
        and item.provenance.configuration_provider_priority == first_priority
    ]
    if any(not _equal(item.contribution.value, first.contribution.value) for item in same_precedence[1:]):
        raise AIxConfigurationConflictError(
            f"equal-precedence configuration-providers define conflicting values for property {property_id!r}"
        )
    shadowed = [item.provenance for item in records[1:]]
    return first, shadowed

def _policy_mode_provenance(
    policy: AIcEffectiveConfigurationPolicy,
    mode: AInConfigurationPolicyMode,
) -> AIcConfigurationContributionProvenance | None:
    for item, provenance in reversed(policy.provenance):
        if item.mode is mode:
            return provenance
    return None

def _allows(policy: AIcEffectiveConfigurationPolicy, value: object) -> bool:
    if policy.has_lock and not _equal(value, policy.lock):
        return False
    if policy.minimum is not None and _compare(value, policy.minimum) < 0:
        return False
    if policy.maximum is not None and _compare(value, policy.maximum) > 0:
        return False
    if policy.in_set is not None and not _contains(policy.in_set, value):
        return False
    if _contains(policy.not_in_set, value):
        return False
    return True

def _compare(left: object, right: object) -> int:
    try:
        return (left > right) - (left < right)  # type: ignore[operator]
    except TypeError as exc:
        raise AIxConfigurationPolicyError(f"policy values are not comparable: {left!r}, {right!r}") from exc

def _as_values(value: object, property_id: str, mode: str) -> list[object]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise AIxConfigurationPolicyError(f"{mode} policy for property {property_id!r} requires an array/set value")
    result: list[object] = []
    for item in value:
        if not _contains(result, item):
            result.append(item)
    return result

def _contains(values: Iterable[object], candidate: object) -> bool:
    return any(_equal(value, candidate) for value in values)

def _equal(left: object, right: object) -> bool:
    return left == right
