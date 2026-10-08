from __future__ import annotations

from eu.algites.frmw.aac.core.capability.aiig_capability_contract_1 import AIigCapabilityContract_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_authorization_permissions_items_1 import AIigCapabilityContractAuthorizationPermissionsItems_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_definition_authorization_requirement_1 import AIigCapabilityContractDefinitionAuthorizationRequirement_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_capability_1 import AIigCapabilityContractCapability_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_operations_items_1 import AIigCapabilityContractOperationsItems_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_operations_items_interactions_items_1 import AIigCapabilityContractOperationsItemsInteractionsItems_1
from eu.algites.frmw.aac.core.capability.aiig_capability_contract_definition_schema_ref_1 import AIigCapabilityContractDefinitionSchemaRef_1
import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping
import yaml
from eu.algites.frmw.aac.core.capability.api import (
    AIcAuthorizationPermissionDescriptor,
    AIcCapabilityContract,
    AInCapabilityOperationInteractionKind,
    AIcCapabilityOperationInteraction,
    AIcSchemaRef,
    AIcCapabilityGroup,
    AIcCapabilityOperation,
    AIcCapabilityRef,
    AIcOperationAuthorizationRequirement,
)
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.implementation.errors import AIxContractAdmissionError, AIxContractConflictError, AIxContractNegotiationError
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

from .aic_admitted_capability_group import AIcAdmittedCapabilityGroup
from .aic_capability_group_catalog import AIcCapabilityGroupCatalog
from .aic_admitted_contract import AIcAdmittedContract
from .aic_active_contract_catalog import AIcActiveContractCatalog

def _parse_contract(raw: Mapping[str, Any], source: str) -> AIcCapabilityContract:
    try:
        capability = raw[AIigCapabilityContract_1.SCHEMA_FIELD_NAME__CAPABILITY]
        operations = raw[AIigCapabilityContract_1.SCHEMA_FIELD_NAME__OPERATIONS]
        if not isinstance(capability, Mapping) or not isinstance(operations, list):
            raise TypeError("capability must be a mapping and operations must be a list")
        permissions = tuple(
            AIcAuthorizationPermissionDescriptor(
                id=str(item[AIigCapabilityContractAuthorizationPermissionsItems_1.SCHEMA_FIELD_NAME__ID]),
                name=normalize_display_text(item.get(AIigCapabilityContractAuthorizationPermissionsItems_1.SCHEMA_FIELD_NAME__NAME)),
                description=normalize_display_text(item.get(AIigCapabilityContractAuthorizationPermissionsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                metadata=dict(item.get(AIigCapabilityContractAuthorizationPermissionsItems_1.SCHEMA_FIELD_NAME__METADATA, {})),
            )
            for item in raw.get(AIigCapabilityContract_1.SCHEMA_FIELD_NAME__AUTHORIZATION_PERMISSIONS, ())
        )
        parsed_ops = []
        for item in operations:
            if not isinstance(item, Mapping):
                raise TypeError("operation must be a mapping")
            raw_authorization = item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__AUTHORIZATION)
            authorization = None
            if raw_authorization is not None:
                if not isinstance(raw_authorization, Mapping):
                    raise TypeError("operation authorization must be a mapping")
                authorization = AIcOperationAuthorizationRequirement(
                    all_of=tuple(str(v) for v in raw_authorization.get(AIigCapabilityContractDefinitionAuthorizationRequirement_1.SCHEMA_FIELD_NAME__ALL_OF, ())),
                    any_of=tuple(str(v) for v in raw_authorization.get(AIigCapabilityContractDefinitionAuthorizationRequirement_1.SCHEMA_FIELD_NAME__ANY_OF, ())),
                )
            raw_interactions = item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__INTERACTIONS, [])
            if not isinstance(raw_interactions, list):
                raise TypeError("operation interactions must be a list")
            interactions = []
            for raw_interaction in raw_interactions:
                if not isinstance(raw_interaction, Mapping):
                    raise TypeError("operation interaction must be a mapping")
                raw_schema = raw_interaction.get(AIigCapabilityContractOperationsItemsInteractionsItems_1.SCHEMA_FIELD_NAME__SCHEMA)
                if not isinstance(raw_schema, Mapping):
                    raise TypeError("operation interaction schema must be a mapping")
                interactions.append(AIcCapabilityOperationInteraction(
                    kind=AInCapabilityOperationInteractionKind(str(raw_interaction[AIigCapabilityContractOperationsItemsInteractionsItems_1.SCHEMA_FIELD_NAME__KIND])),
                    schema=AIcSchemaRef(str(raw_schema[AIigCapabilityContractDefinitionSchemaRef_1.SCHEMA_FIELD_NAME__ID]), int(raw_schema[AIigCapabilityContractDefinitionSchemaRef_1.SCHEMA_FIELD_NAME__VERSION])),
                ))
            parsed_ops.append(AIcCapabilityOperation(
                id=str(item[AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__ID]),
                interactions=tuple(interactions),
                name=normalize_display_text(item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__NAME)),
                description=normalize_display_text(item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                authorization=authorization,
                sensitive_input_paths=tuple(str(v) for v in item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__SENSITIVE_INPUT_PATHS, ())),
                sensitive_output_paths=tuple(str(v) for v in item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__SENSITIVE_OUTPUT_PATHS, ())),
                metadata=dict(item.get(AIigCapabilityContractOperationsItems_1.SCHEMA_FIELD_NAME__METADATA, {})),
            ))
        raw_binding_qualifiers_schema = raw.get(AIigCapabilityContract_1.SCHEMA_FIELD_NAME__BINDING_QUALIFIERS_SCHEMA)
        binding_qualifiers_schema = None
        if raw_binding_qualifiers_schema is not None:
            if not isinstance(raw_binding_qualifiers_schema, Mapping):
                raise TypeError("binding qualifiers schema must be a mapping")
            binding_qualifiers_schema = AIcSchemaRef(
                str(raw_binding_qualifiers_schema[AIigCapabilityContractDefinitionSchemaRef_1.SCHEMA_FIELD_NAME__ID]), int(raw_binding_qualifiers_schema[AIigCapabilityContractDefinitionSchemaRef_1.SCHEMA_FIELD_NAME__VERSION])
            )
        return AIcCapabilityContract(
            capability=AIcCapabilityRef(str(capability[AIigCapabilityContractCapability_1.SCHEMA_FIELD_NAME__ID]), int(capability[AIigCapabilityContractCapability_1.SCHEMA_FIELD_NAME__VERSION])),
            group_id=str(capability[AIigCapabilityContractCapability_1.SCHEMA_FIELD_NAME__GROUP_ID]),
            operations=tuple(parsed_ops),
            binding_qualifiers_schema=binding_qualifiers_schema,
            authorization_permissions=permissions,
            name=normalize_display_text(capability.get(AIigCapabilityContractCapability_1.SCHEMA_FIELD_NAME__NAME)),
            description=normalize_display_text(capability.get(AIigCapabilityContractCapability_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
            metadata=dict(raw.get(AIigCapabilityContract_1.SCHEMA_FIELD_NAME__METADATA, {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AIxContractAdmissionError(f"invalid capability contract in {source}: {exc}") from exc

def _canonical_contract(contract: AIcCapabilityContract) -> bytes:
    return json.dumps(asdict(contract), sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
