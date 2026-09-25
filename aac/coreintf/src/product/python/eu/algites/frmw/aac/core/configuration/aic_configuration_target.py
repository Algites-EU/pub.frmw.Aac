from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .ain_configuration_target_kind import AInConfigurationTargetKind

@dataclass(frozen=True, slots=True)
class AIcConfigurationTarget:
    kind: AInConfigurationTargetKind
    component_id: str
    provider_instance_id: str | None = None

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("configuration target component_id must not be empty")
        if self.kind is AInConfigurationTargetKind.COMPONENT:
            if self.provider_instance_id is not None:
                raise ValueError("COMPONENT configuration target must not carry provider_instance_id")
        elif self.kind is AInConfigurationTargetKind.PROVIDER_INSTANCE:
            if not self.provider_instance_id:
                raise ValueError("PROVIDER_INSTANCE configuration target requires provider_instance_id")

    @property
    def key(self) -> str:
        if self.kind is AInConfigurationTargetKind.COMPONENT:
            return f"COMPONENT:{self.component_id}"
        return f"PROVIDER_INSTANCE:{self.component_id}:{self.provider_instance_id}"
