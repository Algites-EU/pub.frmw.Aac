import pytest

from algites.lib.aac.coreintf.descriptor import AInProviderRuntimeProfile
from algites.lib.aac.coreintf.errors import AIxDescriptorError
from algites.lib.aac.coreimpl.descriptor import AIcDescriptorLoader


def test_loads_simpleaudit_descriptor_from_package():
    descriptor = AIcDescriptorLoader.load_package("algites.lib.aac.simpleaudit")
    assert descriptor.id == "_AAC.component.simpleaudit"
    assert descriptor.capability_providers[0].capabilities[0].id == "_AAC.capability.observation"
    assert descriptor.capability_providers[0].configuration_schema.resource_name == "simpleaudit-config_1.json"
    assert descriptor.capability_providers[0].configuration_schema.schema_id == "simpleaudit-config"
    assert descriptor.capability_providers[0].configuration_schema.write_version == 1
    assert descriptor.capability_providers[0].runtime.profile is AInProviderRuntimeProfile.PROCESS


def test_provider_can_declare_multiple_supported_contract_versions():
    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x
  version: 1
  capability_providers:
    - id: p
      capabilities:
        - id: x.cap
          versions: [1, 3, 2]
      implementation_class: example:Provider
''')
    assert descriptor.capability_providers[0].capability("x.cap").versions == (1, 2, 3)


def test_provider_readiness_requirements_are_loaded():
    from algites.lib.aac.coreintf.readiness import AInReadinessRequirementSource, AInReadinessState

    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x.ready
  version: 1
  capability_providers:
    - id: p
      capabilities:
        - id: x.cap
          versions: [1]
      implementation_class: example:Provider
      readiness_requirements:
        - id: endpoint
          source: COMPONENT_CONFIGURATION
          key: endpoint
          missing_state: DEGRADED
          message: endpoint is optional but recommended
''')
    requirement = descriptor.capability_providers[0].readiness_requirements[0]
    assert requirement.source is AInReadinessRequirementSource.COMPONENT_CONFIGURATION
    assert requirement.missing_state is AInReadinessState.DEGRADED
    assert requirement.key == "endpoint"


def test_component_can_declare_capability_group_resources():
    descriptor = AIcDescriptorLoader.load_text("""
component:
  id: x.groups
  version: 1
  capability_groups:
    - groups/storage.yml
  contracts:
    - contracts/storage.yml
""")
    assert descriptor.capability_group_resources == ("groups/storage.yml",)
    assert descriptor.contract_resources == ("contracts/storage.yml",)


def test_provider_definition_declares_multiple_capabilities_and_instance_access_mode():
    from algites.lib.aac.coreintf.instances import AInProviderAccessMode

    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x.multi
  version: 1
  capability_providers:
    - id: store
      capabilities:
        - id: x.read
          versions: [1, 2]
        - id: x.write
          versions: [1]
      implementation_class: example:Store
      initial_instances:
        - name: external
          access_mode: READ_ONLY
''')
    provider = descriptor.capability_providers[0]
    assert tuple(item.id for item in provider.capabilities) == ("x.read", "x.write")
    assert provider.capability("x.read").versions == (1, 2)
    assert provider.initial_instances[0].access_mode is AInProviderAccessMode.READ_ONLY


def test_legacy_providers_key_is_rejected():
    with pytest.raises(AIxDescriptorError):
        AIcDescriptorLoader.load_text('''
component:
  id: x.legacy
  version: 1
  providers:
    - id: p
      capabilities:
        - id: x.cap
          versions: [1]
      implementation_class: example:Provider
''')


def test_provider_operation_parameter_definitions_are_loaded_with_display_text_and_scopes():
    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x.operation-parameters
  version: 3
  capability_providers:
    - id: git
      capabilities:
        - id: x.sync
          versions: [1]
      implementation_class: example:GitProvider
      operations:
        - capability: x.sync
          capability_version: 1
          operation: pull
          interaction:
            supported_state_result_delivery_modes: [ON_DEMAND_COMPLETE]
          parameters:
            - id: integration_strategy
              name:
                text: Integration strategy
                resource_key: x.integrationStrategy.name
              description:
                text: How retrieved revisions are integrated.
                resource_key: x.integrationStrategy.description
              value_schema:
                type: string
                enum: [MERGE, REBASE]
              enum_values:
                - value: MERGE
                  name:
                    text: Merge
                  description:
                    text: Merge histories.
                - value: REBASE
                  name:
                    text: Rebase
                  description:
                    text: Reapply local revisions.
              default: MERGE
              component_configurable: true
              instance_configurable: true
              invocation_overridable: true
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
