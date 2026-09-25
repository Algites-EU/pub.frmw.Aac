from __future__ import annotations
from abc import ABC, abstractmethod
from .models import AIcVerificationInput, AIcVerificationOutput

class AIiPackageVerifier(ABC):
    @abstractmethod
    def verify(self, verification_input: AIcVerificationInput) -> AIcVerificationOutput: ...
