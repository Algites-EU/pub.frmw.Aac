from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier

class AInSigstoreVerificationMode(str, Enum):
    IDENTITY = "IDENTITY"
    GITHUB = "GITHUB"
