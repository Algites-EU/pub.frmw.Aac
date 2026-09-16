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

from algites.lib.aac.coreintf.authentication import AIcAuthenticationMaterial
from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor
from algites.lib.aac.coreintf.errors import AIxPackageDigestMismatch, AIxPackageManagementError, AIxPackageRevisionConflict
from algites.lib.aac.coreintf.packages import (
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
from algites.lib.aac.coreintf.persistence import AIcStateMutation, AIiStateStore
from algites.lib.aac.coreintf.verification import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier
from algites.lib.aac.coreintf.presentation import normalize_display_text

from .authentication import AIcAuthenticationService
from .descriptor import AIcDescriptorLoader
from .persistence import AIcInMemoryStateStore
from .package_transactions import AIcDurablePackageSelectionManifestStore, AIcPackageReplacementJournal
from .durable import atomic_write_json, durable_replace, fsync_directory, fsync_file

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


class AIcPackageVerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: dict[str, AIiPackageVerifier] = {}

    def register(self, verifier_id: str, verifier: AIiPackageVerifier) -> None:
        if not verifier_id:
            raise ValueError("package verifier id must not be empty")
        self._verifiers[verifier_id] = verifier

    def get(self, verifier_id: str) -> AIiPackageVerifier:
        return self._verifiers[verifier_id]

    def contains(self, verifier_id: str) -> bool:
        return verifier_id in self._verifiers


class AIcStaticPackageSource(AIiPackageSource):
    def __init__(self, source_id: str, candidates: tuple[AIcPackageCandidate, ...], *, priority: int = 0) -> None:
        self.source_id = source_id
        self.priority = int(priority)
        self._candidates = tuple(candidates)

    def candidates(self, requirement: AIcWorkspaceComponentRequirement) -> tuple[AIcPackageCandidate, ...]:
        return tuple(
            item for item in self._candidates
            if item.component_id == requirement.component_id
            and requirement.accepts(item.component_version)
            and (not requirement.source_ids or item.source_id in requirement.source_ids)
        )


class AIcManifestPackageSource(AIiPackageSource):
    """Reference file/HTTP package source backed by a small JSON/YAML manifest."""

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
        if not isinstance(raw, Mapping) or int(raw.get("format_version", 0)) != 1:
            raise AIxPackageManagementError("package source manifest requires format_version: 1")
        raw_items = raw.get("packages", ())
        if not isinstance(raw_items, list):
            raise AIxPackageManagementError("package source manifest packages must be an array")
        result: list[AIcPackageCandidate] = []
        for item in raw_items:
            if not isinstance(item, Mapping):
                raise AIxPackageManagementError("package source manifest item must be a mapping")
            artifact_uri = urljoin(self.manifest_uri, str(item["artifact_uri"]))
            sidecars = tuple(
                AIcPackageSidecar(
                    urljoin(self.manifest_uri, str(sidecar["uri"])),
                    str(sidecar["suffix"]),
                    name=normalize_display_text(sidecar.get("name")),
                    description=normalize_display_text(sidecar.get("description")),
                )
                for sidecar in item.get("sidecars", ())
            )
            result.append(AIcPackageCandidate(
                component_id=str(item["component_id"]),
                component_version=int(item["component_version"]),
                source_id=self.source_id,
                source_uri=self.manifest_uri,
                artifact_uri=artifact_uri,
                artifact_filename=str(item.get("artifact_filename") or Path(urlparse(artifact_uri).path).name),
                package_format=str(item["package_format"]),
                descriptor_path=str(item["descriptor_path"]),
                expected_sha256=str(item["sha256"]) if item.get("sha256") is not None else None,
                runtime_package=str(item["runtime_package"]) if item.get("runtime_package") is not None else None,
                verifier_id=str(item["verifier_id"]) if item.get("verifier_id") is not None else self.verifier_id,
                authentication_profile_id=self.authentication_profile_id,
                sidecars=sidecars,
                metadata=dict(item.get("metadata", {})),
                name=normalize_display_text(item.get("name")),
                description=normalize_display_text(item.get("description")),
            ))
        return tuple(result)

    def candidates(self, requirement: AIcWorkspaceComponentRequirement) -> tuple[AIcPackageCandidate, ...]:
        return tuple(
            item for item in self._load()
            if item.component_id == requirement.component_id
            and requirement.accepts(item.component_version)
            and (not requirement.source_ids or item.source_id in requirement.source_ids)
        )


class AIcPackageSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, tuple[int, AIiPackageSource]] = {}

    def register(self, source_id: str, source: AIiPackageSource, *, priority: int = 0) -> None:
        if not source_id:
            raise ValueError("package source id must not be empty")
        self._sources[source_id] = (int(priority), source)

    def get(self, source_id: str) -> AIiPackageSource:
        return self._sources[source_id][1]

    def candidates(self, requirement: AIcWorkspaceComponentRequirement) -> tuple[AIcPackageCandidate, ...]:
        result: list[tuple[int, AIcPackageCandidate]] = []
        for source_id, (priority, source) in self._sources.items():
            if requirement.source_ids and source_id not in requirement.source_ids:
                continue
            result.extend((priority, item) for item in source.candidates(requirement))
        result.sort(key=lambda item: (-item[1].component_version, -item[0], item[1].source_id, item[1].artifact_uri))
        return tuple(item for _, item in result)


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


class AIcPackageSelectionStore:
    def __init__(
        self, store: AIiStateStore | None = None,
        manifest_store: AIcDurablePackageSelectionManifestStore | None = None,
    ) -> None:
        self.store = store or AIcInMemoryStateStore()
        self.manifest_store = manifest_store
        if self.manifest_store is not None and not self.manifest_store.path.exists():
            self._migrate_legacy_state_if_present()

    @staticmethod
    def _key(application_scope_id: str, component_id: str) -> str:
        return f"{application_scope_id}:{component_id}"

    def _migrate_legacy_state_if_present(self) -> None:
        raw_values = self.store.list(_PACKAGE_SELECTION_NAMESPACE)
        if not raw_values:
            return
        values: list[AIcPackageSelection] = []
        for key, raw in raw_values.items():
            application_scope_id, component_id = key.split(":", 1)
            values.append(AIcPackageSelection(
                application_scope_id, component_id, int(raw["component_version"]), str(raw["sha256"]),
                str(raw["selected_at"]),
                str(raw["previous_sha256"]) if raw.get("previous_sha256") is not None else None,
                int(raw["previous_version"]) if raw.get("previous_version") is not None else None,
            ))
        manifest = AIcPackageSelectionManifest(1, tuple(sorted(values, key=lambda item: (item.application_scope_id, item.component_id))))
        self.manifest_store.write(manifest, expected_record_revision=0)
        records = self.store.list_records(_PACKAGE_SELECTION_NAMESPACE)
        self.store.apply(tuple(
            AIcStateMutation.delete(
                _PACKAGE_SELECTION_NAMESPACE, key, expected_record_revision=records[key].record_revision
            )
            for key in raw_values if key in records
        ))

    def manifest(self) -> AIcPackageSelectionManifest:
        if self.manifest_store is not None:
            return self.manifest_store.read()
        values = []
        for key, raw in self.store.list(_PACKAGE_SELECTION_NAMESPACE).items():
            application_scope_id, component_id = key.split(":", 1)
            values.append(AIcPackageSelection(
                application_scope_id, component_id, int(raw["component_version"]), str(raw["sha256"]),
                str(raw["selected_at"]),
                str(raw["previous_sha256"]) if raw.get("previous_sha256") is not None else None,
                int(raw["previous_version"]) if raw.get("previous_version") is not None else None,
            ))
        return AIcPackageSelectionManifest(0, tuple(sorted(values, key=lambda item: (item.application_scope_id, item.component_id))))

    def _write_manifest(self, manifest: AIcPackageSelectionManifest) -> None:
        if self.manifest_store is not None:
            current = self.manifest_store.read()
            self.manifest_store.write(manifest, expected_record_revision=current.record_revision)
            return
        current_records = self.store.list_records(_PACKAGE_SELECTION_NAMESPACE)
        current_keys = set(current_records)
        target = {self._key(item.application_scope_id, item.component_id): item for item in manifest.selections}
        mutations = []
        for key in current_keys - set(target):
            mutations.append(AIcStateMutation.delete(
                _PACKAGE_SELECTION_NAMESPACE, key,
                expected_record_revision=current_records[key].record_revision,
            ))
        for key, item in target.items():
            current = current_records.get(key)
            mutations.append(AIcStateMutation.put(_PACKAGE_SELECTION_NAMESPACE, key, {
                "component_version": item.component_version,
                "sha256": item.sha256,
                "selected_at": item.selected_at,
                "previous_sha256": item.previous_sha256,
                "previous_version": item.previous_version,
            }, expected_record_revision=None if current is None else current.record_revision, expect_absent=current is None))
        self.store.apply(tuple(mutations))

    def get(self, application_scope_id: str, component_id: str) -> AIcPackageSelection | None:
        return next((
            item for item in self.manifest().selections
            if item.application_scope_id == application_scope_id and item.component_id == component_id
        ), None)

    def all(self) -> tuple[AIcPackageSelection, ...]:
        return self.manifest().selections

    def plan_replacements(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[AIcPackageSelectionManifest, AIcPackageSelectionManifest]:
        ids = [item.component_id for item in packages]
        if len(ids) != len(set(ids)):
            raise AIxPackageManagementError("package replacement transaction must be unique by component id")
        for package in packages:
            if package.state is not AInStoredPackageState.INSTALLED:
                raise AIxPackageManagementError("only installed package artifacts can be selected")
        source = self.manifest()
        values = {(item.application_scope_id, item.component_id): item for item in source.selections}
        for package in packages:
            conflicts = tuple(
                item for item in source.selections
                if item.component_id == package.component_id
                and item.application_scope_id != application_scope_id
                and (item.component_version != package.component_version or item.sha256 != package.sha256)
            )
            if conflicts:
                scopes = ", ".join(sorted(item.application_scope_id for item in conflicts))
                raise AIxPackageRevisionConflict(
                    f"component {package.component_id!r} already has a different active artifact in scopes: {scopes}"
                )
            key = (application_scope_id, package.component_id)
            previous = values.get(key)
            values[key] = AIcPackageSelection(
                application_scope_id, package.component_id, package.component_version, package.sha256, _now(),
                None if previous is None else previous.sha256,
                None if previous is None else previous.component_version,
            )
        target = AIcPackageSelectionManifest(
            source.record_revision + 1,
            tuple(sorted(values.values(), key=lambda item: (item.application_scope_id, item.component_id))),
            None,
        )
        return source, target

    def commit_planned(
        self, source: AIcPackageSelectionManifest, target: AIcPackageSelectionManifest,
        *, transaction_id: str | None = None,
    ) -> AIcPackageSelectionManifest:
        current = self.manifest()
        if current.record_revision != source.record_revision or current.selections != source.selections:
            raise AIxPackageRevisionConflict("active package set changed after replacement planning")
        committed = replace(target, last_transaction_id=transaction_id)
        if self.manifest_store is not None:
            self.manifest_store.write(committed, expected_record_revision=source.record_revision)
        else:
            self._write_manifest(committed)
        return committed

    def select(self, application_scope_id: str, package: AIcStoredPackage) -> AIcPackageSelection:
        source, target = self.plan_replacements(application_scope_id, (package,))
        committed = self.commit_planned(source, target)
        return next(
            item for item in committed.selections
            if item.application_scope_id == application_scope_id and item.component_id == package.component_id
        )

    def references(self, package: AIcStoredPackage) -> tuple[AIcPackageSelection, ...]:
        return tuple(
            item for item in self.all()
            if item.component_id == package.component_id
            and item.component_version == package.component_version
            and item.sha256 == package.sha256
        )

    def rollback(self, application_scope_id: str, component_id: str, package_store: AIcPackageStore) -> AIcPackageSelection:
        current = self.get(application_scope_id, component_id)
        if current is None or current.previous_sha256 is None or current.previous_version is None:
            raise AIxPackageRevisionConflict(f"no previous package selection exists for {component_id!r}")
        previous = package_store.find(component_id, current.previous_version, current.previous_sha256)
        if previous is None:
            obsolete = package_store.find(
                component_id, current.previous_version, current.previous_sha256, AInStoredPackageState.OBSOLETE,
            )
            if obsolete is None:
                raise AIxPackageRevisionConflict("previous package artifact is no longer retained")
            previous = package_store.restore_obsolete(obsolete)
        return self.select(application_scope_id, previous)


class AIcPackageManager:
    def __init__(
        self,
        layout: AIcPackageStoreLayout,
        *,
        authentication: AIcAuthenticationService | None = None,
        store: AIiStateStore | None = None,
        automation_policy: AIcPackageAutomationPolicy = AIcPackageAutomationPolicy(),
    ) -> None:
        self.authentication = authentication or AIcAuthenticationService()
        self.package_store = AIcPackageStore(layout)
        self.sources = AIcPackageSourceRegistry()
        self.verifiers = AIcPackageVerifierRegistry()
        self.state_store = store or AIcInMemoryStateStore()
        state_root = Path(layout.product_root) / layout.core_state_subdirectory
        mutation_lock_path = Path(getattr(
            self.state_store, "mutation_lock_path", state_root / layout.core_lock_filename
        ))
        self.selection_manifest_store = AIcDurablePackageSelectionManifestStore(
            state_root / "active-package-set.json", mutation_lock_path=mutation_lock_path
        )
        self.selections = AIcPackageSelectionStore(self.state_store, self.selection_manifest_store)
        self.transactions = AIcPackageReplacementJournal(
            layout, self.selection_manifest_store, self.state_store
        )
        self.transaction_recovery = self.transactions.recover(self.package_store)
        self.automation_policy = automation_policy

    def register_source(self, source_id: str, source: AIiPackageSource, *, priority: int = 0) -> None:
        self.sources.register(source_id, source, priority=priority)

    def register_verifier(self, verifier_id: str, verifier: AIiPackageVerifier) -> None:
        self.verifiers.register(verifier_id, verifier)

    def _verifier_for(self, candidate: AIcPackageCandidate, fallback: AIiPackageVerifier | None = None) -> AIiPackageVerifier:
        if candidate.verifier_id is not None:
            return self.verifiers.get(candidate.verifier_id)
        if fallback is not None:
            return fallback
        raise AIxPackageManagementError(f"package candidate {candidate.component_id!r} does not select a verifier")

    def download(self, candidate: AIcPackageCandidate, *, fallback_verifier: AIiPackageVerifier | None = None,
                 context: Mapping[str, object] | None = None) -> AIcStoredPackage:
        record = self.package_store.store_downloaded(candidate, authentication=self.authentication, context=context)
        if self.automation_policy.verify_on_download:
            verifier = self._verifier_for(candidate, fallback_verifier)
            output = verifier.verify(AIcVerificationInput(
                candidate.component_id, candidate.component_version, candidate.runtime_package,
                candidate.artifact_uri, candidate.metadata, record.artifact_path,
            ))
            if not output.valid:
                raise AIxPackageManagementError("downloaded package verification failed: " + "; ".join(output.diagnostics))
            provenance = replace(record.provenance, verifier_id=output.verifier_id or candidate.verifier_id,
                                 signer_identity=output.signer_identity, verification_metadata=dict(output.metadata))
            record = replace(record, provenance=provenance)
            self.package_store._write_record(Path(record.artifact_path).parent, record)
        return record

    def install(self, candidate: AIcPackageCandidate, downloaded: AIcStoredPackage, *, fallback_verifier: AIiPackageVerifier | None = None) -> AIcStoredPackage:
        verifier = self._verifier_for(candidate, fallback_verifier)
        return self.package_store.install(downloaded, verifier, verifier_id=candidate.verifier_id)

    def descriptor_from_artifact(self, package: AIcStoredPackage) -> AIcComponentDescriptor:
        if package.package_format.upper() not in {"PYTHON_WHEEL", "ZIP"}:
            raise AIxPackageManagementError(f"descriptor inspection unsupported for package format {package.package_format!r}")
        from zipfile import ZipFile, BadZipFile
        try:
            with ZipFile(package.artifact_path) as archive:
                text = archive.read(package.descriptor_path).decode("utf-8")
        except (OSError, BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise AIxPackageManagementError(f"cannot inspect component descriptor in package artifact: {exc}") from exc
        descriptor = AIcDescriptorLoader.load_text(text, source=f"{package.artifact_path}!/{package.descriptor_path}")
        if descriptor.id != package.component_id or descriptor.version != package.component_version:
            raise AIxPackageManagementError("package manifest component identity does not match descriptor inside artifact")
        return descriptor

    @staticmethod
    def automatic_entitlement_allows(descriptor: AIcComponentDescriptor, effective_permission_ids: set[tuple[str, int, str]]) -> bool:
        if not descriptor.provided_capability_entitlements:
            return True
        if any(permission.implicit for item in descriptor.provided_capability_entitlements for permission in item.permissions):
            return True
        declared = {
            (item.capability_id, item.capability_version, permission.id)
            for item in descriptor.provided_capability_entitlements for permission in item.permissions
        }
        return bool(declared & effective_permission_ids)

    def mark_obsolete(self, package: AIcStoredPackage) -> AIcStoredPackage:
        references = self.selections.references(package)
        if references:
            scopes = ", ".join(item.application_scope_id for item in references)
            raise AIxPackageManagementError(
                f"cannot mark selected package obsolete; selected by application/workspace scopes: {scopes}"
            )
        return self.package_store.mark_obsolete(package)

    def restore_obsolete(self, package: AIcStoredPackage) -> AIcStoredPackage:
        return self.package_store.restore_obsolete(package)


    def begin_replacement_transaction(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...],
        core_state_snapshot: Mapping[str, Mapping[str, Mapping[str, object]]],
    ):
        source_manifest, target_manifest = self.selections.plan_replacements(application_scope_id, packages)
        return self.transactions.begin(
            application_scope_id, source_manifest, target_manifest, packages, core_state_snapshot
        )

    def mark_replacement_cutover_started(self, transaction) -> None:
        self.transactions.mark_cutover_started(
            transaction.transaction_id, transaction.core_state_snapshot
        )

    def commit_replacement_selections(
        self, transaction
    ) -> tuple[AIcPackageSelectionManifest, tuple[str, ...]]:
        committed = self.selections.commit_planned(
            transaction.source_manifest, transaction.target_manifest, transaction_id=transaction.transaction_id
        )
        diagnostics: list[str] = []
        try:
            self.transactions.mark_target_committed(transaction.transaction_id)
        except Exception as exc:
            # The active package-set manifest is the durable commit marker.  If updating the journal
            # phase fails after that atomic replacement, the transaction is nevertheless committed;
            # startup recovery infers this from record revision + transaction id and completes cleanup.
            diagnostics.append(f"target package set committed; journal phase update deferred: {exc}")
        return committed, tuple(diagnostics)

    def complete_replacement_transaction(
        self, transaction, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[tuple[AIcStoredPackage, ...], tuple[str, ...]]:
        retired: list[AIcStoredPackage] = []
        diagnostics: list[str] = []
        for package in packages:
            for old in self.package_store.records(AInStoredPackageState.INSTALLED, package.component_id):
                if old.identity == package.identity or self.selections.references(old):
                    continue
                try:
                    retired.append(self.package_store.mark_obsolete(old))
                except Exception as exc:
                    diagnostics.append(
                        f"deferred cleanup for {old.component_id}/{old.component_version}/{old.sha256}: {exc}"
                    )
        if diagnostics:
            # Keep the active-transaction pointer. Startup recovery will deterministically finish
            # the already-committed target cleanup; release the process lock because the durable
            # active-set record is already authoritative.
            self.transactions.release_cutover_lock()
            return tuple(retired), tuple(diagnostics)
        self.transactions.mark_cleanup_completed(transaction.transaction_id)
        self.transactions.finish(transaction.transaction_id)
        return tuple(retired), ()

    def rollback_replacement_transaction(self, transaction, diagnostics: tuple[str, ...] = ()) -> None:
        self.transactions.mark_rolled_back(transaction.transaction_id, diagnostics)
        self.transactions.finish(transaction.transaction_id)

    def release_replacement_cutover_lock(self) -> None:
        self.transactions.release_cutover_lock()

    def activate_replacements(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[dict[str, AIcStoredPackage | None], tuple[AIcStoredPackage, ...]]:
        """Atomically select a replacement set and retire unselected old artifacts.

        Core replacement code uses the explicit durable transaction methods above.  This convenience
        method remains for package-only callers and still commits the full selection set atomically.
        """
        previous: dict[str, AIcStoredPackage | None] = {}
        for package in packages:
            selection = self.selections.get(application_scope_id, package.component_id)
            previous[package.component_id] = (
                self.package_store.find(package.component_id, selection.component_version, selection.sha256)
                if selection is not None else None
            )
        source, target = self.selections.plan_replacements(application_scope_id, packages)
        self.selections.commit_planned(source, target)
        retired: list[AIcStoredPackage] = []
        for package in packages:
            for old in self.package_store.records(AInStoredPackageState.INSTALLED, package.component_id):
                if old.identity == package.identity or self.selections.references(old):
                    continue
                retired.append(self.package_store.mark_obsolete(old))
        return previous, tuple(retired)

    def rollback_replacements(
        self, application_scope_id: str, previous: Mapping[str, AIcStoredPackage | None],
        targets: tuple[AIcStoredPackage, ...],
    ) -> None:
        """Legacy in-process compensation helper for package-only callers."""
        restored_targets = []
        for component_id, old in previous.items():
            if old is None:
                continue
            restored = old
            if old.state is AInStoredPackageState.OBSOLETE:
                restored = self.package_store.restore_obsolete(old)
            elif self.package_store.find(old.component_id, old.component_version, old.sha256) is None:
                obsolete = self.package_store.find(
                    old.component_id, old.component_version, old.sha256, AInStoredPackageState.OBSOLETE
                )
                if obsolete is not None:
                    restored = self.package_store.restore_obsolete(obsolete)
            restored_targets.append(restored)
        if restored_targets:
            source, target = self.selections.plan_replacements(application_scope_id, tuple(restored_targets))
            self.selections.commit_planned(source, target)
        for target in targets:
            current = self.package_store.find(target.component_id, target.component_version, target.sha256)
            if current is not None and not self.selections.references(current):
                self.package_store.mark_obsolete(current)

    def plan_workspace(self, requirements: AIcWorkspaceComponentRequirements,
                       lock: AIcWorkspaceComponentLock | None = None) -> AIcPackageReconciliationPlan:
        actions: list[AIcPackageReconciliationAction] = []
        installed = self.package_store.records(AInStoredPackageState.INSTALLED)
        by_component: dict[str, list[AIcStoredPackage]] = {}
        for item in installed:
            by_component.setdefault(item.component_id, []).append(item)
        for requirement in requirements.requirements:
            lock_entry = lock.entry(requirement.component_id) if lock is not None else None
            existing = [item for item in by_component.get(requirement.component_id, ()) if requirement.accepts(item.component_version)]
            if lock_entry is not None:
                exact = next((item for item in existing if item.component_version == lock_entry.component_version and item.sha256 == lock_entry.sha256), None)
                if exact is not None:
                    actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="locked artifact is installed"))
                    continue
                candidate = _candidate_from_lock(lock_entry)
            else:
                candidates = self.sources.candidates(requirement)
                candidate = candidates[0] if candidates else None
                if existing and candidate is not None:
                    newest = max(existing, key=lambda item: item.component_version)
                    if newest.component_version >= candidate.component_version:
                        actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="compatible installed artifact is current"))
                        continue
                elif existing:
                    actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="compatible artifact is installed"))
                    continue
            if candidate is None:
                actions.append(AIcPackageReconciliationAction(
                    requirement.component_id, "MISSING" if requirement.required else "OPTIONAL_MISSING",
                    reason="no compatible package candidate",
                ))
                continue
            if requirements.update_policy is AInPackageUpdatePolicy.MANUAL:
                action = "INSTALL_AVAILABLE"
            elif requirements.update_policy is AInPackageUpdatePolicy.NOTIFY:
                action = "UPDATE_AVAILABLE"
            elif requirements.update_policy is AInPackageUpdatePolicy.AUTO_LOCKED and lock_entry is None:
                action = "LOCK_REQUIRED"
            else:
                action = "AUTO_INSTALL"
            actions.append(AIcPackageReconciliationAction(requirement.component_id, action, candidate, "compatible candidate selected"))
        return AIcPackageReconciliationPlan(requirements.workspace_id, requirements.update_policy, tuple(actions))


def _candidate_from_lock(entry: AIcWorkspaceComponentLockEntry) -> AIcPackageCandidate:
    return AIcPackageCandidate(
        component_id=entry.component_id, component_version=entry.component_version, source_id=entry.source_id,
        artifact_uri=entry.artifact_uri, artifact_filename=entry.artifact_filename, expected_sha256=entry.sha256,
        package_format=entry.package_format, descriptor_path=entry.descriptor_path, runtime_package=entry.runtime_package,
        verifier_id=entry.verifier_id, sidecars=entry.sidecars,
    )
