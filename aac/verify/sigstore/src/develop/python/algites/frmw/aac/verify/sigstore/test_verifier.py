from pathlib import Path
import subprocess

from algites.frmw.aac.coreintf.verification import AIcVerificationInput
from algites.frmw.aac.verify.sigstore import AIcSigstorePackageVerifier, AIcSigstoreTrustPolicy


def test_sigstore_verifier_uses_explicit_identity_policy(tmp_path: Path):
    artifact = tmp_path / "sample.whl"
    artifact.write_bytes(b"wheel")
    bundle = Path(str(artifact) + ".sigstore.json")
    bundle.write_text("{}", encoding="utf-8")
    seen = []
    def runner(command):
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")
    verifier = AIcSigstorePackageVerifier(
        AIcSigstoreTrustPolicy(cert_identity="release@example.test", oidc_issuer="https://issuer.example.test"),
        runner=runner,
    )
    output = verifier.verify(AIcVerificationInput("x", 1, None, "test", {}, str(artifact)))
    assert output.valid
    assert "--cert-identity" in seen[0]
    assert "release@example.test" in seen[0]
    assert "--offline" in seen[0]


def test_sigstore_verifier_fails_closed_without_artifact_path():
    verifier = AIcSigstorePackageVerifier(AIcSigstoreTrustPolicy(cert_identity="x", oidc_issuer="y"), runner=lambda cmd: None)
    output = verifier.verify(AIcVerificationInput("x", 1, None, "test", {}))
    assert not output.valid


def test_sigstore_entitlement_verifier_uses_issuer_policy(tmp_path: Path):
    from algites.frmw.aac.coreintf.entitlement import AIcEntitlementLicensingScope
    from algites.frmw.aac.coreintf.entitlement import (
        AIcEntitlementDocument, AIcEntitlementEvidence, AIcEntitlementIssuer, AIcEntitlementSubject,
    )
    from algites.frmw.aac.verify.sigstore import AIcSigstoreEntitlementEvidenceVerifier

    artifact = tmp_path / "license.entitlement.yml"
    artifact.write_text("entitlement", encoding="utf-8")
    bundle = Path(str(artifact) + ".sigstore.json"); bundle.write_text("{}", encoding="utf-8")
    seen = []
    def runner(command):
        seen.append(list(command)); return subprocess.CompletedProcess(command, 0, "", "")
    verifier = AIcSigstoreEntitlementEvidenceVerifier({
        "vendor.example": AIcSigstoreTrustPolicy(cert_identity="license@example.test", oidc_issuer="https://issuer.example.test")
    }, runner=runner)
    document = AIcEntitlementDocument(
        1, "ent", AIcEntitlementIssuer("vendor.example"), AIcEntitlementLicensingScope("WORKSPACE", "ws"),
        AIcEntitlementSubject("ws"), (),
    )
    result = verifier.verify(AIcEntitlementEvidence(
        document, "SIGSTORE", str(artifact), {"artifact_path": str(artifact), "sidecar_path": str(bundle)}
    ))
    assert result.valid and result.signer_identity == "license@example.test"
    assert "license@example.test" in seen[0]
