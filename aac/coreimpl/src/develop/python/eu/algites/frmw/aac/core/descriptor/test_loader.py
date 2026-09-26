import pytest

from eu.algites.frmw.aac.core.descriptor.api import AInProviderRuntimeProfile
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader


def test_loads_simpleaudit_descriptor_from_package():
    descriptor = AIcDescriptorLoader.load_package("eu.algites.frmw.aac.observation.simpleaudit")
    assert descriptor.id == "_AAC.component.simpleaudit"
    assert descriptor.capability_providers[0].capabilities[0].id == "_AAC.capability.observation"
    assert descriptor.capability_providers[0].configuration_schema.resource_name == "simpleaudit-config_1.json"
    assert descriptor.capability_providers[0].configuration_schema.schema_id == "simpleaudit-config"
    assert descriptor.capability_providers[0].configuration_schema.write_version == 1
    assert descriptor.capability_providers[0].runtime.profile is AInProviderRuntimeProfile.PROCESS


def test_provider_can_declare_multiple_supported_contract_versions():
    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: x
  Version: 1
  CapabilityProviders:
    - Id: p
      Capabilities:
        - Id: x.cap
          Versions: [1, 3, 2]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: example:Provider
''')
    assert descriptor.capability_providers[0].capability("x.cap").versions == (1, 2, 3)


def test_provider_readiness_requirements_are_loaded():
    from eu.algites.frmw.aac.core.readiness.api import AInReadinessRequirementSource, AInReadinessState

    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: x.ready
  Version: 1
  CapabilityProviders:
    - Id: p
      Capabilities:
        - Id: x.cap
          Versions: [1]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: example:Provider
      ReadinessRequirements:
        - Id: endpoint
          Source: component_configuration
          Key: endpoint
          MissingState: degraded
          Message: endpoint is optional but recommended
''')
    requirement = descriptor.capability_providers[0].readiness_requirements[0]
    assert requirement.source is AInReadinessRequirementSource.COMPONENT_CONFIGURATION
    assert requirement.missing_state is AInReadinessState.DEGRADED
    assert requirement.key == "endpoint"


def test_component_can_declare_capability_group_resources():
    descriptor = AIcDescriptorLoader.load_text("""
Component:
  Id: x.groups
  Version: 1
  CapabilityGroups:
    - groups/storage.yml
  Capability:
    - capability/storage.yml
""")
    assert descriptor.capability_group_resources == ("groups/storage.yml",)
    assert descriptor.contract_resources == ("capability/storage.yml",)


def test_provider_definition_declares_multiple_capabilities_and_instance_access_mode():
    from eu.algites.frmw.aac.core.instances.api import AInProviderAccessMode

    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: x.multi
  Version: 1
  CapabilityProviders:
    - Id: store
      Capabilities:
        - Id: x.read
          Versions: [1, 2]
        - Id: x.write
          Versions: [1]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: example:Store
      InitialInstances:
        - Name: external
          AccessMode: read_only
''')
    provider = descriptor.capability_providers[0]
    assert tuple(item.id for item in provider.capabilities) == ("x.read", "x.write")
    assert provider.capability("x.read").versions == (1, 2)
    assert provider.initial_instances[0].access_mode is AInProviderAccessMode.READ_ONLY


def test_legacy_providers_key_is_rejected():
    with pytest.raises(AIxDescriptorError):
        AIcDescriptorLoader.load_text('''
Component:
  Id: x.legacy
  Version: 1
  providers:
    - Id: p
      Capabilities:
        - Id: x.cap
          Versions: [1]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: example:Provider
''')


def test_provider_operation_parameter_definitions_are_loaded_with_display_text_and_scopes():
    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: x.operation-parameters
  Version: 3
  CapabilityProviders:
    - Id: git
      Capabilities:
        - Id: x.sync
          Versions: [1]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: example:GitProvider
      Operations:
        - Capability: x.sync
          CapabilityVersion: 1
          Operation: pull
          Interaction:
            SupportedStateResultDeliveryModes: [on_demand_complete]
          Parameters:
            - Id: integration_strategy
              Name:
                Text: Integration strategy
                ResourceKey: x.integrationStrategy.name
              Description:
                Text: How retrieved revisions are integrated.
                ResourceKey: x.integrationStrategy.description
              ValueSchema:
                Type: string
                enum: [MERGE, REBASE]
              EnumValues:
                - Value: MERGE
                  Name:
                    Text: Merge
                  Description:
                    Text: Merge histories.
                - Value: REBASE
                  Name:
                    Text: Rebase
                  Description:
                    Text: Reapply local revisions.
              Default: MERGE
              ComponentConfigurable: true
              InstanceConfigurable: true
              InvocationOverridable: true
''')
    provider = descriptor.capability_providers[0]
    operation = provider.operation_parameter_definition("x.sync", 1, "pull")
    assert operation is not None
    parameter = operation.parameter("integration_strategy")
    assert parameter.name.text == "Integration strategy"
    assert parameter.name.resource_key == "x.integrationStrategy.name"
    assert parameter.description.resource_key == "x.integrationStrategy.description"
    assert parameter.enum_values[0].description.text == "Merge histories."
    assert parameter.has_default and parameter.default == "MERGE"
    assert parameter.component_configurable
    assert parameter.instance_configurable
    assert parameter.invocation_overridable


def test_provider_can_select_implementation_class_by_technology_kind():
    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: x.multitech
  Version: 1
  CapabilityProviders:
    - Id: p
      Capabilities:
        - Id: x.cap
          Versions: [1]
      ImplementationClasses:
        - TechnologyKind: python
          ClassName: example.python:Provider
        - TechnologyKind: java
          ClassName: eu.example.Provider
''')
    provider = descriptor.capability_providers[0]
    assert provider.implementation_class_for("python") == "example.python:Provider"
    assert provider.implementation_class_for("java") == "eu.example.Provider"
    with pytest.raises(KeyError):
        provider.implementation_class_for("mps")
