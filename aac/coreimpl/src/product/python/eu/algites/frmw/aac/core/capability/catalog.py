from __future__ import annotations
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
        capability = raw["Capability"]
        operations = raw["Operations"]
        if not isinstance(capability, Mapping) or not isinstance(operations, list):
            raise TypeError("capability must be a mapping and operations must be a list")
        permissions = tuple(
            AIcAuthorizationPermissionDescriptor(
                id=str(item["Id"]),
                name=normalize_display_text(item.get("Name")),
                description=normalize_display_text(item.get("Description")),
                metadata=dict(item.get("Metadata", {})),
            )
            for item in raw.get("AuthorizationPermissions", ())
        )
        parsed_ops = []
        for item in operations:
            if not isinstance(item, Mapping):
                raise TypeError("operation must be a mapping")
            raw_authorization = item.get("Authorization")
            authorization = None
            if raw_authorization is not None:
                if not isinstance(raw_authorization, Mapping):
                    raise TypeError("operation authorization must be a mapping")
                authorization = AIcOperationAuthorizationRequirement(
                    all_of=tuple(str(v) for v in raw_authorization.get("AllOf", ())),
                    any_of=tuple(str(v) for v in raw_authorization.get("AnyOf", ())),
                )
            raw_interactions = item.get("Interactions", [])
            if not isinstance(raw_interactions, list):
                raise TypeError("operation interactions must be a list")
            interactions = []
            for raw_interaction in raw_interactions:
                if not isinstance(raw_interaction, Mapping):
                    raise TypeError("operation interaction must be a mapping")
                raw_schema = raw_interaction.get("Schema")
                if not isinstance(raw_schema, Mapping):
                    raise TypeError("operation interaction schema must be a mapping")
                interactions.append(AIcCapabilityOperationInteraction(
                    kind=AInCapabilityOperationInteractionKind(str(raw_interaction["Kind"])),
                    schema=AIcSchemaRef(str(raw_schema["Id"]), int(raw_schema["Version"])),
                ))
            parsed_ops.append(AIcCapabilityOperation(
                id=str(item["Id"]),
                interactions=tuple(interactions),
                name=normalize_display_text(item.get("Name")),
                description=normalize_display_text(item.get("Description")),
                authorization=authorization,
                sensitive_input_paths=tuple(str(v) for v in item.get("SensitiveInputPaths", ())),
                sensitive_output_paths=tuple(str(v) for v in item.get("SensitiveOutputPaths", ())),
                metadata=dict(item.get("Metadata", {})),
            ))
        return AIcCapabilityContract(
            capability=AIcCapabilityRef(str(capability["Id"]), int(capability["Version"])),
            group_id=str(capability["GroupId"]),
            operations=tuple(parsed_ops),
            authorization_permissions=permissions,
            name=normalize_display_text(capability.get("Name")),
            description=normalize_display_text(capability.get("Description")),
            metadata=dict(raw.get("Metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AIxContractAdmissionError(f"invalid capability contract in {source}: {exc}") from exc

def _canonical_contract(contract: AIcCapabilityContract) -> bytes:
    return json.dumps(asdict(contract), sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
