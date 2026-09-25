from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

class AIiDataEntityView(ABC):
    """Marker base for generated versioned Data Entity view interfaces."""
