from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcObservationInput, AIcObservationOutput


class AIiObservationProvider(ABC):
    """Python binding of `_AAC.capability.observation` version 1."""

    @abstractmethod
    def observe_1(self, observation_input: AIcObservationInput) -> AIcObservationOutput:
        """Consume one read-only normalized observation event."""
