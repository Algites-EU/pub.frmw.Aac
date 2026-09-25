from __future__ import annotations
from dataclasses import dataclass
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor, AIcConsumerRequirementDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcBindingPreference, AIcProviderInstance
from eu.algites.frmw.aac.core.bindings.store import AIcBindingPreferenceStore, AIcBindingStore
from eu.algites.frmw.aac.core.implementation.errors import AIxBindingResolutionError
from eu.algites.frmw.aac.core.instances.registry import AIcProviderInstanceRegistry
from eu.algites.frmw.aac.core.resolution.bindings import AIcBindingResolver, validate_instance_dag

@dataclass(frozen=True, slots=True)
class AIcResolvedApplicationGraph:
    bindings: tuple[AIcBinding, ...]
    provider_first_order: tuple[str, ...]
