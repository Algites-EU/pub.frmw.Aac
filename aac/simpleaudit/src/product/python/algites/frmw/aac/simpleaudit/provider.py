from __future__ import annotations

import json
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Mapping, TextIO

from algites.frmw.aac.coreintf.observation import AIcObservationInput, AIcObservationOutput, AIiObservationProvider
from algites.frmw.aac.coreintf.runtime import AIiProviderRuntime


class AIcSimpleAuditObserver(AIiProviderRuntime, AIiObservationProvider):
    """Reference observer that writes one record per received observation input."""

    def __init__(self, configuration: Mapping[str, object] | None = None) -> None:
        configuration = dict(configuration or {})
        raw_output = configuration.get("output", {"type": "STDOUT"})
        if not isinstance(raw_output, Mapping):
            raise ValueError("output configuration must be a mapping")
        self._output_type = str(raw_output.get("type", "STDOUT")).upper()
        self._path = raw_output.get("path")
        self._format = str(configuration.get("format", "JSON")).upper()
        if self._output_type not in {"STDOUT", "FILE"}:
            raise ValueError("output.type must be STDOUT or FILE")
        if self._format not in {"JSON", "TEXT"}:
            raise ValueError("format must be JSON or TEXT")
        if self._output_type == "FILE" and not self._path:
            raise ValueError("output.path is required for FILE output")

    def observe_1(self, observation_input: AIcObservationInput) -> AIcObservationOutput:
        line = self._serialize(observation_input)
        if self._output_type == "STDOUT":
            print(line, file=sys.stdout, flush=True)
        else:
            path = Path(str(self._path))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                print(line, file=stream)
        return AIcObservationOutput(accepted=True)

    def _serialize(self, value: AIcObservationInput) -> str:
        if self._format == "JSON":
            return json.dumps(_jsonable(asdict(value)), sort_keys=True, separators=(",", ":"))
        outcome = value.outcome.value if value.outcome is not None else "-"
        return (
            f"{value.phase.value} {value.capability_id}/{value.capability_version} "
            f"{value.operation_id} provider={value.provider_instance_id} "
            f"invocation={value.invocation_id} outcome={outcome} "
            f"arguments={json.dumps(_jsonable(dict(value.arguments)), sort_keys=True)}"
        )


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
