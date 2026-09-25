from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from eu.algites.frmw.aac.core.presentation.api import (
    AIcDisplayContent,
    AIcDisplayText,
    normalize_display_content,
    normalize_display_text,
)

from .ain_ui_field_type import AInUiFieldType
from .aic_ui_configuration_scope import AIcUiConfigurationScope
from .aic_ui_configuration_provider_option import AIcUiConfigurationProviderOption
from .aic_ui_choice import AIcUiChoice
from .aic_ui_field import AIcUiField
from .aic_ui_field_group import AIcUiFieldGroup
from .aic_ui_form import AIcUiForm
from .aic_ui_display import AIcUiDisplay
from .aic_ui_panel import AIcUiPanel
from .aic_ui_component import AIcUiComponent
from .aic_ui_provider_instance import AIcUiProviderInstance
from .aic_ui_binding import AIcUiBinding
from .aic_ui_requirement import AIcUiRequirement
from .aic_ui_requirement_editor import AIcUiRequirementEditor
from .aic_ui_observation_selector import AIcUiObservationSelector
from .aic_ui_observation_binding import AIcUiObservationBinding
from .aic_ui_entitlement_permission import AIcUiEntitlementPermission
from .aic_ui_entitlement_status import AIcUiEntitlementStatus
from .aic_ui_catalog_package_artifact import AIcUiCatalogPackageArtifact
from .aic_ui_package_artifact import AIcUiPackageArtifact
from .aic_ui_upgrade_replacement import AIcUiUpgradeReplacement
from .aic_ui_upgrade_diagnostic import AIcUiUpgradeDiagnostic
from .aic_ui_upgrade_plan import AIcUiUpgradePlan

def _required_display_text(value: AIcDisplayText | str) -> AIcDisplayText:
    normalized = normalize_display_text(value)
    if normalized is None:
        raise ValueError("required display text is missing")
    return normalized

def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)

def _required_display_content(value: AIcDisplayContent | str) -> AIcDisplayContent:
    normalized = normalize_display_content(value)
    if normalized is None:
        raise ValueError("required display content is missing")
    return normalized
