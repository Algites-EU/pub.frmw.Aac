from __future__ import annotations

import keyword
import re
from typing import Mapping

from algites.lib.aac.coreintf.contracts import AIcCapabilityContract

from .schemas import AIcRegisteredSchema, AIcSchemaRegistry


def _pascal(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Capability"


def _identifier(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not candidate or candidate[0].isdigit():
        candidate = "_" + candidate
    if keyword.iskeyword(candidate):
        candidate += "_"
    return candidate


def _schema_type(schema: Mapping[str, object]) -> str:
    raw_type = schema.get("type")
    nullable = False
    if isinstance(raw_type, list):
        nullable = "null" in raw_type
        values = [value for value in raw_type if value != "null"]
        raw_type = values[0] if len(values) == 1 else None
    if "enum" in schema and raw_type in (None, "string"):
        result = "str"
    elif raw_type == "string":
        result = "str"
    elif raw_type == "integer":
        result = "int"
    elif raw_type == "number":
        result = "float"
    elif raw_type == "boolean":
        result = "bool"
    elif raw_type == "array":
        items = schema.get("items")
        item_type = _schema_type(items) if isinstance(items, Mapping) else "object"
        result = f"tuple[{item_type}, ...]"
    elif raw_type == "object":
        result = "Mapping[str, object]"
    else:
        result = "object"
    return f"{result} | None" if nullable else result


def _dto_source(class_name: str, registered: AIcRegisteredSchema) -> str:
    schema = registered.schema
    provenance = [
        f"    \"\"\"Generated from canonical AAC schema {registered.id}/{registered.version}.",
        f"",
        f"    Source: {registered.resource_name}",
        f"    Do not edit manually.\"\"\"",
        f"    __aac_source_id__ = {registered.id!r}",
        f"    __aac_source_version__ = {registered.version}",
        f"    __aac_source_resource__ = {registered.resource_name!r}",
    ]
    if schema.get("type") != "object":
        return "\n".join([
            "@dataclass(frozen=True, slots=True)",
            f"class {class_name}:",
            *provenance,
            f"    value: {_schema_type(schema)}",
            "",
            "    @classmethod",
            "    def from_mapping(cls, value):",
            "        return cls(value)",
            "",
            "    def to_mapping(self):",
            "        return self.value",
        ]) + "\n"
    properties = schema.get("properties", {})
    required = set(schema.get("required", ()))
    if not isinstance(properties, Mapping):
        properties = {}
    lines = ["@dataclass(frozen=True, slots=True)", f"class {class_name}:", *provenance]
    ordered = [key for key in properties if key in required] + [key for key in properties if key not in required]
    if not ordered:
        lines.append("    pass")
    for raw_name in ordered:
        raw_schema = properties[raw_name]
        field_type = _schema_type(raw_schema) if isinstance(raw_schema, Mapping) else "object"
        if raw_name not in required and "None" not in field_type:
            field_type += " | None"
        suffix = "" if raw_name in required else " = None"
        lines.append(f"    {_identifier(str(raw_name))}: {field_type}{suffix}")
    lines.extend(["", "    @classmethod", "    def from_mapping(cls, value):"])
    if ordered:
        args = ", ".join(f"{_identifier(str(name))}=value.get({str(name)!r})" for name in ordered)
        lines.append(f"        return cls({args})")
    else:
        lines.append("        return cls()")
    lines.extend(["", "    def to_mapping(self):"])
    if ordered:
        entries = ", ".join(f"{str(name)!r}: self.{_identifier(str(name))}" for name in ordered)
        lines.append(f"        return {{{entries}}}")
    else:
        lines.append("        return {}")
    return "\n".join(lines) + "\n"


class AIcPythonCapabilityBindingGenerator:
    """Generate Python ABC/DTO source from one canonical capability contract.

    The generated interface is a language binding, never a second source of truth.
    Authorization decorators are generated from the canonical operation metadata.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas

    def generate(self, contract: AIcCapabilityContract, *, canonical_resource: str | None = None) -> str:
        interface_name = f"AIig{_pascal(contract.capability.id.split('.')[-1])}_{contract.capability.version}"
        chunks = [
            "from __future__ import annotations",
            "",
            "from abc import ABC, abstractmethod",
            "from dataclasses import asdict, dataclass, is_dataclass",
            "from typing import Mapping",
            "from algites.lib.aac.coreintf.bindings import aig_authorization, aig_operation",
            "",
        ]
        dto_names: dict[tuple[str, str], str] = {}
        emitted_schema_types: set[tuple[str, int]] = set()
        for operation in contract.operations:
            for direction, resource in (("Input", operation.input_schema), ("Output", operation.output_schema)):
                if resource is None:
                    continue
                registered = self.schemas.get(resource)
                class_name = f"AIcgd{_pascal(registered.id)}_{registered.version}"
                dto_names[(operation.id, direction)] = class_name
                schema_identity = (registered.id, registered.version)
                if schema_identity not in emitted_schema_types:
                    chunks.extend([_dto_source(class_name, registered), ""])
                    emitted_schema_types.add(schema_identity)
        interface_lines = [
            f"class {interface_name}(ABC):",
            f"    \"\"\"Generated from canonical AAC capability contract {contract.capability.id}/{contract.capability.version}.\"\"\"",
            f"    __aac_source_id__ = {contract.capability.id!r}",
            f"    __aac_source_version__ = {contract.capability.version}",
            f"    __aac_source_resource__ = {canonical_resource!r}",
            f"    __aac_capability_id__ = {contract.capability.id!r}",
            f"    __aac_capability_version__ = {contract.capability.version}",
            "",
        ]
        chunks.extend(interface_lines)
        for operation in contract.operations:
            input_name = dto_names.get((operation.id, "Input"), "Mapping[str, object]")
            output_name = dto_names.get((operation.id, "Output"), "object")
            auth = operation.authorization
            chunks.append(f"    @aig_operation({operation.id!r})")
            if auth is not None:
                chunks.append(f"    @aig_authorization(all_of={auth.all_of!r}, any_of={auth.any_of!r})")
            chunks.extend([
                "    @abstractmethod",
                f"    def {_identifier(operation.id)}(self, request: {input_name}) -> {output_name}: ...",
                "",
            ])
        chunks.extend([
            "    def __aac_invoke__(self, operation_id: str, arguments: Mapping[str, object]):",
        ])
        for index, operation in enumerate(contract.operations):
            prefix = "if" if index == 0 else "elif"
            input_name = dto_names.get((operation.id, "Input"))
            method_name = _identifier(operation.id)
            chunks.append(f"        {prefix} operation_id == {operation.id!r}:")
            if input_name:
                chunks.append(f"            request = {input_name}.from_mapping(dict(arguments))")
            else:
                chunks.append("            request = dict(arguments)")
            chunks.append(f"            result = self.{method_name}(request)")
            chunks.append('            return result.to_mapping() if hasattr(result, "to_mapping") else (asdict(result) if is_dataclass(result) else result)')
        chunks.extend([
            "        raise KeyError(operation_id)",
            "",
        ])
        return "\n".join(chunks)
