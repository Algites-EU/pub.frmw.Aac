from __future__ import annotations

from dataclasses import dataclass

from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry
from eu.algites.tool.codegen.defs.ain_definition_kind import AInDefinitionKind
from eu.algites.tool.codegen.defs.aic_generation_names import AIcGenerationNames

from .aic_aac_schema_type_generator import AIcAacSchemaTypeGenerator


def _doc(value: str | None, fallback: str) -> str:
    return " ".join((value or fallback).replace('"""', '\"\"\"').split())


@dataclass(frozen=True, slots=True)
class AIcdAacGeneratedDataEntitySources:
    """Data Entity specialization plus its ordinary General-generated schema units."""

    binding_source: str
    schema_sources: tuple[object, ...]


class AIcPythonDataEntityBindingGenerator:
    """Generate only AAC-specific mutable views/codecs over standard General AIig types.

    Property identity, getters, canonical metadata and DTO rendering remain in
    pub.tool.General. This adds just the versioned mutation contract and codec.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas
        self._schema_types = AIcAacSchemaTypeGenerator()

    def generate(self, schema_id: str, version: int) -> str:
        return self.generate_sources(schema_id, version).binding_source

    def generate_sources(self, schema_id: str, version: int) -> AIcdAacGeneratedDataEntitySources:
        registered = self.schemas.get_identity(schema_id, version)
        generated = self._schema_types.generate(registered)
        definition = generated.definition
        if definition.kind is not AInDefinitionKind.OBJECT or generated.implementation is None:
            raise ValueError('Data Entity view generation requires an object JSON definition')
        base = generated.contract.primary_type
        if base.source_definition_id != schema_id or base.source_definition_version != version:
            raise ValueError('Canonical schema type identity mismatch')
        base_name = base.type_name
        stem = base_name[len('AIig'):-len(f'_{version}')] if base_name.endswith(f'_{version}') else base_name[len('AIig'):]
        view_name = f'AIig{stem}DataEntityView_{version}'
        codec_name = f'AIcg{stem}Codec_{version}'
        lines = [
            'from __future__ import annotations',
            '',
            'from abc import abstractmethod',
            'from typing import Mapping',
            f'from {base.module_name} import {base_name}',
            'from eu.algites.frmw.aac.core.dataentity.api import AIcDataEntityType, AIiDataEntityCodec, AIiDataEntityView',
            '',
            f'class {view_name}({base_name}, AIiDataEntityView):',
            f'    """AAC mutable view of the canonical General contract {schema_id}/{version}.',
            '',
            f'    {_doc(definition.description, "Generated Data Entity view.")}',
            '    """',
            f'    __aac_source_id__ = {schema_id!r}',
            f'    __aac_source_version__ = {version}',
            f'    __aac_source_resource__ = {registered.resource_name!r}',
            '',
        ]
        name_helper = AIcGenerationNames()
        for prop in definition.properties:
            # Canonical getters and field constants are inherited from base AIig.
            name = name_helper.property_name(prop.source_name, self._schema_types.profile)
            lines.extend([
                '    @abstractmethod',
                f'    def set_{name}_{version}(self, value: object) -> None:',
                f'        """Update {_doc(prop.description, prop.source_name)}"""',
                '        ...',
                '',
            ])
        lines.extend([
            '    def to_mapping(self) -> Mapping[str, object]:',
            f'        return {codec_name}().serialize(self)',
            '',
            f'class {codec_name}(AIiDataEntityCodec[{view_name}]):',
            f'    schema_id = {schema_id!r}',
            f'    schema_version = {version}',
            f'    view_type = {view_name}',
            '',
            f'    def serialize(self, value: {view_name}) -> Mapping[str, object]:',
            '        result: dict[str, object] = {}',
        ])
        for prop in definition.properties:
            name = name_helper.property_name(prop.source_name, self._schema_types.profile)
            suffix = name[0].upper() + name[1:]
            constant = name_helper.schema_field_name_constant(prop.source_name, self._schema_types.profile)
            field = f'{view_name}.{constant}'
            if prop.required:
                lines.append(f'        result[{field}] = value.get{suffix}()')
            else:
                lines.extend([
                    f'        value_{name} = value.get{suffix}()',
                    f'        if value_{name} is not None:',
                    f'            result[{field}] = value_{name}',
                ])
        lines.extend([
            '        return result',
            '',
            f'    def deserialize_into(self, payload: Mapping[str, object], target: {view_name}) -> None:',
        ])
        for prop in definition.properties:
            name = name_helper.property_name(prop.source_name, self._schema_types.profile)
            constant = name_helper.schema_field_name_constant(prop.source_name, self._schema_types.profile)
            lines.append(f'        target.set_{name}_{version}(payload.get({view_name}.{constant}))')
        if not definition.properties:
            lines.append('        return None')
        lines.extend([
            '',
            f'{view_name}.TYPE = AIcDataEntityType({schema_id!r}, {version}, {view_name})',
            '',
        ])
        return AIcdAacGeneratedDataEntitySources(
            "\n".join(lines), (generated.contract, generated.mutable_interface, generated.implementation))
