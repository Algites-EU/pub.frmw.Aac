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

from .aic_configuration_contribution_record import AIcConfigurationContributionRecord
from .aic_configuration_provider_registry import AIcConfigurationProviderRegistry
from .aic_configuration_read_service import AIcConfigurationReadService

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

class AIcConfigurationResolver:
    """Resolve provider contributions for a concrete ordered configuration-scope chain.

    This class intentionally owns no persistence. It consumes normalized contributions
    from registered configuration-providers and implements deterministic policy/value
    semantics from the generic AAC specification.
    """

    def __init__(self, providers: AIcConfigurationProviderRegistry, read_service: AIcConfigurationReadService | None = None) -> None:
        self.providers = providers
        self.read_service = read_service

    def resolve(
        self,
        *,
        configuration_target: AIcConfigurationTarget,
        configuration_scopes: tuple[AIcResolvedConfigurationScope, ...],
        property_ids: Iterable[str],
        accepted_configuration_scope_types: Mapping[str, tuple[str, ...]] | None = None,
        schema_defaults: Mapping[str, object] | None = None,
        context: Mapping[str, object] | None = None,
    ) -> AIcEffectiveConfiguration:
        records: dict[str, list[AIcConfigurationContributionRecord]] = {str(item): [] for item in property_ids}
        accepted = dict(accepted_configuration_scope_types or {})
        raw_context = dict(context or {})
        diagnostics: list[str] = []

        for resolved_scope in configuration_scopes:
            for binding in resolved_scope.configuration_providers:
                provider = self.providers.get(binding.configuration_provider_id)
                request = AIcConfigurationProviderRequest(
                    configuration_target, resolved_scope.configuration_scope, raw_context
                )
                if self.read_service is not None:
                    read_result = self.read_service.read(binding.configuration_provider_id, request)
                    contributions = read_result.contributions
                    diagnostics.extend(read_result.diagnostics)
                else:
                    contributions = provider.contributions(request)
                seen_provider_properties: set[str] = set()
                for contribution in contributions:
                    if contribution.property_id not in records:
                        continue
                    if contribution.property_id in seen_provider_properties:
                        raise AIxConfigurationConflictError(
                            f"configuration-provider {binding.configuration_provider_id!r} returned property {contribution.property_id!r} more than once"
                        )
                    seen_provider_properties.add(contribution.property_id)
                    allowed_types = accepted.get(contribution.property_id)
                    if allowed_types and resolved_scope.configuration_scope.type not in allowed_types:
                        raise AIxConfigurationPolicyError(
                            f"property {contribution.property_id!r} does not accept configuration-scope type {resolved_scope.configuration_scope.type!r}"
                        )
                    if contribution.policy_modes and not resolved_scope.policy_authority:
                        raise AIxConfigurationPolicyError(
                            f"configuration-scope {resolved_scope.configuration_scope.key!r} is not a policy authority"
                        )
                    provenance = AIcConfigurationContributionProvenance(
                        resolved_scope.configuration_scope,
                        binding.configuration_provider_id,
                        binding.priority,
                    )
                    records[contribution.property_id].append(AIcConfigurationContributionRecord(
                        contribution,
                        provenance,
                        resolved_scope.policy_authority,
                    ))

        values: dict[str, AIcEffectiveConfigurationValue] = {}
        scope_order = {scope.configuration_scope.key: index for index, scope in enumerate(configuration_scopes)}
        for property_id in records:
            values[property_id] = self._resolve_property(
                property_id,
                records[property_id],
                scope_order,
                schema_defaults if schema_defaults is not None else {},
            )
        return AIcEffectiveConfiguration(configuration_target, values, configuration_scopes, tuple(diagnostics))

    def _resolve_property(
        self,
        property_id: str,
        records: list[AIcConfigurationContributionRecord],
        scope_order: Mapping[str, int],
        schema_defaults: Mapping[str, object],
    ) -> AIcEffectiveConfigurationValue:
        policy_records = [item for item in records if item.contribution.policy_modes]
        # Least-specific -> most-specific; provider priority stays deterministic inside a scope.
        policy_records.sort(key=lambda item: (
            -scope_order[item.provenance.configuration_scope.key],
            -item.provenance.configuration_provider_priority,
            item.provenance.configuration_provider_id,
        ))
        policy = _compose_policy(property_id, policy_records)

        explicit_records = [item for item in records if item.contribution.has_value]
        explicit_records.sort(key=lambda item: (
            scope_order[item.provenance.configuration_scope.key],
            -item.provenance.configuration_provider_priority,
            item.provenance.configuration_provider_id,
        ))
        selected, shadowed = _select_explicit(property_id, explicit_records, scope_order)
        if selected is not None:
            value = selected.contribution.value
            if not _allows(policy, value):
                raise AIxConfigurationPolicyError(
                    f"explicit value for property {property_id!r} from {selected.provenance.configuration_scope.key} violates effective policy"
                )
            if policy.has_lock:
                lock_provenance = _policy_mode_provenance(policy, AInConfigurationPolicyMode.LOCK)
                return AIcEffectiveConfigurationValue(
                    property_id, policy.lock, AInConfigurationValueSourceKind.POLICY_LOCK,
                    lock_provenance, policy, tuple([selected.provenance, *shadowed]),
                )
            return AIcEffectiveConfigurationValue(
                property_id, value, AInConfigurationValueSourceKind.EXPLICIT,
                selected.provenance, policy, tuple(shadowed),
            )

        if policy.has_lock:
            lock_provenance = _policy_mode_provenance(policy, AInConfigurationPolicyMode.LOCK)
            return AIcEffectiveConfigurationValue(
                property_id,
                policy.lock,
                AInConfigurationValueSourceKind.POLICY_LOCK,
                lock_provenance,
                policy,
            )

        default_records: list[tuple[object, AIcConfigurationContributionProvenance]] = []
        for item in records:
            for mode in item.contribution.policy_modes:
                if mode.mode is AInConfigurationPolicyMode.DEFAULT:
                    default_records.append((mode.value, item.provenance))
        default_records.sort(key=lambda item: (
            scope_order[item[1].configuration_scope.key],
            -item[1].configuration_provider_priority,
            item[1].configuration_provider_id,
        ))
        for value, provenance in default_records:
            if not _allows(policy, value):
                raise AIxConfigurationPolicyError(
                    f"policy DEFAULT for property {property_id!r} from {provenance.configuration_scope.key} violates effective policy"
                )
            return AIcEffectiveConfigurationValue(
                property_id, value, AInConfigurationValueSourceKind.POLICY_DEFAULT, provenance, policy
            )

        if property_id in schema_defaults:
            value = schema_defaults[property_id]
            if not _allows(policy, value):
                raise AIxConfigurationPolicyError(f"schema default for property {property_id!r} violates effective policy")
            return AIcEffectiveConfigurationValue(
                property_id, value, AInConfigurationValueSourceKind.SCHEMA_DEFAULT, None, policy
            )
        return AIcEffectiveConfigurationValue(
            property_id, None, AInConfigurationValueSourceKind.UNDEFINED, None, policy
        )
