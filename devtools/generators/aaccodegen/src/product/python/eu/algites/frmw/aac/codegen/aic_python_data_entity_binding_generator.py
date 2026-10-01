from __future__ import annotations

from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry
from eu.algites.tool.codegen.defs.ain_definition_kind import AInDefinitionKind
from eu.algites.tool.codegen.defs.ain_value_kind import AInValueKind

from .aic_general_defs_inline_dto_adapter import AIcGeneralDefsInlineDtoAdapter


def _python_type(prop) -> str:
    if prop.reference is not None:
        result = "object"
    elif prop.value_kind is AInValueKind.STRING:
        result = "str"
    elif prop.value_kind is AInValueKind.INTEGER:
        result = "int"
    elif prop.value_kind is AInValueKind.NUMBER:
        result = "float"
    elif prop.value_kind is AInValueKind.BOOLEAN:
        result = "bool"
    elif prop.value_kind is AInValueKind.ARRAY:
        item_type = {
            AInValueKind.STRING: "str",
            AInValueKind.INTEGER: "int",
            AInValueKind.NUMBER: "float",
            AInValueKind.BOOLEAN: "bool",
        }.get(prop.item_value_kind, "object")
        result = f"tuple[{item_type}, ...]"
    elif prop.value_kind is AInValueKind.OBJECT:
        result = "Mapping[str, object]"
    else:
        result = "object"
    return f"{result} | None" if prop.nullable else result


def _doc(value: str | None, fallback: str) -> str:
    return " ".join((value or fallback).replace('"""', '\\"\\"\\"').split())


class AIcPythonDataEntityBindingGenerator:
    """Generate an AAC Data Entity view and codec over the shared canonical-definition model.

    JSON definition parsing, definition identity, property normalization, and naming are delegated
    to ``pub.tool.General``. Only the versioned Data Entity view and codec semantics remain AAC-
    specific here.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas
        self._defs = AIcGeneralDefsInlineDtoAdapter()

    def generate(self, schema_id: str, version: int) -> str:
        registered = self.schemas.get_identity(schema_id, version)
        definition = self._defs.normalize(registered)
        if definition.kind is not AInDefinitionKind.OBJECT:
            raise ValueError("Data Entity view generation requires an object JSON definition")
        interface_name = self._defs.interface_type_name(definition)
        version_suffix = f"_{version}"
        interface_stem = interface_name[len("AIig"):-len(version_suffix)] if interface_name.endswith(version_suffix) else interface_name[len("AIig"):]
        codec_name = f"AIcg{interface_stem}Codec_{version}"
        definition_doc = _doc(
            definition.description,
            f"Generated Data Entity view for canonical definition {schema_id}/{version}.",
        )
        lines = [
            "from __future__ import annotations",
            "",
            "from abc import abstractmethod",
            "from typing import Mapping",
            "from eu.algites.frmw.aac.core.dataentity.api import AIcDataEntityType, AIiDataEntityCodec, AIiDataEntityView",
            "",
            f"class {interface_name}(AIiDataEntityView):",
            f'    """{definition_doc}',
            "",
            f"    Generated from canonical definition {schema_id}/{version}. Source: {registered.resource_name}. Do not edit manually.",
            '    """',
            f"    __aac_source_id__ = {schema_id!r}",
            f"    __aac_source_version__ = {version}",
            f"    __aac_source_resource__ = {registered.resource_name!r}",
            "",
        ]
        if not definition.properties:
            lines.append("    pass")
        for prop in definition.properties:
            name = self._defs.property_name(prop.source_name)
            value_type = _python_type(prop)
            if not prop.required and "None" not in value_type:
                value_type += " | None"
            property_doc = _doc(prop.description, f"Canonical property {prop.source_name}.")
            lines.extend([
                "    @abstractmethod",
                f"    def get_{name}_{version}(self) -> {value_type}:",
                f'        """Return {property_doc}"""',
                "        ...",
                "",
                "    @abstractmethod",
                f"    def set_{name}_{version}(self, value: {value_type}) -> None:",
                f'        """Set {property_doc}"""',
                "        ...",
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
        for prop in definition.properties:
            name = self._defs.property_name(prop.source_name)
            if prop.required:
                lines.append(f"        result[{prop.source_name!r}] = value.get_{name}_{version}()")
            else:
                lines.extend([
                    f"        value_{name} = value.get_{name}_{version}()",
                    f"        if value_{name} is not None:",
                    f"            result[{prop.source_name!r}] = value_{name}",
                ])
        lines.extend([
            "        return result",
            "",
            f"    def deserialize_into(self, payload: Mapping[str, object], target: {interface_name}) -> None:",
        ])
        if definition.properties:
            for prop in definition.properties:
                name = self._defs.property_name(prop.source_name)
                lines.append(f"        target.set_{name}_{version}(payload.get({prop.source_name!r}))")
        else:
            lines.append("        return None")
        lines.extend([
            "",
            f"{interface_name}.TYPE = AIcDataEntityType({schema_id!r}, {version}, {interface_name})",
            "",
        ])
        return "\n".join(lines)
