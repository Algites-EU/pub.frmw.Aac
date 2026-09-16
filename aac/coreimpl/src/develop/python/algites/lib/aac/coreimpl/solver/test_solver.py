from __future__ import annotations

from algites.lib.aac.coreintf.catalog import (
    AIcCatalogArtifact, AIcCatalogArtifactLocator, AIcCatalogCapabilityOffer,
    AIcCatalogCapabilityRequirement, AIcCatalogComponent, AIcCatalogDocument,
    AIcCatalogPersistentSchema, AIcCatalogRelease, AInCatalogPersistentSchemaKind,
)
from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import (
    AIcComponentDescriptor, AIcConsumerRequirementDescriptor, AIcPersistedSchemaDescriptor,
    AIcProviderDefinitionDescriptor,
)
from algites.lib.aac.coreintf.solver import AIcTargetStateRequest
from algites.lib.aac.coreimpl.catalog import AIcStaticCatalogProvider
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore, AIcInstalledComponent
from algites.lib.aac.coreimpl.descriptor import AIcDiscoveredComponent


def _descriptor(component_id: str, version: int, *, capability: str, capability_version: int,
                requirement: tuple[str, int] | None = None, schema_version: int | None = None):
    requirements = ()
    if requirement is not None:
        requirements = (AIcConsumerRequirementDescriptor(
            "dependency", requirement[0], (requirement[1],), AInConsumerCardinality.SINGLE, True
        ),)
    schema = None
    if schema_version is not None:
        schema = AIcPersistedSchemaDescriptor(
            f"{component_id}.config", schema_version, (schema_version,), resource_name=f"config_{schema_version}.json"
        )
    provider = AIcProviderDefinitionDescriptor(
        "main", capability, (capability_version,), "example.Provider",
        requirements=requirements,
    )
    return AIcComponentDescriptor(component_id, version, providers=(provider,), component_configuration_schema=schema)


def _release(version: int, *, capability: str, capability_version: int,
             requirement: tuple[str, int] | None = None, schema_version: int | None = None):
    requires = ()
    if requirement is not None:
        requires = (AIcCatalogCapabilityRequirement(
            "dependency", requirement[0], (requirement[1],), AInConsumerCardinality.SINGLE, True
        ),)
    schemas = ()
    if schema_version is not None:
        schemas = (AIcCatalogPersistentSchema(
            AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION,
            "schema", schema_version,
        ),)
    digest = (f"{version:064x}")[-64:]
    return AIcCatalogRelease(
        version,
        provides=(AIcCatalogCapabilityOffer(capability, (capability_version,)),),
        requires=requires,
        persistent_schemas=schemas,
        artifacts=(AIcCatalogArtifact(
            "wheel", AIcCatalogArtifactLocator("URI", f"file:///v{version}.whl"),
            f"v{version}.whl", "PYTHON_WHEEL", "pkg/component.yml", digest, runtime_package="pkg",
        ),),
    )


def _core_with_graph():
    core = AIcApplicationComponentCore()
    current = (
        _descriptor("A", 1, capability="a", capability_version=1, requirement=("x", 1)),
        _descriptor("B", 2, capability="x", capability_version=1),
        _descriptor("C", 7, capability="y", capability_version=1),
    )
    for descriptor in current:
        discovered = AIcDiscoveredComponent(descriptor, "pkg", f"{descriptor.id}:component.yml")
        core._installed[descriptor.id] = AIcInstalledComponent(discovered)
    document = AIcCatalogDocument(
        2, "eu.algites.app.orchestrator", "PYTHON",
        (
            AIcCatalogComponent("A", (
                _release(1, capability="a", capability_version=1, requirement=("x", 1)),
                _release(4, capability="a", capability_version=1, requirement=("x", 2)),
            )),
            AIcCatalogComponent("B", (
                _release(2, capability="x", capability_version=1),
                _release(3, capability="x", capability_version=2),
                _release(5, capability="x", capability_version=2, requirement=("y", 2)),
            )),
            AIcCatalogComponent("C", (
                _release(7, capability="y", capability_version=1),
                _release(8, capability="y", capability_version=2),
            )),
        ),
    )
    core.catalog_product_id = document.product_id
    core.catalog_technology_id = document.technology_id
    core.register_catalog_provider("test", AIcStaticCatalogProvider("test", document))
    return core


def test_solver_prefers_freshest_compatible_dependency_branch_not_minimum_change_count():
    core = _core_with_graph()
    result = core.solve_compatible_target_state("app", (AIcTargetStateRequest.exact("A", 4),))
    assert result.primary is not None
    targets = {item.component_id: item.target_version for item in result.primary.selections}
    assert targets == {"A": 4, "B": 5, "C": 8}
    assert any(item.component_id == "B" and not item.requested for item in result.primary.changed)
    alternatives = [
        {item.component_id: item.target_version for item in solution.selections}
        for solution in result.alternatives
    ]
    assert {"A": 4, "B": 3, "C": 7} in alternatives
    # C/8 is not retained as an unrelated change in the B/3 branch.
    assert {"A": 4, "B": 3, "C": 8} not in alternatives


def test_solver_only_offers_schema_neutral_downgrade_as_nonrecommended_alternative():
    core = AIcApplicationComponentCore()
    current = _descriptor("A", 2, capability="a", capability_version=1, requirement=("x", 1), schema_version=3)
    provider = _descriptor("B", 4, capability="x", capability_version=1, schema_version=5)
    for descriptor in (current, provider):
        core._installed[descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(descriptor, "pkg", "component.yml"))
    # A/3 requires X/2, but only B/3 can provide it.  B/3 has the same persistence schema as B/4.
    document = AIcCatalogDocument(2, "eu.algites.app.orchestrator", "PYTHON", (
        AIcCatalogComponent("A", (
            AIcCatalogRelease(2, provides=(AIcCatalogCapabilityOffer("a", (1,)),),
                              requires=(AIcCatalogCapabilityRequirement("dependency", "x", (1,), mandatory=True),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "A.config", 3),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///a2.whl"), "a2.whl", "PYTHON_WHEEL", "pkg/component.yml", "1"*64),)),
            AIcCatalogRelease(3, provides=(AIcCatalogCapabilityOffer("a", (1,)),),
                              requires=(AIcCatalogCapabilityRequirement("dependency", "x", (2,), mandatory=True),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "A.config", 3),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///a3.whl"), "a3.whl", "PYTHON_WHEEL", "pkg/component.yml", "2"*64),)),
        )),
        AIcCatalogComponent("B", (
            AIcCatalogRelease(3, provides=(AIcCatalogCapabilityOffer("x", (2,)),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "B.config", 5),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///b3.whl"), "b3.whl", "PYTHON_WHEEL", "pkg/component.yml", "3"*64),)),
            AIcCatalogRelease(4, provides=(AIcCatalogCapabilityOffer("x", (1,)),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "B.config", 5),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///b4.whl"), "b4.whl", "PYTHON_WHEEL", "pkg/component.yml", "4"*64),)),
        )),
    ))
    core.catalog_product_id = document.product_id; core.catalog_technology_id = document.technology_id
    core.register_catalog_provider("test", AIcStaticCatalogProvider("test", document))
    result = core.solve_compatible_target_state("app", (AIcTargetStateRequest.exact("A", 3),))
    assert result.primary is None
    assert result.alternatives and result.alternatives[0].contains_downgrade
    targets = {item.component_id: item.target_version for item in result.alternatives[0].selections}
    assert targets == {"A": 3, "B": 3}
    assert any(item.code == "DOWNGRADE_ONLY" for item in result.diagnostics)


def test_solver_rejects_downgrade_when_persistent_schema_generation_differs():
    core = AIcApplicationComponentCore()
    current_a = _descriptor("A", 2, capability="a", capability_version=1, requirement=("x", 1))
    current_b = _descriptor("B", 4, capability="x", capability_version=1, schema_version=6)
    for descriptor in (current_a, current_b):
        core._installed[descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(descriptor, "pkg", "component.yml"))
    document = AIcCatalogDocument(2, "eu.algites.app.orchestrator", "PYTHON", (
        AIcCatalogComponent("A", (
            _release(3, capability="a", capability_version=1, requirement=("x", 2)),
        )),
        AIcCatalogComponent("B", (
            AIcCatalogRelease(3, provides=(AIcCatalogCapabilityOffer("x", (2,)),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "B.config", 5),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///b3.whl"), "b3.whl", "PYTHON_WHEEL", "pkg/component.yml", "5"*64),)),
            AIcCatalogRelease(4, provides=(AIcCatalogCapabilityOffer("x", (1,)),),
                              persistent_schemas=(AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "B.config", 6),),
                              artifacts=(AIcCatalogArtifact("wheel", AIcCatalogArtifactLocator("URI", "file:///b4.whl"), "b4.whl", "PYTHON_WHEEL", "pkg/component.yml", "6"*64),)),
        )),
    ))
    core.catalog_product_id = document.product_id; core.catalog_technology_id = document.technology_id
    core.register_catalog_provider("test", AIcStaticCatalogProvider("test", document))
    result = core.solve_compatible_target_state("app", (AIcTargetStateRequest.exact("A", 3),))
    assert result.primary is None and not result.alternatives
    assert any(item.code in {"DOWNGRADE_SCHEMA_INCOMPATIBLE", "NO_SOLUTION"} for item in result.diagnostics)
