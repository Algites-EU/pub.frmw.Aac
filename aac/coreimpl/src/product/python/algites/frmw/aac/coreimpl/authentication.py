from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Mapping

from algites.frmw.aac.coreintf.authentication import (
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


class AIcSecretProviderRegistry(AIiSecretResolver):
    def __init__(self) -> None:
        self._providers: dict[str, AIiSecretProvider] = {}

    def register(self, secret_provider_id: str, provider: AIiSecretProvider) -> None:
        if not secret_provider_id:
            raise ValueError("secret_provider_id must not be empty")
        if secret_provider_id in self._providers:
            raise ValueError(f"secret-provider {secret_provider_id!r} is already registered")
        self._providers[secret_provider_id] = provider

    def contains(self, secret_provider_id: str) -> bool:
        return secret_provider_id in self._providers

    def get(self, secret_provider_id: str) -> AIiSecretProvider:
        return self._providers[secret_provider_id]

    def resolve_secret(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str | bytes:
        return self.get(reference.secret_provider_id).resolve(reference, context)


class AIcEnvironmentSecretProvider(AIiSecretProvider):
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def resolve(self, reference: AIcSecretReference, context: Mapping[str, object] | None = None) -> str:
        key = self.prefix + reference.key
        if key not in os.environ:
            raise KeyError(f"environment secret {key!r} is not defined")
        return os.environ[key]


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


class AIcAuthenticationHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, AIiAuthenticationHandler] = {}

    def register(self, mechanism: str, handler: AIiAuthenticationHandler) -> None:
        mechanism = mechanism.strip()
        if not mechanism:
            raise ValueError("authentication mechanism must not be empty")
        self._handlers[mechanism] = handler

    def get(self, mechanism: str) -> AIiAuthenticationHandler:
        return self._handlers[mechanism]


class AIcAuthenticationProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, AIcAuthenticationProfile] = {}

    def register(self, profile: AIcAuthenticationProfile) -> None:
        if profile.id in self._profiles:
            raise ValueError(f"authentication profile {profile.id!r} is already registered")
        self._profiles[profile.id] = profile

    def contains(self, profile_id: str) -> bool:
        return profile_id in self._profiles

    def get(self, profile_id: str) -> AIcAuthenticationProfile:
        return self._profiles[profile_id]


class AIcNoneAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        return AIcAuthenticationMaterial()


class AIcBasicAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        username = _parameter_text(request.profile, "username", secret_resolver, request.context)
        password = _parameter_text(request.profile, "password", secret_resolver, request.context)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return AIcAuthenticationMaterial(headers={"Authorization": f"Basic {token}"})


class AIcBearerAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        token = _parameter_text(request.profile, "token", secret_resolver, request.context)
        return AIcAuthenticationMaterial(headers={"Authorization": f"Bearer {token}"})


class AIcClientCertificateAuthenticationHandler(AIiAuthenticationHandler):
    def authenticate(self, request, secret_resolver):
        certificate_path = _parameter_text(request.profile, "certificate_path", secret_resolver, request.context)
        private_key_path = _optional_parameter_text(request.profile, "private_key_path", secret_resolver, request.context)
        private_key_password = _optional_parameter_text(request.profile, "private_key_password", secret_resolver, request.context)
        return AIcAuthenticationMaterial(client_certificate=AIcClientCertificateMaterial(
            certificate_path=certificate_path,
            private_key_path=private_key_path,
            private_key_password=private_key_password,
        ))


class AIcAuthenticationService:
    def __init__(self, secret_providers: AIcSecretProviderRegistry | None = None) -> None:
        self.secret_providers = secret_providers or AIcSecretProviderRegistry()
        self.profiles = AIcAuthenticationProfileRegistry()
        self.handlers = AIcAuthenticationHandlerRegistry()
        self.handlers.register("NONE", AIcNoneAuthenticationHandler())
        self.handlers.register("BASIC", AIcBasicAuthenticationHandler())
        self.handlers.register("BEARER", AIcBearerAuthenticationHandler())
        self.handlers.register("CLIENT_CERTIFICATE", AIcClientCertificateAuthenticationHandler())

    def register_profile(self, profile: AIcAuthenticationProfile) -> None:
        self.profiles.register(profile)

    def material(\
        self, profile_id: str | None, *, transport_kind: str, endpoint: str | None = None,\
        context: Mapping[str, object] | None = None,\
    ) -> AIcAuthenticationMaterial:
        if profile_id is None:
            return AIcAuthenticationMaterial()
        profile = self.profiles.get(profile_id)
        handler = self.handlers.get(profile.mechanism)
        return handler.authenticate(AIcAuthenticationRequest(profile, transport_kind, endpoint, dict(context or {})), self.secret_providers)


def _parameter_text(profile, key, secret_resolver, context) -> str:
    parameter = profile.parameters.get(key)
    if parameter is None:
        raise ValueError(f"authentication profile {profile.id!r} requires parameter {key!r}")
    if parameter.secret_reference is not None:
        value = secret_resolver.resolve_secret(parameter.secret_reference, context)
    else:
        value = parameter.value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if value is None:
        raise ValueError(f"authentication parameter {key!r} has no value")
    return str(value)


def _optional_parameter_text(profile, key, secret_resolver, context) -> str | None:
    if key not in profile.parameters:
        return None
    return _parameter_text(profile, key, secret_resolver, context)
