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

class AIcOperationProgress:
    def __init__(self) -> None:
        self._interaction = current_operation_interaction()
        self._last_state_poll = 0.0
        self._last_report = 0.0
        self._state = self._interaction.caller_snapshot()

    def _refresh(self, *, force: bool = False):
        now = time.monotonic()
        if force or now - self._last_state_poll >= 0.1:
            self._state = self._interaction.caller_snapshot()
            self._last_state_poll = now
        if self._state.cancellation_requested:
            raise AIxOperationCancelled("operation cancellation was requested")
        return self._state

    def checkpoint(self) -> None:
        self._refresh()

    def report(
        self,
        phase_id: str,
        text: str,
        *,
        current: int | float | None = None,
        total: int | float | None = None,
        unit: str | None = None,
        force: bool = False,
    ) -> None:
        state = self._refresh(force=force)
        now = time.monotonic()
        interval = 0 if state.reporting_interval_ms is None else state.reporting_interval_ms / 1000.0
        if not force and interval > 0 and now - self._last_report < interval:
            return
        self._interaction.report(AIcOperationInteractionEvent(
            event_type=AInOperationInteractionEventType.PROGRESS,
            progress_id=phase_id,
            phase_id=phase_id,
            name=AIcDisplayText(text=text),
            current=current,
            total=total,
            unit=unit,
        ))
        self._last_report = now
