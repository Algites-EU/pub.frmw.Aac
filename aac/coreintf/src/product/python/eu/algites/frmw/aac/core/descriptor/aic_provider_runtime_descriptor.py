from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .ain_provider_runtime_profile import AInProviderRuntimeProfile

@dataclass(frozen=True, slots=True)
class AIcProviderRuntimeDescriptor:
    profile: AInProviderRuntimeProfile = AInProviderRuntimeProfile.IN_PROCESS
    command: tuple[str, ...] = ()
    cwd: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("runtime timeout_seconds must be > 0")
        if self.profile is not AInProviderRuntimeProfile.PROCESS and self.command:
            raise ValueError("runtime command is only valid for PROCESS profile")
