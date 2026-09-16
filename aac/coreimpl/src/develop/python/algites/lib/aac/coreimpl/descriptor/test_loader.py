from algites.lib.aac.coreintf.descriptor import AInProviderRuntimeProfile
from algites.lib.aac.coreimpl.descriptor import AIcDescriptorLoader


def test_loads_simpleaudit_descriptor_from_package():
    descriptor = AIcDescriptorLoader.load_package("algites.lib.aac.simpleaudit")
    assert descriptor.id == "_AAC.component.simpleaudit"
    assert descriptor.providers[0].capability_id == "_AAC.capability.observation"
    assert descriptor.providers[0].configuration_schema.resource_name == "simpleaudit-config_1.json"
    assert descriptor.providers[0].configuration_schema.schema_id == "simpleaudit-config"
    assert descriptor.providers[0].configuration_schema.write_version == 1
    assert descriptor.providers[0].runtime.profile is AInProviderRuntimeProfile.PROCESS


def test_provider_can_declare_multiple_supported_contract_versions():
    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x
  version: 1
  providers:
    - id: p
      capability:
        id: x.cap
        versions: [1, 3, 2]
      implementation_class: example:Provider
''')
    assert descriptor.providers[0].capability_versions == (1, 2, 3)


def test_provider_readiness_requirements_are_loaded():
    from algites.lib.aac.coreintf.readiness import AInReadinessRequirementSource, AInReadinessState

    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: x.ready
  version: 1
  providers:
    - id: p
      capability:
        id: x.cap
        version: 1
      implementation_class: example:Provider
      readiness_requirements:
        - id: endpoint
          source: COMPONENT_CONFIGURATION
          key: endpoint
          missing_state: DEGRADED
          message: endpoint is optional but recommended
''')
    requirement = descriptor.providers[0].readiness_requirements[0]
    assert requirement.source is AInReadinessRequirementSource.COMPONENT_CONFIGURATION
    assert requirement.missing_state is AInReadinessState.DEGRADED
    assert requirement.key == "endpoint"
