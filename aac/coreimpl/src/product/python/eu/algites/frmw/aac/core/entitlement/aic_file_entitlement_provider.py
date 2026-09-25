from __future__ import annotations
from pathlib import Path
from typing import Iterable
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementEvidence,
    AIcEntitlementProviderRequest,
    AIiEntitlementProvider,
)
from eu.algites.frmw.aac.core.entitlement.documents import AIcEntitlementDocumentLoader

class AIcFileEntitlementProvider(AIiEntitlementProvider):
    """Reference read-only entitlement provider backed by signed entitlement files.

    Files are discovered by glob; the detached verification sidecar is intentionally not
    interpreted here. Its path is exposed in verification_material so an evidence verifier
    such as the Sigstore plugin can validate the exact entitlement bytes.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        pattern: str = "*.entitlement.yml",
        evidence_type: str = "SIGNED_FILE",
        sidecar_suffix: str = ".sigstore.json",
    ) -> None:
        self.root = Path(root)
        self.pattern = pattern
        self.evidence_type = evidence_type
        self.sidecar_suffix = sidecar_suffix

    def evidence(self, request: AIcEntitlementProviderRequest) -> tuple[AIcEntitlementEvidence, ...]:
        if not self.root.exists():
            return ()
        result: list[AIcEntitlementEvidence] = []
        for path in sorted(self.root.glob(self.pattern)):
            if not path.is_file():
                continue
            document = AIcEntitlementDocumentLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))
            if document.licensing_scope != request.licensing_scope:
                continue
            if request.subject is not None and document.subject.id != request.subject.id:
                continue
            sidecar = Path(str(path) + self.sidecar_suffix)
            result.append(AIcEntitlementEvidence(
                document=document,
                evidence_type=self.evidence_type,
                source=str(path),
                verification_material={
                    "artifact_path": str(path),
                    "sidecar_path": str(sidecar),
                    "sidecar_exists": sidecar.is_file(),
                },
            ))
        return tuple(result)
