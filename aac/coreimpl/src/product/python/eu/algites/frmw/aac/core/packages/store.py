from __future__ import annotations
import hashlib
import json
import os
import shutil
import ssl
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import yaml
from eu.algites.frmw.aac.core.authentication.api import AIcAuthenticationMaterial
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.errors import AIxPackageDigestMismatch, AIxPackageManagementError, AIxPackageRevisionConflict
from eu.algites.frmw.aac.core.packages.api import (
    AInPackageUpdatePolicy,
    AInStoredPackageState,
    AIcPackageAutomationPolicy,
    AIcPackageCandidate,
    AIcPackageProvenance,
    AIcPackageReconciliationAction,
    AIcPackageReconciliationPlan,
    AIcPackageSelection,
    AIcPackageSelectionManifest,
    AIcPackageSidecar,
    AIcPackageStoreLayout,
    AIcStoredPackage,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentLockEntry,
    AIcWorkspaceComponentRequirement,
    AIcWorkspaceComponentRequirements,
    AIiPackageSource,
)
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.packages.transactions import AIcDurablePackageSelectionManifestStore, AIcPackageReplacementJournal
from eu.algites.frmw.aac.core.persistence.durable import atomic_write_json, durable_replace, fsync_directory, fsync_file

from .aic_package_verifier_registry import AIcPackageVerifierRegistry
from .aic_static_package_source import AIcStaticPackageSource
from .aic_manifest_package_source import AIcManifestPackageSource
from .aic_package_source_registry import AIcPackageSourceRegistry
from .aic_package_store import AIcPackageStore
from .aic_package_selection_store import AIcPackageSelectionStore
from .aic_package_manager import AIcPackageManager

_PACKAGE_SELECTION_NAMESPACE = "aac.packages.selection"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_segment(value: str) -> str:
    if not value:
        raise ValueError("package path segment must not be empty")
    return quote(value, safe="._-")

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _ssl_context(material: AIcAuthenticationMaterial) -> ssl.SSLContext | None:
    certificate = material.client_certificate
    if certificate is None:
        return None
    context = ssl.create_default_context()
    context.load_cert_chain(
        certificate.certificate_path,
        keyfile=certificate.private_key_path,
        password=certificate.private_key_password,
    )
    return context

def _read_uri(
    uri: str,
    *,
    authentication: AIcAuthenticationService | None = None,
    authentication_profile_id: str | None = None,
    context: Mapping[str, object] | None = None,
    timeout_seconds: float = 30.0,
) -> bytes:
    parsed = urlparse(uri)
    if parsed.scheme in {"", "file"}:
        path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(uri)
        return path.read_bytes()
    if parsed.scheme not in {"http", "https"}:
        raise AIxPackageManagementError(f"unsupported package URI scheme {parsed.scheme!r}")
    material = authentication.material(
        authentication_profile_id, transport_kind="HTTP", endpoint=uri, context=context
    ) if authentication is not None else AIcAuthenticationMaterial()
    request = Request(uri, headers=dict(material.headers), method="GET")
    with urlopen(request, timeout=timeout_seconds, context=_ssl_context(material)) as response:
        return response.read()

def _candidate_from_lock(entry: AIcWorkspaceComponentLockEntry) -> AIcPackageCandidate:
    return AIcPackageCandidate(
        component_id=entry.component_id, component_version=entry.component_version, source_id=entry.source_id,
        artifact_uri=entry.artifact_uri, artifact_filename=entry.artifact_filename, expected_sha256=entry.sha256,
        package_format=entry.package_format, descriptor_path=entry.descriptor_path, runtime_package=entry.runtime_package,
        verifier_id=entry.verifier_id, sidecars=entry.sidecars,
    )
