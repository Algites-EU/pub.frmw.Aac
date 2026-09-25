from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier

from .ain_sigstore_verification_mode import AInSigstoreVerificationMode
from .aic_sigstore_trust_policy import AIcSigstoreTrustPolicy
from .aic_sigstore_package_verifier import AIcSigstorePackageVerifier
from .aic_sigstore_entitlement_evidence_verifier import AIcSigstoreEntitlementEvidenceVerifier
