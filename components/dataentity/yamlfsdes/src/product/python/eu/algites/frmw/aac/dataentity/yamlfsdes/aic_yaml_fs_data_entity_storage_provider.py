from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import shutil
import threading
import time
import zipfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence
from uuid import uuid4
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from eu.algites.frmw.aac.core.dataentity.api import (
    AIiDataEntityApplyDirectRecordChanges_1,
    AIiDataEntityCreateStorageBackup_1,
    AIiDataEntityEnsureStorageSupport_1,
    AIiDataEntityGetRecord_1,
    AIiDataEntityInspectStorageBackup_1,
    AIiDataEntityInspectStorageSupport_1,
    AIiDataEntityQueryRecords_1,
    AIiDataEntityRetireStorageSupport_1,
    AIiDataEntityRestoreStorageBackup_1,
)
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationInteractionEventType, AInStateResultDeliveryMode, AIcOperationInteractionEvent, AIcOperationInteractionFeatures, AIxOperationCancelled,
    current_operation_interaction,
)
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

from .aic_operation_progress import AIcOperationProgress
from .aic_operation_state_result_publisher import AIcOperationStateResultPublisher

_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")

_RECORD_KEYS = {"Uid", "SchemaId", "SchemaVersion", "RecordRevision", "State", "Payload"}

_SUPPORT_STATUSES = {"ready", "retired"}

_TRANSACTION_STATES = {"prepared", "COMMITTING", "committed"}

_SUPPORT_FORMAT_VERSION = 1

_TRANSACTION_FORMAT_VERSION = 1

_BACKUP_FORMAT_VERSION = 1

_LAYOUT_FORMAT_VERSION = 1

def _safe_segment(value: object, field: str) -> str:
    text = _non_empty_string(value, field)
    if _SAFE_SEGMENT.fullmatch(text) is None:
        raise ValueError(f"{field} must use portable filesystem identifier characters [A-Za-z0-9._-]")
    return text

def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value

def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be an integer >= 1")
    return value

def _string_set(value: object, field: str) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field} must be an array")
    return {_non_empty_string(item, field) for item in value}

def _integer_set(value: object, field: str) -> set[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field} must be an array")
    return {_positive_int(item, field) for item in value}

def _canonical_digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _read_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"cannot read YAML storage document {path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"YAML storage document must contain an object: {path}")
    return {str(key): value for key, value in raw.items()}

def _schema_path_to_data_path(schema_path: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    index = 0
    while index < len(schema_path):
        token = schema_path[index]
        if token == "properties" and index + 1 < len(schema_path):
            result.append(schema_path[index + 1])
            index += 2
        elif token == "items":
            result.append("*")
            index += 1
        else:
            index += 1
    return tuple(result)

def _values_at_path(value: object, path: Sequence[str]) -> tuple[object, ...]:
    if not path:
        return (value,)
    head, *tail = path
    if head == "*":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return ()
        result: list[object] = []
        for item in value:
            result.extend(_values_at_path(item, tail))
        return tuple(result)
    if not isinstance(value, Mapping) or head not in value:
        return ()
    return _values_at_path(value[head], tail)

def _lock_file(stream) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        if stream.read(1) == b"":
            stream.seek(0)
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)

def _unlock_file(stream) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)

class AIcYamlFsDataEntityStorageProvider(
    AIiProviderRuntime,
    AIiDataEntityGetRecord_1,
    AIiDataEntityInspectStorageBackup_1,
    AIiDataEntityQueryRecords_1,
    AIiDataEntityApplyDirectRecordChanges_1,
    AIiDataEntityCreateStorageBackup_1,
    AIiDataEntityInspectStorageSupport_1,
    AIiDataEntityEnsureStorageSupport_1,
    AIiDataEntityRetireStorageSupport_1,
    AIiDataEntityRestoreStorageBackup_1,
):
    """YAML filesystem implementation of the AAC generic Data Entity storage capabilities."""

    def __init__(self, configuration: Mapping[str, object] | None = None) -> None:
        configuration = dict(configuration or {})
        raw_root = configuration.get("RootDirectory")
        if not isinstance(raw_root, str) or not raw_root.strip():
            raise ValueError("root_directory must be a non-empty string")
        self.root = Path(raw_root).expanduser().resolve(strict=False)
        self._thread_lock = threading.RLock()

    def get_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        schema_id = _safe_segment(request.get("SchemaId"), "schema_id")
        uid = _safe_segment(request.get("Uid"), "uid")
        if not self.root.exists():
            return {"Record": None}
        with self._locked_storage():
            record = self._find_record(schema_id, uid)
            return {"Record": None if record is None else record}

    def query_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        schema_id = _safe_segment(request.get("SchemaId"), "schema_id")
        if not self.root.exists():
            return {"Records": [], "ContinuationToken": None}
        with self._locked_storage():
            states = _string_set(request.get("States", ("active",)), "states")
            if not states or not states.issubset({"active", "tombstone"}):
                raise ValueError("states must contain active and/or tombstone")
            versions = _integer_set(request.get("StoredSchemaVersionFilter", ()), "stored_schema_version_filter")
            uids = _string_set(request.get("Uids", ()), "uids")
            order = str(request.get("Order", "uid_asc"))
            if order not in {"uid_asc", "uid_desc"}:
                raise ValueError("order must be uid_asc or uid_desc")
            raw_limit = request.get("Limit")
            limit = None if raw_limit is None else int(raw_limit)
            if limit is not None and limit < 1:
                raise ValueError("limit must be >= 1 when specified")
            references = request.get("References", ())
            if not isinstance(references, Sequence) or isinstance(references, (str, bytes, bytearray)):
                raise TypeError("references must be an array")
            reference_match = str(request.get("ReferenceMatch", "all"))
            if reference_match not in {"all", "any"}:
                raise ValueError("reference_match must be all or any")

            criteria_digest = self._query_criteria_digest(request)
            cursor = self._decode_continuation_token(request.get("ContinuationToken"), criteria_digest)
            records = self._query_candidates(schema_id, versions)
            filtered: list[dict[str, object]] = []
            seen_uids: set[str] = set()
            for record in records:
                uid = str(record["Uid"])
                if uid in seen_uids:
                    raise RuntimeError(f"duplicate stored Data Entity identity {schema_id}/{uid}")
                seen_uids.add(uid)
                if str(record["State"]) not in states:
                    continue
                if uids and uid not in uids:
                    continue
                if references and not self._matches_references(record, references, reference_match):
                    continue
                filtered.append(record)

            filtered.sort(key=lambda item: str(item["Uid"]), reverse=order == "uid_desc")
            if cursor is not None:
                if order == "uid_asc":
                    filtered = [item for item in filtered if str(item["Uid"]) > cursor]
                else:
                    filtered = [item for item in filtered if str(item["Uid"]) < cursor]

            page = filtered if limit is None else filtered[:limit]
            token = None
            if limit is not None and len(filtered) > limit and page:
                token = self._encode_continuation_token(criteria_digest, str(page[-1]["Uid"]))
            publisher = AIcOperationStateResultPublisher()
            published: list[dict[str, object]] = []
            for record in page:
                published.append(record)
                publisher.publish(
                    complete={"Records": list(published), "ContinuationToken": token},
                    delta={"Records": [record], "ContinuationToken": token},
                )
            return {"Records": page, "ContinuationToken": token}

    def apply_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        progress = AIcOperationProgress()
        progress.report("prepare", "Preparing Data Entity changes", force=True)
        raw_changes = request.get("Changes")
        if not isinstance(raw_changes, Sequence) or isinstance(raw_changes, (str, bytes, bytearray)) or not raw_changes:
            raise ValueError("changes must be a non-empty array")
        with self._locked_storage(create_root=True):
            plans, results = self._plan_changes(raw_changes)
            progress.report("prepare", "Preparing Data Entity changes", current=len(plans), total=len(plans), unit="CHANGES")
            transaction = self._prepare_transaction(plans)
            self._set_transaction_state(transaction, "COMMITTING")
            try:
                self._finish_transaction(transaction)
            except Exception:
                self._finish_transaction(transaction)
            self._set_transaction_state(transaction, "committed")
            self._cleanup_transaction(transaction)
            publisher = AIcOperationStateResultPublisher()
            published: list[dict[str, object]] = []
            for result in results:
                published.append(result)
                publisher.publish(complete={"Changes": list(published)}, delta={"Changes": [result]})
            progress.report("completed", "Data Entity changes committed", current=len(results), total=len(results), unit="CHANGES", force=True)
            return {"Changes": results}

    def inspect_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        schema_id = _safe_segment(request.get("SchemaId"), "schema_id")
        schema_version = _positive_int(request.get("SchemaVersion"), "schema_version")
        if not self.root.exists():
            return {"Status": "not_provisioned", "Metadata": self._support_metadata(schema_id, schema_version, None)}
        with self._locked_storage():
            return self._inspect_support(schema_id, schema_version)

    def ensure_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        schema_id = _safe_segment(request.get("SchemaId"), "schema_id")
        schema_version = _positive_int(request.get("SchemaVersion"), "schema_version")
        canonical_schema = request.get("CanonicalSchema")
        if not isinstance(canonical_schema, Mapping):
            raise TypeError("canonical_schema must be an object")
        references = request.get("References", ())
        if not isinstance(references, Sequence) or isinstance(references, (str, bytes, bytearray)):
            raise TypeError("references must be an array")
        normalized_references = self._normalize_reference_definitions(references)
        canonical_digest = _canonical_digest(canonical_schema)

        with self._locked_storage(create_root=True):
            manifest_path = self._support_manifest_path(schema_id, schema_version)
            current = self._read_support_manifest(manifest_path)
            if current is not None:
                if current.get("FormatVersion") != _SUPPORT_FORMAT_VERSION:
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["storage-support manifest has an unsupported format_version"],
                        "Metadata": self._support_metadata(schema_id, schema_version, current),
                    }
                if str(current.get("SchemaId")) != schema_id or int(current.get("SchemaVersion", 0)) != schema_version:
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["storage-support manifest identity does not match its path"],
                        "Metadata": self._support_metadata(schema_id, schema_version, current),
                    }
                if str(current.get("Status")) not in _SUPPORT_STATUSES:
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["storage-support manifest has an invalid status"],
                        "Metadata": self._support_metadata(schema_id, schema_version, current),
                    }
                stored_schema = current.get("CanonicalSchema")
                if not isinstance(stored_schema, Mapping) or _canonical_digest(stored_schema) != str(current.get("canonical_digest")):
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["stored .schema.yml canonical schema does not match its canonical_digest"],
                        "Metadata": self._support_metadata(schema_id, schema_version, current),
                    }
                if str(current.get("canonical_digest")) != canonical_digest:
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["stored support metadata has a different canonical schema digest"],
                        "Metadata": self._support_metadata(schema_id, schema_version, current),
                    }
                changed = str(current.get("Status")) != "ready" or current.get("References") != normalized_references
            else:
                version_directory = self._version_directory(schema_id, schema_version)
                has_records = version_directory.is_dir() and any(
                    path.name != ".schema.yml" for path in version_directory.glob("*.yml")
                )
                if has_records:
                    return {
                        "Status": "incompatible",
                        "Changed": False,
                        "Diagnostics": ["record files exist without durable .schema.yml metadata"],
                        "Metadata": self._support_metadata(schema_id, schema_version, None),
                    }
                changed = True

            version_directory = self._version_directory(schema_id, schema_version)
            if not version_directory.exists():
                version_directory.mkdir(parents=True, exist_ok=True)
                changed = True
            manifest = {
                "FormatVersion": _SUPPORT_FORMAT_VERSION,
                "SchemaId": schema_id,
                "SchemaVersion": schema_version,
                "Status": "ready",
                "canonical_digest": canonical_digest,
                "CanonicalSchema": dict(canonical_schema),
                "References": normalized_references,
            }
            self._atomic_write_yaml(manifest_path, manifest)
            return {
                "Status": "ready",
                "Changed": changed,
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }

    def retire_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        schema_id = _safe_segment(request.get("SchemaId"), "schema_id")
        schema_version = _positive_int(request.get("SchemaVersion"), "schema_version")
        if not self.root.exists():
            return {"Status": "not_provisioned", "Changed": False}
        with self._locked_storage():
            manifest_path = self._support_manifest_path(schema_id, schema_version)
            manifest = self._read_support_manifest(manifest_path)
            if manifest is None:
                inspected = self._inspect_support(schema_id, schema_version)
                return {
                    "Status": str(inspected["Status"]),
                    "Changed": False,
                    "Diagnostics": list(inspected.get("Diagnostics", ())),
                    "Metadata": dict(inspected.get("Metadata", {})),
                }
            inspected = self._inspect_support(schema_id, schema_version)
            if inspected["Status"] == "incompatible":
                return {
                    "Status": "incompatible",
                    "Changed": False,
                    "Diagnostics": list(inspected.get("Diagnostics", ())),
                    "Metadata": dict(inspected.get("Metadata", {})),
                }
            status = str(manifest.get("Status"))
            changed = status != "retired"
            if changed:
                manifest = dict(manifest)
                manifest["Status"] = "retired"
                self._atomic_write_yaml(manifest_path, manifest)
            return {
                "Status": "retired",
                "Changed": changed,
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }

    def create_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        progress = AIcOperationProgress()
        progress.report("scan", "Scanning storage data", force=True)
        backup_file = self._backup_file_path(request.get("BackupFile"))
        overwrite = bool(request.get("Overwrite", False))
        if backup_file.exists() and not overwrite:
            raise FileExistsError(f"backup file already exists: {backup_file}")
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_storage(create_root=True):
            files = self._backup_data_files()
            entries = []
            schema_version_count = 0
            record_count = 0
            for index, path in enumerate(files, start=1):
                progress.checkpoint()
                relative = path.relative_to(self.root).as_posix()
                content = path.read_bytes()
                entries.append({"Path": relative, "Sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
                if path.name == ".schema.yml":
                    schema_version_count += 1
                elif path.suffix == ".yml":
                    record_count += 1
                progress.report("scan", "Scanning storage data", current=index, total=len(files), unit="FILES")
            manifest = {
                "FormatVersion": _BACKUP_FORMAT_VERSION,
                "provider_type": "yamlfsdes",
                "layout_format_version": _LAYOUT_FORMAT_VERSION,
                "CreatedAt": datetime.now(timezone.utc).isoformat(),
                "SchemaVersionCount": schema_version_count,
                "RecordCount": record_count,
                "files": entries,
            }
            temporary = backup_file.parent / f".{backup_file.name}.{uuid4().hex}.tmp"
            try:
                progress.report("archive", "Creating backup archive", current=0, total=len(files), unit="FILES", force=True)
                with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                    archive.writestr("backup.yml", yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
                    for index, path in enumerate(files, start=1):
                        progress.checkpoint()
                        archive.write(path, path.relative_to(self.root).as_posix())
                        progress.report("archive", "Creating backup archive", current=index, total=len(files), unit="FILES")
                os.replace(temporary, backup_file)
                _fsync_directory(backup_file.parent)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        progress.report("completed", "Storage backup created", current=len(files), total=len(files), unit="FILES", force=True)
        return {
            "BackupFile": str(backup_file),
            "Format": "zip",
            "SchemaVersionCount": schema_version_count,
            "RecordCount": record_count,
            "Metadata": {"provider_type": "yamlfsdes", "layout_format_version": _LAYOUT_FORMAT_VERSION},
        }

    def inspect_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        backup_file = self._backup_file_path(request.get("BackupFile"), require_outside_root=False)
        validation_level = str(request.get("ValidationLevel", "integrity"))
        if validation_level not in {"integrity", "full"}:
            raise ValueError("validation_level must be integrity or full")
        status, diagnostics, metadata, _ = self._validate_backup(backup_file, validation_level)
        result: dict[str, object] = {"Status": status}
        if diagnostics:
            result["Diagnostics"] = diagnostics
        if metadata:
            result["Metadata"] = metadata
        return result

    def restore_backup_1(self, request: Mapping[str, object]) -> Mapping[str, object]:
        backup_file = self._backup_file_path(request.get("BackupFile"), require_outside_root=False)
        mode = str(request.get("Mode", "empty_only"))
        if mode not in {"empty_only", "replace_all"}:
            raise ValueError("restore mode must be empty_only or replace_all")
        progress = AIcOperationProgress()
        progress.report("validate", "Validating backup before restore", force=True)
        status, diagnostics, metadata, manifest = self._validate_backup(backup_file, "full", progress)
        if status != "valid" or manifest is None:
            raise RuntimeError("cannot restore invalid YAMLFS DES backup: " + "; ".join(diagnostics or [status]))
        with self._locked_storage(create_root=True):
            if mode == "empty_only" and self._data_has_persistent_content():
                raise RuntimeError("restore mode empty_only requires an empty target data/ tree")
            progress.report("restore", "Preparing restored storage", force=True)
            transaction = self._prepare_restore_transaction(backup_file, manifest, mode)
            self._set_restore_transaction_state(transaction, "COMMITTING")
            self._finish_restore_transaction(transaction)
            self._set_restore_transaction_state(transaction, "committed")
            self._cleanup_transaction(transaction)
        progress.report("completed", "Storage restore completed", force=True)
        return {
            "Restored": True,
            "BackupFile": str(backup_file),
            "Mode": mode,
            "SchemaVersionCount": int(metadata.get("SchemaVersionCount", 0)),
            "RecordCount": int(metadata.get("RecordCount", 0)),
            "Metadata": {"provider_type": "yamlfsdes", "layout_format_version": _LAYOUT_FORMAT_VERSION},
        }

    @contextmanager
    def _locked_storage(self, *, create_root: bool = False) -> Iterator[None]:
        with self._thread_lock:
            if create_root:
                self.root.mkdir(parents=True, exist_ok=True)
            if not self.root.exists():
                yield
                return
            metadata = self.root / ".yamlfsdes"
            metadata.mkdir(parents=True, exist_ok=True)
            lock_path = metadata / "storage.lock"
            with lock_path.open("a+b") as stream:
                _lock_file(stream)
                try:
                    self._recover_transactions()
                    self._recover_restore_transactions()
                    yield
                finally:
                    _unlock_file(stream)

    def _schema_directory(self, schema_id: str) -> Path:
        return self._checked_path(self.root / "data" / _safe_segment(schema_id, "schema_id"))

    def _version_directory(self, schema_id: str, schema_version: int) -> Path:
        return self._checked_path(self._schema_directory(schema_id) / str(_positive_int(schema_version, "schema_version")))

    def _record_path(self, schema_id: str, schema_version: int, uid: str) -> Path:
        return self._checked_path(self._version_directory(schema_id, schema_version) / f"{_safe_segment(uid, 'uid')}.yml")

    def _support_manifest_path(self, schema_id: str, schema_version: int) -> Path:
        return self._checked_path(self._version_directory(schema_id, schema_version) / ".schema.yml")

    def _checked_path(self, path: Path) -> Path:
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise ValueError("resolved YAML filesystem storage path escapes root_directory")
        return path

    def _find_record(self, schema_id: str, uid: str) -> dict[str, object] | None:
        matches: list[tuple[int, Path]] = []
        schema_directory = self._schema_directory(schema_id)
        if not schema_directory.is_dir():
            return None
        for version_directory in self._version_directories(schema_id):
            path = self._checked_path(version_directory / f"{uid}.yml")
            if path.is_file():
                matches.append((int(version_directory.name), path))
        if len(matches) > 1:
            versions = ", ".join(str(version) for version, _ in matches)
            raise RuntimeError(f"duplicate stored Data Entity identity {schema_id}/{uid} in versions {versions}")
        if not matches:
            return None
        version, path = matches[0]
        return self._read_record(path, schema_id, version, uid)

    def _version_directories(self, schema_id: str) -> tuple[Path, ...]:
        schema_directory = self._schema_directory(schema_id)
        if not schema_directory.is_dir():
            return ()
        values = [
            path for path in schema_directory.iterdir()
            if path.is_dir() and path.name.isdigit() and int(path.name) >= 1
        ]
        values.sort(key=lambda path: int(path.name))
        return tuple(values)

    def _read_record(self, path: Path, schema_id: str, schema_version: int, uid: str) -> dict[str, object]:
        raw = _read_yaml_mapping(path)
        if set(raw) != _RECORD_KEYS:
            raise RuntimeError(f"invalid Data Entity record keys in {path}")
        if str(raw.get("SchemaId")) != schema_id or int(raw.get("SchemaVersion", 0)) != schema_version:
            raise RuntimeError(f"Data Entity record metadata does not match storage path {path}")
        if str(raw.get("Uid")) != uid:
            raise RuntimeError(f"Data Entity UID does not match filename {path}")
        revision = raw.get("RecordRevision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise RuntimeError(f"YAML filesystem record_revision must be a positive integer in {path}")
        state = str(raw.get("State"))
        if state not in {"active", "tombstone"}:
            raise RuntimeError(f"invalid Data Entity state in {path}")
        payload = raw.get("Payload")
        if not isinstance(payload, Mapping):
            raise RuntimeError(f"Data Entity payload must be an object in {path}")
        return {
            "Uid": uid,
            "SchemaId": schema_id,
            "SchemaVersion": schema_version,
            "RecordRevision": revision,
            "State": state,
            "Payload": dict(payload),
        }

    def _query_candidates(self, schema_id: str, versions: set[int]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for version_directory in self._version_directories(schema_id):
            version = int(version_directory.name)
            if versions and version not in versions:
                continue
            for raw_path in sorted(version_directory.glob("*.yml"), key=lambda value: value.name):
                if raw_path.name == ".schema.yml":
                    continue
                path = self._checked_path(raw_path)
                uid = path.stem
                _safe_segment(uid, "uid")
                records.append(self._read_record(path, schema_id, version, uid))
        return records

    def _query_criteria_digest(self, request: Mapping[str, object]) -> str:
        criteria = {str(key): value for key, value in request.items() if key not in {"ContinuationToken", "Limit"}}
        return _canonical_digest(criteria)

    def _encode_continuation_token(self, criteria_digest: str, last_uid: str) -> str:
        raw = json.dumps(
            {"Version": 1, "criteria_digest": criteria_digest, "last_uid": last_uid},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _decode_continuation_token(self, token: object, criteria_digest: str) -> str | None:
        if token is None:
            return None
        if not isinstance(token, str) or not token:
            raise ValueError("continuation_token must be a non-empty string")
        try:
            padding = "=" * (-len(token) % 4)
            raw = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
        except Exception as exc:
            raise ValueError("invalid continuation_token") from exc
        if not isinstance(raw, Mapping) or raw.get("Version") != 1 or raw.get("criteria_digest") != criteria_digest:
            raise ValueError("continuation_token does not match this query")
        return _safe_segment(raw.get("last_uid"), "continuation_token last_uid")

    def _matches_references(self, record: Mapping[str, object], selectors: Sequence[object], mode: str) -> bool:
        schema_id = str(record["SchemaId"])
        schema_version = int(record["SchemaVersion"])
        manifest = self._read_support_manifest(self._support_manifest_path(schema_id, schema_version))
        definitions = () if manifest is None else manifest.get("References", ())
        if not isinstance(definitions, Sequence) or isinstance(definitions, (str, bytes, bytearray)):
            definitions = ()
        payload = record["Payload"]
        assert isinstance(payload, Mapping)
        matches = [self._matches_reference_selector(payload, definitions, selector) for selector in selectors]
        return all(matches) if mode == "all" else any(matches)

    def _matches_reference_selector(
        self,
        payload: Mapping[str, object],
        definitions: Sequence[object],
        selector: object,
    ) -> bool:
        if not isinstance(selector, Mapping):
            raise TypeError("reference selector must be an object")
        target = selector.get("Target")
        if not isinstance(target, Mapping):
            raise TypeError("reference target must be an object")
        target_schema_id = str(target.get("SchemaId"))
        target_uid = str(target.get("Uid"))
        requested_path_raw = selector.get("SchemaPath")
        requested_path = None
        if requested_path_raw is not None:
            if not isinstance(requested_path_raw, Sequence) or isinstance(requested_path_raw, (str, bytes, bytearray)):
                raise TypeError("reference schema_path must be an array")
            requested_path = tuple(str(value) for value in requested_path_raw)
        for definition in definitions:
            if not isinstance(definition, Mapping):
                continue
            if str(definition.get("TargetSchemaId")) != target_schema_id:
                continue
            schema_path_raw = definition.get("SchemaPath")
            if not isinstance(schema_path_raw, Sequence) or isinstance(schema_path_raw, (str, bytes, bytearray)):
                continue
            schema_path = tuple(str(value) for value in schema_path_raw)
            if requested_path is not None and requested_path != schema_path:
                continue
            data_path = _schema_path_to_data_path(schema_path)
            if any(str(value) == target_uid for value in _values_at_path(payload, data_path)):
                return True
        return False

    def _plan_changes(self, raw_changes: Sequence[object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        plans: list[dict[str, object]] = []
        results: list[dict[str, object]] = []
        identities: set[tuple[str, str]] = set()
        for raw_change in raw_changes:
            if not isinstance(raw_change, Mapping):
                raise TypeError("each Data Entity change must be an object")
            change_id = _non_empty_string(raw_change.get("ChangeId"), "change_id")
            change_type = _non_empty_string(raw_change.get("Type"), "type")
            schema_id = _safe_segment(raw_change.get("SchemaId"), "schema_id")
            uid = _safe_segment(raw_change.get("Uid"), "uid")
            identity = (schema_id, uid)
            if identity in identities:
                raise ValueError(f"changeset contains Data Entity {schema_id}/{uid} more than once")
            identities.add(identity)
            current = self._find_record(schema_id, uid)

            if change_type == "create_record":
                if current is not None:
                    raise FileExistsError(f"Data Entity {schema_id}/{uid} already exists")
                schema_version = _positive_int(raw_change.get("SchemaVersion"), "schema_version")
                self._require_support_ready(schema_id, schema_version)
                record = self._record_from_change(raw_change, 1)
                plans.append({
                    "Type": "write",
                    "old_path": None,
                    "new_path": self._relative(self._record_path(schema_id, schema_version, uid)),
                    "Record": record,
                })
                results.append({
                    "ChangeId": change_id,
                    "Type": change_type,
                    "SchemaId": schema_id,
                    "Uid": uid,
                    "RecordRevision": 1,
                })
                continue

            if current is None:
                raise FileNotFoundError(f"Data Entity {schema_id}/{uid} does not exist")
            expected_revision = raw_change.get("ExpectedRecordRevision")
            if expected_revision != current["RecordRevision"]:
                raise RuntimeError(
                    f"record revision conflict for {schema_id}/{uid}: expected {expected_revision!r}, "
                    f"stored {current['RecordRevision']!r}"
                )
            old_path = self._record_path(schema_id, int(current["SchemaVersion"]), uid)

            if change_type == "replace_record":
                schema_version = _positive_int(raw_change.get("SchemaVersion"), "schema_version")
                self._require_support_ready(schema_id, schema_version)
                next_revision = int(current["RecordRevision"]) + 1
                record = self._record_from_change(raw_change, next_revision)
                plans.append({
                    "Type": "write",
                    "old_path": self._relative(old_path),
                    "new_path": self._relative(self._record_path(schema_id, schema_version, uid)),
                    "Record": record,
                })
                results.append({
                    "ChangeId": change_id,
                    "Type": change_type,
                    "SchemaId": schema_id,
                    "Uid": uid,
                    "RecordRevision": next_revision,
                })
            elif change_type == "delete_record":
                plans.append({"Type": "DELETE", "old_path": self._relative(old_path)})
                results.append({
                    "ChangeId": change_id,
                    "Type": change_type,
                    "SchemaId": schema_id,
                    "Uid": uid,
                })
            else:
                raise ValueError(f"unsupported Data Entity change type {change_type!r}")
        return plans, results

    def _record_from_change(self, change: Mapping[str, object], revision: int) -> dict[str, object]:
        payload = change.get("Payload")
        if not isinstance(payload, Mapping):
            raise TypeError("Data Entity change payload must be an object")
        state = str(change.get("State"))
        if state not in {"active", "tombstone"}:
            raise ValueError("Data Entity change state must be active or tombstone")
        return {
            "Uid": _safe_segment(change.get("Uid"), "uid"),
            "SchemaId": _safe_segment(change.get("SchemaId"), "schema_id"),
            "SchemaVersion": _positive_int(change.get("SchemaVersion"), "schema_version"),
            "RecordRevision": revision,
            "State": state,
            "Payload": dict(payload),
        }

    def _require_support_ready(self, schema_id: str, schema_version: int) -> None:
        inspected = self._inspect_support(schema_id, schema_version)
        if inspected["Status"] != "ready":
            raise RuntimeError(
                f"Data Entity storage support {schema_id}/{schema_version} is {inspected['Status']}, not ready"
            )

    def _inspect_support(self, schema_id: str, schema_version: int) -> dict[str, object]:
        manifest_path = self._support_manifest_path(schema_id, schema_version)
        manifest = self._read_support_manifest(manifest_path)
        version_directory = self._version_directory(schema_id, schema_version)
        if manifest is None:
            has_records = version_directory.is_dir() and any(path.name != ".schema.yml" for path in version_directory.glob("*.yml"))
            if has_records:
                return {
                    "Status": "incompatible",
                    "Diagnostics": ["record files exist without durable .schema.yml metadata"],
                    "Metadata": self._support_metadata(schema_id, schema_version, None),
                }
            return {
                "Status": "not_provisioned",
                "Metadata": self._support_metadata(schema_id, schema_version, None),
            }
        if manifest.get("FormatVersion") != _SUPPORT_FORMAT_VERSION:
            return {
                "Status": "incompatible",
                "Diagnostics": ["storage-support manifest has an unsupported format_version"],
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }
        status = str(manifest.get("Status"))
        if status not in _SUPPORT_STATUSES:
            return {
                "Status": "incompatible",
                "Diagnostics": ["storage-support manifest has an invalid status"],
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }
        if str(manifest.get("SchemaId")) != schema_id or int(manifest.get("SchemaVersion", 0)) != schema_version:
            return {
                "Status": "incompatible",
                "Diagnostics": ["storage-support manifest identity does not match its path"],
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }
        stored_schema = manifest.get("CanonicalSchema")
        if not isinstance(stored_schema, Mapping) or _canonical_digest(stored_schema) != str(manifest.get("canonical_digest")):
            return {
                "Status": "incompatible",
                "Diagnostics": ["durable .schema.yml canonical schema does not match its canonical_digest"],
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }
        if not version_directory.is_dir():
            return {
                "Status": "incompatible",
                "Diagnostics": ["storage-support manifest exists but the schema/version directory is missing"],
                "Metadata": self._support_metadata(schema_id, schema_version, manifest),
            }
        return {"Status": status, "Metadata": self._support_metadata(schema_id, schema_version, manifest)}

    def _support_metadata(
        self,
        schema_id: str,
        schema_version: int,
        manifest: Mapping[str, object] | None,
    ) -> dict[str, object]:
        version_directory = self._version_directory(schema_id, schema_version)
        metadata: dict[str, object] = {
            "Layout": "<root>/data/<schema-id>/<schema-version>/<entity-uid>.yml",
            "relative_path": self._relative(version_directory),
            "RecordCount": len(tuple(path for path in version_directory.glob("*.yml") if path.name != ".schema.yml")) if version_directory.is_dir() else 0,
        }
        if manifest is not None and manifest.get("canonical_digest") is not None:
            metadata["canonical_digest"] = str(manifest["canonical_digest"])
        return metadata

    def _normalize_reference_definitions(self, references: Sequence[object]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for reference in references:
            if not isinstance(reference, Mapping):
                raise TypeError("storage-support reference definition must be an object")
            path_raw = reference.get("SchemaPath")
            if not isinstance(path_raw, Sequence) or isinstance(path_raw, (str, bytes, bytearray)) or not path_raw:
                raise ValueError("storage-support reference schema_path must be a non-empty array")
            target_schema_id = _non_empty_string(reference.get("TargetSchemaId"), "target_schema_id")
            normalized.append({
                "SchemaPath": [str(value) for value in path_raw],
                "TargetSchemaId": target_schema_id,
            })
        normalized.sort(key=lambda value: (str(value["TargetSchemaId"]), tuple(value["SchemaPath"])))
        return normalized

    def _read_support_manifest(self, path: Path) -> dict[str, object] | None:
        if not path.is_file():
            return None
        return _read_yaml_mapping(path)

    def _prepare_transaction(self, plans: Sequence[Mapping[str, object]]) -> Path:
        transaction = self.root / "journal" / "record-changes" / str(uuid4())
        staged = transaction / "staged"
        staged.mkdir(parents=True, exist_ok=False)
        manifest_plans: list[dict[str, object]] = []
        for index, plan in enumerate(plans):
            kind = str(plan["Type"])
            if kind == "write":
                stage_name = f"{index}.yml"
                record = plan.get("Record")
                if not isinstance(record, Mapping):
                    raise TypeError("transaction write plan is missing record data")
                self._atomic_write_yaml(staged / stage_name, record)
                manifest_plans.append({
                    "Type": "write",
                    "old_path": plan.get("old_path"),
                    "new_path": str(plan["new_path"]),
                    "stage": f"staged/{stage_name}",
                })
            elif kind == "DELETE":
                manifest_plans.append({"Type": "DELETE", "old_path": str(plan["old_path"])})
            else:
                raise ValueError(f"unknown transaction plan type {kind!r}")
        self._atomic_write_yaml(transaction / "manifest.yml", {
            "FormatVersion": _TRANSACTION_FORMAT_VERSION,
            "State": "prepared",
            "Operations": manifest_plans,
        })
        _fsync_directory(transaction)
        return transaction

    def _set_transaction_state(self, transaction: Path, state: str) -> None:
        if state not in _TRANSACTION_STATES:
            raise ValueError(f"invalid transaction state {state!r}")
        manifest_path = transaction / "manifest.yml"
        manifest = _read_yaml_mapping(manifest_path)
        manifest["State"] = state
        self._atomic_write_yaml(manifest_path, manifest)
        _fsync_directory(transaction)

    def _finish_transaction(self, transaction: Path) -> None:
        manifest = _read_yaml_mapping(transaction / "manifest.yml")
        if manifest.get("FormatVersion") != _TRANSACTION_FORMAT_VERSION:
            raise RuntimeError("cannot finish transaction with unsupported format_version")
        state = str(manifest.get("State"))
        if state not in {"COMMITTING", "committed"}:
            raise RuntimeError(f"cannot finish transaction in state {state!r}")
        operations = manifest.get("Operations")
        if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes, bytearray)):
            raise RuntimeError("transaction manifest operations are invalid")
        for operation in operations:
            if not isinstance(operation, Mapping):
                raise RuntimeError("transaction operation is invalid")
            kind = str(operation.get("Type"))
            old_path = self._path_from_relative(operation.get("old_path")) if operation.get("old_path") else None
            if kind == "write":
                new_path = self._path_from_relative(operation.get("new_path"))
                stage = self._transaction_path(transaction, operation.get("stage"))
                if not stage.is_file():
                    raise RuntimeError(f"transaction staged record is missing: {stage}")
                self._atomic_copy(stage, new_path)
                if old_path is not None and old_path != new_path and old_path.exists():
                    old_path.unlink()
                    _fsync_directory(old_path.parent)
            elif kind == "DELETE":
                if old_path is not None and old_path.exists():
                    old_path.unlink()
                    _fsync_directory(old_path.parent)
            else:
                raise RuntimeError(f"unknown transaction operation {kind!r}")

    def _recover_transactions(self) -> None:
        transactions = self.root / "journal" / "record-changes"
        if not transactions.is_dir():
            return
        for transaction in sorted(path for path in transactions.iterdir() if path.is_dir()):
            manifest_path = transaction / "manifest.yml"
            if not manifest_path.is_file():
                shutil.rmtree(transaction)
                continue
            manifest = _read_yaml_mapping(manifest_path)
            if manifest.get("FormatVersion") != _TRANSACTION_FORMAT_VERSION:
                raise RuntimeError("cannot recover YAMLFS DES transaction with unsupported format_version")
            state = str(manifest.get("State"))
            if state == "prepared":
                shutil.rmtree(transaction)
            elif state == "COMMITTING":
                self._finish_transaction(transaction)
                self._set_transaction_state(transaction, "committed")
                self._cleanup_transaction(transaction)
            elif state == "committed":
                self._cleanup_transaction(transaction)
            else:
                raise RuntimeError(f"cannot recover YAMLFS DES transaction with state {state!r}")

    def _cleanup_transaction(self, transaction: Path) -> None:
        try:
            shutil.rmtree(transaction)
            _fsync_directory(transaction.parent)
        except FileNotFoundError:
            pass

    def _backup_file_path(self, raw: object, *, require_outside_root: bool = True) -> Path:
        text = _non_empty_string(raw, "backup_file")
        path = Path(text).expanduser().resolve(strict=False)
        if require_outside_root and path.is_relative_to(self.root):
            raise ValueError("backup_file must be outside root_directory")
        return path

    def _backup_data_files(self) -> tuple[Path, ...]:
        data = self.root / "data"
        if not data.is_dir():
            return ()
        files = []
        for path in data.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"YAMLFS DES data tree must not contain symbolic links: {path}")
            if path.is_file():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(data.resolve(strict=False)):
                    raise RuntimeError("data file escapes data/ tree")
                files.append(path)
        files.sort(key=lambda value: value.relative_to(self.root).as_posix())
        return tuple(files)

    def _validate_backup(
        self,
        backup_file: Path,
        validation_level: str = "integrity",
        progress: "AIcOperationProgress | None" = None,
    ) -> tuple[str, list[str], dict[str, object], dict[str, object] | None]:
        progress = progress or AIcOperationProgress()
        if validation_level not in {"integrity", "full"}:
            raise ValueError("validation_level must be integrity or full")
        if not backup_file.is_file():
            return "not_found", ["backup file does not exist"], {}, None
        try:
            progress.report("integrity", "Validating backup integrity", force=True)
            with zipfile.ZipFile(backup_file, "r") as archive:
                names = archive.namelist()
                if "backup.yml" not in names:
                    return "invalid", ["backup.yml is missing"], {}, None
                manifest_raw = yaml.safe_load(archive.read("backup.yml").decode("utf-8"))
                if not isinstance(manifest_raw, Mapping):
                    return "invalid", ["backup.yml must contain an object"], {}, None
                manifest = dict(manifest_raw)
                if manifest.get("FormatVersion") != _BACKUP_FORMAT_VERSION:
                    return "invalid", ["unsupported backup format_version"], {}, None
                if manifest.get("provider_type") != "yamlfsdes":
                    return "invalid", ["backup was not created by yamlfsdes"], {}, None
                if manifest.get("layout_format_version") != _LAYOUT_FORMAT_VERSION:
                    return "invalid", ["unsupported YAMLFS DES layout_format_version"], {}, None
                raw_files = manifest.get("files")
                if not isinstance(raw_files, Sequence) or isinstance(raw_files, (str, bytes, bytearray)):
                    return "invalid", ["backup file manifest is invalid"], {}, None
                expected_names = {"backup.yml"}
                for index, entry in enumerate(raw_files, start=1):
                    progress.checkpoint()
                    if not isinstance(entry, Mapping):
                        return "invalid", ["backup file entry is invalid"], {}, None
                    raw_path = _non_empty_string(entry.get("Path"), "backup entry path")
                    path = Path(raw_path)
                    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "data":
                        return "invalid", [f"unsafe backup entry Path: {raw_path}"], {}, None
                    expected_names.add(path.as_posix())
                    content = archive.read(path.as_posix())
                    if hashlib.sha256(content).hexdigest() != str(entry.get("Sha256")):
                        return "invalid", [f"backup checksum mismatch: {raw_path}"], {}, None
                    if len(content) != int(entry.get("size", -1)):
                        return "invalid", [f"backup size mismatch: {raw_path}"], {}, None
                    progress.report("integrity", "Validating backup integrity", current=index, total=len(raw_files), unit="FILES")
                actual_files = {name for name in names if not name.endswith("/")}
                if actual_files != expected_names:
                    return "invalid", ["backup zip contains files not declared by backup.yml"], {}, None
                if validation_level == "full":
                    diagnostics = self._validate_backup_content(archive, tuple(sorted(expected_names - {"backup.yml"})), progress)
                    if diagnostics:
                        return "invalid", diagnostics, {}, None
                metadata = {
                    "provider_type": "yamlfsdes",
                    "layout_format_version": _LAYOUT_FORMAT_VERSION,
                    "CreatedAt": str(manifest.get("CreatedAt", "")),
                    "SchemaVersionCount": int(manifest.get("SchemaVersionCount", 0)),
                    "RecordCount": int(manifest.get("RecordCount", 0)),
                    "ValidationLevel": validation_level,
                }
                if validation_level == "full":
                    schema_count = sum(1 for name in expected_names if name.endswith("/.schema.yml"))
                    record_count = sum(1 for name in expected_names if name.startswith("data/") and name.endswith(".yml") and not name.endswith("/.schema.yml"))
                    if schema_count != metadata["SchemaVersionCount"]:
                        return "invalid", ["backup schema_version_count does not match backup contents"], {}, None
                    if record_count != metadata["RecordCount"]:
                        return "invalid", ["backup record_count does not match backup contents"], {}, None
                progress.report("completed", "Backup validation completed", force=True)
                return "valid", [], metadata, manifest
        except AIxOperationCancelled:
            raise
        except (OSError, zipfile.BadZipFile, KeyError, ValueError, TypeError, yaml.YAMLError, SchemaError, ValidationError) as exc:
            return "invalid", [str(exc)], {}, None

    def _validate_backup_content(
        self,
        archive: zipfile.ZipFile,
        names: Sequence[str],
        progress: "AIcOperationProgress",
    ) -> list[str]:
        progress.report("content", "Validating backup storage content", current=0, total=len(names), unit="FILES", force=True)
        schemas: dict[tuple[str, int], Mapping[str, object]] = {}
        record_files: list[tuple[str, int, str, str]] = []
        for index, raw_path in enumerate(names, start=1):
            progress.checkpoint()
            path = Path(raw_path)
            if len(path.parts) != 4 or path.parts[0] != "data":
                return [f"backup data entry has invalid YAMLFS DES Layout: {raw_path}"]
            schema_id = _safe_segment(path.parts[1], "backup schema_id")
            if not path.parts[2].isdigit():
                return [f"backup schema version directory is invalid: {raw_path}"]
            schema_version = _positive_int(int(path.parts[2]), "backup schema_version")
            if path.name == ".schema.yml":
                manifest_raw = yaml.safe_load(archive.read(raw_path).decode("utf-8"))
                if not isinstance(manifest_raw, Mapping):
                    return [f"storage-support manifest must contain an object: {raw_path}"]
                manifest = dict(manifest_raw)
                if manifest.get("FormatVersion") != _SUPPORT_FORMAT_VERSION:
                    return [f"storage-support manifest has unsupported FormatVersion: {raw_path}"]
                if str(manifest.get("SchemaId")) != schema_id or int(manifest.get("SchemaVersion", 0)) != schema_version:
                    return [f"storage-support manifest identity does not match backup Path: {raw_path}"]
                if str(manifest.get("Status")) not in _SUPPORT_STATUSES:
                    return [f"storage-support manifest has invalid Status: {raw_path}"]
                canonical_schema = manifest.get("CanonicalSchema")
                if not isinstance(canonical_schema, Mapping):
                    return [f"storage-support canonical_schema must be an object: {raw_path}"]
                if _canonical_digest(canonical_schema) != str(manifest.get("canonical_digest")):
                    return [f"storage-support canonical schema digest mismatch: {raw_path}"]
                Draft202012Validator.check_schema(dict(canonical_schema))
                references = manifest.get("References", ())
                if not isinstance(references, Sequence) or isinstance(references, (str, bytes, bytearray)):
                    return [f"storage-support references must be an array: {raw_path}"]
                for reference in references:
                    if not isinstance(reference, Mapping):
                        return [f"storage-support reference must be an object: {raw_path}"]
                    schema_path = reference.get("SchemaPath")
                    if not isinstance(schema_path, Sequence) or isinstance(schema_path, (str, bytes, bytearray)) or not schema_path:
                        return [f"storage-support reference schema_path must be a non-empty array: {raw_path}"]
                    _non_empty_string(reference.get("TargetSchemaId"), "reference target_schema_id")
                schemas[(schema_id, schema_version)] = dict(canonical_schema)
            elif path.suffix == ".yml":
                uid = _safe_segment(path.stem, "backup uid")
                record_files.append((schema_id, schema_version, uid, raw_path))
            else:
                return [f"unsupported file in backup data tree: {raw_path}"]
            progress.report("content", "Validating backup storage content", current=index, total=len(names), unit="FILES")

        identities: set[tuple[str, str]] = set()
        for index, (schema_id, schema_version, uid, raw_path) in enumerate(record_files, start=1):
            progress.checkpoint()
            identity = (schema_id, uid)
            if identity in identities:
                return [f"duplicate stored Data Entity identity {schema_id}/{uid} in backup"]
            identities.add(identity)
            canonical_schema = schemas.get((schema_id, schema_version))
            if canonical_schema is None:
                return [f"record exists without matching .schema.yml Metadata: {raw_path}"]
            raw = yaml.safe_load(archive.read(raw_path).decode("utf-8"))
            if not isinstance(raw, Mapping) or set(raw) != _RECORD_KEYS:
                return [f"invalid Data Entity record structure: {raw_path}"]
            if str(raw.get("SchemaId")) != schema_id or int(raw.get("SchemaVersion", 0)) != schema_version:
                return [f"Data Entity record metadata does not match backup Path: {raw_path}"]
            if str(raw.get("Uid")) != uid:
                return [f"Data Entity UID does not match backup filename: {raw_path}"]
            revision = raw.get("RecordRevision")
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                return [f"Data Entity record_revision must be a positive integer: {raw_path}"]
            if str(raw.get("State")) not in {"active", "tombstone"}:
                return [f"invalid Data Entity State: {raw_path}"]
            payload = raw.get("Payload")
            if not isinstance(payload, Mapping):
                return [f"Data Entity payload must be an object: {raw_path}"]
            try:
                Draft202012Validator(dict(canonical_schema)).validate(dict(payload))
            except ValidationError as exc:
                return [f"Data Entity payload does not satisfy canonical schema in {raw_path}: {exc.message}"]
            progress.report("records", "Validating Data Entity records", current=index, total=len(record_files), unit="RECORDS")
        return []

    def _data_has_persistent_content(self) -> bool:
        data = self.root / "data"
        return data.is_dir() and any(path.is_file() for path in data.rglob("*"))

    def _prepare_restore_transaction(self, backup_file: Path, manifest: Mapping[str, object], mode: str) -> Path:
        transaction = self.root / "journal" / "restore" / str(uuid4())
        staged_data = transaction / "staged-data"
        staged_data.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(backup_file, "r") as archive:
            for entry in manifest.get("files", ()):  # already validated
                assert isinstance(entry, Mapping)
                raw_path = str(entry["Path"])
                relative = Path(raw_path).relative_to("data")
                target = staged_data / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                content = archive.read(raw_path)
                if hashlib.sha256(content).hexdigest() != str(entry.get("Sha256")):
                    raise RuntimeError(f"backup changed after validation: checksum mismatch for {raw_path}")
                if len(content) != int(entry.get("size", -1)):
                    raise RuntimeError(f"backup changed after validation: size mismatch for {raw_path}")
                with target.open("wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
        self._atomic_write_yaml(transaction / "manifest.yml", {
            "FormatVersion": _TRANSACTION_FORMAT_VERSION,
            "Kind": "RESTORE",
            "State": "prepared",
            "Mode": mode,
            "BackupFile": str(backup_file),
        })
        _fsync_directory(transaction)
        return transaction

    def _set_restore_transaction_state(self, transaction: Path, state: str) -> None:
        self._set_transaction_state(transaction, state)

    def _finish_restore_transaction(self, transaction: Path) -> None:
        manifest = _read_yaml_mapping(transaction / "manifest.yml")
        if manifest.get("FormatVersion") != _TRANSACTION_FORMAT_VERSION or manifest.get("Kind") != "RESTORE":
            raise RuntimeError("cannot finish invalid YAMLFS DES restore transaction")
        if str(manifest.get("State")) not in {"COMMITTING", "committed"}:
            raise RuntimeError("restore transaction is not committing")
        current = self.root / "data"
        previous = transaction / "previous-data"
        staged = transaction / "staged-data"
        if staged.exists():
            if current.exists() and not previous.exists():
                os.replace(current, previous)
                _fsync_directory(self.root)
            if current.exists():
                raise RuntimeError("restore transaction has both current data and staged data")
            os.replace(staged, current)
            _fsync_directory(self.root)
        if not current.is_dir():
            raise RuntimeError("restore transaction did not produce a data/ directory")

    def _recover_restore_transactions(self) -> None:
        transactions = self.root / "journal" / "restore"
        if not transactions.is_dir():
            return
        for transaction in sorted(path for path in transactions.iterdir() if path.is_dir()):
            manifest_path = transaction / "manifest.yml"
            if not manifest_path.is_file():
                shutil.rmtree(transaction)
                continue
            manifest = _read_yaml_mapping(manifest_path)
            if manifest.get("FormatVersion") != _TRANSACTION_FORMAT_VERSION or manifest.get("Kind") != "RESTORE":
                raise RuntimeError("cannot recover YAMLFS DES restore transaction with unsupported format")
            state = str(manifest.get("State"))
            if state == "prepared":
                shutil.rmtree(transaction)
            elif state == "COMMITTING":
                self._finish_restore_transaction(transaction)
                self._set_restore_transaction_state(transaction, "committed")
                self._cleanup_transaction(transaction)
            elif state == "committed":
                self._cleanup_transaction(transaction)
            else:
                raise RuntimeError(f"cannot recover YAMLFS DES restore transaction with state {state!r}")

    def _atomic_write_yaml(self, path: Path, value: Mapping[str, object]) -> None:
        text = yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True)
        self._atomic_write_bytes(path, text.encode("utf-8"))

    def _atomic_copy(self, source: Path, target: Path) -> None:
        self._atomic_write_bytes(target, source.read_bytes())

    def _atomic_write_bytes(self, path: Path, content: bytes) -> None:
        path = self._checked_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)

    def _relative(self, path: Path) -> str:
        return path.resolve(strict=False).relative_to(self.root).as_posix()

    def _path_from_relative(self, raw: object) -> Path:
        relative = _non_empty_string(raw, "transaction relative path")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("transaction path escapes storage root")
        return self._checked_path(self.root / path)

    def _transaction_path(self, transaction: Path, raw: object) -> Path:
        relative = _non_empty_string(raw, "transaction stage path")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("transaction stage path escapes transaction directory")
        resolved = (transaction / path).resolve(strict=False)
        if not resolved.is_relative_to(transaction.resolve(strict=False)):
            raise RuntimeError("transaction stage path escapes transaction directory")
        return transaction / path
