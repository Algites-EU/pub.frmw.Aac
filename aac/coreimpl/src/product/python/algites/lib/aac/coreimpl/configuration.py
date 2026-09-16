from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from algites.lib.aac.coreintf.configuration import (
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
from algites.lib.aac.coreintf.context import AIcConfigurationScope
from algites.lib.aac.coreintf.migration import AInSchemaRuntimeInterpretation
from algites.lib.aac.coreintf.persistence import AInPersistenceCapability

from .errors import AIxConfigurationConflictError, AIxConfigurationPolicyError


class AIcConfigurationProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AIiConfigurationProvider] = {}

    def register(self, configuration_provider_id: str, provider: AIiConfigurationProvider) -> None:
        if not configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")
        self._providers[configuration_provider_id] = provider

    def contains(self, configuration_provider_id: str) -> bool:
        return configuration_provider_id in self._providers

    def get(self, configuration_provider_id: str) -> AIiConfigurationProvider:
        return self._providers[configuration_provider_id]


class AIcConfigurationScopeResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, AIiConfigurationScopeResolver] = {}

    def register(self, configuration_scope_resolver_id: str, resolver: AIiConfigurationScopeResolver) -> None:
        if not configuration_scope_resolver_id:
            raise ValueError("configuration_scope_resolver_id must not be empty")
        self._resolvers[configuration_scope_resolver_id] = resolver

    def contains(self, configuration_scope_resolver_id: str) -> bool:
        return configuration_scope_resolver_id in self._resolvers

    def get(self, configuration_scope_resolver_id: str) -> AIiConfigurationScopeResolver:
        return self._resolvers[configuration_scope_resolver_id]


class AIcStaticConfigurationScopeResolver(AIiConfigurationScopeResolver):
    """Simple bootstrap/test resolver using a type->id mapping from the request context.

    SYSTEM commonly resolves without an id. Other configuration-scope types are present
    only when the supplied context contains an identity for that type.
    """

    def resolve(self, request: AIcConfigurationScopeResolutionRequest) -> AIcConfigurationScope | None:
        if request.configuration_scope_type == "SYSTEM":
            raw = request.context.get("SYSTEM")
            return AIcConfigurationScope("SYSTEM", str(raw) if raw is not None else None)
        raw = request.context.get(request.configuration_scope_type)
        if raw is None:
            return None
        return AIcConfigurationScope(request.configuration_scope_type, str(raw))


class AIcStaticConfigurationProvider(AIiConfigurationProvider):
    """In-memory read-only provider useful for bootstrap defaults/tests."""

    def __init__(self, contributions: Mapping[object, Iterable[AIcConfigurationContribution]]) -> None:
        self._contributions = {key: tuple(value) for key, value in contributions.items()}

    def contributions(self, request: AIcConfigurationProviderRequest) -> tuple[AIcConfigurationContribution, ...]:
        exact = (request.configuration_scope.key, request.configuration_target.key)
        if exact in self._contributions:
            return self._contributions[exact]
        # Scope-only entries are convenient for defaults/tests and apply to any target.
        return self._contributions.get(request.configuration_scope.key, ())


class AIcAllowOwnNamespaceConfigurationMutationAuthorizer(AIiConfigurationMutationAuthorizer):
    """Baseline Core authorizer: caller may mutate only its own component namespace.

    Product profiles can replace this with principal/role-aware authorization.  The actor
    component id is supplied as ``actor_context['component_id']``; product/UI administrative
    principals may set ``configuration_admin=True``.
    """

    def authorized_capabilities(self, request, actor_context, provider_capabilities):
        technical = tuple(provider_capabilities)
        if actor_context.get("configuration_admin") is True or actor_context.get("component_id") == request.configuration_target.component_id:
            return technical
        return tuple(item for item in technical if item is AInConfigurationProviderCapability.READ)

    def authorize(self, change_set: AIcConfigurationChangeSet) -> tuple[bool, tuple[str, ...]]:
        actor = change_set.actor_context.get("component_id")
        if change_set.actor_context.get("configuration_admin") is True:
            return True, ()
        if actor == change_set.configuration_target.component_id:
            return True, ()
        return False, ("configuration mutation is outside the caller component namespace",)


class AIcConfigurationMutationService:
    def __init__(self, providers: AIcConfigurationProviderRegistry, authorizer: AIiConfigurationMutationAuthorizer) -> None:
        self.providers = providers
        self.authorizer = authorizer

    def access(self, request: AIcConfigurationProviderRequest, actor_context: Mapping[str, object] | None = None) -> AIcConfigurationProviderAccess:
        provider = self.providers.get(request.context.get("configuration_provider_id", "")) if request.context.get("configuration_provider_id") else None
        if provider is None:
            raise ValueError("configuration provider id must be supplied in request.context['configuration_provider_id']")
        technical = tuple(provider.capabilities(request))
        authorized = tuple(self.authorizer.authorized_capabilities(request, dict(actor_context or {}), technical))
        diagnostics = () if set(authorized) == set(technical) else ("one or more provider mutation capabilities are not authorized for the current principal",)
        return AIcConfigurationProviderAccess(
            request.configuration_scope, str(request.context["configuration_provider_id"]), request.configuration_target, technical, authorized, diagnostics
        )

    def access_for(
        self, configuration_provider_id: str, request: AIcConfigurationProviderRequest, actor_context: Mapping[str, object] | None = None
    ) -> AIcConfigurationProviderAccess:
        provider = self.providers.get(configuration_provider_id)
        technical = tuple(provider.capabilities(request))
        authorized = tuple(self.authorizer.authorized_capabilities(request, dict(actor_context or {}), technical))
        diagnostics = () if set(authorized) == set(technical) else ("one or more provider mutation capabilities are not authorized for the current principal",)
        return AIcConfigurationProviderAccess(
            request.configuration_scope, configuration_provider_id, request.configuration_target, technical, authorized, diagnostics
        )

    def apply(self, change_set: AIcConfigurationChangeSet) -> AIcConfigurationMutationResult:
        provider = self.providers.get(change_set.configuration_provider_id)
        request = AIcConfigurationProviderRequest(
            change_set.configuration_target, change_set.configuration_scope, change_set.actor_context
        )
        capabilities = set(provider.capabilities(request))
        required = {AInConfigurationProviderCapability.READ}
        for change in change_set.changes:
            if change.operation.value == "SET_VALUE":
                required.add(AInConfigurationProviderCapability.WRITE_VALUE)
            elif change.operation.value == "DELETE_VALUE":
                required.add(AInConfigurationProviderCapability.DELETE_VALUE)
            elif change.operation.value == "SET_POLICY":
                required.add(AInConfigurationProviderCapability.WRITE_POLICY)
            elif change.operation.value == "DELETE_POLICY":
                required.add(AInConfigurationProviderCapability.DELETE_POLICY)
        missing = required - capabilities
        if missing:
            raise AIxConfigurationPolicyError(
                "configuration-provider lacks required mutation capabilities: "
                + ", ".join(sorted(item.value for item in missing))
            )
        authorized = set(self.authorizer.authorized_capabilities(request, change_set.actor_context, tuple(capabilities)))
        unauthorized = required - authorized
        if unauthorized:
            raise AIxConfigurationPolicyError(
                "configuration mutation capability is not authorized: " + ", ".join(sorted(item.value for item in unauthorized))
            )
        allowed, diagnostics = self.authorizer.authorize(change_set)
        if not allowed:
            raise AIxConfigurationPolicyError("configuration mutation is not authorized: " + "; ".join(diagnostics))
        if len(change_set.changes) > 1 and AInConfigurationProviderCapability.ATOMIC_CHANGE_SET not in capabilities:
            raise AIxConfigurationPolicyError("configuration-provider does not support atomic multi-change mutation")
        return provider.apply_changes(change_set)


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderReadResult:
    contributions: tuple[AIcConfigurationContribution, ...]
    diagnostics: tuple[str, ...] = ()


class AIcConfigurationReadService:
    """Normalize versioned provider snapshots before they enter configuration resolution.

    Unsupported persisted representations are preserved by their provider and treated as an
    unavailable contribution.  They do not abort resolution; diagnostics explain why the
    contribution was omitted.
    """

    def __init__(
        self, providers, migrations, schema_declaration_resolver, schema_registry, *, persist_migrations: bool = True
    ) -> None:
        self.providers = providers
        self.migrations = migrations
        self.schema_declaration_resolver = schema_declaration_resolver
        self.schema_registry = schema_registry
        self.persist_migrations = persist_migrations

    def read(self, configuration_provider_id: str, request: AIcConfigurationProviderRequest) -> AIcConfigurationProviderReadResult:
        provider = self.providers.get(configuration_provider_id)
        snapshot = provider.snapshot(request)
        if snapshot is None:
            return AIcConfigurationProviderReadResult(tuple(provider.contributions(request)))
        declaration, component_version = self.schema_declaration_resolver(request.configuration_target)
        if declaration is None:
            return AIcConfigurationProviderReadResult(tuple(provider.contributions(request)))
        payload = snapshot.payload
        assessment = self.migrations.compatibility.assess(
            payload.configuration_schema_id, payload.configuration_schema_version, declaration
        )
        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.UNSUPPORTED:
            return AIcConfigurationProviderReadResult((), (
                f"configuration provider {configuration_provider_id!r} contribution for {request.configuration_target.key} "
                f"uses unsupported representation {payload.configuration_schema_id}/{payload.configuration_schema_version}; "
                "the contribution is unavailable and resolution continues with other inputs",
            ))

        if assessment.runtime_interpretation is AInSchemaRuntimeInterpretation.TRANSFORMED:
            try:
                payload = self.migrations.migrate_to_write_version(
                    payload, declaration, written_by_component_version=component_version
                )
                self._validate_target(payload, declaration)
            except Exception as exc:
                return AIcConfigurationProviderReadResult((), (
                    f"configuration provider {configuration_provider_id!r} contribution for {request.configuration_target.key} "
                    f"could not be transformed safely and is unavailable: {exc}",
                ))
            # Persistence convergence is deliberately best-effort and is not required for reads.
            persisted_revision = snapshot.record_revision
            if self.persist_migrations:
                try:
                    persistence_capabilities = set(provider.persistence_capabilities(request))
                    if AInPersistenceCapability.SINGLE_RECORD_CAS in persistence_capabilities:
                        result = provider.replace_payload(request, payload, snapshot.record_revision)
                        persisted_revision = result.record_revision
                except Exception:
                    pass
            snapshot = type(snapshot)(
                snapshot.configuration_scope, snapshot.configuration_target, persisted_revision, payload
            )
        else:
            # DIRECT means use the stored representation as-is even when a migration path to the
            # preferred write version also exists.  Such a path is relevant only to optional
            # persistence convergence.
            try:
                if assessment.at_target_write_version:
                    self._validate_target(payload, declaration)
                else:
                    self._validate_direct(payload)
            except Exception as exc:
                return AIcConfigurationProviderReadResult((), (
                    f"configuration provider {configuration_provider_id!r} contribution for {request.configuration_target.key} "
                    f"declares a directly readable representation but its payload is not usable: {exc}",
                ))

        return AIcConfigurationProviderReadResult(self._payload_contributions(snapshot))

    def contributions(self, configuration_provider_id: str, request: AIcConfigurationProviderRequest):
        return self.read(configuration_provider_id, request).contributions

    def _validate_target(self, payload, declaration) -> None:
        if declaration.resource_name is not None:
            self.schema_registry.normalize(declaration.resource_name, payload.values, apply_defaults=False)

    def _validate_direct(self, payload) -> None:
        try:
            registered = self.schema_registry.get_identity(payload.configuration_schema_id, payload.configuration_schema_version)
        except KeyError:
            # ``readable_versions`` is the component's compatibility declaration.  A historical
            # schema resource need not remain bundled merely to consume a representation that the
            # component explicitly promises to read.
            return
        self.schema_registry.normalize(registered.resource_name, payload.values, apply_defaults=False)

    @staticmethod
    def _payload_contributions(snapshot):
        payload = snapshot.payload
        keys = list(dict.fromkeys([*payload.values.keys(), *payload.policies.keys()]))
        result = []
        for property_id in keys:
            result.append(AIcConfigurationContribution(
                property_id=str(property_id),
                value=payload.values.get(property_id),
                has_value=property_id in payload.values,
                policy_modes=tuple(payload.policies.get(property_id, ())),
                configuration_schema_id=payload.configuration_schema_id,
                configuration_schema_version=payload.configuration_schema_version,
                written_by_component_version=payload.written_by_component_version,
                metadata={"provider_record_revision": snapshot.record_revision},
            ))
        return tuple(result)


class AIcConfigurationContextResolver:
    def __init__(self, resolvers: AIcConfigurationScopeResolverRegistry) -> None:
        self.resolvers = resolvers

    def resolve(self, profile: AIcConfigurationProfile, context: Mapping[str, object]) -> tuple[AIcResolvedConfigurationScope, ...]:
        result: list[AIcResolvedConfigurationScope] = []
        seen: set[tuple[str, str | None]] = set()
        for definition in profile.configuration_scopes:
            resolver = self.resolvers.get(definition.configuration_scope_resolver_id)
            scope = resolver.resolve(AIcConfigurationScopeResolutionRequest(
                definition.configuration_scope_type,
                definition.id,
                dict(context),
            ))
            if scope is None:
                if definition.mandatory:
                    raise AIxConfigurationConflictError(
                        f"mandatory configuration-scope {definition.id!r} ({definition.configuration_scope_type}) could not be resolved"
                    )
                continue
            key = (scope.type, scope.id)
            if key in seen:
                raise AIxConfigurationConflictError(f"configuration-scope {scope.key!r} occurs more than once in the active chain")
            seen.add(key)
            ordered_bindings = tuple(sorted(
                definition.configuration_providers,
                key=lambda item: (-item.priority, item.configuration_provider_id),
            ))
            result.append(AIcResolvedConfigurationScope(definition.id, scope, ordered_bindings, definition.policy_authority))
        return tuple(result)


@dataclass(frozen=True, slots=True)
class AIcConfigurationContributionRecord:
    contribution: AIcConfigurationContribution
    provenance: AIcConfigurationContributionProvenance
    policy_authority: bool


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
