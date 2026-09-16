from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor
from algites.lib.aac.coreintf.configuration import AInConfigurationTargetKind, AIcConfigurationTarget, AIcEffectiveConfiguration
from algites.lib.aac.coreintf.entitlement import AIcEntitlementContext, AIcResolvedEntitlementLicensingScope
from algites.lib.aac.coreintf.instances import AIcBinding, AInProviderInstanceState
from algites.lib.aac.coreintf.lifecycle import AIcLifecycleContext, AInLifecycleStage, AInLifecycleState, AIcLifecycleStatus, AIiValidationHook, AIcValidationResult
from algites.lib.aac.coreintf.observation import AIiObservationProvider
from algites.lib.aac.coreintf.persistence import AIiStateStore
from algites.lib.aac.coreintf.runtime import AIiProviderRuntime
from algites.lib.aac.coreintf.readiness import AIcProviderReadiness, AIcComponentReadiness, AIcCapabilityReadiness
from algites.lib.aac.coreintf.verification import AIiPackageVerifier, AIcVerificationInput

from .contracts import AIcActiveContractCatalog
from .descriptor import AIcDiscoveredComponent
from .entitlement import AIcEntitlementManager
from .errors import AIxLifecycleError
from algites.lib.aac.coreintf.invocation import AIiCapabilityEndpoint
from .invocation import AIcCapabilityHandleFactory, AIcEndpointRegistry
from .loading import load_class
from .observation import AIcEndpointObservationProvider, AIcObservationDispatcher, OBSERVATION_CAPABILITY_ID
from .persistence import AIcInMemoryStateStore
from .provisioning import AIcProvisioningEngine
from .resolution import validate_instance_dag
from .runtime import instantiate_provider
from .readiness import AIcReadinessEvaluator
from .verification import AIcPythonPackageVerifier

_LIFECYCLE_NAMESPACE = "aac.lifecycle"


@dataclass(frozen=True, slots=True)
class AIcActivationOutcome:
    status: AIcLifecycleStatus
    runtime_instance_ids: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


class AIcLifecycleEngine:
    def __init__(
        self,
        *,
        contract_catalog: AIcActiveContractCatalog,
        provisioning: AIcProvisioningEngine,
        entitlement: AIcEntitlementManager | None = None,
        store: AIiStateStore | None = None,
        endpoints: AIcEndpointRegistry | None = None,
        handles: AIcCapabilityHandleFactory | None = None,
        observations: AIcObservationDispatcher | None = None,
        verifier: AIiPackageVerifier | None = None,
    ) -> None:
        self.contract_catalog = contract_catalog
        self.provisioning = provisioning
        self.entitlement = entitlement or AIcEntitlementManager()
        self.store = store or provisioning.store or AIcInMemoryStateStore()
        self.endpoints = endpoints or AIcEndpointRegistry()
        self.handles = handles
        self.observations = observations
        self.verifier = verifier or AIcPythonPackageVerifier()
        self._runtimes: dict[str, AIiProviderRuntime] = {}
        self._readiness: dict[tuple[str, str], AIcProviderReadiness] = {}
        self._readiness_inputs: dict[str, tuple[AIcEffectiveConfiguration, AIcEffectiveConfiguration]] = {}
        self.licensing_scopes: tuple[AIcResolvedEntitlementLicensingScope, ...] = ()
        self.entitlement_context: Mapping[str, object] = {}

    @staticmethod
    def _key(application_scope_id: str, component_id: str) -> str:
        return f"{application_scope_id}:{component_id}"

    def status(self, application_scope_id: str, component_id: str) -> AIcLifecycleStatus:
        raw = self.store.get(_LIFECYCLE_NAMESPACE, self._key(application_scope_id, component_id))
        return AIcLifecycleStatus(AInLifecycleState.INSTALLED) if raw is None else _status_from_dict(raw)

    def _save(self, application_scope_id: str, component_id: str, status: AIcLifecycleStatus) -> AIcLifecycleStatus:
        self.store.put(_LIFECYCLE_NAMESPACE, self._key(application_scope_id, component_id), _status_to_dict(status))
        return status

    def _advance(self, application_scope_id: str, component_id: str, state: AInLifecycleState, stage: AInLifecycleStage, diagnostics: tuple[str, ...] = ()) -> AIcLifecycleStatus:
        current = self.status(application_scope_id, component_id)
        completed = current.completed_stages if stage in current.completed_stages else current.completed_stages + (stage,)
        return self._save(application_scope_id, component_id, AIcLifecycleStatus(state, completed, None, diagnostics))

    def prepare_component(self, application_scope_id: str, component: AIcDiscoveredComponent) -> AIcLifecycleStatus:
        descriptor = component.descriptor
        diagnostics: list[str] = []
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.VERIFIED, AInLifecycleStage.DISCOVER)
        verification = self.verifier.verify(AIcVerificationInput(descriptor.id, descriptor.version, component.package, component.source, descriptor.metadata, component.artifact_path))
        if not verification.valid:
            raise AIxLifecycleError("package verification failed: " + "; ".join(verification.diagnostics))
        diagnostics.extend(verification.diagnostics)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.VERIFIED, AInLifecycleStage.VERIFY, tuple(diagnostics))

        if component.package is None and descriptor.contract_resources:
            raise AIxLifecycleError("contract resources require a package-backed discovered component")
        for resource_name in descriptor.contract_resources:
            self.contract_catalog.admit_package_resource(component.package, resource_name)  # type: ignore[arg-type]
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.VERIFIED, AInLifecycleStage.ADMIT_CONTRACTS, tuple(diagnostics))

        outcome = self.provisioning.provision(application_scope_id, descriptor)
        diagnostics.extend(outcome.diagnostics)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.PROVISIONED, AInLifecycleStage.PROVISION, tuple(diagnostics))

        diagnostics.extend(self.provisioning.validate_instances(descriptor))
        if descriptor.lifecycle.validate is not None:
            hook_class = load_class(descriptor.lifecycle.validate, AIiValidationHook)
            result = hook_class().validate(_context(application_scope_id, descriptor))
            if not isinstance(result, AIcValidationResult) or not result.valid:
                detail = result.diagnostics if isinstance(result, AIcValidationResult) else ("invalid validation hook result",)
                raise AIxLifecycleError("component-specific validation failed: " + "; ".join(detail))
            diagnostics.extend(result.diagnostics)
        if self.provisioning.registry.find(component_id=descriptor.id, states=(AInProviderInstanceState.UNCONFIGURED,)):
            self._advance(application_scope_id, descriptor.id, AInLifecycleState.PROVISIONED_UNCONFIGURED, AInLifecycleStage.VALIDATE, tuple(diagnostics))
            raise AIxLifecycleError("one or more provider instances remain unconfigured")
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.PROVISIONED, AInLifecycleStage.VALIDATE, tuple(diagnostics))

        # Ordinary entitlement permissions are contextual runtime inputs, not lifecycle
        # admission gates. A component may remain active with an empty/minimal permission
        # set and implement free/degraded behavior. Hard activation prerequisites, if a
        # future product profile introduces them, are a distinct mechanism.
        component_entitlement = self.entitlement.evaluate_component(
            descriptor, licensing_scopes=self.licensing_scopes, context=self.entitlement_context
        )
        diagnostics.extend(component_entitlement.diagnostics)
        return self._advance(
            application_scope_id, descriptor.id, AInLifecycleState.PROVISIONED,
            AInLifecycleStage.EVALUATE_ENTITLEMENT, tuple(diagnostics)
        )

    def mark_resolved(self, application_scope_id: str, descriptor: AIcComponentDescriptor) -> AIcLifecycleStatus:
        return self._advance(application_scope_id, descriptor.id, AInLifecycleState.RESOLVED, AInLifecycleStage.RESOLVE)

    def activate_instance(
        self, application_scope_id: str, descriptor: AIcComponentDescriptor, instance_id: str, bindings: tuple[AIcBinding, ...],
        *, component_configuration: AIcEffectiveConfiguration | None = None,
        provider_instance_configuration: AIcEffectiveConfiguration | None = None,
    ) -> AIiProviderRuntime:
        instance = self.provisioning.registry.get(instance_id)
        provider = descriptor.provider(instance.provider_definition_id)
        component_configuration = component_configuration or AIcEffectiveConfiguration(
            AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, instance.component_id), {}, ()
        )
        provider_instance_configuration = provider_instance_configuration or AIcEffectiveConfiguration(
            AIcConfigurationTarget(AInConfigurationTargetKind.PROVIDER_INSTANCE, instance.component_id, instance.id), {}, ()
        )
        entitlement_context = self.entitlement.evaluate_component(
            descriptor,
            licensing_scopes=self.licensing_scopes,
            provider_instance=instance,
            context=self.entitlement_context,
        )
        runtime = instantiate_provider(
            application_scope_id, instance, provider, entitlement_context,
            component_configuration=component_configuration,
            provider_instance_configuration=provider_instance_configuration,
        )
        runtime.entitlement_changed(entitlement_context)
        self._runtimes[instance.id] = runtime
        if isinstance(runtime, AIiCapabilityEndpoint):
            self.endpoints.register(instance.id, runtime)
        else:
            self.endpoints.register_object(instance.id, runtime)
        self.provisioning.registry.update(instance.id, state=AInProviderInstanceState.INACTIVE)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.INSTANTIATED, AInLifecycleStage.INSTANTIATE)

        handles = self.handles.for_consumer(instance.id, bindings) if self.handles is not None else {}
        for requirement in provider.requirements:
            count = len(handles.get(requirement.id, ()))
            if requirement.mandatory and count == 0:
                raise AIxLifecycleError(f"mandatory requirement {requirement.id!r} has no resolved capability handle")
            if requirement.cardinality.value == "SINGLE" and count > 1:
                raise AIxLifecycleError(f"SINGLE requirement {requirement.id!r} has {count} handles")
        runtime.wire(handles)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.WIRED, AInLifecycleStage.WIRE)

        self._readiness_inputs[instance.id] = (component_configuration, provider_instance_configuration)
        runtime.prepare_activation()
        static_readiness = AIcReadinessEvaluator.static_provider_readiness(
            application_scope_id, descriptor.id, instance.id, provider,
            component_configuration, provider_instance_configuration, self.entitlement_context, instance.configuration,
        )
        self._readiness[(application_scope_id, instance.id)] = AIcReadinessEvaluator.combine_runtime(
            static_readiness, runtime.readiness()
        )
        self.provisioning.registry.update(instance.id, state=AInProviderInstanceState.ACTIVATABLE)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.ACTIVATABLE, AInLifecycleStage.ACTIVATABLE)

        if self.observations is not None and provider.capability_id == OBSERVATION_CAPABILITY_ID:
            if isinstance(runtime, AIiObservationProvider):
                self.observations.register_provider(instance.id, runtime)
            elif isinstance(runtime, AIiCapabilityEndpoint) and self.handles is not None:
                self.observations.register_provider(
                    instance.id,
                    AIcEndpointObservationProvider(instance.id, runtime, self.handles.dispatcher),
                )
            else:
                raise AIxLifecycleError("observation provider runtime has no invocable observation endpoint")
        runtime.activate()
        self.provisioning.registry.update(instance.id, state=AInProviderInstanceState.ACTIVE)
        self._advance(application_scope_id, descriptor.id, AInLifecycleState.ACTIVE, AInLifecycleStage.ACTIVATE)
        return runtime

    def activate(self, application_scope_id: str, component: AIcDiscoveredComponent, *, bindings: tuple[AIcBinding, ...] = ()) -> AIcActivationOutcome:
        self.prepare_component(application_scope_id, component)
        consumer_first = validate_instance_dag(bindings)
        self.mark_resolved(application_scope_id, component.descriptor)
        local_ids = {instance.id for instance in self.provisioning.registry.find(component_id=component.descriptor.id)}
        order = [instance_id for instance_id in reversed(consumer_first) if instance_id in local_ids]
        order.extend(sorted(local_ids - set(order)))
        for instance_id in order:
            self.activate_instance(application_scope_id, component.descriptor, instance_id, bindings)
        return AIcActivationOutcome(self.status(application_scope_id, component.descriptor.id), tuple(order))

    def provider_readiness(self, application_scope_id: str, provider_instance_id: str) -> AIcProviderReadiness | None:
        return self._readiness.get((application_scope_id, provider_instance_id))

    def component_readiness(self, application_scope_id: str, component_id: str) -> AIcComponentReadiness:
        reports = tuple(
            report for (scope_id, _), report in self._readiness.items()
            if scope_id == application_scope_id and report.component_id == component_id
        )
        return AIcReadinessEvaluator.component(application_scope_id, component_id, reports)

    def capability_readiness(self, application_scope_id: str) -> tuple[AIcCapabilityReadiness, ...]:
        reports = tuple(report for (scope_id, _), report in self._readiness.items() if scope_id == application_scope_id)
        return AIcReadinessEvaluator.capabilities(application_scope_id, reports)

    def refresh_instance_readiness(
        self, application_scope_id: str, descriptor: AIcComponentDescriptor, instance_id: str,
        *, component_configuration: AIcEffectiveConfiguration | None = None,
        provider_configuration: AIcEffectiveConfiguration | None = None,
    ) -> AIcProviderReadiness:
        instance = self.provisioning.registry.get(instance_id)
        provider = descriptor.provider(instance.provider_definition_id)
        if component_configuration is None or provider_configuration is None:
            inputs = self._readiness_inputs.get(instance_id)
            if inputs is None:
                raise KeyError(f"readiness inputs unavailable for provider instance {instance_id!r}")
            component_configuration, provider_configuration = inputs
        self._readiness_inputs[instance_id] = (component_configuration, provider_configuration)
        static = AIcReadinessEvaluator.static_provider_readiness(
            application_scope_id, descriptor.id, instance_id, provider,
            component_configuration, provider_configuration, self.entitlement_context, instance.configuration,
        )
        runtime = self._runtimes[instance_id]
        report = AIcReadinessEvaluator.combine_runtime(static, runtime.readiness())
        self._readiness[(application_scope_id, instance_id)] = report
        return report

    def suspend_instance(self, instance_id: str, reason: str) -> None:
        runtime = self._runtimes.get(instance_id)
        if runtime is not None:
            runtime.suspend(reason)
        self.provisioning.registry.update(instance_id, state=AInProviderInstanceState.SUSPENDED)

    def deactivate_instance(self, instance_id: str, reason: str) -> None:
        runtime = self._runtimes.pop(instance_id, None)
        if runtime is not None:
            runtime.deactivate(reason)
            try:
                from .process import AIcProcessProviderRuntime
                if isinstance(runtime, AIcProcessProviderRuntime):
                    runtime.close()
            except Exception:
                # Deactivation already happened; endpoint cleanup/state transition must continue.
                pass
        self.endpoints.unregister(instance_id)
        for key in tuple(self._readiness):
            if key[1] == instance_id:
                self._readiness.pop(key, None)
        self._readiness_inputs.pop(instance_id, None)
        if self.observations is not None:
            self.observations.unregister_provider(instance_id)
        self.provisioning.registry.update(instance_id, state=AInProviderInstanceState.INACTIVE)


    def suspend(self, application_scope_id: str, descriptor: AIcComponentDescriptor, reason: str) -> AIcLifecycleStatus:
        for instance in self.provisioning.registry.find(component_id=descriptor.id):
            self.suspend_instance(instance.id, reason)
        return self._advance(application_scope_id, descriptor.id, AInLifecycleState.SUSPENDED, AInLifecycleStage.SUSPEND, (reason,))

    def deactivate(self, application_scope_id: str, descriptor: AIcComponentDescriptor, reason: str) -> AIcLifecycleStatus:
        for instance in self.provisioning.registry.find(component_id=descriptor.id):
            self.deactivate_instance(instance.id, reason)
        return self._advance(application_scope_id, descriptor.id, AInLifecycleState.DEACTIVATED, AInLifecycleStage.DEACTIVATE, (reason,))

    def revalidate_entitlements(self, application_scope_id: str, descriptor: AIcComponentDescriptor) -> tuple[str, ...]:
        """Refresh effective permission contexts without rebuilding the binding graph."""
        updated: list[str] = []
        component_context = self.entitlement.evaluate_component(
            descriptor, licensing_scopes=self.licensing_scopes, context=self.entitlement_context
        )
        for instance in self.provisioning.registry.find(component_id=descriptor.id):
            effective = self.entitlement.evaluate_component(
                descriptor, licensing_scopes=self.licensing_scopes,
                provider_instance=instance, context=self.entitlement_context
            )
            runtime = self._runtimes.get(instance.id)
            if runtime is not None:
                runtime.entitlement_changed(effective)
                updated.append(instance.id)
        if component_context.diagnostics:
            current = self.status(application_scope_id, descriptor.id)
            self._save(application_scope_id, descriptor.id, AIcLifecycleStatus(
                current.state, current.completed_stages, current.failed_stage,
                current.diagnostics + component_context.diagnostics,
            ))
        return tuple(updated)

    def runtime(self, instance_id: str) -> AIiProviderRuntime:
        return self._runtimes[instance_id]

    def runtime_instance_ids(self) -> tuple[str, ...]:
        return tuple(self._runtimes)

    def deactivate_all_runtimes(self, reason: str) -> tuple[str, ...]:
        ids = tuple(self._runtimes)
        for instance_id in reversed(ids):
            self.deactivate_instance(instance_id, reason)
        return ids


def _context(application_scope_id: str, descriptor: AIcComponentDescriptor) -> AIcLifecycleContext:
    return AIcLifecycleContext(application_scope_id, descriptor.id, descriptor.version)


def _status_to_dict(status: AIcLifecycleStatus) -> dict[str, object]:
    return {
        "state": status.state.value,
        "completed_stages": [stage.value for stage in status.completed_stages],
        "last_failure_stage": status.last_failure_stage.value if status.last_failure_stage else None,
        "diagnostics": list(status.diagnostics),
    }


def _status_from_dict(raw: Mapping[str, object]) -> AIcLifecycleStatus:
    return AIcLifecycleStatus(
        state=AInLifecycleState(str(raw["state"])),
        completed_stages=tuple(AInLifecycleStage(str(value)) for value in raw.get("completed_stages", ())),
        last_failure_stage=AInLifecycleStage(str(raw["last_failure_stage"])) if raw.get("last_failure_stage") else None,
        diagnostics=tuple(str(value) for value in raw.get("diagnostics", ())),
    )
