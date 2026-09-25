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

from .aic_yaml_fs_data_entity_storage_provider import AIcYamlFsDataEntityStorageProvider
from .aic_operation_state_result_publisher import AIcOperationStateResultPublisher
from .aic_operation_progress import AIcOperationProgress

_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")

_RECORD_KEYS = {"uid", "schema_id", "schema_version", "record_revision", "state", "payload"}

_SUPPORT_STATUSES = {"READY", "RETIRED"}

_TRANSACTION_STATES = {"PREPARED", "COMMITTING", "COMMITTED"}

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
