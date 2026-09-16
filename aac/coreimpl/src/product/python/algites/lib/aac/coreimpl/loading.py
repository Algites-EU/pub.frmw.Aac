from __future__ import annotations

import importlib
from typing import TypeVar

from .errors import AIxPluginLoadError

T = TypeVar("T")


def load_symbol(reference: str) -> object:
    """Load `module:qualname` without probing component classes for undeclared hooks."""
    try:
        module_name, qualname = reference.split(":", 1)
    except ValueError as exc:
        raise AIxPluginLoadError(f"invalid Python symbol reference {reference!r}; expected module:qualname") from exc
    try:
        value: object = importlib.import_module(module_name)
        for part in qualname.split("."):
            value = getattr(value, part)
        return value
    except (ImportError, AttributeError) as exc:
        raise AIxPluginLoadError(f"cannot load Python symbol {reference!r}") from exc


def load_class(reference: str, expected_base: type[T] | None = None) -> type[T]:
    value = load_symbol(reference)
    if not isinstance(value, type):
        raise AIxPluginLoadError(f"{reference!r} does not resolve to a class")
    if expected_base is not None and not issubclass(value, expected_base):
        raise AIxPluginLoadError(f"{reference!r} does not implement {expected_base.__module__}.{expected_base.__qualname__}")
    return value
