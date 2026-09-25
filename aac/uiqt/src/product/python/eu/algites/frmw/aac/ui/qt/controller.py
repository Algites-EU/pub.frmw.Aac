from __future__ import annotations
import json
from dataclasses import replace
from typing import Mapping
from eu.algites.frmw.aac.core.catalog.api import AIcCatalogQuery
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationMutationOperation, AInConfigurationTargetKind, AIcConfigurationChange,
    AIcConfigurationChangeSet, AIcConfigurationProviderRequest, AIcConfigurationTarget,
)
from eu.algites.frmw.aac.core.context.api import AIcConfigurationScope
from eu.algites.frmw.aac.core.instances.api import AIcBindingPreference
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText, normalize_display_text
from eu.algites.frmw.aac.core.packages.api import AInStoredPackageState
from eu.algites.frmw.aac.core.solver.api import AIcTargetStateRequest, AIcTargetStateSolution, AIcTargetStateSolverResult
from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationBinding,
    AIcObservationSelector,
    AInObservationPhase,
)
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
from eu.algites.frmw.aac.ui.api import (
    AIiAacUiController,
    AIcUiConfigurationProviderOption,
    AIcUiConfigurationScope,
    AInUiFieldType,
    AIcUiBinding,
    AIcUiChoice,
    AIcUiComponent,
    AIcUiField,
    AIcUiFieldGroup,
    AIcUiForm,
    AIcUiObservationBinding,
    AIcUiObservationSelector,
    AIcUiProviderInstance,
    AIcUiRequirement,
    AIcUiRequirementEditor,
    AIcUiEntitlementPermission,
    AIcUiEntitlementStatus,
    AIcUiCatalogPackageArtifact,
    AIcUiPackageArtifact,
    AIcUiUpgradeDiagnostic,
    AIcUiUpgradePlan,
    AIcUiUpgradeReplacement,
)

from .aic_core_ui_controller import AIcCoreUiController

def _display_text(value: AIcDisplayText | None) -> AIcDisplayText | None:
    return value

def _display_text_value(value: AIcDisplayText | None) -> str | None:
    return None if value is None else value.fallback

def _schema_display_text(value: object | None) -> AIcDisplayText | None:
    if value is None:
        return None
    if isinstance(value, (str, Mapping, AIcDisplayText)):
        return normalize_display_text(value)
    return AIcDisplayText(text=str(value))

def _field_from_schema(field_id: str, raw: Mapping[str, object], value: object, required: bool) -> AIcUiField:
    title = _schema_display_text(raw.get("x-aac-name")) or AIcDisplayText(text=str(raw.get("title", field_id.replace("_", " ").title())))
    description = _schema_display_text(raw.get("x-aac-description"))
    if description is None and raw.get("description") is not None:
        description = AIcDisplayText(text=str(raw["description"]))
    ui_type = str(raw.get("x-aac-ui-type", "")).upper()
    secret = bool(raw.get("x-aac-secret", False))
    enum_values = raw.get("enum")
    choices = tuple(AIcUiChoice(item, AIcDisplayText(text=str(item))) for item in enum_values) if isinstance(enum_values, list) else ()
    if ui_type in AInUiFieldType.__members__:
        field_type = AInUiFieldType[ui_type]
    elif choices:
        field_type = AInUiFieldType.ENUM
    else:
        schema_type = raw.get("type")
        field_type = {
            "integer": AInUiFieldType.INTEGER,
            "number": AInUiFieldType.NUMBER,
            "boolean": AInUiFieldType.BOOLEAN,
            "string": AInUiFieldType.STRING,
        }.get(str(schema_type), AInUiFieldType.JSON)
    if secret and field_type is AInUiFieldType.STRING:
        field_type = AInUiFieldType.SECRET_REFERENCE
    if value is None and "default" in raw:
        value = raw["default"]
    if field_type is AInUiFieldType.JSON and value is not None and not isinstance(value, str):
        value = json.loads(json.dumps(value))
    accepted_scopes_raw = raw.get("x-aac-configuration-scopes", ())
    accepted_scopes = tuple(str(item) for item in accepted_scopes_raw) if isinstance(accepted_scopes_raw, list) else ()
    return AIcUiField(
        id=field_id, label=title, field_type=field_type, value=value, required=required,
        read_only=False, description=description, choices=choices, multiple=False, secret=secret,
        metadata=dict(raw), accepted_configuration_scope_types=accepted_scopes,
    )
