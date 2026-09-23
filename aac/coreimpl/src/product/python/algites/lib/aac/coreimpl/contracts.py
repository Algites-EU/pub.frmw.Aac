from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

import yaml

from algites.lib.aac.coreintf.contracts import (
    AIcAuthorizationPermissionDescriptor,
    AIcCapabilityContract,
    AIcCapabilityGroup,
    AIcCapabilityOperation,
    AIcCapabilityRef,
    AIcOperationAuthorizationRequirement,
)
from algites.lib.aac.coreintf.presentation import normalize_display_text

from .errors import AIxContractAdmissionError, AIxContractConflictError, AIxContractNegotiationError
from .schema_resources import read_core_schema
from .schemas import AIcSchemaRegistry


@dataclass(frozen=True, slots=True)
class AIcAdmittedCapabilityGroup:
    group: AIcCapabilityGroup
    source: str
    fingerprint: str


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
        names = (
            "definitions/aac-capability-group-data-entities_1.yml",
            "definitions/aac-capability-group-data-entity-loading_1.yml",
            "definitions/aac-capability-group-data-entity-storing_1.yml",
            "definitions/aac-capability-group-data-entity-storage-management_1.yml",
            "definitions/aac-capability-group-runtime_1.yml",
            "definitions/aac-capability-group-runtime-observation_1.yml",
        )
        return tuple(self.admit_package_resource("algites.lib.aac.coreintf.contracts", name) for name in names)

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


@dataclass(frozen=True, slots=True)
class AIcAdmittedContract:
    contract: AIcCapabilityContract
    source: str
    fingerprint: str


class AIcActiveContractCatalog:
    def __init__(self, schema_registry: AIcSchemaRegistry | None = None) -> None:
        self.schema_registry = schema_registry or AIcSchemaRegistry()
        self.groups = AIcCapabilityGroupCatalog(self.schema_registry)
        self._contracts: dict[tuple[str, int], AIcAdmittedContract] = {}
        try:
            self.schema_registry.get("capability-contract_1.json")
        except KeyError:
            self.schema_registry.register_text(
                "capability-contract_1.json", read_core_schema("capability-contract_1.json"), source="AAC core schema"
            )

    def admit(self, contract: AIcCapabilityContract, *, source: str = "<memory>") -> AIcAdmittedContract:
        if not self.groups.contains(contract.group_id):
            raise AIxContractAdmissionError(
                f"capability {contract.capability.id!r}/{contract.capability.version} references unknown group {contract.group_id!r}"
            )
        canonical = _canonical_contract(contract)
        fingerprint = hashlib.sha256(canonical).hexdigest()
        key = (contract.capability.id, contract.capability.version)
        existing = self._contracts.get(key)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise AIxContractConflictError(
                    f"conflicting canonical definitions for {key[0]}/{key[1]} from {existing.source!r} and {source!r}"
                )
            return existing
        admitted = AIcAdmittedContract(contract, source, fingerprint)
        self._contracts[key] = admitted
        return admitted

    def admit_text(self, text: str, *, source: str = "<memory>") -> AIcAdmittedContract:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxContractAdmissionError(f"invalid contract YAML in {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxContractAdmissionError(f"contract {source} must be a mapping")
        try:
            self.schema_registry.normalize("capability-contract_1.json", raw, apply_defaults=False)
        except Exception as exc:
            raise AIxContractAdmissionError(f"contract schema validation failed for {source}: {exc}") from exc
        return self.admit(_parse_contract(raw, source), source=source)

    def admit_file(self, path: str | Path) -> AIcAdmittedContract:
        path = Path(path)
        return self.admit_text(path.read_text(encoding="utf-8"), source=str(path))

    def admit_package_resource(self, package: str, resource_name: str) -> AIcAdmittedContract:
        try:
            text = resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise AIxContractAdmissionError(f"cannot read contract {resource_name!r} from package {package!r}") from exc
        return self.admit_text(text, source=f"{package}:{resource_name}")

    def admit_builtin_contracts(self) -> tuple[AIcAdmittedContract, ...]:
        self.groups.admit_builtin_groups()
        schema_resources = (
            "observation-input_1.json", "observation-output_1.json",
            "data-entity-get-record-request_1.json", "data-entity-get-record-result_1.json",
            "data-entity-query-records-request_1.json", "data-entity-query-records-result_1.json",
            "data-entity-apply-direct-record-changes-request_1.json",
            "data-entity-apply-direct-record-changes-result_1.json",
            "data-entity-inspect-storage-support-request_1.json",
            "data-entity-inspect-storage-support-result_1.json",
            "data-entity-ensure-storage-support-request_1.json",
            "data-entity-ensure-storage-support-result_1.json",
            "data-entity-retire-storage-support-request_1.json",
            "data-entity-retire-storage-support-result_1.json",
        )
        for resource_name in schema_resources:
            try:
                self.schema_registry.get(resource_name)
            except KeyError:
                self.schema_registry.register_text(resource_name, read_core_schema(resource_name), source="AAC core schema")
        contract_resources = (
            "definitions/aac-capability-observation_1.yml",
            "definitions/aac-data-entity-get-record_1.yml",
            "definitions/aac-data-entity-query-records_1.yml",
            "definitions/aac-data-entity-apply-direct-record-changes_1.yml",
            "definitions/aac-data-entity-inspect-storage-support_1.yml",
            "definitions/aac-data-entity-ensure-storage-support_1.yml",
            "definitions/aac-data-entity-retire-storage-support_1.yml",
        )
        return tuple(
            self.admit_package_resource("algites.lib.aac.coreintf.contracts", resource_name)
            for resource_name in contract_resources
        )

    def get(self, capability_id: str, version: int) -> AIcCapabilityContract:
        return self._contracts[(capability_id, version)].contract

    def contains(self, capability_id: str, version: int) -> bool:
        return (capability_id, version) in self._contracts

    def versions(self, capability_id: str) -> tuple[int, ...]:
        return tuple(sorted(version for (candidate_id, version) in self._contracts if candidate_id == capability_id))

    def negotiate(
        self,
        capability_id: str,
        consumer_versions: tuple[int, ...] | list[int],
        provider_versions: tuple[int, ...] | list[int],
        lifecycle_allowed_versions: tuple[int, ...] | list[int] | None = None,
    ) -> int:
        consumer = set(consumer_versions)
        provider = set(provider_versions)
        active = set(self.versions(capability_id))
        valid = consumer & provider & active
        if lifecycle_allowed_versions is not None:
            valid &= set(lifecycle_allowed_versions)
        if not valid:
            raise AIxContractNegotiationError(
                f"no negotiable version for {capability_id!r}: consumer={sorted(consumer)}, provider={sorted(provider)}, active={sorted(active)}"
            )
        return max(valid)


    def snapshot(self):
        return (copy.deepcopy(self._contracts), self.groups.snapshot())

    def restore(self, snapshot) -> None:
        self._contracts = copy.deepcopy(snapshot[0])
        self.groups.restore(snapshot[1])

    def operation(self, capability_id: str, version: int, operation_id: str) -> AIcCapabilityOperation:
        return self.get(capability_id, version).operation(operation_id)


def _parse_contract(raw: Mapping[str, Any], source: str) -> AIcCapabilityContract:
    try:
        capability = raw["capability"]
        operations = raw["operations"]
        if not isinstance(capability, Mapping) or not isinstance(operations, list):
            raise TypeError("capability must be a mapping and operations must be a list")
        permissions = tuple(
            AIcAuthorizationPermissionDescriptor(
                id=str(item["id"]),
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in raw.get("authorization_permissions", ())
        )
        parsed_ops = []
        for item in operations:
            if not isinstance(item, Mapping):
                raise TypeError("operation must be a mapping")
            raw_authorization = item.get("authorization")
            authorization = None
            if raw_authorization is not None:
                if not isinstance(raw_authorization, Mapping):
                    raise TypeError("operation authorization must be a mapping")
                authorization = AIcOperationAuthorizationRequirement(
                    all_of=tuple(str(v) for v in raw_authorization.get("all_of", ())),
                    any_of=tuple(str(v) for v in raw_authorization.get("any_of", ())),
                )
            parsed_ops.append(AIcCapabilityOperation(
                id=str(item["id"]),
                input_type=str(item.get("input", "Object")),
                output_type=str(item.get("output", "Object")),
                input_schema=str(item["input_schema"]) if item.get("input_schema") is not None else None,
                output_schema=str(item["output_schema"]) if item.get("output_schema") is not None else None,
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
                authorization=authorization,
                sensitive_input_paths=tuple(str(v) for v in item.get("sensitive_input_paths", ())),
                sensitive_output_paths=tuple(str(v) for v in item.get("sensitive_output_paths", ())),
                metadata=dict(item.get("metadata", {})),
            ))
        return AIcCapabilityContract(
            capability=AIcCapabilityRef(str(capability["id"]), int(capability["version"])),
            group_id=str(capability["group_id"]),
            operations=tuple(parsed_ops),
            authorization_permissions=permissions,
            name=normalize_display_text(capability.get("name")),
            description=normalize_display_text(capability.get("description")),
            metadata=dict(raw.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AIxContractAdmissionError(f"invalid capability contract in {source}: {exc}") from exc

def _canonical_contract(contract: AIcCapabilityContract) -> bytes:
    return json.dumps(asdict(contract), sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
