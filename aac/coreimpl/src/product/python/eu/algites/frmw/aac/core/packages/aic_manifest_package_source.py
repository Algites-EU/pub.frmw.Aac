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
        raise AIxPackageManagementError(f"unsupported package uri scheme {parsed.scheme!r}")
    material = authentication.material(
        authentication_profile_id, transport_kind="HTTP", endpoint=uri, context=context
    ) if authentication is not None else AIcAuthenticationMaterial()
    request = Request(uri, headers=dict(material.headers), method="GET")
    with urlopen(request, timeout=timeout_seconds, context=_ssl_context(material)) as response:
        return response.read()

class AIcManifestPackageSource(AIiPackageSource):
    """Reference file/HTTP package source backed by a small json/YAML manifest."""

    def __init__(
        self,
        source_id: str,
        manifest_uri: str,
        *,
        authentication: AIcAuthenticationService | None = None,
        authentication_profile_id: str | None = None,
        verifier_id: str | None = None,
        priority: int = 0,
        timeout_seconds: float = 30.0,
        context: Mapping[str, object] | None = None,
    ) -> None:
        self.source_id = source_id
        self.manifest_uri = manifest_uri
        self.authentication = authentication
        self.authentication_profile_id = authentication_profile_id
        self.verifier_id = verifier_id
        self.priority = int(priority)
        self.timeout_seconds = float(timeout_seconds)
        self.context = dict(context or {})

    def _load(self) -> tuple[AIcPackageCandidate, ...]:
        text = _read_uri(
            self.manifest_uri,
            authentication=self.authentication,
            authentication_profile_id=self.authentication_profile_id,
            context=self.context,
            timeout_seconds=self.timeout_seconds,
        ).decode("utf-8")
        raw = yaml.safe_load(text)
        if not isinstance(raw, Mapping) or int(raw.get("FormatVersion", 0)) != 1:
            raise AIxPackageManagementError("package source manifest requires FormatVersion: 1")
        raw_items = raw.get("Packages", ())
        if not isinstance(raw_items, list):
            raise AIxPackageManagementError("package source manifest packages must be an array")
        result: list[AIcPackageCandidate] = []
        for item in raw_items:
            if not isinstance(item, Mapping):
                raise AIxPackageManagementError("package source manifest item must be a mapping")
            artifact_uri = urljoin(self.manifest_uri, str(item["ArtifactUri"]))
            sidecars = tuple(
                AIcPackageSidecar(
                    urljoin(self.manifest_uri, str(sidecar["Uri"])),
                    str(sidecar["Suffix"]),
                    name=normalize_display_text(sidecar.get("Name")),
                    description=normalize_display_text(sidecar.get("Description")),
                )
                for sidecar in item.get("Sidecars", ())
            )
            result.append(AIcPackageCandidate(
                component_id=str(item["ComponentId"]),
                component_version=int(item["ComponentVersion"]),
                source_id=self.source_id,
                source_uri=self.manifest_uri,
                artifact_uri=artifact_uri,
                artifact_filename=str(item.get("ArtifactFilename") or Path(urlparse(artifact_uri).path).name),
                package_format=str(item["PackageFormat"]),
                descriptor_path=str(item["DescriptorPath"]),
                expected_sha256=str(item["Sha256"]) if item.get("Sha256") is not None else None,
                runtime_package=str(item["RuntimePackage"]) if item.get("RuntimePackage") is not None else None,
                verifier_id=str(item["VerifierId"]) if item.get("VerifierId") is not None else self.verifier_id,
                authentication_profile_id=self.authentication_profile_id,
                sidecars=sidecars,
                metadata=dict(item.get("Metadata", {})),
                name=normalize_display_text(item.get("Name")),
                description=normalize_display_text(item.get("Description")),
            ))
        return tuple(result)

    def candidates(self, requirement: AIcWorkspaceComponentRequirement) -> tuple[AIcPackageCandidate, ...]:
        return tuple(
            item for item in self._load()
            if item.component_id == requirement.component_id
            and requirement.accepts(item.component_version)
            and (not requirement.source_ids or item.source_id in requirement.source_ids)
        )
