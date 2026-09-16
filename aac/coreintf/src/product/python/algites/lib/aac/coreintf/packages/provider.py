from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AIcPackageCandidate, AIcWorkspaceComponentRequirement


class AIiPackageSource(ABC):
    @abstractmethod
    def candidates(self, requirement: AIcWorkspaceComponentRequirement) -> tuple[AIcPackageCandidate, ...]: ...
