from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

from algites.lib.aac.coreintf.verification import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier


class AInSigstoreVerificationMode(str, Enum):
    IDENTITY = "IDENTITY"
    GITHUB = "GITHUB"


@dataclass(frozen=True, slots=True)
class AIcSigstoreTrustPolicy:
    mode: AInSigstoreVerificationMode = AInSigstoreVerificationMode.IDENTITY
    cert_identity: str | None = None
    oidc_issuer: str | None = None
    repository: str | None = None
    offline: bool = True
    bundle_suffix: str = ".sigstore.json"
    trust_config: str | None = None


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


class AIcSigstoreEntitlementEvidenceVerifier:
    """Detached Sigstore verifier for entitlement-document files.

    The configured policy is selected by the document issuer id. Core separately applies
    its trusted-issuer/component policy, so a cryptographically valid but unauthorized signer
    does not become a trusted license issuer merely by being validly signed.
    """

    def __init__(
        self,
        policies: dict[str, AIcSigstoreTrustPolicy],
        *,
        runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.policies = dict(policies)
        self._runner = runner or AIcSigstorePackageVerifier._run

    def verify(self, evidence):
        from algites.lib.aac.coreintf.entitlement import AIcEntitlementEvidenceVerification

        policy = self.policies.get(evidence.document.issuer.id)
        if policy is None:
            return AIcEntitlementEvidenceVerification(
                False, "_AAC.sigstore.entitlement", (f"no Sigstore trust policy for issuer {evidence.document.issuer.id!r}",)
            )
        artifact_raw = evidence.verification_material.get("artifact_path") or evidence.source
        if not artifact_raw:
            return AIcEntitlementEvidenceVerification(False, "_AAC.sigstore.entitlement", ("entitlement evidence has no artifact path",))
        artifact = Path(str(artifact_raw))
        bundle_raw = evidence.verification_material.get("sidecar_path")
        bundle = Path(str(bundle_raw)) if bundle_raw else Path(str(artifact) + policy.bundle_suffix)
        if not artifact.is_file() or not bundle.is_file():
            return AIcEntitlementEvidenceVerification(False, "_AAC.sigstore.entitlement", ("entitlement file or detached Sigstore bundle is missing",))
        command: list[str] = [sys.executable, "-m", "sigstore"]
        if policy.trust_config:
            command += ["--trust-config", policy.trust_config]
        signer_identity = policy.cert_identity
        if policy.mode is AInSigstoreVerificationMode.IDENTITY:
            if not policy.cert_identity or not policy.oidc_issuer:
                return AIcEntitlementEvidenceVerification(False, "_AAC.sigstore.entitlement", ("identity mode requires cert_identity and oidc_issuer",))
            command += [
                "verify", "identity", str(artifact), "--bundle", str(bundle),
                "--cert-identity", policy.cert_identity, "--cert-oidc-issuer", policy.oidc_issuer,
            ]
        else:
            if not policy.repository and not policy.cert_identity:
                return AIcEntitlementEvidenceVerification(False, "_AAC.sigstore.entitlement", ("github mode requires repository or cert_identity",))
            command += ["verify", "github", str(artifact), "--bundle", str(bundle)]
            if policy.repository:
                command += ["--repository", policy.repository]
                signer_identity = signer_identity or policy.repository
            if policy.cert_identity:
                command += ["--cert-identity", policy.cert_identity]
        if policy.offline:
            command.append("--offline")
        result = self._runner(command)
        if result.returncode == 0:
            return AIcEntitlementEvidenceVerification(
                True, "_AAC.sigstore.entitlement", signer_identity=signer_identity,
                metadata={"artifact_path": str(artifact), "bundle_path": str(bundle)},
            )
        detail = (result.stderr or result.stdout or "sigstore verification failed").strip()
        return AIcEntitlementEvidenceVerification(False, "_AAC.sigstore.entitlement", (detail,), signer_identity=signer_identity)
