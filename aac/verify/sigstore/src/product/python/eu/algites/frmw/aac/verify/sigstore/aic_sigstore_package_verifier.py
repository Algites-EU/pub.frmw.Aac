from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier

from .aic_sigstore_trust_policy import AIcSigstoreTrustPolicy
from .ain_sigstore_verification_mode import AInSigstoreVerificationMode

class AIcSigstorePackageVerifier(AIiPackageVerifier):
    """Verify an artifact using the official ``sigstore`` Python CLI module.

    The signature proves artifact integrity; the supplied trust policy determines which
    signer/publisher identity is accepted. The verifier never falls back to "any valid signer".
    """

    def __init__(self, policy: AIcSigstoreTrustPolicy, *, runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None) -> None:
        self.policy = policy
        self._runner = runner or self._run

    @staticmethod
    def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def verify(self, verification_input: AIcVerificationInput) -> AIcVerificationOutput:
        if not verification_input.artifact_path:
            return AIcVerificationOutput(False, ("Sigstore verification requires artifact_path",))
        artifact = Path(verification_input.artifact_path)
        if not artifact.is_file():
            return AIcVerificationOutput(False, (f"artifact does not exist: {artifact}",))
        bundle = Path(str(artifact) + self.policy.bundle_suffix)
        if not bundle.is_file():
            return AIcVerificationOutput(False, (f"Sigstore bundle does not exist: {bundle}",))

        command: list[str] = [sys.executable, "-m", "sigstore"]
        if self.policy.trust_config:
            command += ["--trust-config", self.policy.trust_config]
        if self.policy.mode is AInSigstoreVerificationMode.IDENTITY:
            if not self.policy.cert_identity or not self.policy.oidc_issuer:
                return AIcVerificationOutput(False, ("identity mode requires cert_identity and oidc_issuer",))
            command += ["verify", "identity", str(artifact), "--bundle", str(bundle), "--cert-identity", self.policy.cert_identity, "--cert-oidc-issuer", self.policy.oidc_issuer]
        else:
            if not self.policy.repository and not self.policy.cert_identity:
                return AIcVerificationOutput(False, ("github mode requires repository or cert_identity",))
            command += ["verify", "github", str(artifact), "--bundle", str(bundle)]
            if self.policy.repository:
                command += ["--repository", self.policy.repository]
            if self.policy.cert_identity:
                command += ["--cert-identity", self.policy.cert_identity]
        if self.policy.offline:
            command.append("--offline")
        result = self._runner(command)
        if result.returncode == 0:
            return AIcVerificationOutput(True, verifier_id="_AAC.sigstore.package", signer_identity=self.policy.cert_identity or self.policy.repository)
        detail = (result.stderr or result.stdout or "sigstore verification failed").strip()
        return AIcVerificationOutput(False, (detail,), verifier_id="_AAC.sigstore.package", signer_identity=self.policy.cert_identity or self.policy.repository)
