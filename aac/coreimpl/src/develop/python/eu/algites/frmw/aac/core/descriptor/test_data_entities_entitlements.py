import pytest

from eu.algites.frmw.aac.core.descriptor.api import AInDataEntityAccess
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader


def test_descriptor_declares_versioned_configuration_entitlement_and_data_entity_support():
    descriptor = AIcDescriptorLoader.load_text('''
component:
  id: vendor.foo
  version: 2
  component_configuration_schema:
    id: foo-component-config
    write_version: 2
    readable_versions: [1, 2]
    resource: foo-component-config_2.json
    migrations:
      - from: 1
        to: 2
        migrator: vendor.foo:migrate_component_config_1_to_2
  capability_providers:
    - id: main
      capabilities:
        - id: vendor.foo.document
          versions: [1]
      implementation_classes:
      - technology-kind: python
        class-name: vendor.foo:Provider
      configuration_schema:
        id: foo-instance-config
        write_version: 1
        readable_versions: [1]
        resource: foo-instance-config_1.json
  entitlement_licensing_scopes:
    - type: USER
      name:
        text: User
        resource_key: vendor.foo.licensing_scope.user.name
      description:
        text: One identified user.
        resource_key: vendor.foo.licensing_scope.user.description
    - type: WORKSPACE
      name:
        text: Workspace
        resource_key: vendor.foo.licensing_scope.workspace.name
      description:
        text: One logical workspace.
        resource_key: vendor.foo.licensing_scope.workspace.description
  provided_capability_entitlements:
    - capability:
        id: vendor.foo.document
        version: 1
      permissions:
        - id: view
        - id: edit
          possible_licensing_scopes: [USER, WORKSPACE]
  data_entity_support:
    - schema_id: vendor.foo.node-data
      readable_versions: [2, 3]
      writable_versions: [2, 3]
      preferred_write_version: 3
      migrations:
        - from: 2
          to: 3
          migrator: vendor.foo:migrate_node_data_2_to_3
      data_entity_requirements:
        - schema_id: _AO.NodeDefinition
          access: [READ]
          readable_versions: [4, 5]
          required: true
        - schema_id: vendor.inventory.Asset
          access: [READ, WRITE]
          readable_versions: [1, 2]
          writable_versions: [2]
          required: false
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
component:
  id: vendor.foo
  version: 1
  entity_extensions:
    - entity_type_id: _AO.NodeDefinition
      core_entity_access: [READ]
''')
