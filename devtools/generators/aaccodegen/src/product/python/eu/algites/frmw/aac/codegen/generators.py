from __future__ import annotations
import keyword
import re
from typing import Mapping
from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AInCapabilityOperationInteractionKind
from eu.algites.frmw.aac.core.schemas.registry import AIcRegisteredSchema, AIcSchemaRegistry

from .aic_python_capability_binding_generator import AIcPythonCapabilityBindingGenerator
from .aic_python_data_entity_binding_generator import AIcPythonDataEntityBindingGenerator

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
