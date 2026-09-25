from __future__ import annotations

from contextvars import ContextVar

from eu.algites.frmw.aac.core.authorization.api import AIcAuthorizationPrincipal

CURRENT_INVOCATION_ID: ContextVar[str | None] = ContextVar("aac_current_invocation_id", default=None)
CURRENT_AUTHORIZATION_PRINCIPAL: ContextVar[AIcAuthorizationPrincipal | None] = ContextVar(
    "aac_current_authorization_principal", default=None
)
