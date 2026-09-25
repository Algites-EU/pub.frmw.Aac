from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier

from .aic_sigstore_package_verifier import AIcSigstorePackageVerifier
from .aic_sigstore_trust_policy import AIcSigstoreTrustPolicy
from .ain_sigstore_verification_mode import AInSigstoreVerificationMode

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
        from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementEvidenceVerification

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
