from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import (
    AIcComponentDescriptor,
    AIcConsumerRequirementDescriptor,
    AIcProviderDefinitionDescriptor,
)
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore, AIcInstalledComponent
from algites.lib.aac.coreimpl.descriptor import AIcDiscoveredComponent
from algites.lib.aac.uiqt.controller import AIcCoreUiController
from algites.lib.aac.uiintf import AIcUiObservationBinding, AIcUiObservationSelector


def test_simpleaudit_configuration_form_and_update():
    core = AIcApplicationComponentCore()
    core.install_aac_package("algites.lib.aac.simpleaudit")
    descriptor = core.installed("_AAC.component.simpleaudit").descriptor
    core.provisioning.provision("test", descriptor)
    controller = AIcCoreUiController(core)

    instance = controller.provider_instances()[0]
    form = controller.provider_configuration_form(instance.id)
    assert [field.id for field in form.fields] == ["output", "format"]
    assert form.fields[1].field_type.value == "ENUM"
    updated = controller.update_provider_configuration(instance.id, {"output": {"type": "STDOUT"}, "format": "TEXT"})
    assert core.instances.get(updated.id).configuration["format"] == "TEXT"


def test_requirements_include_unresolved_and_preference_uses_instance_ids():
    core = AIcApplicationComponentCore()
    provider_descriptor = AIcComponentDescriptor(
        "vendor.provider", 1,
        providers=(AIcProviderDefinitionDescriptor("p", "vendor.cap", (1,), "vendor:Provider"),),
    )
    consumer_descriptor = AIcComponentDescriptor(
        "vendor.consumer", 1,
        providers=(AIcProviderDefinitionDescriptor(
            "c", "vendor.consumer-cap", (1,), "vendor:Consumer",
            requirements=(AIcConsumerRequirementDescriptor(
                "target", "vendor.cap", (1,), AInConsumerCardinality.SINGLE, True,
            ),),
        ),),
    )
    core._installed[provider_descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(provider_descriptor, None, "test"))
    core._installed[consumer_descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(consumer_descriptor, None, "test"))
    p = core.instances.create(provider_descriptor.id, provider_descriptor.providers[0], name="provider")
    c = core.instances.create(consumer_descriptor.id, consumer_descriptor.providers[0], name="consumer")
    controller = AIcCoreUiController(core)

    requirements = controller.requirements()
    assert len(requirements) == 1
    assert requirements[0].selected_provider_instance_ids == ()
    editor = controller.requirement_editor(c.id, "target")
    assert [choice.value for choice in editor.provider_choices] == [p.id]
    controller.set_requirement_providers(c.id, "target", (p.id,))
    assert core.preferences.get(c.id, "target").provider_instance_ids == (p.id,)


def test_observation_topology_round_trip():
    core = AIcApplicationComponentCore()
    core.install_aac_package("algites.lib.aac.simpleaudit")
    descriptor = core.installed("_AAC.component.simpleaudit").descriptor
    core.provisioning.provision("test", descriptor)
    controller = AIcCoreUiController(core)
    observer = controller.provider_instances()[0]
    binding = AIcUiObservationBinding(observer.id, (AIcUiObservationSelector("vendor.*", (), (), ("PRE", "POST")),))
    controller.put_observation_binding(binding)
    assert controller.observation_bindings() == (binding,)
    controller.delete_observation_binding(observer.id)
    assert controller.observation_bindings() == ()


def test_create_provider_instance_can_start_unconfigured():
    core = AIcApplicationComponentCore()
    core.schemas.register("required-config_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"required_value": {"type": "string"}},
        "required": ["required_value"],
    })
    descriptor = AIcComponentDescriptor(
        "vendor.configurable", 1,
        providers=(AIcProviderDefinitionDescriptor(
            "p", "vendor.configurable-cap", (1,), "vendor:Provider",
            configuration_schema="required-config_1.json",
        ),),
    )
    core._installed[descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(descriptor, None, "test"))
    controller = AIcCoreUiController(core)
    created = controller.create_provider_instance(descriptor.id, "p", "new")
    assert created.state == "UNCONFIGURED"


def test_scoped_configuration_form_exposes_rw_provider_and_updates_it(tmp_path):
    from algites.lib.aac.coreimpl.bootstrap import AIcConfigurationBootstrapLoader

    core = AIcApplicationComponentCore()
    core.install_aac_package("algites.lib.aac.simpleaudit")
    descriptor = core.installed("_AAC.component.simpleaudit").descriptor
    core.provisioning.provision("test", descriptor)
    bootstrap = AIcConfigurationBootstrapLoader.load_text(f"""
configuration_bootstrap:
  schema_version: 1
  default_configuration_profile: p
  configuration_scope_resolvers:
    - id: mapping
      type: MAPPING
  configuration_providers:
    - id: workspace-file
      type: FILESYSTEM
      settings:
        root: {str(tmp_path)!r}
  configuration_profiles:
    - id: p
      version: 1
      configuration_scopes:
        - id: workspace
          type: WORKSPACE
          resolver: mapping
          configuration_providers:
            - id: workspace-file
              priority: 100
""")
    core.apply_configuration_bootstrap(bootstrap, context={"WORKSPACE": "w-1"})
    controller = AIcCoreUiController(core, {"configuration_admin": True})
    instance = controller.provider_instances()[0]
    form = controller.provider_configuration_form(instance.id)
    assert len(form.configuration_provider_options) == 1
    option = form.configuration_provider_options[0]
    assert option.can_write_value
    controller.update_provider_scoped_configuration(
        instance.id, option.configuration_scope.type, option.configuration_scope.id,
        option.configuration_provider_id,
        {"output": {"type": "STDOUT"}, "format": "TEXT"}, option.record_revision,
    )
    effective = core.resolve_provider_scoped_configuration(instance.id)
    assert effective.plain_values()["format"] == "TEXT"


def test_entitlement_status_exposes_effective_permission_metadata():
    from algites.lib.aac.coreintf.descriptor import AIcCapabilityEntitlementDescriptor, AIcPermissionDescriptor

    core = AIcApplicationComponentCore()
    descriptor = AIcComponentDescriptor(
        "vendor.entitled", 1,
        providers=(AIcProviderDefinitionDescriptor("p", "vendor.entitled.cap", (1,), "vendor:Provider"),),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "vendor.entitled.cap", 1,
            (AIcPermissionDescriptor("BASIC"),),
        ),),
    )
    core._installed[descriptor.id] = AIcInstalledComponent(AIcDiscoveredComponent(descriptor, None, "test"))
    status = AIcCoreUiController(core).entitlement_status(descriptor.id)
    assert len(status.permissions) == 1
    assert status.permissions[0].permission_id == "BASIC"
    assert status.permissions[0].implicit


def test_catalog_browse_download_install_ui_flow(tmp_path):
    import hashlib
    from zipfile import ZipFile

    from algites.lib.aac.coreintf.packages import AIcPackageStoreLayout
    from algites.lib.aac.coreintf.verification import AIcVerificationOutput, AIiPackageVerifier
    from algites.lib.aac.coreimpl.bootstrap import AIcCatalogBootstrapLoader

    class _Verifier(AIiPackageVerifier):
        def verify(self, verification_input):
            return AIcVerificationOutput(True, verifier_id="test", signer_identity="ui-catalog-test")

    wheel = tmp_path / "demo.whl"
    descriptor_path = "demo/component.yml"
    descriptor = '''component:
  id: com.example.ui-demo
  version: 2
  providers:
    - id: main
      capability:
        id: com.example.ui-cap
        versions: [1]
      implementation_class: demo:Provider
  entitlement_licensing_scopes:
    - type: USER
      name: User
      description: One identified user.
  provided_capability_entitlements:
    - capability:
        id: com.example.ui-cap
        version: 1
      permissions:
        - id: BASIC
        - id: PRO
          possible_licensing_scopes: [USER]
'''
    with ZipFile(wheel, "w") as archive:
        archive.writestr(descriptor_path, descriptor)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    catalog = tmp_path / "catalog.yml"
    catalog.write_text(f'''catalog:
  format_version: 4
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
  components:
    - component_id: com.example.ui-demo
      name: UI Demo
      description: Catalog UI test component
      entitlement_info_url: https://example.invalid/license
      releases:
        - version: 2
          provides:
            - capability: com.example.ui-cap
              versions: [1]
          entitlement_licensing_scopes:
            - type: USER
              name: User
              description: One identified user.
          provided_capability_entitlements:
            - capability:
                id: com.example.ui-cap
                version: 1
              permissions:
                - id: BASIC
                - id: PRO
                  possible_licensing_scopes: [USER]
          artifacts:
            - id: wheel
              locator:
                type: URI
                uri: {wheel.name}
              artifact_filename: demo.whl
              package_format: PYTHON_WHEEL
              descriptor_path: {descriptor_path}
              sha256: {digest}
              runtime_package: demo
              verifier_id: test
''', encoding="utf-8")

    core = AIcApplicationComponentCore()
    core.configure_package_management(AIcPackageStoreLayout(str(tmp_path / "product")))
    core.register_package_verifier("test", _Verifier())
    core.apply_catalog_bootstrap(AIcCatalogBootstrapLoader.load_text(f'''catalog_bootstrap:
  schema_version: 1
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
  sources:
    - id: local
      type: FILESYSTEM
      uri: {catalog}
'''))
    current_descriptor = AIcComponentDescriptor(
        "com.example.ui-demo", 1,
        providers=(AIcProviderDefinitionDescriptor("main", "com.example.ui-cap", (1,), "demo:Provider"),),
    )
    core._installed[current_descriptor.id] = AIcInstalledComponent(
        AIcDiscoveredComponent(current_descriptor, None, "test")
    )
    controller = AIcCoreUiController(core)

    assert controller.catalog_defaults() == ("eu.algites.app.orchestrator", "PYTHON")
    (item,) = controller.catalog_packages("eu.algites.app.orchestrator", "PYTHON", "UI Demo")
    assert item.name == "UI Demo"
    assert item.entitlement_summary == (
        "com.example.ui-cap/1:BASIC [included]",
        "com.example.ui-cap/1:PRO [User]",
    )
    assert not item.downloaded and not item.installed

    solver_result = controller.solve_catalog_target("default", item.identity)
    assert solver_result.primary is not None
    assert [(entry.component_id, entry.current_version, entry.target_version) for entry in solver_result.primary.changed] == [
        ("com.example.ui-demo", 1, 2)
    ]
    assert not solver_result.primary.contains_downgrade

    downloaded = controller.download_catalog_package(item.identity)
    assert downloaded.state == "DOWNLOADED"
    refreshed = controller.catalog_packages("eu.algites.app.orchestrator", "PYTHON", "UI Demo")[0]
    assert refreshed.downloaded and not refreshed.installed

    installed = controller.install_catalog_package(item.identity)
    assert installed.state == "INSTALLED"
    refreshed = controller.catalog_packages("eu.algites.app.orchestrator", "PYTHON", "UI Demo")[0]
    assert refreshed.downloaded and refreshed.installed
