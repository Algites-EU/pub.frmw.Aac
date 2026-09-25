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

class AIcOperationStateResultPublisher:
    """Provider-owned state-result delivery helper; Core remains opaque to delta semantics."""

    def __init__(self) -> None:
        self._interaction = current_operation_interaction()
        self._last_served_request_id = 0
        self._pending_deltas: dict[int, object] = {}

    def publish(self, *, complete: object, delta: object) -> int:
        caller = self._interaction.caller_snapshot()
        accepted = caller.last_accepted_state_result_revision
        self._pending_deltas = {
            revision: payload for revision, payload in self._pending_deltas.items() if revision > accepted
        }
        mode = caller.state_result_delivery_mode
        if mode in (
            AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
            AInStateResultDeliveryMode.ALWAYS_COMPLETE,
        ):
            return self._interaction.update_state_result(complete)
        if mode is AInStateResultDeliveryMode.ON_CHANGE_DELTA:
            return self._interaction.update_state_result(delta)

        revision = self._interaction.state_result_changed()
        if mode is AInStateResultDeliveryMode.ON_DEMAND_DELTA:
            self._pending_deltas[revision] = delta

        caller = self._interaction.caller_snapshot()
        request_id = caller.state_result_request_id
        if request_id > self._last_served_request_id:
            if mode is AInStateResultDeliveryMode.ON_DEMAND_COMPLETE:
                self._interaction.deliver_state_result(complete, revision=revision)
            elif mode is AInStateResultDeliveryMode.ON_DEMAND_DELTA:
                accepted = caller.last_accepted_state_result_revision
                for pending_revision in sorted(self._pending_deltas):
                    if pending_revision > accepted:
                        self._interaction.deliver_state_result(
                            self._pending_deltas[pending_revision], revision=pending_revision
                        )
            self._last_served_request_id = request_id
        return revision
