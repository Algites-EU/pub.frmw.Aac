from algites.lib.aac.coreintf.descriptor import AInEntityExtensionDataAccess
from algites.lib.aac.coreimpl.descriptor import AIcDescriptorLoader


def test_descriptor_declares_versioned_configuration_entitlement_and_entity_extension():
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
  providers:
    - id: main
      capability:
        id: vendor.foo.document
        version: 1
      implementation_class: vendor.foo:Provider
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
  entity_extensions:
    - entity_type_id: _AO.NodeDefinition
      core_entity_access: [READ]
      extension_data:
        access: READ_WRITE
        component_extension_schema:
          id: vendor.foo.node-extension
          write_version: 3
          readable_versions: [2, 3]
          migrations:
            - from: 2
              to: 3
              migrator: vendor.foo:migrate_node_extension_2_to_3
        compatible_core_entity_schemas:
          - schema_id: _AO.NodeDefinition
            readable_versions: [4, 5]
      ui:
        contribution: true
''')
    assert descriptor.component_configuration_schema.schema_id == "foo-component-config"
    assert descriptor.component_configuration_schema.write_version == 2
    assert descriptor.component_configuration_schema.resource_name == "foo-component-config_2.json"
    assert [item.type for item in descriptor.entitlement_licensing_scopes] == ["USER", "WORKSPACE"]
    assert descriptor.entitlement_licensing_scopes[1].name.resource_key == "vendor.foo.licensing_scope.workspace.name"
    assert descriptor.entitlement_licensing_scopes[1].description.resource_key == "vendor.foo.licensing_scope.workspace.description"
    entitlement = descriptor.capability_entitlement("vendor.foo.document", 1)
    assert entitlement.permission("edit").possible_licensing_scope_types == ("USER", "WORKSPACE")
    extension = descriptor.entity_extensions[0]
    assert extension.entity_type_id == "_AO.NodeDefinition"
    assert extension.extension_data.access is AInEntityExtensionDataAccess.READ_WRITE
    assert extension.extension_data.component_extension_schema.schema_id == "vendor.foo.node-extension"
    assert extension.extension_data.component_extension_schema.write_version == 3
    assert extension.extension_data.supports_core_entity_schema("_AO.NodeDefinition", 5)
    assert not extension.extension_data.supports_core_entity_schema("_AO.NodeDefinition", 6)
