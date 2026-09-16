from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..presentation import AIcDisplayText
from ..persistence import AInPersistenceTransactionPhase


class AInStoredPackageState(str, Enum):
    DOWNLOADED = "DOWNLOADED"
    INSTALLED = "INSTALLED"
    OBSOLETE = "OBSOLETE"


class AInPackageUpdatePolicy(str, Enum):
    MANUAL = "MANUAL"
    NOTIFY = "NOTIFY"
    AUTO_COMPATIBLE = "AUTO_COMPATIBLE"
    AUTO_LOCKED = "AUTO_LOCKED"


@dataclass(frozen=True, slots=True)
class AIcPackageStoreLayout:
    """Product-supplied filesystem layout for AAC-managed package artifacts.

    AAC recommends ``plugins/downloaded``, ``plugins/installed`` and ``plugins/obsolete``
    below the product-owned root, but every relative name remains product-overridable.
    """

    product_root: str
    package_store_subdirectory: str = "plugins"
    downloaded_subdirectory: str = "downloaded"
    installed_subdirectory: str = "installed"
    obsolete_subdirectory: str = "obsolete"
    core_state_subdirectory: str = "aac-state"
    transactions_subdirectory: str = "transactions"
    core_lock_filename: str = "core.lock"

    def __post_init__(self) -> None:
        if not self.product_root:
            raise ValueError("package store product_root must not be empty")
        for name, value in (
            ("package_store_subdirectory", self.package_store_subdirectory),
            ("downloaded_subdirectory", self.downloaded_subdirectory),
            ("installed_subdirectory", self.installed_subdirectory),
            ("obsolete_subdirectory", self.obsolete_subdirectory),
            ("core_state_subdirectory", self.core_state_subdirectory),
            ("transactions_subdirectory", self.transactions_subdirectory),
            ("core_lock_filename", self.core_lock_filename),
        ):
            if not value:
                raise ValueError(f"{name} must not be empty")
            if value.startswith(("/", "\\")) or ".." in value.replace("\\", "/").split("/"):
                raise ValueError(f"{name} must be a relative path without parent traversal")


@dataclass(frozen=True, slots=True)
class AIcPackageSidecar:
    uri: str
    suffix: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.uri or not self.suffix or not self.suffix.startswith("."):
            raise ValueError("package sidecar requires uri and dot-prefixed suffix")


@dataclass(frozen=True, slots=True)
class AIcPackageCandidate:
    component_id: str
    component_version: int
    source_id: str
    artifact_uri: str
    artifact_filename: str
    package_format: str
    descriptor_path: str
    source_uri: str | None = None
    expected_sha256: str | None = None
    runtime_package: str | None = None
    verifier_id: str | None = None
    authentication_profile_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.component_id or self.component_version < 1:
            raise ValueError("package candidate requires component id/version")
        if not self.source_id or not self.artifact_uri or not self.artifact_filename:
            raise ValueError("package candidate requires source/artifact information")
        if not self.package_format or not self.descriptor_path:
            raise ValueError("package candidate requires package_format and descriptor_path")
        if self.expected_sha256 is not None:
            digest = self.expected_sha256.lower()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("expected_sha256 must contain exactly 64 hexadecimal characters")
            object.__setattr__(self, "expected_sha256", digest)


@dataclass(frozen=True, slots=True)
class AIcPackageProvenance:
    source_id: str
    source_uri: str | None
    artifact_uri: str
    sha256: str
    downloaded_at: str
    verifier_id: str | None = None
    signer_identity: str | None = None
    verification_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcStoredPackage:
    component_id: str
    component_version: int
    sha256: str
    state: AInStoredPackageState
    artifact_path: str
    package_format: str
    descriptor_path: str
    runtime_package: str | None
    provenance: AIcPackageProvenance
    sidecar_paths: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def identity(self) -> tuple[str, int, str]:
        return self.component_id, self.component_version, self.sha256


@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentRequirement:
    component_id: str
    versions: tuple[int, ...] = ()
    required: bool = True
    source_ids: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("workspace component requirement component_id must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("workspace component requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("workspace component requirement versions must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("workspace component requirement source_ids must be unique")

    def accepts(self, version: int) -> bool:
        return not self.versions or version in self.versions


@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentRequirements:
    workspace_id: str
    requirements: tuple[AIcWorkspaceComponentRequirement, ...]
    update_policy: AInPackageUpdatePolicy = AInPackageUpdatePolicy.MANUAL

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError("workspace_id must not be empty")
        ids = [item.component_id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("workspace component requirements must be unique by component_id")


@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentLockEntry:
    component_id: str
    component_version: int
    sha256: str
    source_id: str
    artifact_uri: str
    artifact_filename: str
    package_format: str
    descriptor_path: str
    source_uri: str | None = None
    runtime_package: str | None = None
    verifier_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()

    def __post_init__(self) -> None:
        if not self.component_id or self.component_version < 1:
            raise ValueError("workspace component lock entry requires component id/version")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("workspace component lock sha256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentLock:
    workspace_id: str
    entries: tuple[AIcWorkspaceComponentLockEntry, ...]

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError("workspace component lock workspace_id must not be empty")
        ids = [item.component_id for item in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("workspace component lock entries must be unique by component_id")

    def entry(self, component_id: str) -> AIcWorkspaceComponentLockEntry | None:
        return next((item for item in self.entries if item.component_id == component_id), None)


@dataclass(frozen=True, slots=True)
class AIcPackageAutomationPolicy:
    verify_on_download: bool = True
    require_entitlement_for_automatic_paid_component: bool = True
    allow_automatic_download: bool = True
    allow_automatic_install: bool = True




@dataclass(frozen=True, slots=True)
class AIcPackageSourceRegistration:
    id: str
    type: str
    uri: str
    authentication_profile_id: str | None = None
    verifier_id: str | None = None
    priority: int = 0
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type or not self.uri:
            raise ValueError("package source registration requires id/type/uri")


@dataclass(frozen=True, slots=True)
class AIcPackageBootstrap:
    schema_version: int
    layout: AIcPackageStoreLayout
    sources: tuple[AIcPackageSourceRegistration, ...] = ()
    automation_policy: AIcPackageAutomationPolicy = AIcPackageAutomationPolicy()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("package bootstrap schema_version must be >= 1")
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("package source registration ids must be unique")


@dataclass(frozen=True, slots=True)
class AIcPackageSelection:
    application_scope_id: str
    component_id: str
    component_version: int
    sha256: str
    selected_at: str
    previous_sha256: str | None = None
    previous_version: int | None = None




@dataclass(frozen=True, slots=True)
class AIcPackageSelectionManifest:
    record_revision: int
    selections: tuple[AIcPackageSelection, ...] = ()
    last_transaction_id: str | None = None

    def __post_init__(self) -> None:
        if self.record_revision < 0:
            raise ValueError("package selection record_revision must not be negative")
        keys = [(item.application_scope_id, item.component_id) for item in self.selections]
        if len(keys) != len(set(keys)):
            raise ValueError("package selection manifest contains duplicate scope/component entries")



@dataclass(frozen=True, slots=True)
class AIcPackageTransactionRecovery:
    transaction_id: str
    phase: AInPersistenceTransactionPhase
    action: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcPackageReconciliationAction:
    component_id: str
    action: str
    candidate: AIcPackageCandidate | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AIcPackageReconciliationPlan:
    workspace_id: str
    policy: AInPackageUpdatePolicy
    actions: tuple[AIcPackageReconciliationAction, ...]

@dataclass(frozen=True, slots=True)
class AIcComponentUpgradeReplacement:
    component_id: str
    previous_version: int
    target_version: int
    previous_sha256: str | None = None
    target_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.component_id or self.previous_version < 1 or self.target_version < 1:
            raise ValueError("component upgrade replacement requires component id and versions >= 1")
        if self.target_version == self.previous_version and self.target_sha256 == self.previous_sha256:
            raise ValueError("component upgrade replacement must change version and/or artifact digest")


@dataclass(frozen=True, slots=True)
class AIcUpgradeCompatibilityDiagnostic:
    component_id: str
    message: str
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    capability_id: str | None = None
    consumer_versions: tuple[int, ...] = ()
    provider_versions: tuple[int, ...] = ()
    available_provider_component_ids: tuple[str, ...] = ()
    blocking: bool = True
    code: str | None = None


@dataclass(frozen=True, slots=True)
class AIcComponentUpgradePlan:
    application_scope_id: str
    replacements: tuple[AIcComponentUpgradeReplacement, ...]
    compatible: bool
    diagnostics: tuple[AIcUpgradeCompatibilityDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        ids = [item.component_id for item in self.replacements]
        if len(ids) != len(set(ids)):
            raise ValueError("upgrade replacements must be unique by component_id")
        if self.compatible and any(item.blocking for item in self.diagnostics):
            raise ValueError("compatible upgrade plan must not contain blocking compatibility diagnostics")


@dataclass(frozen=True, slots=True)
class AIcComponentUpgradeTransactionOutcome:
    application_scope_id: str
    replacements: tuple[AIcComponentUpgradeReplacement, ...]
    rolled_back: bool = False
    diagnostics: tuple[str, ...] = ()

