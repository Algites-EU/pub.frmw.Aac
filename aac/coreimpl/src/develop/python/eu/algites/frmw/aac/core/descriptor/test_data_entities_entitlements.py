import pytest

from eu.algites.frmw.aac.core.descriptor.api import AInDataEntityAccess
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader


def test_descriptor_declares_versioned_configuration_entitlement_and_data_entity_support():
    descriptor = AIcDescriptorLoader.load_text('''
Component:
  Id: vendor.foo
  Version: 2
  ComponentConfigurationSchema:
    Id: foo-component-config
    WriteVersion: 2
    ReadableVersions: [1, 2]
    Resource: foo-component-config_2.json
    Migrations:
      - From: 1
        To: 2
        Migrator: vendor.foo:migrate_component_config_1_to_2
  CapabilityProviders:
    - Id: main
      Capabilities:
        - Id: vendor.foo.document
          Versions: [1]
      ImplementationClasses:
      - TechnologyKind: python
        ProviderClassName: vendor.foo:Provider
      ConfigurationSchema:
        Id: foo-instance-config
        WriteVersion: 1
        ReadableVersions: [1]
        Resource: foo-instance-config_1.json
  EntitlementLicensingScopes:
    - Type: USER
      Name:
        Text: User
        ResourceKey: vendor.foo.licensing_scope.user.name
      Description:
        Text: One identified user.
        ResourceKey: vendor.foo.licensing_scope.user.description
    - Type: WORKSPACE
      Name:
        Text: Workspace
        ResourceKey: vendor.foo.licensing_scope.workspace.name
      Description:
        Text: One logical workspace.
        ResourceKey: vendor.foo.licensing_scope.workspace.description
  ProvidedCapabilityEntitlements:
    - Capability:
        Id: vendor.foo.document
        Version: 1
      Permissions:
        - Id: view
        - Id: edit
          PossibleLicensingScopes: [USER, WORKSPACE]
  DataEntitySupport:
    - SchemaId: vendor.foo.node-data
      ReadableVersions: [2, 3]
      WritableVersions: [2, 3]
      PreferredWriteVersion: 3
      Migrations:
        - From: 2
          To: 3
          Migrator: vendor.foo:migrate_node_data_2_to_3
      DataEntityRequirements:
        - SchemaId: _AO.NodeDefinition
          Access: [read]
          ReadableVersions: [4, 5]
          Required: true
        - SchemaId: vendor.inventory.Asset
          Access: [read, write]
          ReadableVersions: [1, 2]
          WritableVersions: [2]
          Required: false
''')
    assert descriptor.component_configuration_schema.schema_id == "foo-component-config"
    assert descriptor.component_configuration_schema.write_version == 2
    assert descriptor.component_configuration_schema.resource_name == "foo-component-config_2.json"
    assert [item.type for item in descriptor.entitlement_licensing_scopes] == ["USER", "WORKSPACE"]
    entitlement = descriptor.capability_entitlement("vendor.foo.document", 1)
    assert entitlement.permission("edit").possible_licensing_scope_types == ("USER", "WORKSPACE")

    support = descriptor.data_entity_support[0]
    assert support.schema_id == "vendor.foo.node-data"
    assert support.readable_versions == (2, 3)
    assert support.writable_versions == (2, 3)
    assert support.preferred_write_version == 3
    assert support.migrations[0].migrator_id == "vendor.foo:migrate_node_data_2_to_3"
    requirement = support.data_entity_requirements[0]
    assert requirement.schema_id == "_AO.NodeDefinition"
    assert requirement.access == (AInDataEntityAccess.READ,)
    assert requirement.readable_versions == (4, 5)
    assert requirement.required


def test_old_entity_extensions_descriptor_shape_is_rejected():
    with pytest.raises(Exception):
        AIcDescriptorLoader.load_text('''
Component:
  Id: vendor.foo
  Version: 1
  entity_extensions:
    - entity_type_id: _AO.NodeDefinition
      core_entity_access: [read]
''')
