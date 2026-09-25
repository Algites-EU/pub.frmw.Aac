from __future__ import annotations

from importlib import util

from algites.frmw.aac.coreintf.verification import AIiPackageVerifier, AIcVerificationInput, AIcVerificationOutput


class AIcPythonPackageVerifier(AIiPackageVerifier):
    """Baseline Python-profile verifier.

    It verifies that a package-backed component resolves to an importable module. Signature/trust
    verification can be supplied by replacing this Core-owned verifier.
    """

    def verify(self, verification_input: AIcVerificationInput) -> AIcVerificationOutput:
        if verification_input.package is None:
            return AIcVerificationOutput(True)
        if util.find_spec(verification_input.package) is None:
            return AIcVerificationOutput(False, (f"package {verification_input.package!r} is not importable",))
        return AIcVerificationOutput(True)
