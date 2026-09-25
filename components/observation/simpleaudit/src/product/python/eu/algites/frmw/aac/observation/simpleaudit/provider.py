from __future__ import annotations
import json
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Mapping, TextIO
from eu.algites.frmw.aac.core.observation.api import AIcObservationInput, AIcObservationOutput, AIiObservationProvider
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

from .aic_simple_audit_observer import AIcSimpleAuditObserver

def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
