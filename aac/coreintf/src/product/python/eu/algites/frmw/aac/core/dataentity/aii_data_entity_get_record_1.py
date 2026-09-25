from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping

class AIiDataEntityGetRecord_1(ABC):
    @abstractmethod
    def get_1(self, request: Mapping[str, object]) -> Mapping[str, object]: ...
