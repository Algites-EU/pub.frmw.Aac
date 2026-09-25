from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcClientCertificateMaterial:
    certificate_path: str
    private_key_path: str | None = None
    private_key_password: str | None = None

    def __post_init__(self) -> None:
        if not self.certificate_path:
            raise ValueError("certificate_path must not be empty")
