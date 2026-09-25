from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier

from .ain_sigstore_verification_mode import AInSigstoreVerificationMode

@dataclass(frozen=True, slots=True)
class AIcSigstoreTrustPolicy:
    mode: AInSigstoreVerificationMode = AInSigstoreVerificationMode.IDENTITY
    cert_identity: str | None = None
    oidc_issuer: str | None = None
    repository: str | None = None
    offline: bool = True
    bundle_suffix: str = ".sigstore.json"
    trust_config: str | None = None
