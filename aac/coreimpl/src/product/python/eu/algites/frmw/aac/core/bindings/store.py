from __future__ import annotations
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcBindingPreference
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.persistence.state_store_support import state_delete_mutation, state_put_mutation
from eu.algites.frmw.aac.core.resolution.bindings import validate_instance_dag

from .aic_binding_store import AIcBindingStore
from .aic_binding_preference_store import AIcBindingPreferenceStore

_BINDING_NAMESPACE = "aac.bindings"

_PREFERENCE_NAMESPACE = "aac.binding-preferences"

def _binding_to_dict(binding: AIcBinding) -> dict[str, object]:
    return {
        "consumer_instance_id": binding.consumer_instance_id,
        "requirement_id": binding.requirement_id,
        "provider_instance_id": binding.provider_instance_id,
        "capability_id": binding.capability_id,
        "capability_version": binding.capability_version,
    }

def _binding_from_dict(raw) -> AIcBinding:
    return AIcBinding(
        str(raw["consumer_instance_id"]), str(raw["requirement_id"]), str(raw["provider_instance_id"]),
        str(raw["capability_id"]), int(raw["capability_version"]),
    )
