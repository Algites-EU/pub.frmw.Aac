from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from threading import RLock
from types import ModuleType

_MODULE_GENERATION_LOCK = RLock()

from eu.algites.frmw.aac.core.schemas.registry import AIcRegisteredSchema
from eu.algites.lib.naming.convention.aic_algites_naming_profiles import AIcAlgitesNamingProfiles
from eu.algites.tool.codegen.defs.aic_json_schema_reader import AIcJsonSchemaReader
from eu.algites.tool.codegen.defs.aic_schema_contract_interface_generator import AIcSchemaContractInterfaceGenerator
from eu.algites.tool.codegen.defs.aicd_code_generation_request import AIcdCodeGenerationRequest
from eu.algites.tool.codegen.defs.aicd_definition_load_request import AIcdDefinitionLoadRequest
from eu.algites.tool.codegen.defs.ain_code_generation_target import AInCodeGenerationTarget
from eu.algites.tool.codegen.defs.ain_definition_source_kind import AInDefinitionSourceKind
from eu.algites.tool.codegen.sdo.aic_sdo_codegen_service import AIcSdoCodegenService


@dataclass(frozen=True, slots=True)
class AIcdAacSchemaTypeSources:
    """General stage-one read contract and stage-two SDO units."""

    definition: object
    contract: object
    mutable_interface: object | None
    implementation: object | None


class AIcAacSchemaTypeGenerator:
    """Adapt AAC's canonical schema registration to General's *standard* two stages.

    Defs Codegen generates only AIig read contracts. SDO Codegen consumes the
    annotated AIig contract and generates AIigd and AIcgd. AAC does not render
    data objects, parse generated sources or invent type names.
    """

    DEFAULT_NAMESPACE = 'eu.algites.frmw.aac.generated'

    def __init__(self, namespace: str = DEFAULT_NAMESPACE) -> None:
        if not namespace or not all(part.isidentifier() for part in namespace.split('.')):
            raise ValueError(f'Invalid generated namespace: {namespace!r}')
        self.namespace = namespace
        self.profile = AIcAlgitesNamingProfiles.python_profile()
        self._reader = AIcJsonSchemaReader()
        self._contract_generator = AIcSchemaContractInterfaceGenerator()
        self._sdo_generator = AIcSdoCodegenService()

    def generate(self, registered: AIcRegisteredSchema) -> AIcdAacSchemaTypeSources:
        load_request = AIcdDefinitionLoadRequest(
            Path(registered.resource_name), AInDefinitionSourceKind.JSONDEFS, self.profile)
        definition = self._reader.read(
            registered.schema, load_request, AInDefinitionSourceKind.JSONDEFS,
            'x-aac-schema-id', 'x-aac-schema-version', 'x-jsondefs-name')
        request = AIcdCodeGenerationRequest(
            definition, AInCodeGenerationTarget.PYTHON, self.namespace, self.profile)
        contract = self._contract_generator.generate(request)
        if definition.kind.name == 'ENUM':
            return AIcdAacSchemaTypeSources(definition, contract, None, None)
        # The schema-independent SDO stage accepts *importable Python types*.
        # Materialize an ephemeral module in memory; never inline its source into
        # the AAC binding, and do not write generated artifacts into this repo.
        primary = contract.primary_type
        module_name = primary.module_name
        with _MODULE_GENERATION_LOCK:
            previous = sys.modules.get(module_name)
            module = ModuleType(module_name)
            module.__package__ = self.namespace
            sys.modules[module_name] = module
            try:
                exec(compile(contract.source, contract.relative_path, 'exec'), module.__dict__)
                read_type = getattr(module, primary.type_name)
                generated = self._sdo_generator.generate(read_type)
            finally:
                if previous is None:
                    sys.modules.pop(module_name, None)
                else:
                    sys.modules[module_name] = previous
        return AIcdAacSchemaTypeSources(
            definition, contract, generated.mutable_interface, generated.implementation)
