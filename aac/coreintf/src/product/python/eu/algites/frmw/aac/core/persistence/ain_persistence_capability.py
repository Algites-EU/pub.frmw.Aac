from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

class AInPersistenceCapability(str, Enum):
    READ = "READ"
    SINGLE_RECORD_CAS = "SINGLE_RECORD_CAS"
    MULTI_RECORD_TRANSACTION = "MULTI_RECORD_TRANSACTION"
