from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.configuration.api import AInConfigurationTargetKind, AIcConfigurationTarget, AIcEffectiveConfiguration
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementContext, AIcResolvedEntitlementLicensingScope
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AInProviderInstanceState
from eu.algites.frmw.aac.core.lifecycle.api import AIcLifecycleContext, AInLifecycleStage, AInLifecycleState, AIcLifecycleStatus, AIiValidationHook, AIcValidationResult
from eu.algites.frmw.aac.core.observation.api import AIiObservationProvider
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime
from eu.algites.frmw.aac.core.readiness.api import AIcProviderReadiness, AIcComponentReadiness, AIcCapabilityReadiness
from eu.algites.frmw.aac.core.verification.api import AIiPackageVerifier, AIcVerificationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.descriptor.loader import AIcDiscoveredComponent
from eu.algites.frmw.aac.core.entitlement.runtime import AIcEntitlementManager
from eu.algites.frmw.aac.core.implementation.errors import AIxLifecycleError
from eu.algites.frmw.aac.core.invocation.api import AIiCapabilityEndpoint
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcCapabilityHandleFactory, AIcEndpointRegistry
from eu.algites.frmw.aac.core.loading.symbols import load_class
from eu.algites.frmw.aac.core.observation.dispatcher import AIcEndpointObservationProvider, AIcObservationDispatcher, OBSERVATION_CAPABILITY_ID
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.provisioning.engine import AIcProvisioningEngine
from eu.algites.frmw.aac.core.resolution.bindings import validate_instance_dag
from eu.algites.frmw.aac.core.runtime.provider_instantiation import instantiate_provider
from eu.algites.frmw.aac.core.readiness.evaluator import AIcReadinessEvaluator
from eu.algites.frmw.aac.core.verification.python_package import AIcPythonPackageVerifier

@dataclass(frozen=True, slots=True)
class AIcActivationOutcome:
    status: AIcLifecycleStatus
    runtime_instance_ids: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()
