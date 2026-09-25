from __future__ import annotations

from collections.abc import Callable


def aig_operation(operation_id: str):
    """Attach generated binding metadata. Canonical contracts remain authoritative."""
    if not operation_id:
        raise ValueError("operation_id must not be empty")
    def decorate(function: Callable):
        setattr(function, "__aac_operation_id__", operation_id)
        return function
    return decorate


def aig_authorization(*, all_of: tuple[str, ...] = (), any_of: tuple[str, ...] = ()):
    """Attach generated authorization metadata for diagnostics/reflection only."""
    def decorate(function: Callable):
        setattr(function, "__aac_authorization_all_of__", tuple(all_of))
        setattr(function, "__aac_authorization_any_of__", tuple(any_of))
        return function
    return decorate
