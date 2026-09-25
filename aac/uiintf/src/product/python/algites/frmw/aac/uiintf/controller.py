from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from algites.frmw.aac.coreintf.solver import AIcTargetStateSolution, AIcTargetStateSolverResult

from .models import (
    AIcUiBinding,
    AIcUiComponent,
    AIcUiForm,
    AIcUiObservationBinding,
    AIcUiProviderInstance,
    AIcUiRequirement,
    AIcUiRequirementEditor,
    AIcUiEntitlementStatus,
    AIcUiCatalogPackageArtifact,
    AIcUiPackageArtifact,
    AIcUiUpgradePlan,
)


class AIiAacUiController(ABC):
    """Technology-neutral administration surface over Core-owned AAC state."""

    @abstractmethod
    def components(self) -> tuple[AIcUiComponent, ...]: ...

    @abstractmethod
    def provider_instances(self, component_id: str | None = None) -> tuple[AIcUiProviderInstance, ...]: ...

    @abstractmethod
    def create_provider_instance(self, component_id: str, provider_definition_id: str, name: str = "default") -> AIcUiProviderInstance: ...

    @abstractmethod
    def rename_provider_instance(self, instance_id: str, name: str) -> AIcUiProviderInstance: ...

    @abstractmethod
    def remove_provider_instance(self, instance_id: str) -> None: ...

    @abstractmethod
    def provider_configuration_form(self, instance_id: str) -> AIcUiForm: ...

    @abstractmethod
    def update_provider_scoped_configuration(
        self, instance_id: str, configuration_scope_type: str, configuration_scope_id: str | None,
        configuration_provider_id: str, values: Mapping[str, object], expected_record_revision: str | int | None = None,
    ) -> AIcUiProviderInstance: ...

    @abstractmethod
    def update_provider_configuration(self, instance_id: str, values: Mapping[str, object]) -> AIcUiProviderInstance: ...

    @abstractmethod
    def bindings(self) -> tuple[AIcUiBinding, ...]: ...

    @abstractmethod
    def requirements(self) -> tuple[AIcUiRequirement, ...]: ...

    @abstractmethod
    def requirement_editor(self, consumer_instance_id: str, requirement_id: str) -> AIcUiRequirementEditor: ...

    @abstractmethod
    def set_requirement_providers(self, consumer_instance_id: str, requirement_id: str, provider_instance_ids: tuple[str, ...]) -> None: ...

    @abstractmethod
    def set_requirement_authorizations(
        self, consumer_instance_id: str, requirement_id: str, permission_ids: tuple[str, ...]
    ) -> None: ...

    @abstractmethod
    def entitlement_status(self, component_id: str) -> AIcUiEntitlementStatus: ...

    @abstractmethod
    def observation_bindings(self) -> tuple[AIcUiObservationBinding, ...]: ...

    @abstractmethod
    def put_observation_binding(self, binding: AIcUiObservationBinding) -> None: ...

    @abstractmethod
    def delete_observation_binding(self, observer_instance_id: str) -> None: ...

    @abstractmethod
    def catalog_defaults(self) -> tuple[str | None, str | None]: ...

    @abstractmethod
    def catalog_packages(
        self, product_id: str, technology_id: str, text: str | None = None
    ) -> tuple[AIcUiCatalogPackageArtifact, ...]: ...


    @abstractmethod
    def solve_catalog_target(
        self, application_scope_id: str, identity: tuple[str, str, str, str, int, str]
    ) -> AIcTargetStateSolverResult: ...

    @abstractmethod
    def apply_target_state_solution(
        self, application_scope_id: str, solution: AIcTargetStateSolution
    ) -> AIcTargetStateSolution: ...

    @abstractmethod
    def download_catalog_package(
        self, identity: tuple[str, str, str, str, int, str]
    ) -> AIcUiPackageArtifact: ...

    @abstractmethod
    def install_catalog_package(
        self, identity: tuple[str, str, str, str, int, str]
    ) -> AIcUiPackageArtifact: ...

    @abstractmethod
    def restore_obsolete_package(self, identity: tuple[str, int, str]) -> AIcUiPackageArtifact: ...

    @abstractmethod
    def package_artifacts(self) -> tuple[AIcUiPackageArtifact, ...]: ...

    @abstractmethod
    def plan_package_upgrades(
        self, application_scope_id: str, package_identities: tuple[tuple[str, int, str], ...]
    ) -> AIcUiUpgradePlan: ...

    @abstractmethod
    def apply_package_upgrades(
        self, application_scope_id: str, package_identities: tuple[tuple[str, int, str], ...]
    ) -> AIcUiUpgradePlan: ...
