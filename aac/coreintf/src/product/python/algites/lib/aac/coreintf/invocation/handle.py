from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from ..instances import AIcBinding
from .models import AIcInvocationOutput


class AIiCapabilityHandle(ABC):
    """Core-owned consumer-side handle for one resolved provider-instance binding."""

    @property
    @abstractmethod
    def binding(self) -> AIcBinding: ...

    @abstractmethod
    def invoke(self, operation_id: str, arguments: Mapping[str, object] | None = None) -> AIcInvocationOutput: ...
