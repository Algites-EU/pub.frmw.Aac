from __future__ import annotations

from dataclasses import dataclass

from algites.frmw.aac.coreintf.descriptor import AIcComponentDescriptor

from .errors import AIxCoreImplementationError


class AIxNamespacePolicyError(AIxCoreImplementationError):
    pass


@dataclass(frozen=True, slots=True)
class AIcReservedNamespace:
    prefix: str


class AIcNamespacePolicy:
    def __init__(self) -> None:
        self._reserved: set[str] = {"_AAC."}

    def reserve(self, prefix: str) -> None:
        if not prefix.endswith("."):
            raise ValueError("reserved namespace prefix must end with '.'")
        self._reserved.add(prefix)

    def validate(self, descriptor: AIcComponentDescriptor, trusted_prefixes: tuple[str, ...] = ()) -> None:
        identities = [descriptor.id]
        identities.extend(
            capability.id for provider in descriptor.capability_providers for capability in provider.capabilities
        )
        for provider in descriptor.capability_providers:
            identities.extend(requirement.capability_id for requirement in provider.requirements)
        for identity in identities:
            for prefix in self._reserved:
                if identity.startswith(prefix) and prefix not in trusted_prefixes:
                    raise AIxNamespacePolicyError(
                        f"component {descriptor.id!r} uses reserved namespace {prefix!r} without Core trust"
                    )
