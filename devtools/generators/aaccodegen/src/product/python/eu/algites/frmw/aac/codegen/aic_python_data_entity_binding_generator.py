from __future__ import annotations
import keyword
import re
from typing import Mapping
from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AInCapabilityOperationInteractionKind
from eu.algites.frmw.aac.core.schemas.registry import AIcRegisteredSchema, AIcSchemaRegistry

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

class AIcPythonDataEntityBindingGenerator:
    """Generate one versioned Python Data Entity view interface and codec from canonical JSON Schema.

    Version suffixes are part of the generated method names so one current implementation object
    can implement several historical schema views without method-signature collisions.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas

    def generate(self, schema_id: str, version: int) -> str:
        registered = self.schemas.get_identity(schema_id, version)
        schema = registered.schema
        if schema.get("type") != "object":
            raise ValueError("Data Entity view generation requires an object JSON schema")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            properties = {}
        required = set(schema.get("required", ()))
        stem = _pascal(schema_id.split(".")[-1])
        interface_name = f"AIig{stem}_{version}"
        codec_name = f"AIcg{stem}Codec_{version}"
        lines = [
            "from __future__ import annotations",
            "",
            "from abc import abstractmethod",
            "from typing import Mapping",
            "from eu.algites.frmw.aac.core.dataentity.api import AIcDataEntityType, AIiDataEntityCodec, AIiDataEntityView",
            "",
            f"class {interface_name}(AIiDataEntityView):",
            f"    \"\"\"Generated Data Entity view for {schema_id}/{version}.\"\"\"",
            f"    __aac_source_id__ = {schema_id!r}",
            f"    __aac_source_version__ = {version}",
            f"    __aac_source_resource__ = {registered.resource_name!r}",
            "",
        ]
        if not properties:
            lines.append("    pass")
        for raw_name, raw_schema in properties.items():
            name = _identifier(str(raw_name))
            value_type = _schema_type(raw_schema) if isinstance(raw_schema, Mapping) else "object"
            if raw_name not in required and "None" not in value_type:
                value_type += " | None"
            lines.extend([
                "    @abstractmethod",
                f"    def get_{name}_{version}(self) -> {value_type}: ...",
                "",
                "    @abstractmethod",
                f"    def set_{name}_{version}(self, value: {value_type}) -> None: ...",
                "",
            ])
        lines.extend([
            f"class {codec_name}(AIiDataEntityCodec[{interface_name}]):",
            f"    schema_id = {schema_id!r}",
            f"    schema_version = {version}",
            f"    view_type = {interface_name}",
            "",
            f"    def serialize(self, value: {interface_name}) -> Mapping[str, object]:",
            "        result: dict[str, object] = {}",
        ])
        for raw_name in properties:
            name = _identifier(str(raw_name))
            if raw_name in required:
                lines.append(f"        result[{str(raw_name)!r}] = value.get_{name}_{version}()")
            else:
                lines.extend([
                    f"        value_{name} = value.get_{name}_{version}()",
                    f"        if value_{name} is not None:",
                    f"            result[{str(raw_name)!r}] = value_{name}",
                ])
        lines.extend([
            "        return result",
            "",
            f"    def deserialize_into(self, payload: Mapping[str, object], target: {interface_name}) -> None:",
        ])
        if properties:
            for raw_name in properties:
                name = _identifier(str(raw_name))
                lines.append(f"        target.set_{name}_{version}(payload.get({str(raw_name)!r}))")
        else:
            lines.append("        return None")
        lines.extend([
            "",
            f"{interface_name}.TYPE = AIcDataEntityType({schema_id!r}, {version}, {interface_name})",
            "",
        ])
        return "\n".join(lines)
