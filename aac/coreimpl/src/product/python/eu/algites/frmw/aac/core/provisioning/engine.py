from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.instances.api import AInProviderInstanceState
from eu.algites.frmw.aac.core.lifecycle.api import AIiProvisioningHook, AIiUnprovisioningHook
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.provisioning.api import AIcProvisionContext, AIcProvisioningResult
from eu.algites.frmw.aac.core.bindings.store import AIcBindingStore
from eu.algites.frmw.aac.core.implementation.errors import AIxProvisioningError, AIxSchemaValidationError
from eu.algites.frmw.aac.core.instances.registry import AIcProviderInstanceRegistry, instance_to_dict
from eu.algites.frmw.aac.core.loading.symbols import load_class
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.persistence.state_store_support import state_delete_mutation, state_put_mutation
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

from .aic_provisioning_outcome import AIcProvisioningOutcome
from .aic_provisioning_engine import AIcProvisioningEngine

_COMPONENT_STATE_NAMESPACE = "aac.component-provisioning"

_PROVIDER_NAMESPACE = "aac.provider-instances"
