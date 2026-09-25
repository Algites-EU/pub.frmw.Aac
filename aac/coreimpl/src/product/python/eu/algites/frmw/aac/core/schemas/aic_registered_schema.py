from __future__ import annotations
import copy
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping
from jsonschema import Draft202012Validator, validators
from eu.algites.frmw.aac.core.implementation.errors import AIxSchemaValidationError

@dataclass(frozen=True, slots=True)
class AIcRegisteredSchema:
    id: str
    version: int
    resource_name: str
    schema: Mapping[str, object]
    source: str

    @property
    def key(self) -> str:
        return self.resource_name
