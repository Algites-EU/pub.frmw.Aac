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

class AIcPackageStore:
    """Filesystem artifact store. Installed artifacts are immutable; active state is metadata elsewhere."""

    def __init__(self, layout: AIcPackageStoreLayout) -> None:
        self.layout = layout
        self.root = Path(layout.product_root) / layout.package_store_subdirectory
        self.downloaded_root = self.root / layout.downloaded_subdirectory
        self.installed_root = self.root / layout.installed_subdirectory
        self.obsolete_root = self.root / layout.obsolete_subdirectory

    def _directory(self, state: AInStoredPackageState, component_id: str, version: int, digest: str) -> Path:
        root = {
            AInStoredPackageState.DOWNLOADED: self.downloaded_root,
            AInStoredPackageState.INSTALLED: self.installed_root,
            AInStoredPackageState.OBSOLETE: self.obsolete_root,
        }[state]
        return root / _safe_segment(component_id) / str(version) / digest

    @staticmethod
    def _record_path(directory: Path) -> Path:
        return directory / "package-record.json"

    def _write_record(self, directory: Path, record: AIcStoredPackage) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        raw = {
            "component_id": record.component_id,
            "component_version": record.component_version,
            "sha256": record.sha256,
            "state": record.state.value,
            "artifact_filename": Path(record.artifact_path).name,
            "package_format": record.package_format,
            "descriptor_path": record.descriptor_path,
            "runtime_package": record.runtime_package,
            "provenance": {
                "source_id": record.provenance.source_id,
                "source_uri": record.provenance.source_uri,
                "artifact_uri": record.provenance.artifact_uri,
                "sha256": record.provenance.sha256,
                "downloaded_at": record.provenance.downloaded_at,
                "verifier_id": record.provenance.verifier_id,
                "signer_identity": record.provenance.signer_identity,
                "verification_metadata": dict(record.provenance.verification_metadata),
            },
            "sidecars": {suffix: Path(path).name for suffix, path in record.sidecar_paths.items()},
            "metadata": dict(record.metadata),
        }
        atomic_write_json(self._record_path(directory), raw)

    def _read_record(self, directory: Path) -> AIcStoredPackage:
        raw = json.loads(self._record_path(directory).read_text(encoding="utf-8"))
        provenance_raw = raw["provenance"]
        artifact_path = directory / raw["artifact_filename"]
        sidecars = {str(suffix): str(directory / filename) for suffix, filename in raw.get("sidecars", {}).items()}
        derived_state = AInStoredPackageState(str(raw["state"]))
        try:
            if directory.is_relative_to(self.downloaded_root):
                derived_state = AInStoredPackageState.DOWNLOADED
            elif directory.is_relative_to(self.installed_root):
                derived_state = AInStoredPackageState.INSTALLED
            elif directory.is_relative_to(self.obsolete_root):
                derived_state = AInStoredPackageState.OBSOLETE
        except (AttributeError, ValueError):
            pass
        return AIcStoredPackage(
            str(raw["component_id"]), int(raw["component_version"]), str(raw["sha256"]),
            derived_state, str(artifact_path), str(raw["package_format"]),
            str(raw["descriptor_path"]), raw.get("runtime_package"),
            AIcPackageProvenance(
                str(provenance_raw["source_id"]), provenance_raw.get("source_uri"),
                str(provenance_raw["artifact_uri"]), str(provenance_raw["sha256"]),
                str(provenance_raw["downloaded_at"]), provenance_raw.get("verifier_id"),
                provenance_raw.get("signer_identity"), dict(provenance_raw.get("verification_metadata", {})),
            ),
            sidecars, dict(raw.get("metadata", {})),
        )

    def store_downloaded(self, candidate: AIcPackageCandidate, *, authentication: AIcAuthenticationService | None = None,
                         context: Mapping[str, object] | None = None) -> AIcStoredPackage:
        self.downloaded_root.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="download-", dir=self.downloaded_root))
        try:
            artifact = temp_dir / Path(candidate.artifact_filename).name
            artifact.write_bytes(_read_uri(
                candidate.artifact_uri, authentication=authentication,
                authentication_profile_id=candidate.authentication_profile_id, context=context,
            ))
            fsync_file(artifact)
            digest = _sha256(artifact)
            if candidate.expected_sha256 is not None and digest != candidate.expected_sha256:
                raise AIxPackageDigestMismatch(
                    f"package digest mismatch for {candidate.component_id}/{candidate.component_version}: "
                    f"expected {candidate.expected_sha256}, got {digest}"
                )
            sidecar_paths: dict[str, str] = {}
            for sidecar in candidate.sidecars:
                path = Path(str(artifact) + sidecar.suffix)
                path.write_bytes(_read_uri(
                    sidecar.uri, authentication=authentication,
                    authentication_profile_id=candidate.authentication_profile_id, context=context,
                ))
                fsync_file(path)
                sidecar_paths[sidecar.suffix] = str(path)
            final_dir = self._directory(AInStoredPackageState.DOWNLOADED, candidate.component_id, candidate.component_version, digest)
            if final_dir.exists():
                shutil.rmtree(temp_dir)
                return self._read_record(final_dir)
            provenance = AIcPackageProvenance(
                candidate.source_id, candidate.source_uri, candidate.artifact_uri, digest, _now()
            )
            record = AIcStoredPackage(
                candidate.component_id, candidate.component_version, digest, AInStoredPackageState.DOWNLOADED,
                str(artifact), candidate.package_format, candidate.descriptor_path, candidate.runtime_package,
                provenance, sidecar_paths, dict(candidate.metadata),
            )
            self._write_record(temp_dir, record)
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            fsync_directory(temp_dir)
            durable_replace(temp_dir, final_dir)
            return self._read_record(final_dir)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def install(self, downloaded: AIcStoredPackage, verifier: AIiPackageVerifier, *, verifier_id: str | None = None) -> AIcStoredPackage:
        if downloaded.state is not AInStoredPackageState.DOWNLOADED:
            raise AIxPackageManagementError("only downloaded packages can be installed")
        source_artifact = Path(downloaded.artifact_path)
        if _sha256(source_artifact) != downloaded.sha256:
            raise AIxPackageDigestMismatch("downloaded artifact changed after it entered the package store")
        target_dir = self._directory(AInStoredPackageState.INSTALLED, downloaded.component_id, downloaded.component_version, downloaded.sha256)
        if target_dir.exists():
            return self._read_record(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="install-", dir=target_dir.parent))
        try:
            target_artifact = temp_dir / source_artifact.name
            shutil.copy2(source_artifact, target_artifact)
            fsync_file(target_artifact)
            sidecars: dict[str, str] = {}
            for suffix, source in downloaded.sidecar_paths.items():
                target = Path(str(target_artifact) + suffix)
                shutil.copy2(source, target)
                fsync_file(target)
                sidecars[suffix] = str(target)
            # Mandatory re-verification of the exact bytes in the temporary install destination.
            output = verifier.verify(AIcVerificationInput(
                downloaded.component_id, downloaded.component_version, downloaded.runtime_package,
                downloaded.provenance.artifact_uri, downloaded.metadata, str(target_artifact),
            ))
            if not output.valid:
                raise AIxPackageManagementError("package verification failed before install promotion: " + "; ".join(output.diagnostics))
            if _sha256(target_artifact) != downloaded.sha256:
                raise AIxPackageDigestMismatch("install destination bytes differ from downloaded artifact")
            provenance = replace(
                downloaded.provenance,
                verifier_id=output.verifier_id or verifier_id or downloaded.provenance.verifier_id,
                signer_identity=output.signer_identity or downloaded.provenance.signer_identity,
                verification_metadata=dict(output.metadata),
            )
            record = AIcStoredPackage(
                downloaded.component_id, downloaded.component_version, downloaded.sha256,
                AInStoredPackageState.INSTALLED, str(target_artifact), downloaded.package_format,
                downloaded.descriptor_path, downloaded.runtime_package, provenance, sidecars, downloaded.metadata,
            )
            self._write_record(temp_dir, record)
            fsync_directory(temp_dir)
            durable_replace(temp_dir, target_dir)
            return self._read_record(target_dir)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def mark_obsolete(self, installed: AIcStoredPackage) -> AIcStoredPackage:
        if installed.state is not AInStoredPackageState.INSTALLED:
            raise AIxPackageManagementError("only installed packages can be marked obsolete")
        source_dir = Path(installed.artifact_path).parent
        target_dir = self._directory(AInStoredPackageState.OBSOLETE, installed.component_id, installed.component_version, installed.sha256)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(source_dir, ignore_errors=True)
            return self._read_record(target_dir)
        durable_replace(source_dir, target_dir)
        record = replace(installed, state=AInStoredPackageState.OBSOLETE, artifact_path=str(target_dir / Path(installed.artifact_path).name),
                         sidecar_paths={suffix: str(target_dir / Path(path).name) for suffix, path in installed.sidecar_paths.items()})
        self._write_record(target_dir, record)
        return record

    def restore_obsolete(self, obsolete: AIcStoredPackage) -> AIcStoredPackage:
        if obsolete.state is not AInStoredPackageState.OBSOLETE:
            raise AIxPackageManagementError("only obsolete packages can be restored")
        source_dir = Path(obsolete.artifact_path).parent
        target_dir = self._directory(AInStoredPackageState.INSTALLED, obsolete.component_id, obsolete.component_version, obsolete.sha256)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(source_dir, ignore_errors=True)
            return self._read_record(target_dir)
        durable_replace(source_dir, target_dir)
        record = replace(obsolete, state=AInStoredPackageState.INSTALLED, artifact_path=str(target_dir / Path(obsolete.artifact_path).name),
                         sidecar_paths={suffix: str(target_dir / Path(path).name) for suffix, path in obsolete.sidecar_paths.items()})
        self._write_record(target_dir, record)
        return record

    def records(self, state: AInStoredPackageState | None = None, component_id: str | None = None) -> tuple[AIcStoredPackage, ...]:
        roots = [
            (AInStoredPackageState.DOWNLOADED, self.downloaded_root),
            (AInStoredPackageState.INSTALLED, self.installed_root),
            (AInStoredPackageState.OBSOLETE, self.obsolete_root),
        ]
        result: list[AIcStoredPackage] = []
        for candidate_state, root in roots:
            if state is not None and candidate_state is not state:
                continue
            if not root.exists():
                continue
            for record_path in root.rglob("package-record.json"):
                record = self._read_record(record_path.parent)
                if component_id is None or record.component_id == component_id:
                    result.append(record)
        result.sort(key=lambda item: (item.component_id, item.component_version, item.sha256, item.state.value))
        return tuple(result)

    def find(self, component_id: str, version: int, sha256: str, state: AInStoredPackageState = AInStoredPackageState.INSTALLED) -> AIcStoredPackage | None:
        directory = self._directory(state, component_id, version, sha256)
        return self._read_record(directory) if self._record_path(directory).exists() else None
