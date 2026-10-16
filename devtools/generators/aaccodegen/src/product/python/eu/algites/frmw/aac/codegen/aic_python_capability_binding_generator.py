from __future__ import annotations
import keyword
import re
from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AInCapabilityOperationInteractionKind
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

from .aic_aac_schema_type_generator import AIcAacSchemaTypeGenerator
from eu.algites.tool.codegen.defs.ain_defs_name_role import AInDefsNameRole
from dataclasses import dataclass

def _pascal(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Capability"

def _identifier(value: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
    candidate = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not candidate or candidate[0].isdigit():
        candidate = "_" + candidate
    if keyword.iskeyword(candidate):
        candidate += "_"
    return candidate

@dataclass(frozen=True, slots=True)
class AIcdAacGeneratedCapabilitySources:
    """Binding source and self-contained standalone canonical schema source files."""

    binding_source: str
    schema_sources: tuple[object, ...]


class AIcPythonCapabilityBindingGenerator:
    """Generate Python provider/caller bindings from one canonical capability contract.

    Portable interaction schemas remain the source of truth.  Data types are projected
    deterministically from schema identity; operation-specific failure exception names
    are projected deterministically from capability/operation identity.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas
        self._schema_types = AIcAacSchemaTypeGenerator()

    @staticmethod
    def _exception_stem(contract: AIcCapabilityContract, operation_id: str) -> str:
        capability_stem = _pascal(contract.capability.id.split(".")[-1])
        if len(contract.operations) == 1:
            return capability_stem
        return capability_stem + _pascal(operation_id)

    def generate(self, contract: AIcCapabilityContract, *, canonical_resource: str | None = None) -> str:
        """Generate only AAC binding code; schema units are emitted by generate_sources."""
        return self.generate_sources(contract, canonical_resource=canonical_resource).binding_source

    def generate_sources(self, contract: AIcCapabilityContract,
                         *, canonical_resource: str | None = None) -> AIcdAacGeneratedCapabilitySources:
        """Generate AAC binding plus reusable, separately importable General data types."""
        capability_stem = _pascal(contract.capability.id.split(".")[-1])
        interface_name = f"AIig{capability_stem}_{contract.capability.version}"
        caller_name = f"AIcg{capability_stem}Caller_{contract.capability.version}"
        chunks = [
            "from __future__ import annotations",
            "",
            "from abc import ABC, abstractmethod",
            "from dataclasses import asdict, dataclass, is_dataclass",
            "from typing import Any, Mapping",
            "from eu.algites.frmw.aac.core.bindings.api import aig_authorization, aig_operation",
            "from eu.algites.frmw.aac.core.invocation.api import (",
            "    AInOperationCompletionState, AIcOperationCompletion, AIcOperationFailure,",
            "    AIiCapabilityHandle, AIiOperationFailureExceptionFactory,",
            "    AIiOperationInteractionCallerToProviderOnCaller, AIiOperationInteractionProviderToCallerOnProvider, AIcOperationInteractionCallerToProviderMessage,",
            "    AIxCapabilityOperationFailed, current_operation_interaction,",
            ")",
            "",
        ]
        dto_by_operation_kind: dict[tuple[str, AInCapabilityOperationInteractionKind], str] = {}
        dto_imports: dict[str, str] = {}
        source_by_path: dict[str, object] = {}
        identity_by_qualified_name: dict[str, tuple[str, int]] = {}
        emitted: set[tuple[str, int]] = set()
        for operation in contract.operations:
            for interaction in operation.interactions:
                registered = self.schemas.get_identity(interaction.schema.id, interaction.schema.version)
                schema_identity = (registered.id, registered.version)
                if schema_identity not in emitted:
                    generated = self._schema_types.generate(registered)
                    for unit in (generated.contract, generated.mutable_interface, generated.implementation):
                        if unit is None:
                            continue
                        identity = unit.primary_type
                        if identity.source_definition_id != registered.id or identity.source_definition_version != registered.version:
                            raise ValueError(f'Canonical type identity mismatch for {registered.id}/{registered.version}')
                        prior = identity_by_qualified_name.get(identity.fully_qualified_type_name)
                        if prior is not None and prior != schema_identity:
                            raise ValueError(f'generated DTO name collision {identity.fully_qualified_type_name!r} for schemas '
                                             f'{prior[0]}/{prior[1]} and {registered.id}/{registered.version}')
                        identity_by_qualified_name[identity.fully_qualified_type_name] = schema_identity
                        source_by_path[unit.relative_path] = unit
                        if identity.type_role in ("SMART_DATA_OBJECT_TYPE", AInDefsNameRole.ENUM_TYPE):
                            dto_imports[identity.type_name] = identity.module_name
                    emitted.add(schema_identity)
                # This lookup is deliberately driven by metadata, never by source text.
                data_units = [unit for unit in source_by_path.values()
                              if unit.primary_type.source_definition_id == registered.id
                              and unit.primary_type.source_definition_version == registered.version
                              and unit.primary_type.type_role in ("SMART_DATA_OBJECT_TYPE", AInDefsNameRole.ENUM_TYPE)]
                if len(data_units) != 1:
                    raise ValueError(f'Canonical DTO for {registered.id}/{registered.version} is missing or ambiguous')
                dto_by_operation_kind[(operation.id, interaction.kind)] = data_units[0].type_name
        for type_name, module in sorted(dto_imports.items()):
            chunks.append(f'from {module} import {type_name}')
        chunks.append('')

        exception_by_operation: dict[str, str] = {}
        factory_by_operation: dict[str, str] = {}
        for operation in contract.operations:
            stem = self._exception_stem(contract, operation.id)
            exception_name = f"AIxg{stem}Failed_{contract.capability.version}"
            factory_name = f"AIcg{stem}FailedFactory_{contract.capability.version}"
            exception_by_operation[operation.id] = exception_name
            factory_by_operation[operation.id] = factory_name
            failure_dto = dto_by_operation_kind.get(
                (operation.id, AInCapabilityOperationInteractionKind.FINAL_FAILED_STATE_RESULT_EXTENSION)
            )
            chunks.extend([
                f"class {exception_name}(AIxCapabilityOperationFailed):",
                f"    \"\"\"Generated failure exception for {contract.capability.id}/{contract.capability.version}/{operation.id}.\"\"\"",
                "    def __init__(self, failure: AIcOperationFailure) -> None:",
                "        super().__init__(failure)",
            ])
            if failure_dto is None:
                chunks.append("        self.additional_data = None")
            else:
                chunks.extend([
                    f"        self.additional_data: {failure_dto} | None = (",
                    f"            {failure_dto}.from_mapping(failure.extension)",
                    "            if isinstance(failure.extension, Mapping) else None",
                    "        )",
                ])
            chunks.extend([
                "",
                f"class {factory_name}(AIiOperationFailureExceptionFactory[{exception_name}]):",
                f"    def create(self, failure: AIcOperationFailure) -> {exception_name}:",
                f"        return {exception_name}(failure)",
                "",
            ])

        chunks.extend([
            f"class {interface_name}(ABC):",
            f"    \"\"\"Generated provider interface from canonical AAC capability contract {contract.capability.id}/{contract.capability.version}.\"\"\"",
            f"    __aac_source_id__ = {contract.capability.id!r}",
            f"    __aac_source_version__ = {contract.capability.version}",
            f"    __aac_source_resource__ = {canonical_resource!r}",
            f"    __aac_capability_id__ = {contract.capability.id!r}",
            f"    __aac_capability_version__ = {contract.capability.version}",
            "",
        ])
        for operation in contract.operations:
            input_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.INPUT))
            output_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT))
            return_name = output_name or "None"
            auth = operation.authorization
            chunks.append(f"    @aig_operation({operation.id!r})")
            if auth is not None:
                chunks.append(f"    @aig_authorization(all_of={auth.all_of!r}, any_of={auth.any_of!r})")
            chunks.append("    @abstractmethod")
            if input_name:
                chunks.append(
                    f"    def {_identifier(operation.id)}_{contract.capability.version}(self, request: {input_name}, interaction: AIiOperationInteractionProviderToCallerOnProvider) -> {return_name}: ..."
                )
            else:
                chunks.append(
                    f"    def {_identifier(operation.id)}_{contract.capability.version}(self, interaction: AIiOperationInteractionProviderToCallerOnProvider) -> {return_name}: ..."
                )
            chunks.append("")
        chunks.append("    def __aac_invoke__(self, operation_id: str, arguments: Mapping[str, object]):")
        for index, operation in enumerate(contract.operations):
            prefix = "if" if index == 0 else "elif"
            input_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.INPUT))
            method_name = f"{_identifier(operation.id)}_{contract.capability.version}"
            chunks.append(f"        {prefix} operation_id == {operation.id!r}:")
            if input_name:
                chunks.append(f"            request = {input_name}.from_mapping(dict(arguments))")
                chunks.append(f"            result = self.{method_name}(request, current_operation_interaction())")
            else:
                chunks.append(f"            result = self.{method_name}(current_operation_interaction())")
            chunks.append('            return result.to_mapping() if hasattr(result, "to_mapping") else (asdict(result) if is_dataclass(result) else result)')
        chunks.extend(["        raise KeyError(operation_id)", ""])

        chunks.extend([
            f"class {caller_name}:",
            f"    \"\"\"Generated typed caller facade for {contract.capability.id}/{contract.capability.version}.\"\"\"",
            "    def __init__(self, handle: AIiCapabilityHandle) -> None:",
            "        self._handle = handle",
            "",
        ])
        for operation in contract.operations:
            method_name = f"{_identifier(operation.id)}_{contract.capability.version}"
            input_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.INPUT))
            success_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT))
            cancelled_name = dto_by_operation_kind.get((operation.id, AInCapabilityOperationInteractionKind.FINAL_CANCELLED_STATE_RESULT))
            exception_name = exception_by_operation[operation.id]
            factory_name = factory_by_operation[operation.id]
            success_type = success_name or "object"
            cancelled_type = cancelled_name or "object"
            args = []
            if input_name:
                args.append(f"request: {input_name}")
            args.append(f"interaction: AIiOperationInteractionCallerToProviderOnCaller[{exception_name}, AIcOperationInteractionCallerToProviderMessage] | None = None")
            signature = ", ".join(args)
            chunks.append(
                f"    def {method_name}(self, {signature}) -> AIcOperationCompletion[{success_type}, {cancelled_type}]:"
            )
            chunks.extend([
                "        effective_interaction = interaction or self._handle.new_operation_interaction()",
                "        if effective_interaction.exception_factory() is None:",
                f"            effective_interaction.set_exception_factory({factory_name}())",
            ])
            if input_name:
                chunks.append("        arguments = request.to_mapping()")
            else:
                chunks.append("        arguments = {}")
            chunks.extend([
                "        try:",
                f"            completion = self._handle.invoke_completion({operation.id!r}, arguments, operation_interaction=effective_interaction)",
                "        except AIxCapabilityOperationFailed as exception:",
                f"            if not isinstance(exception, {exception_name}):",
                f"                raise TypeError('operation failure exception factory must return {exception_name} or its subclass') from exception",
                "            raise",
                "        if completion.state is AInOperationCompletionState.SUCCESS:",
            ])
            if success_name:
                chunks.extend([
                    "            raw = completion.success_result",
                    f"            typed = {success_name}.from_mapping(raw) if isinstance(raw, Mapping) else raw",
                    "            return AIcOperationCompletion(completion.state, success_result=typed)",
                ])
            else:
                chunks.append("            return AIcOperationCompletion(completion.state)")
            chunks.append("        raw = completion.cancelled_result")
            if cancelled_name:
                chunks.extend([
                    f"        typed = {cancelled_name}.from_mapping(raw) if isinstance(raw, Mapping) else raw",
                    "        return AIcOperationCompletion(completion.state, cancelled_result=typed)",
                ])
            else:
                chunks.append("        return AIcOperationCompletion(completion.state)")
            chunks.append("")
        return AIcdAacGeneratedCapabilitySources("\n".join(chunks), tuple(source_by_path.values()))
