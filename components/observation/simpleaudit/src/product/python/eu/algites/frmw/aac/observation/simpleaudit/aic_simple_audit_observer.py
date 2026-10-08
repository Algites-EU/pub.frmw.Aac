from __future__ import annotations
from eu.algites.frmw.aac.core.observation.aicgd_observation_output_1 import AIcgdObservationOutput_1
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Mapping, TextIO
from eu.algites.frmw.aac.core.observation.api import AIigObservationInput_1, AIigObservationOutput_1, AIiObservationProvider
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

class AIcSimpleAuditObserver(AIiProviderRuntime, AIiObservationProvider):
    """Reference observer that writes one record per received observation input."""

    def __init__(self, configuration: Mapping[str, object] | None = None) -> None:
        configuration = dict(configuration or {})
        raw_output = configuration.get("Output", {"Type": "stdout"})
        if not isinstance(raw_output, Mapping):
            raise ValueError("output configuration must be a mapping")
        self._output_type = str(raw_output.get("Type", "stdout")).lower()
        self._path = raw_output.get("Path")
        self._format = str(configuration.get("Format", "json")).lower()
        if self._output_type not in {"stdout", "file"}:
            raise ValueError("output.type must be stdout or file")
        if self._format not in {"json", "text"}:
            raise ValueError("format must be json or text")
        if self._output_type == "file" and not self._path:
            raise ValueError("output.path is required for file output")

    def observe_1(self, observation_input: AIigObservationInput_1) -> AIigObservationOutput_1:
        line = self._serialize(observation_input)
        if self._output_type == "stdout":
            print(line, file=sys.stdout, flush=True)
        else:
            path = Path(str(self._path))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                print(line, file=stream)
        return AIcgdObservationOutput_1(accepted=True)

    def _serialize(self, value: AIigObservationInput_1) -> str:
        if self._format == "json":
            return json.dumps(_jsonable(value.to_mapping()), sort_keys=True, separators=(",", ":"))
        locWire = value.to_mapping()
        outcome = locWire.get(AIigObservationInput_1.SCHEMA_FIELD_NAME__OUTCOME) or "-"
        phase = locWire[AIigObservationInput_1.SCHEMA_FIELD_NAME__PHASE]
        return (
            f"{phase} {value.capability_id}/{value.capability_version} "
            f"{value.operation_id} provider={value.provider_instance_id} "
            f"invocation={value.invocation_id} outcome={outcome} "
            f"arguments={json.dumps(_jsonable(locWire.get(AIigObservationInput_1.SCHEMA_FIELD_NAME__ARGUMENTS, {})), sort_keys=True)}"
        )
