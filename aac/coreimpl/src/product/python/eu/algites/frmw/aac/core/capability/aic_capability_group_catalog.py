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

class AIcCapabilityGroupCatalog:
    def __init__(self, schema_registry: AIcSchemaRegistry | None = None) -> None:
        self.schema_registry = schema_registry or AIcSchemaRegistry()
        self._groups: dict[str, AIcAdmittedCapabilityGroup] = {}
        try:
            self.schema_registry.get("capability-group_1.json")
        except KeyError:
            self.schema_registry.register_text(
                "capability-group_1.json", read_core_schema("capability-group_1.json"), source="AAC core schema"
            )

    def admit(self, group: AIcCapabilityGroup, *, source: str = "<memory>") -> AIcAdmittedCapabilityGroup:
        if group.parent_group_id is not None and group.parent_group_id not in self._groups:
            raise AIxContractAdmissionError(
                f"capability group {group.id!r} references unknown parent group {group.parent_group_id!r}"
            )
        canonical = json.dumps(asdict(group), sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
        fingerprint = hashlib.sha256(canonical).hexdigest()
        existing = self._groups.get(group.id)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise AIxContractConflictError(
                    f"conflicting canonical capability-group definitions for {group.id!r} from "
                    f"{existing.source!r} and {source!r}"
                )
            return existing
        admitted = AIcAdmittedCapabilityGroup(group, source, fingerprint)
        self._groups[group.id] = admitted
        return admitted

    def admit_text(self, text: str, *, source: str = "<memory>") -> AIcAdmittedCapabilityGroup:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxContractAdmissionError(f"invalid capability-group YAML in {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxContractAdmissionError(f"capability-group {source} must be a mapping")
        try:
            self.schema_registry.normalize("capability-group_1.json", raw, apply_defaults=False)
            item = raw["group"]
            group = AIcCapabilityGroup(
                id=str(item["id"]),
                parent_group_id=str(item["parent_group_id"]) if item.get("parent_group_id") is not None else None,
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
                metadata=dict(item.get("metadata", {})),
            )
        except Exception as exc:
            raise AIxContractAdmissionError(f"capability-group schema validation failed for {source}: {exc}") from exc
        return self.admit(group, source=source)

    def admit_package_resource(self, package: str, resource_name: str) -> AIcAdmittedCapabilityGroup:
        try:
            text = resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise AIxContractAdmissionError(
                f"cannot read capability group {resource_name!r} from package {package!r}"
            ) from exc
        return self.admit_text(text, source=f"{package}:{resource_name}")

    def admit_builtin_groups(self) -> tuple[AIcAdmittedCapabilityGroup, ...]:
        resources_to_admit = (
            ("eu.algites.frmw.aac.core.dataentity", "definitions/aac-capability-group-data-entities_1.yml"),
            ("eu.algites.frmw.aac.core.dataentity", "definitions/aac-capability-group-data-entity-loading_1.yml"),
            ("eu.algites.frmw.aac.core.dataentity", "definitions/aac-capability-group-data-entity-storing_1.yml"),
            ("eu.algites.frmw.aac.core.dataentity", "definitions/aac-capability-group-data-entity-storage-management_1.yml"),
            ("eu.algites.frmw.aac.core.dataentity", "definitions/aac-capability-group-data-entity-storage-backup-restore_1.yml"),
            ("eu.algites.frmw.aac.core.runtime", "definitions/aac-capability-group-runtime_1.yml"),
            ("eu.algites.frmw.aac.core.observation", "definitions/aac-capability-group-runtime-observation_1.yml"),
        )
        return tuple(self.admit_package_resource(package, resource) for package, resource in resources_to_admit)

    def get(self, group_id: str) -> AIcCapabilityGroup:
        return self._groups[group_id].group

    def contains(self, group_id: str) -> bool:
        return group_id in self._groups

    def all(self) -> tuple[AIcCapabilityGroup, ...]:
        return tuple(admitted.group for admitted in self._groups.values())

    def snapshot(self):
        return copy.deepcopy(self._groups)

    def restore(self, snapshot) -> None:
        self._groups = copy.deepcopy(snapshot)
