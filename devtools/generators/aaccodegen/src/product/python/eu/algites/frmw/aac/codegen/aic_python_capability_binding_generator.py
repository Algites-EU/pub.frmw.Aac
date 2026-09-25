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
    """Generate Python provider/caller bindings from one canonical capability contract.

    Portable interaction schemas remain the source of truth.  Data types are projected
    deterministically from schema identity; operation-specific failure exception names
    are projected deterministically from capability/operation identity.
    """

    def __init__(self, schemas: AIcSchemaRegistry) -> None:
        self.schemas = schemas

    @staticmethod
    def _exception_stem(contract: AIcCapabilityContract, operation_id: str) -> str:
        capability_stem = _pascal(contract.capability.id.split(".")[-1])
        if len(contract.operations) == 1:
            return capability_stem
        return capability_stem + _pascal(operation_id)

    def generate(self, contract: AIcCapabilityContract, *, canonical_resource: str | None = None) -> str:
        capability_stem = _pascal(contract.capability.id.split(".")[-1])
        interface_name = f"AIig{capability_stem}_{contract.capability.version}"
        caller_name = f"AIcg{capability_stem}Caller_{contract.capability.version}"
        chunks = [
            "from __future__ import annotations",
            "",
            "from abc import ABC, abstractmethod",
            "from dataclasses import asdict, dataclass, is_dataclass",
            "from typing import Mapping",
            "from eu.algites.frmw.aac.core.bindings.api import aig_authorization, aig_operation",
            "from eu.algites.frmw.aac.core.invocation.api import (",
            "    AInOperationCompletionState, AIcOperationCompletion, AIcOperationFailure,",
            "    AIiCapabilityHandle, AIiOperationFailureExceptionFactory,",
            "    AIiOperationInteractionCallerToProvider, AIiOperationInteractionProviderToCaller,",
            "    AIxCapabilityOperationFailed, current_operation_interaction,",
            ")",
            "",
        ]
        dto_by_identity: dict[tuple[str, int], str] = {}
        dto_by_operation_kind: dict[tuple[str, AInCapabilityOperationInteractionKind], str] = {}
        identity_by_dto_name: dict[str, tuple[str, int]] = {}
        emitted_schema_types: set[tuple[str, int]] = set()
        for operation in contract.operations:
            for interaction in operation.interactions:
                registered = self.schemas.get_identity(interaction.schema.id, interaction.schema.version)
                schema_identity = (registered.id, registered.version)
                class_name = f"AIcgd{_pascal(registered.id.split('.')[-1])}_{registered.version}"
                existing_identity = identity_by_dto_name.get(class_name)
                if existing_identity is not None and existing_identity != schema_identity:
                    raise ValueError(
                        f"generated DTO name collision {class_name!r} for schemas "
                        f"{existing_identity[0]}/{existing_identity[1]} and {registered.id}/{registered.version}; "
                        "rename one canonical schema id or introduce an explicit naming rule before generation"
                    )
                identity_by_dto_name[class_name] = schema_identity
                dto_by_identity[schema_identity] = class_name
                dto_by_operation_kind[(operation.id, interaction.kind)] = class_name
                if schema_identity not in emitted_schema_types:
                    chunks.extend([_dto_source(class_name, registered), ""])
                    emitted_schema_types.add(schema_identity)

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
                    f"    def {_identifier(operation.id)}_{contract.capability.version}(self, request: {input_name}, interaction: AIiOperationInteractionProviderToCaller) -> {return_name}: ..."
                )
            else:
                chunks.append(
                    f"    def {_identifier(operation.id)}_{contract.capability.version}(self, interaction: AIiOperationInteractionProviderToCaller) -> {return_name}: ..."
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
            args.append(f"interaction: AIiOperationInteractionCallerToProvider[{exception_name}] | None = None")
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
        return "\n".join(chunks)
