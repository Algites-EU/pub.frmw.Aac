from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from algites.lib.aac.coreintf.presentation import (
    AIcDisplayContent,
    AIcDisplayText,
    normalize_display_content,
    normalize_display_text,
)


class AInUiFieldType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"
    MULTILINE = "MULTILINE"
    JSON = "JSON"
    SECRET_REFERENCE = "SECRET_REFERENCE"
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    INSTANCE_REFERENCE = "INSTANCE_REFERENCE"
    CAPABILITY_REFERENCE = "CAPABILITY_REFERENCE"


def _required_display_text(value: AIcDisplayText | str) -> AIcDisplayText:
    normalized = normalize_display_text(value)
    if normalized is None:
        raise ValueError("required display text is missing")
    return normalized


def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)


def _required_display_content(value: AIcDisplayContent | str) -> AIcDisplayContent:
    normalized = normalize_display_content(value)
    if normalized is None:
        raise ValueError("required display content is missing")
    return normalized


@dataclass(frozen=True, slots=True)
class AIcUiConfigurationScope:
    type: str
    id: str | None = None
    editable: bool = False
    policy_authority: bool = False

    @property
    def key(self) -> str:
        return self.type if self.id is None else f"{self.type}({self.id})"



@dataclass(frozen=True, slots=True)
class AIcUiConfigurationProviderOption:
    configuration_scope: AIcUiConfigurationScope
    configuration_provider_id: str
    technical_capabilities: tuple[str, ...] = ()
    authorized_capabilities: tuple[str, ...] = ()
    record_revision: str | int | None = None
    diagnostics: tuple[str, ...] = ()

    @property
    def can_write_value(self) -> bool:
        return "WRITE_VALUE" in self.authorized_capabilities

    @property
    def can_write_policy(self) -> bool:
        return "WRITE_POLICY" in self.authorized_capabilities


@dataclass(frozen=True, slots=True)
class AIcUiChoice:
    value: object
    label: AIcDisplayText
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _required_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiField:
    id: str
    label: AIcDisplayText
    field_type: AInUiFieldType
    value: object | None = None
    required: bool = False
    read_only: bool = False
    description: AIcDisplayText | None = None
    choices: tuple[AIcUiChoice, ...] = ()
    multiple: bool = False
    secret: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)
    accepted_configuration_scope_types: tuple[str, ...] = ()
    effective_configuration_scope: AIcUiConfigurationScope | None = None
    effective_configuration_provider_id: str | None = None
    value_source_kind: str | None = None
    policy_modes: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _required_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiFieldGroup:
    id: str
    label: AIcDisplayText | None
    fields: tuple[AIcUiField, ...]
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _optional_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiForm:
    id: str
    title: AIcDisplayText
    groups: tuple[AIcUiFieldGroup, ...]
    configuration_scopes: tuple[AIcUiConfigurationScope, ...] = ()
    active_configuration_profile_id: str | None = None
    configuration_provider_options: tuple[AIcUiConfigurationProviderOption, ...] = ()
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _required_display_text(self.title))
        object.__setattr__(self, "description", _optional_display_text(self.description))

    @property
    def fields(self) -> tuple[AIcUiField, ...]:
        return tuple(field for group in self.groups for field in group.fields)


@dataclass(frozen=True, slots=True)
class AIcUiDisplay:
    id: str
    content: AIcDisplayContent
    title: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _required_display_content(self.content))
        object.__setattr__(self, "title", _optional_display_text(self.title))


@dataclass(frozen=True, slots=True)
class AIcUiPanel:
    id: str
    title: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    displays: tuple[AIcUiDisplay, ...] = ()
    forms: tuple[AIcUiForm, ...] = ()
    panels: tuple["AIcUiPanel", ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _optional_display_text(self.title))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiComponent:
    id: str
    version: int
    provider_definition_ids: tuple[str, ...]
    permission_count: int = 0
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    origin: str | None = None
    readiness_state: str | None = None
    readiness_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiProviderInstance:
    id: str
    component_id: str
    provider_definition_id: str
    name: AIcDisplayText
    capabilities: tuple[tuple[str, tuple[int, ...]], ...]
    access_mode: str
    state: str
    configuration_schema: str | None
    readiness_state: str | None = None
    readiness_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_display_text(self.name))

    def supports_capability(self, capability_id: str) -> bool:
        return any(value[0] == capability_id for value in self.capabilities)

    @property
    def capabilities_text(self) -> str:
        return ", ".join(
            f"{capability_id} [{', '.join(str(version) for version in versions)}]"
            for capability_id, versions in self.capabilities
        )


@dataclass(frozen=True, slots=True)
class AIcUiBinding:
    consumer_instance_id: str
    requirement_id: str
    provider_instance_id: str
    capability_id: str
    capability_version: int


@dataclass(frozen=True, slots=True)
class AIcUiRequirement:
    consumer_instance_id: str
    consumer_instance_name: AIcDisplayText
    requirement_id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: str
    mandatory: bool
    selected_provider_instance_ids: tuple[str, ...] = ()
    requested_authorizations: tuple[str, ...] = ()
    granted_authorizations: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumer_instance_name", _required_display_text(self.consumer_instance_name))
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiRequirementEditor:
    consumer_instance_id: str
    requirement_id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: str
    mandatory: bool
    selected_provider_instance_ids: tuple[str, ...]
    provider_choices: tuple[AIcUiChoice, ...]
    requested_authorizations: tuple[str, ...] = ()
    granted_authorizations: tuple[str, ...] = ()
    authorization_choices: tuple[AIcUiChoice, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcUiObservationSelector:
    capability: str = "*"
    versions: tuple[int, ...] = ()
    operations: tuple[str, ...] = ()
    phases: tuple[str, ...] = ("PRE", "POST")


@dataclass(frozen=True, slots=True)
class AIcUiObservationBinding:
    observer_instance_id: str
    selectors: tuple[AIcUiObservationSelector, ...]


@dataclass(frozen=True, slots=True)
class AIcUiEntitlementPermission:
    component_id: str
    capability_id: str
    capability_version: int
    permission_id: str
    effective_from: str | None = None
    effective_until: str | None = None
    licensing_scope: str | None = None
    entitlement_id: str | None = None
    issuer_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    implicit: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))


@dataclass(frozen=True, slots=True)
class AIcUiEntitlementStatus:
    component_id: str
    permissions: tuple[AIcUiEntitlementPermission, ...]
    next_transition_at: str | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcUiCatalogPackageArtifact:
    source_id: str
    product_id: str
    technology_id: str
    component_id: str
    component_version: int
    artifact_id: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    publisher: str | None = None
    package_format: str | None = None
    artifact_uri: str | None = None
    sha256: str | None = None
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    entitlement_summary: tuple[str, ...] = ()
    entitlement_info_url: str | None = None
    homepage_url: str | None = None
    documentation_url: str | None = None
    icon_url: str | None = None
    downloaded: bool = False
    installed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))

    @property
    def identity(self) -> tuple[str, str, str, str, int, str]:
        return (
            self.source_id, self.product_id, self.technology_id,
            self.component_id, self.component_version, self.artifact_id,
        )



@dataclass(frozen=True, slots=True)
class AIcUiPackageArtifact:
    component_id: str
    component_version: int
    sha256: str
    state: str
    selected_application_scope_ids: tuple[str, ...] = ()
    source_id: str | None = None
    signer_identity: str | None = None
    artifact_path: str | None = None

    @property
    def identity(self) -> tuple[str, int, str]:
        return self.component_id, self.component_version, self.sha256

    @property
    def selected(self) -> bool:
        return bool(self.selected_application_scope_ids)


@dataclass(frozen=True, slots=True)
class AIcUiUpgradeReplacement:
    component_id: str
    previous_version: int
    target_version: int


@dataclass(frozen=True, slots=True)
class AIcUiUpgradeDiagnostic:
    component_id: str
    message: AIcDisplayText
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    capability_id: str | None = None
    consumer_versions: tuple[int, ...] = ()
    provider_versions: tuple[int, ...] = ()
    available_provider_component_ids: tuple[str, ...] = ()
    blocking: bool = True
    code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", _required_display_text(self.message))


@dataclass(frozen=True, slots=True)
class AIcUiUpgradePlan:
    application_scope_id: str
    replacements: tuple[AIcUiUpgradeReplacement, ...]
    compatible: bool
    diagnostics: tuple[AIcUiUpgradeDiagnostic, ...] = ()
