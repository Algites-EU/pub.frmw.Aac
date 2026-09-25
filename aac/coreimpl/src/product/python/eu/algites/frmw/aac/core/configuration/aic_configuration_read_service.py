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

from .aic_configuration_provider_read_result import AIcConfigurationProviderReadResult

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
