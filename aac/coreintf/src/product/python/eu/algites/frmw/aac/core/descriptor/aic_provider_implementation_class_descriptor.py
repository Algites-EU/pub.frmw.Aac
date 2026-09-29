from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AIcProviderImplementationClassDescriptor:
    technology_kind: str
    provider_class_name: str
    capability_profile_matcher_class_name: str | None = None

    def __post_init__(self) -> None:
        if not self.technology_kind.strip():
            raise ValueError("provider implementation technology_kind must not be empty")
        if not self.provider_class_name.strip():
            raise ValueError("provider implementation provider_class_name must not be empty")
        if self.capability_profile_matcher_class_name is not None and not self.capability_profile_matcher_class_name.strip():
            raise ValueError("provider implementation capability_profile_matcher_class_name must not be empty")
