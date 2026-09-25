from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

class AInOperationInteractionDetailLevel(str, Enum):
    SUMMARY = "SUMMARY"
    DETAILED = "DETAILED"
