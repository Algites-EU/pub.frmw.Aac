from __future__ import annotations
import base64
import os
from pathlib import Path
from typing import Mapping
from eu.algites.frmw.aac.core.authentication.api import (
    AInSecretProviderCapability,
    AIcAuthenticationMaterial,
    AIcAuthenticationProfile,
    AIcAuthenticationRequest,
    AIcClientCertificateMaterial,
    AIcSecretReference,
    AIiAuthenticationHandler,
    AIiSecretProvider,
    AIiSecretResolver,
)

class AIcFileSecretProvider(AIiSecretProvider):
    """Small filesystem secret provider.

    It is intentionally policy-neutral: filesystem ownership/permissions protect the bytes;
    AAC authorization still controls which application operations may request/use them.
    """

    def __init__(self, root: str | Path, *, read_only: bool = True, encoding: str = "utf-8") -> None:
        self.root = Path(root)
        self.read_only = read_only
        self.encoding = encoding

    def _path(self, key: str) -> Path:
        if not key or key in {".", ".."} or "/" in key or "\\" in key:
            raise ValueError("filesystem secret key must be one safe path segment")
        return self.root / key

    def capabilities(self, context: Mapping[str, object] | None = None):
        result = [AInSecretProviderCapability.READ]
        if not self.read_only:
            result += [AInSecretProviderCapability.WRITE, AInSecretProviderCapability.DELETE]
        return tuple(result)

    def resolve(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str:
        return self._path(reference.key).read_text(encoding=self.encoding).rstrip("\r\n")

    def put(self, key: str, value: str | bytes, context: Mapping[str, object] | None = None) -> None:
        if self.read_only:
            raise PermissionError("secret-provider is read-only")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        tmp = path.with_name(path.name + ".tmp")
        if isinstance(value, bytes):
            tmp.write_bytes(value)
        else:
            tmp.write_text(value, encoding=self.encoding)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    def delete(self, key: str, context: Mapping[str, object] | None = None) -> None:
        if self.read_only:
            raise PermissionError("secret-provider is read-only")
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass
