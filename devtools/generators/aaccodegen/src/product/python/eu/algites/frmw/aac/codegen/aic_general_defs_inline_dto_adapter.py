from __future__ import annotations

from pathlib import Path

from eu.algites.frmw.aac.core.schemas.registry import AIcRegisteredSchema
from eu.algites.lib.naming.convention.aic_algites_naming_profiles import AIcAlgitesNamingProfiles
from eu.algites.lib.naming.convention.ain_output_name_kind import AInOutputNameKind
from eu.algites.tool.codegen.defs.aic_generation_names import AIcGenerationNames
from eu.algites.tool.codegen.defs.aic_json_schema_reader import AIcJsonSchemaReader
from eu.algites.tool.codegen.defs.aic_python_code_generation_backend import AIcPythonCodeGenerationBackend
from eu.algites.tool.codegen.defs.aicd_code_generation_request import AIcdCodeGenerationRequest
from eu.algites.tool.codegen.defs.aicd_definition_load_request import AIcdDefinitionLoadRequest
from eu.algites.tool.codegen.defs.ain_code_generation_target import AInCodeGenerationTarget
from eu.algites.tool.codegen.defs.ain_definition_source_kind import AInDefinitionSourceKind


class AIcGeneralDefsInlineDtoAdapter:
    """Adapt registered AAC JSON definitions to the shared defs-codegen model and backend.

    AAC capability bindings are emitted as one combined Python source unit, while the shared
    defs-codegen backend normally emits one standalone module per canonical definition. This
    adapter keeps schema normalization, naming, documentation, provenance, and DTO rendering in
    ``pub.tool.General`` and extracts only the generated declaration needed by the AAC binding.
    """

    def __init__(self) -> None:
        self.profile = AIcAlgitesNamingProfiles.python_profile()
        self.names = AIcGenerationNames()
        self._reader = AIcJsonSchemaReader()
        self._backend = AIcPythonCodeGenerationBackend()

    def normalize(self, registered: AIcRegisteredSchema):
        """Normalize one registered AAC schema through the shared JSON definitions reader."""
        request = AIcdDefinitionLoadRequest(
            Path(registered.resource_name),
            AInDefinitionSourceKind.JSONDEFS,
            self.profile,
        )
        return self._reader.read(
            registered.schema,
            request,
            AInDefinitionSourceKind.JSONDEFS,
            "x-aac-schema-id",
            "x-aac-schema-version",
            "x-jsondefs-name",
        )

    def interface_type_name(self, definition) -> str:
        """Project an AAC interface name from the normalized definition using shared naming rules."""
        return self.names.type_name(definition, self.profile, AInOutputNameKind.INTERFACE_TYPE)

    def property_name(self, source_name: str) -> str:
        """Project a Python property name using the shared Algites naming profile."""
        return self.names.property_name(source_name, self.profile)

    def generate(self, registered: AIcRegisteredSchema) -> tuple[str, str]:
        """Return the generated DTO type name and inlinable class declaration."""
        definition = self.normalize(registered)
        generated = self._backend.generate(
            AIcdCodeGenerationRequest(
                definition,
                AInCodeGenerationTarget.PYTHON,
                "eu.algites.frmw.aac.generated",
                self.profile,
            )
        )
        marker = "@dataclass(frozen=True, slots=True)\n"
        if marker not in generated.source:
            raise ValueError(
                f"AAC interaction schema {registered.id}/{registered.version} must generate a data-object type"
            )
        preamble, declaration = generated.source.split(marker, 1)
        if "from ." in preamble:
            raise ValueError(
                f"AAC inline DTO schema {registered.id}/{registered.version} contains an external canonical reference; "
                "inline reference imports are not supported"
            )
        return generated.type_name, marker + declaration
