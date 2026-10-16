from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Mapping

from .interaction import AIcNullOperationInteraction, AIiOperationInteractionProviderToCallerOnProvider

_CURRENT_OPERATION_PARAMETERS: ContextVar[Mapping[str, object]] = ContextVar(
    "aac_current_operation_parameters", default={}
)
_CURRENT_BINDING_QUALIFIER_PROFILES: ContextVar[tuple[Mapping[str, object], ...]] = ContextVar(
    "aac_current_binding_qualifier_profiles", default=()
)
_CURRENT_OPERATION_INTERACTION: ContextVar[AIiOperationInteractionProviderToCallerOnProvider] = ContextVar(
    "aac_current_operation_interaction", default=None
)
_CURRENT_INVOCATION_LOCALE: ContextVar[str | None] = ContextVar(
    "aac_current_invocation_locale", default=None
)


def current_operation_parameters() -> Mapping[str, object]:
    """Return effective provider-specific parameters for the current capability invocation."""
    return dict(_CURRENT_OPERATION_PARAMETERS.get())


def current_binding_qualifier_profiles() -> tuple[Mapping[str, object], ...]:
    """Return the provider qualifier profiles selected for the current binding."""
    return tuple(dict(profile) for profile in _CURRENT_BINDING_QUALIFIER_PROFILES.get())


def current_operation_interaction() -> AIiOperationInteractionProviderToCallerOnProvider:
    """Return the provider-facing interaction channel for the current capability invocation."""
    return _CURRENT_OPERATION_INTERACTION.get() or AIcNullOperationInteraction()


def current_invocation_locale() -> str | None:
    """Return the BCP-47 locale requested for the current capability invocation, if any."""
    return _CURRENT_INVOCATION_LOCALE.get()


@contextmanager
def operation_parameter_context(parameters: Mapping[str, object]):
    token = _CURRENT_OPERATION_PARAMETERS.set(dict(parameters))
    try:
        yield
    finally:
        _CURRENT_OPERATION_PARAMETERS.reset(token)


@contextmanager
def binding_qualifier_profiles_context(binding_qualifier_profiles: tuple[Mapping[str, object], ...]):
    token = _CURRENT_BINDING_QUALIFIER_PROFILES.set(tuple(dict(profile) for profile in binding_qualifier_profiles))
    try:
        yield
    finally:
        _CURRENT_BINDING_QUALIFIER_PROFILES.reset(token)


@contextmanager
def operation_interaction_context(interaction: AIiOperationInteractionProviderToCallerOnProvider | None):
    token = _CURRENT_OPERATION_INTERACTION.set(interaction or AIcNullOperationInteraction())
    try:
        yield
    finally:
        _CURRENT_OPERATION_INTERACTION.reset(token)


@contextmanager
def invocation_locale_context(locale: str | None):
    token = _CURRENT_INVOCATION_LOCALE.set(locale)
    try:
        yield
    finally:
        _CURRENT_INVOCATION_LOCALE.reset(token)
