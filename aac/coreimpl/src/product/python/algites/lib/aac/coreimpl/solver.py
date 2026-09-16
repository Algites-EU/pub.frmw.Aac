from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping

from algites.lib.aac.coreintf.catalog import (
    AIcCatalogEntry,
    AIcCatalogPersistentSchema,
    AIcCatalogQuery,
    AInCatalogPersistentSchemaKind,
)
from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import (
    AIcCapabilityEntitlementDescriptor,
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcEntitlementLicensingScopeDescriptor,
    AIcProviderDefinitionDescriptor,
)
from algites.lib.aac.coreintf.packages import (
    AInStoredPackageState,
    AIcStoredPackage,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentRequirements,
)
from algites.lib.aac.coreintf.readiness import AInReadinessState
from algites.lib.aac.coreintf.solver import (
    AInTargetStateChangeDirection,
    AInTargetStateRequestMode,
    AIcSolverEntitlementDiagnostic,
    AIcSolverExplanation,
    AIcSolverReadinessDiagnostic,
    AIcTargetStateRequest,
    AIcTargetStateSelection,
    AIcTargetStateSolution,
    AIcTargetStateSolverResult,
)


@dataclass(frozen=True, slots=True)
class AIcSolverRequirement:
    id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: AInConsumerCardinality
    mandatory: bool


@dataclass(frozen=True, slots=True)
class AIcSolverCandidate:
    component_id: str
    version: int
    provides: tuple[tuple[str, tuple[int, ...]], ...]
    requires: tuple[AIcSolverRequirement, ...]
    persistent_schemas: tuple[AIcCatalogPersistentSchema, ...]
    entitlements: tuple[AIcCapabilityEntitlementDescriptor, ...]
    entitlement_licensing_scopes: tuple[AIcEntitlementLicensingScopeDescriptor, ...] = ()
    descriptor: AIcComponentDescriptor | None = None
    stored_package: AIcStoredPackage | None = None
    catalog_entry: AIcCatalogEntry | None = None
    catalog_artifact_id: str | None = None

    @property
    def source_id(self) -> str | None:
        if self.catalog_entry is not None:
            return self.catalog_entry.source_id
        if self.stored_package is not None:
            return self.stored_package.provenance.source_id
        return None

    @property
    def local_state(self) -> AInStoredPackageState | None:
        return None if self.stored_package is None else self.stored_package.state

    @property
    def entropy_key(self) -> tuple:
        return self.component_id, self.version, self.source_id or "", self.catalog_artifact_id or ""


class AIcCompatibleTargetStateSolver:
    """Find catalog-backed compatible upgrade sets for the current component population.

    The solver deliberately does not add entirely new component ids.  It changes versions of
    components already present in the active target population.  This keeps Build 19 focused on
    automatic multi-component upgrade closure; topology-expanding installation can be layered on
    later without weakening replacement transaction semantics.
    """

    def __init__(self, core) -> None:
        self.core = core

    def solve(
        self,
        application_scope_id: str,
        requests: tuple[AIcTargetStateRequest, ...],
        *,
        workspace_requirements: AIcWorkspaceComponentRequirements | None = None,
        workspace_lock: AIcWorkspaceComponentLock | None = None,
        max_alternatives: int = 3,
        max_combinations: int = 20000,
    ) -> AIcTargetStateSolverResult:
        if not requests:
            raise ValueError("target-state solver requires at least one request")
        request_by_id = {item.component_id: item for item in requests}
        if len(request_by_id) != len(requests):
            raise ValueError("target-state solver requests must be unique by component id")

        current = self._current_candidates()
        missing = sorted(set(request_by_id) - set(current))
        if missing:
            return AIcTargetStateSolverResult(
                requests, None, (),
                tuple(AIcSolverExplanation(
                    "REQUEST_COMPONENT_NOT_ACTIVE",
                    f"component {component_id!r} is not in the active component population; Build 19 solver only changes versions of active components",
                    component_id,
                ) for component_id in missing),
            )

        universe = self._candidate_universe(current)
        closure = self._dependency_closure(current, universe, set(request_by_id))
        closure.update(request_by_id)
        closure.intersection_update(current)

        options: dict[str, tuple[AIcSolverCandidate, ...]] = {}
        diagnostics: list[AIcSolverExplanation] = []
        lock_by_id = {entry.component_id: entry for entry in workspace_lock.entries} if workspace_lock else {}
        req_by_id = {item.component_id: item for item in workspace_requirements.requirements} if workspace_requirements else {}

        for component_id in sorted(closure):
            values = list(universe.get(component_id, ()))
            current_candidate = current[component_id]
            request = request_by_id.get(component_id)
            lock = lock_by_id.get(component_id)
            workspace_requirement = req_by_id.get(component_id)
            filtered = []
            for candidate in values:
                if request is not None and not self._request_accepts(request, current_candidate.version, candidate.version):
                    continue
                if lock is not None and candidate.version != lock.component_version:
                    continue
                if workspace_requirement is not None and not workspace_requirement.accepts(candidate.version):
                    continue
                filtered.append(candidate)
            if request is None and not filtered:
                filtered = [current_candidate]
            if request is not None and not filtered:
                diagnostics.append(AIcSolverExplanation(
                    "NO_REQUESTED_VERSION",
                    f"no candidate release satisfies request for {component_id!r}",
                    component_id,
                ))
            # Prefer local representation for the same version, otherwise deterministic catalog source.
            dedup: dict[int, AIcSolverCandidate] = {}
            for candidate in sorted(filtered, key=self._candidate_preference_key):
                dedup.setdefault(candidate.version, candidate)
            options[component_id] = tuple(sorted(dedup.values(), key=lambda item: item.version, reverse=True))

        if diagnostics:
            return AIcTargetStateSolverResult(requests, None, (), tuple(diagnostics))

        component_ids = tuple(sorted(options))
        count = 1
        for component_id in component_ids:
            count *= max(1, len(options[component_id]))
            if count > max_combinations:
                return AIcTargetStateSolverResult(requests, None, (), (
                    AIcSolverExplanation(
                        "SEARCH_SPACE_LIMIT",
                        f"solver search space exceeds {max_combinations} target combinations; narrow requested/catalog versions",
                    ),
                ))

        no_downgrade: list[AIcTargetStateSolution] = []
        downgrade: list[AIcTargetStateSolution] = []
        rejected_reasons: list[AIcSolverExplanation] = []
        for combination in product(*(options[component_id] for component_id in component_ids)):
            target = dict(current)
            target.update({candidate.component_id: candidate for candidate in combination})
            if not self._requests_satisfied(requests, target, current):
                continue
            if not self._workspace_satisfied(target, workspace_requirements, workspace_lock):
                continue
            downgrade_components = tuple(
                component_id for component_id, candidate in target.items()
                if component_id in current and candidate.version < current[component_id].version
            )
            if downgrade_components:
                unsafe = tuple(
                    component_id for component_id in downgrade_components
                    if not self._downgrade_schema_safe(current[component_id], target[component_id])
                )
                if unsafe:
                    rejected_reasons.append(AIcSolverExplanation(
                        "DOWNGRADE_SCHEMA_INCOMPATIBLE",
                        "automatic downgrade rejected because persistent configuration/extension schema generations differ: "
                        + ", ".join(sorted(unsafe)),
                    ))
                    continue
            compatible, explanations = self._compatible(target)
            if not compatible:
                rejected_reasons.extend(explanations[:1])
                continue
            if self._has_unnecessary_changes(
                target, current, set(request_by_id), workspace_requirements, workspace_lock
            ):
                continue
            solution = self._solution(
                application_scope_id, current, target, request_by_id, closure,
                contains_downgrade=bool(downgrade_components), explanations=explanations,
                universe=universe,
            )
            (downgrade if downgrade_components else no_downgrade).append(solution)

        no_downgrade.sort(key=self._solution_score)
        downgrade.sort(key=self._solution_score)
        if no_downgrade:
            primary = self._mark_recommended(no_downgrade[0], True)
            alternatives = [self._mark_recommended(item, False) for item in no_downgrade[1:max_alternatives + 1]]
            room = max(0, max_alternatives - len(alternatives))
            alternatives.extend(self._mark_recommended(item, False) for item in downgrade[:room])
            return AIcTargetStateSolverResult(requests, primary, tuple(alternatives), ())
        if downgrade:
            # Downgrade solutions are intentionally never recommended automatically.
            alternatives = tuple(self._mark_recommended(item, False) for item in downgrade[:max_alternatives])
            return AIcTargetStateSolverResult(
                requests, None, alternatives,
                (AIcSolverExplanation(
                    "DOWNGRADE_ONLY",
                    "no upgrade-only solution exists; compatible downgrade alternatives are available but require explicit user choice",
                ),),
            )

        rendered = self._deduplicate_explanations(rejected_reasons)
        if not rendered:
            rendered = (AIcSolverExplanation("NO_SOLUTION", "no compatible target component set exists"),)
        return AIcTargetStateSolverResult(requests, None, (), rendered)

    def _current_candidates(self) -> dict[str, AIcSolverCandidate]:
        return {
            component_id: self._from_descriptor(item.discovered.descriptor)
            for component_id, item in self.core._installed.items()
        }

    def _candidate_universe(self, current: Mapping[str, AIcSolverCandidate]) -> dict[str, tuple[AIcSolverCandidate, ...]]:
        values: dict[str, list[AIcSolverCandidate]] = {component_id: [candidate] for component_id, candidate in current.items()}
        if self.core.package_manager is not None:
            for package in self.core.package_manager.package_store.records():
                if package.component_id not in current:
                    continue
                try:
                    descriptor = self.core.package_manager.descriptor_from_artifact(package)
                except Exception:
                    continue
                values.setdefault(package.component_id, []).append(self._from_descriptor(descriptor, stored_package=package))
        if self.core.catalog_product_id and self.core.catalog_technology_id:
            query = AIcCatalogQuery(self.core.catalog_product_id, self.core.catalog_technology_id)
            for entry in self.core.query_catalog(query):
                if entry.component_id not in current:
                    continue
                artifact = entry.release.artifacts[0] if entry.release.artifacts else None
                values.setdefault(entry.component_id, []).append(AIcSolverCandidate(
                    entry.component_id,
                    entry.component_version,
                    tuple((offer.capability_id, tuple(offer.versions)) for offer in entry.release.provides),
                    tuple(AIcSolverRequirement(req.id, req.capability_id, tuple(req.versions), req.cardinality, req.mandatory) for req in entry.release.requires),
                    tuple(entry.release.persistent_schemas),
                    tuple(entry.release.provided_capability_entitlements),
                    tuple(entry.release.entitlement_licensing_scopes),
                    catalog_entry=entry,
                    catalog_artifact_id=(artifact.id if artifact is not None else None),
                ))
        result = {}
        for component_id, candidates in values.items():
            unique: dict[tuple[int, str | None, str | None], AIcSolverCandidate] = {}
            for candidate in sorted(candidates, key=self._candidate_preference_key):
                key = (candidate.version, candidate.source_id, candidate.catalog_artifact_id)
                unique.setdefault(key, candidate)
            result[component_id] = tuple(unique.values())
        return result

    @staticmethod
    def _candidate_preference_key(candidate: AIcSolverCandidate) -> tuple:
        local_rank = {
            AInStoredPackageState.INSTALLED: 0,
            AInStoredPackageState.DOWNLOADED: 1,
            AInStoredPackageState.OBSOLETE: 2,
            None: 3,
        }[candidate.local_state]
        descriptor_rank = 0 if candidate.descriptor is not None else 1
        return candidate.version * -1, local_rank, descriptor_rank, candidate.source_id or "", candidate.catalog_artifact_id or ""

    @staticmethod
    def _from_descriptor(descriptor: AIcComponentDescriptor, *, stored_package: AIcStoredPackage | None = None) -> AIcSolverCandidate:
        provides = tuple(
            (provider.capability_id, tuple(provider.capability_versions))
            for provider in descriptor.providers
        )
        requires = tuple(
            AIcSolverRequirement(req.id, req.capability_id, tuple(req.versions), req.cardinality, req.mandatory)
            for provider in descriptor.providers for req in provider.requirements
        )
        schemas: list[AIcCatalogPersistentSchema] = []
        if descriptor.component_configuration_schema is not None:
            item = descriptor.component_configuration_schema
            schemas.append(AIcCatalogPersistentSchema(
                AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, item.schema_id, item.write_version
            ))
        for provider in descriptor.providers:
            if provider.configuration_schema is not None:
                item = provider.configuration_schema
                schemas.append(AIcCatalogPersistentSchema(
                    AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION, item.schema_id, item.write_version, provider_id=provider.id
                ))
        for extension in descriptor.entity_extensions:
            item = extension.extension_data.component_extension_schema
            if item is not None:
                schemas.append(AIcCatalogPersistentSchema(
                    AInCatalogPersistentSchemaKind.ENTITY_EXTENSION, item.schema_id, item.write_version, entity_type_id=extension.entity_type_id
                ))
        return AIcSolverCandidate(
            descriptor.id, descriptor.version, provides, requires, tuple(schemas),
            tuple(descriptor.provided_capability_entitlements), tuple(descriptor.entitlement_licensing_scopes),
            descriptor=descriptor, stored_package=stored_package,
        )

    def _dependency_closure(
        self, current: Mapping[str, AIcSolverCandidate], universe: Mapping[str, tuple[AIcSolverCandidate, ...]], seed: set[str]
    ) -> set[str]:
        closure = set(seed)
        changed = True
        while changed:
            changed = False
            for component_id in tuple(closure):
                candidates = universe.get(component_id, ())
                for candidate in candidates:
                    for requirement in candidate.requires:
                        if not requirement.mandatory:
                            continue
                        for provider_id in current:
                            if provider_id in closure:
                                continue
                            if any(self._candidate_provides(option, requirement) for option in universe.get(provider_id, ())):
                                closure.add(provider_id)
                                changed = True
        return closure

    @staticmethod
    def _request_accepts(request: AIcTargetStateRequest, current_version: int, candidate_version: int) -> bool:
        if request.mode is AInTargetStateRequestMode.EXACT:
            return candidate_version == request.versions[0]
        if request.mode is AInTargetStateRequestMode.ONE_OF:
            return candidate_version in request.versions
        return candidate_version >= current_version

    @classmethod
    def _requests_satisfied(cls, requests, target, current) -> bool:
        return all(
            request.component_id in target
            and cls._request_accepts(request, current[request.component_id].version, target[request.component_id].version)
            for request in requests
        )

    @staticmethod
    def _workspace_satisfied(target, requirements, lock) -> bool:
        if requirements is not None:
            for requirement in requirements.requirements:
                candidate = target.get(requirement.component_id)
                if requirement.required and candidate is None:
                    return False
                if candidate is not None and not requirement.accepts(candidate.version):
                    return False
        if lock is not None:
            for entry in lock.entries:
                candidate = target.get(entry.component_id)
                if candidate is None or candidate.version != entry.component_version:
                    return False
        return True

    @staticmethod
    def _candidate_provides(candidate: AIcSolverCandidate, requirement: AIcSolverRequirement) -> bool:
        requested = set(requirement.versions)
        for capability_id, versions in candidate.provides:
            if capability_id != requirement.capability_id:
                continue
            if not requested or requested.intersection(versions):
                return True
        return False

    def _compatible(self, target: Mapping[str, AIcSolverCandidate]) -> tuple[bool, tuple[AIcSolverExplanation, ...]]:
        explanations: list[AIcSolverExplanation] = []
        for consumer_id, consumer in target.items():
            for requirement in consumer.requires:
                if not requirement.mandatory:
                    continue
                providers = [
                    (provider_id, candidate)
                    for provider_id, candidate in target.items()
                    if self._candidate_provides(candidate, requirement)
                ]
                if providers:
                    # Explanation is attached only to changed provider selections later.
                    continue
                explanations.append(AIcSolverExplanation(
                    "UNSATISFIED_CAPABILITY",
                    f"{consumer_id}/{consumer.version} requires capability {requirement.capability_id} "
                    f"versions {list(requirement.versions) or ['ANY']} but no target component provides a compatible version",
                    consumer_id,
                    capability_id=requirement.capability_id,
                ))
        return not explanations, tuple(explanations)


    def _has_unnecessary_changes(
        self, target, current, requested_ids: set[str], workspace_requirements, workspace_lock
    ) -> bool:
        for component_id, candidate in target.items():
            if component_id in requested_ids or candidate.version == current[component_id].version:
                continue
            probe = dict(target)
            probe[component_id] = current[component_id]
            compatible, _ = self._compatible(probe)
            if compatible and self._workspace_satisfied(probe, workspace_requirements, workspace_lock):
                return True
        return False

    @staticmethod
    def _downgrade_schema_safe(current: AIcSolverCandidate, target: AIcSolverCandidate) -> bool:
        if not current.persistent_schemas or not target.persistent_schemas:
            return not current.persistent_schemas and not target.persistent_schemas
        current_map = {item.identity: (item.schema_id, item.write_version) for item in current.persistent_schemas}
        target_map = {item.identity: (item.schema_id, item.write_version) for item in target.persistent_schemas}
        return current_map == target_map

    def _solution(
        self, application_scope_id, current, target, request_by_id, closure, *, contains_downgrade, explanations, universe
    ) -> AIcTargetStateSolution:
        selections: list[AIcTargetStateSelection] = []
        causal: list[AIcSolverExplanation] = list(explanations)
        for component_id in sorted(current):
            before = current[component_id]
            after = target[component_id]
            if after.version == before.version:
                direction = AInTargetStateChangeDirection.UNCHANGED
            elif after.version > before.version:
                direction = AInTargetStateChangeDirection.UPGRADE
            else:
                direction = AInTargetStateChangeDirection.DOWNGRADE
            local = after.local_state
            selections.append(AIcTargetStateSelection(
                component_id, before.version, after.version, direction,
                requested=component_id in request_by_id,
                source_id=after.source_id,
                artifact_id=after.catalog_artifact_id,
                target_sha256=(after.stored_package.sha256 if after.stored_package is not None else
                               (after.catalog_entry.release.artifacts[0].sha256 if after.catalog_entry is not None and after.catalog_entry.release.artifacts else None)),
                download_required=(after.catalog_entry is not None and local is None),
                install_required=(after.catalog_entry is not None and local is not AInStoredPackageState.INSTALLED),
            ))
            if direction is not AInTargetStateChangeDirection.UNCHANGED:
                if component_id in request_by_id:
                    causal.append(AIcSolverExplanation(
                        "REQUESTED_CHANGE",
                        f"requested {component_id}: {before.version} -> {after.version}",
                        component_id,
                    ))
                else:
                    reasons = self._why_required(component_id, target)
                    causal.extend(reasons or (AIcSolverExplanation(
                        "AUTOMATIC_CHANGE",
                        f"solver selected {component_id}/{after.version} inside the requested capability dependency closure",
                        component_id,
                    ),))
        entitlement_diagnostics = self._entitlement_diagnostics(target)
        readiness_diagnostics: list[AIcSolverReadinessDiagnostic] = []
        for component_id, candidate in target.items():
            if candidate.version == current[component_id].version:
                try:
                    report = self.core.lifecycle.component_readiness(application_scope_id, component_id)
                except Exception:
                    continue
                if report.state is not AInReadinessState.READY:
                    readiness_diagnostics.append(AIcSolverReadinessDiagnostic(
                        component_id, report.state, "current runtime readiness remains degraded in this target"
                    ))
        freshness_penalty = 0
        for component_id in closure:
            versions = sorted({item.version for item in universe.get(component_id, ())}, reverse=True)
            target_version = target[component_id].version
            if target_version in versions:
                freshness_penalty += versions.index(target_version)
        return AIcTargetStateSolution(
            tuple(selections), self._deduplicate_explanations(causal), entitlement_diagnostics,
            tuple(readiness_diagnostics), not contains_downgrade, contains_downgrade, freshness_penalty,
        )

    @staticmethod
    def _why_required(component_id: str, target: Mapping[str, AIcSolverCandidate]) -> tuple[AIcSolverExplanation, ...]:
        provider = target[component_id]
        result = []
        for consumer_id, consumer in target.items():
            if consumer_id == component_id:
                continue
            for requirement in consumer.requires:
                if requirement.mandatory and AIcCompatibleTargetStateSolver._candidate_provides(provider, requirement):
                    result.append(AIcSolverExplanation(
                        "CAPABILITY_DEPENDENCY",
                        f"{component_id}/{provider.version} supplies {requirement.capability_id} required by {consumer_id}/{consumer.version}",
                        component_id, consumer_id, requirement.capability_id,
                    ))
        return tuple(result)

    def _entitlement_diagnostics(self, target: Mapping[str, AIcSolverCandidate]) -> tuple[AIcSolverEntitlementDiagnostic, ...]:
        result = []
        for component_id, candidate in target.items():
            if not candidate.entitlements:
                continue
            descriptor = candidate.descriptor or self._entitlement_descriptor(candidate)
            try:
                context = self.core.entitlement.evaluate_component(
                    descriptor, licensing_scopes=self.core.active_licensing_scopes, context=self.core.application_context
                )
            except Exception:
                context = None
            info_url = candidate.catalog_entry.component.entitlement_info_url if candidate.catalog_entry else None
            for capability in candidate.entitlements:
                for permission in capability.permissions:
                    if not permission.possible_licensing_scope_types:
                        continue
                    granted = bool(context and context.has_permission(
                        capability.capability_id, capability.capability_version, permission.id
                    ))
                    if not granted:
                        result.append(AIcSolverEntitlementDiagnostic(
                            component_id, capability.capability_id, capability.capability_version, permission.id,
                            tuple(permission.possible_licensing_scope_types), False, info_url,
                        ))
        return tuple(result)

    @staticmethod
    def _entitlement_descriptor(candidate: AIcSolverCandidate) -> AIcComponentDescriptor:
        providers = tuple(
            AIcProviderDefinitionDescriptor(
                id=f"_solver_{index}", capability_id=capability_id, capability_versions=versions,
                implementation_class="_AAC.solver.placeholder",
            )
            for index, (capability_id, versions) in enumerate(candidate.provides)
        )
        return AIcComponentDescriptor(
            candidate.component_id, candidate.version, providers=providers,
            provided_capability_entitlements=candidate.entitlements,
            entitlement_licensing_scopes=candidate.entitlement_licensing_scopes,
        )

    @staticmethod
    def _solution_score(solution: AIcTargetStateSolution) -> tuple:
        # No-downgrade solutions are separated before scoring.  Within the causal closure,
        # prefer the freshest compatible branch; only then minimize the number of changes.
        changed_count = len(solution.changed)
        return solution.freshness_penalty, changed_count, tuple(
            (item.component_id, -item.target_version) for item in solution.selections
        )

    @staticmethod
    def _mark_recommended(solution: AIcTargetStateSolution, value: bool) -> AIcTargetStateSolution:
        return AIcTargetStateSolution(
            solution.selections, solution.explanations, solution.entitlement_diagnostics,
            solution.readiness_diagnostics, value, solution.contains_downgrade, solution.freshness_penalty,
        )

    @staticmethod
    def _deduplicate_explanations(values) -> tuple[AIcSolverExplanation, ...]:
        seen = set()
        result = []
        for value in values:
            key = (value.code, value.message, value.component_id, value.caused_by_component_id, value.capability_id)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return tuple(result)
