from __future__ import annotations
from eu.algites.frmw.aac.core.authorization.api import AIcComponentAuthorizationGrant
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore

from .aic_component_authorization_grant_store import AIcComponentAuthorizationGrantStore

_NAMESPACE = "aac.component-authorization-grants"
