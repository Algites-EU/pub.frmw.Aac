from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcBinding:
    consumer_instance_id: str
    requirement_id: str
    provider_instance_id: str
    capability_id: str
    capability_version: int
    binding_qualifier_profiles: tuple[Mapping[str, object], ...] = ()
