from __future__ import annotations

import sys
from pathlib import Path
from importlib import resources

import pytest

from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore
from algites.lib.aac.coreimpl.errors import AIxUpgradeError


def _write_candidate(root: Path, package: str, *, version: int, broken: bool = False) -> None:
    pkg = root / package
    (pkg / "schemas").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "provider.py").write_text(
        "from algites.lib.aac.coreintf.runtime import AIiProviderRuntime\n"
        "from algites.lib.aac.coreintf.observation import AIiObservationProvider, AIcObservationOutput\n"
        "class AIcCandidateObserver(AIiProviderRuntime, AIiObservationProvider):\n"
        "    def __init__(self, configuration): self.configuration = configuration\n"
        "    def observe(self, observation_input): return AIcObservationOutput(accepted=True)\n",
        encoding="utf-8",
    )
    schema_text = resources.files("algites.lib.aac.simpleaudit").joinpath("schemas/simpleaudit-config_1.json").read_text(encoding="utf-8")
    (pkg / "schemas" / "simpleaudit-config_1.json").write_text(schema_text, encoding="utf-8")
    impl = f"{package}.missing:Nope" if broken else f"{package}.provider:AIcCandidateObserver"
    (pkg / "component.yml").write_text(
        f'''component:\n  id: _AAC.component.simpleaudit\n  version: {version}\n  providers:\n    - id: observation\n      capability:\n        id: _AAC.capability.observation\n        version: 1\n      implementation_class: {impl}\n      configuration_schema:\n        id: simpleaudit-config\n        write_version: 1\n        readable_versions: [1]\n        resource: simpleaudit-config_1.json\n      initial_instances:\n        - name: default\n          configuration: {{}}\n''',
        encoding="utf-8",
    )


def test_hot_upgrade_preserves_provider_instance_id(tmp_path: Path):
    _write_candidate(tmp_path, "candidate_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_aac_package("algites.lib.aac.simpleaudit")
        core.activate_application("app")
        before = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
        outcome = core.upgrade_aac_package("app", "candidate_v2")
        after = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
        assert outcome.previous_version == 1
        assert outcome.current_version == 2
        assert before.id == after.id
        assert core.installed("_AAC.component.simpleaudit").descriptor.version == 2
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("candidate_v2", None)
        sys.modules.pop("candidate_v2.provider", None)


def test_failed_upgrade_rolls_back_descriptor_and_runtime(tmp_path: Path):
    _write_candidate(tmp_path, "candidate_bad", version=2, broken=True)
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_aac_package("algites.lib.aac.simpleaudit")
        core.activate_application("app")
        before = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
        with pytest.raises(AIxUpgradeError, match="rolled back"):
            core.upgrade_aac_package("app", "candidate_bad")
        after = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
        assert core.installed("_AAC.component.simpleaudit").descriptor.version == 1
        assert before.id == after.id
        assert core.lifecycle.runtime(after.id) is not None
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("candidate_bad", None)


def _write_graph_component(root: Path, package: str, *, component_id: str, version: int,
                           provided_capability: str, provided_version: int,
                           requirement_version: int | None = None,
                           contract_version: int | None = None) -> None:
    pkg = root / package
    (pkg / "contracts").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "provider.py").write_text(
        "from algites.lib.aac.coreintf.runtime import AIiProviderRuntime\n"
        "class Provider(AIiProviderRuntime):\n"
        "    def __init__(self, configuration): pass\n",
        encoding="utf-8",
    )
    contracts = ""
    if contract_version is not None:
        (pkg / "contracts" / f"x_{contract_version}.yml").write_text(
            f"capability:\n  id: com.example.x\n  version: {contract_version}\n"
            "operations:\n  - id: ping\n    input: Object\n    output: Object\n",
            encoding="utf-8",
        )
        contracts = f"  contracts:\n    - contracts/x_{contract_version}.yml\n"
    requirement = ""
    if requirement_version is not None:
        requirement = (
            "      requirements:\n"
            "        - id: x\n"
            "          capability: com.example.x\n"
            f"          versions: [{requirement_version}]\n"
            "          mandatory: true\n"
        )
    (pkg / "component.yml").write_text(
        f"component:\n  id: {component_id}\n  version: {version}\n"
        + contracts
        + "  providers:\n"
          "    - id: main\n"
        + f"      capability:\n        id: {provided_capability}\n        version: {provided_version}\n"
          f"      implementation_class: {package}.provider:Provider\n"
        + requirement
        + "      initial_instances:\n        - name: default\n          configuration: {}\n",
        encoding="utf-8",
    )


def test_multi_component_target_state_can_be_valid_when_each_single_upgrade_is_not(tmp_path: Path):
    _write_graph_component(
        tmp_path, "consumer_v1", component_id="com.example.consumer", version=1,
        provided_capability="com.example.consumer-host", provided_version=1,
        requirement_version=1, contract_version=1,
    )
    _write_graph_component(
        tmp_path, "provider_v1", component_id="com.example.provider", version=1,
        provided_capability="com.example.x", provided_version=1,
    )
    _write_graph_component(
        tmp_path, "consumer_v2", component_id="com.example.consumer", version=2,
        provided_capability="com.example.consumer-host", provided_version=1,
        requirement_version=2, contract_version=2,
    )
    _write_graph_component(
        tmp_path, "provider_v2", component_id="com.example.provider", version=2,
        provided_capability="com.example.x", provided_version=2,
    )
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("consumer_v1")
        core.install_python_package("provider_v1")
        core.activate_application("app")

        single = core.plan_python_package_upgrades("app", ("consumer_v2",))
        assert not single.compatible
        assert any(item.component_id == "com.example.consumer" and item.capability_id == "com.example.x" for item in single.diagnostics)

        pair = core.plan_python_package_upgrades("app", ("consumer_v2", "provider_v2"))
        assert pair.compatible
        outcome = core.upgrade_python_packages("app", ("consumer_v2", "provider_v2"))
        assert {item.component_id for item in outcome.replacements} == {"com.example.consumer", "com.example.provider"}
        assert core.installed("com.example.consumer").descriptor.version == 2
        assert core.installed("com.example.provider").descriptor.version == 2
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("consumer_v1", "provider_v1", "consumer_v2", "provider_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)


def _write_migrating_component(root: Path, package: str, *, version: int, broken: bool = False) -> None:
    pkg = root / package
    (pkg / "schemas").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "provider.py").write_text(
        "from algites.lib.aac.coreintf.runtime import AIiProviderRuntime\n"
        "from algites.lib.aac.coreintf.observation import AIiObservationProvider, AIcObservationOutput\n"
        "class Provider(AIiProviderRuntime, AIiObservationProvider):\n"
        "    def __init__(self, configuration): pass\n"
        "    def observe(self, observation_input): return AIcObservationOutput(accepted=True)\n",
        encoding="utf-8",
    )
    if version == 1:
        (pkg / "schemas" / "upgrade-component-config_1.json").write_text(
            '{"x-aac-schema-id":"upgrade-component-config","x-aac-schema-version":1,'
            '"type":"object","properties":{"old_name":{"type":"string"}},"required":["old_name"]}',
            encoding="utf-8",
        )
        (pkg / "schemas" / "upgrade-data_1.json").write_text(
            '{"x-aac-schema-id":"upgrade-data","x-aac-schema-version":1,'
            '"type":"object","properties":{"old_name":{"type":"string"}},"required":["old_name"]}',
            encoding="utf-8",
        )
        config = """  component_configuration_schema:\n    id: upgrade-component-config\n    write_version: 1\n    readable_versions: [1]\n    resource: upgrade-component-config_1.json\n"""
        data_entity_support = """  data_entity_support:\n    - schema_id: upgrade-data\n      readable_versions: [1]\n      writable_versions: [1]\n      preferred_write_version: 1\n"""
    else:
        (pkg / "schemas" / "upgrade-component-config_2.json").write_text(
            '{"x-aac-schema-id":"upgrade-component-config","x-aac-schema-version":2,'
            '"type":"object","properties":{"new_name":{"type":"string"}},"required":["new_name"]}',
            encoding="utf-8",
        )
        (pkg / "schemas" / "upgrade-data_2.json").write_text(
            '{"x-aac-schema-id":"upgrade-data","x-aac-schema-version":2,'
            '"type":"object","properties":{"new_name":{"type":"string"}},"required":["new_name"]}',
            encoding="utf-8",
        )
        config = """  component_configuration_schema:\n    id: upgrade-component-config\n    write_version: 2\n    readable_versions: [2]\n    resource: upgrade-component-config_2.json\n    migrations:\n      - from: 1\n        to: 2\n        migrator: cfg-1-to-2\n"""
        data_entity_support = """  data_entity_support:\n    - schema_id: upgrade-data\n      readable_versions: [1, 2]\n      writable_versions: [1, 2]\n      preferred_write_version: 2\n      migrations:\n        - from: 1\n          to: 2\n          migrator: data-1-to-2\n"""
    implementation = f"{package}.missing:Nope" if broken else f"{package}.provider:Provider"
    (pkg / "component.yml").write_text(
        "component:\n"
        "  id: com.example.migrating\n"
        f"  version: {version}\n"
        + config
        + "  providers:\n"
          "    - id: main\n"
          "      capability:\n"
          "        id: _AAC.capability.observation\n"
          "        version: 1\n"
        + f"      implementation_class: {implementation}\n"
          "      initial_instances:\n"
          "        - name: default\n"
          "          configuration: {}\n"
        + data_entity_support,
        encoding="utf-8",
    )


def _prepare_migrating_core(tmp_path: Path):
    from algites.lib.aac.coreintf.configuration import (
        AIcConfigurationMigrationResult, AIcConfigurationPersistedPayload,
        AIcConfigurationProviderBinding, AIcConfigurationProviderRequest,
        AIcConfigurationTarget, AInConfigurationTargetKind, AIcResolvedConfigurationScope,
        AIiConfigurationMigrator,
    )
    from algites.lib.aac.coreintf.context import AIcConfigurationScope
    from algites.lib.aac.coreimpl.configuration_providers import AIcFileSystemConfigurationProvider

    class ConfigMigrator(AIiConfigurationMigrator):
        def migrate(self, request):
            return AIcConfigurationMigrationResult(
                "upgrade-component-config", 2, {"new_name": request.source.values["old_name"]}
            )

    core = AIcApplicationComponentCore()
    core.install_python_package("migrating_v1", trusted_namespace_prefixes=("_AAC.",))
    core.activate_application("app")

    provider = AIcFileSystemConfigurationProvider(tmp_path / "config")
    core.register_configuration_provider("fs", provider)
    scope = AIcConfigurationScope("WORKSPACE", "w-1")
    core.active_configuration_scopes = (
        AIcResolvedConfigurationScope(
            "workspace", scope, (AIcConfigurationProviderBinding("fs"),), True
        ),
    )
    target = AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, "com.example.migrating")
    request = AIcConfigurationProviderRequest(target, scope)
    provider.replace_payload(
        request,
        AIcConfigurationPersistedPayload(
            target, "upgrade-component-config", 1, 1, {"old_name": "configuration"}
        ),
    )
    core.configuration_migrations.register("cfg-1-to-2", ConfigMigrator())
    return core, provider, request


def test_upgrade_converges_configuration_and_admits_data_entity_support_after_cutover(tmp_path: Path):
    _write_migrating_component(tmp_path, "migrating_v1", version=1)
    _write_migrating_component(tmp_path, "migrating_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core, provider, request = _prepare_migrating_core(tmp_path)
        plan = core.plan_python_package_upgrades("app", ("migrating_v2",))
        assert plan.compatible
        core.upgrade_python_packages("app", ("migrating_v2",), trusted_namespace_prefixes=("_AAC.",))
        config = provider.snapshot(request)
        assert config.payload.configuration_schema_version == 2
        assert config.payload.values == {"new_name": "configuration"}
        (support,) = core.installed("com.example.migrating").descriptor.data_entity_support
        assert support.schema_id == "upgrade-data"
        assert support.readable_versions == (1, 2)
        assert support.preferred_write_version == 2
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("migrating_v1", "migrating_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)


def test_failed_upgrade_leaves_persisted_configuration_untouched(tmp_path: Path):
    _write_migrating_component(tmp_path, "migrating_v1", version=1)
    _write_migrating_component(tmp_path, "migrating_bad_v2", version=2, broken=True)
    sys.path.insert(0, str(tmp_path))
    try:
        core, provider, request = _prepare_migrating_core(tmp_path)
        with pytest.raises(AIxUpgradeError, match="rolled back"):
            core.upgrade_python_packages("app", ("migrating_bad_v2",), trusted_namespace_prefixes=("_AAC.",))
        config = provider.snapshot(request)
        assert config.payload.configuration_schema_version == 1
        assert config.payload.values == {"old_name": "configuration"}
        assert core.installed("com.example.migrating").descriptor.version == 1
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("migrating_v1", "migrating_bad_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)


def _write_same_namespace_wheel(path: Path, *, version: int, broken: bool = False) -> None:
    from zipfile import ZipFile

    component = f'''component:
  id: com.example.same-namespace
  version: {version}
  contracts:
    - contracts/same_1.yml
  providers:
    - id: main
      capability:
        id: com.example.same.capability
        version: 1
      implementation_class: sameupgrade.{"missing" if broken else "provider"}:{"Nope" if broken else "Provider"}
      initial_instances:
        - name: default
          configuration: {{}}
'''
    contract = '''capability:
  id: com.example.same.capability
  version: 1
operations:
  - id: ping
    input: Object
    output: Object
'''
    provider = (
        "from algites.lib.aac.coreintf.runtime import AIiProviderRuntime\n"
        "class Provider(AIiProviderRuntime):\n"
        f"    marker = {version}\n"
        "    def __init__(self, configuration): pass\n"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("sameupgrade/__init__.py", "")
        archive.writestr("sameupgrade/provider.py", provider)
        archive.writestr("sameupgrade/component.yml", component)
        archive.writestr("sameupgrade/contracts/same_1.yml", contract)


def test_same_python_namespace_is_reloaded_from_exact_target_wheel(tmp_path: Path):
    old_wheel = tmp_path / "sameupgrade-1.whl"
    new_wheel = tmp_path / "sameupgrade-2.whl"
    _write_same_namespace_wheel(old_wheel, version=1)
    _write_same_namespace_wheel(new_wheel, version=2)
    sys.path.insert(0, str(old_wheel))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("sameupgrade", artifact_path=str(old_wheel))
        core.activate_application("app")
        instance = core.instances.find(component_id="com.example.same-namespace")[0]
        assert core.lifecycle.runtime(instance.id).marker == 1

        plan = core.plan_python_package_upgrades(
            "app", ("sameupgrade",), artifact_paths={"sameupgrade": str(new_wheel)}
        )
        assert plan.compatible
        core.upgrade_python_packages(
            "app", ("sameupgrade",), artifact_paths={"sameupgrade": str(new_wheel)}
        )

        instance = core.instances.find(component_id="com.example.same-namespace")[0]
        assert core.lifecycle.runtime(instance.id).marker == 2
        assert sys.path[0] == str(new_wheel)
        assert str(old_wheel) not in sys.path
    finally:
        while str(old_wheel) in sys.path:
            sys.path.remove(str(old_wheel))
        while str(new_wheel) in sys.path:
            sys.path.remove(str(new_wheel))
        for name in tuple(sys.modules):
            if name == "sameupgrade" or name.startswith("sameupgrade."):
                sys.modules.pop(name, None)


def test_same_python_namespace_rollback_restores_old_module_and_path(tmp_path: Path):
    old_wheel = tmp_path / "sameupgrade-1.whl"
    bad_wheel = tmp_path / "sameupgrade-2-bad.whl"
    _write_same_namespace_wheel(old_wheel, version=1)
    _write_same_namespace_wheel(bad_wheel, version=2, broken=True)
    sys.path.insert(0, str(old_wheel))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("sameupgrade", artifact_path=str(old_wheel))
        core.activate_application("app")
        instance = core.instances.find(component_id="com.example.same-namespace")[0]
        old_runtime_class = core.lifecycle.runtime(instance.id).__class__

        with pytest.raises(AIxUpgradeError, match="rolled back"):
            core.upgrade_python_packages(
                "app", ("sameupgrade",), artifact_paths={"sameupgrade": str(bad_wheel)}
            )

        instance = core.instances.find(component_id="com.example.same-namespace")[0]
        runtime = core.lifecycle.runtime(instance.id)
        assert runtime.marker == 1
        assert runtime.__class__ is old_runtime_class
        assert str(old_wheel) in sys.path
        assert str(bad_wheel) not in sys.path
    finally:
        while str(old_wheel) in sys.path:
            sys.path.remove(str(old_wheel))
        while str(bad_wheel) in sys.path:
            sys.path.remove(str(bad_wheel))
        for name in tuple(sys.modules):
            if name == "sameupgrade" or name.startswith("sameupgrade."):
                sys.modules.pop(name, None)


def test_stored_package_transaction_commits_selection_and_obsoletes_old_artifact(tmp_path: Path):
    import hashlib

    from algites.lib.aac.coreintf.packages import AIcPackageCandidate, AIcPackageStoreLayout, AInStoredPackageState
    from algites.lib.aac.coreintf.verification import AIcVerificationOutput, AIiPackageVerifier

    class AIcAcceptVerifier(AIiPackageVerifier):
        def verify(self, verification_input):
            return AIcVerificationOutput(True, verifier_id="test")

    source = tmp_path / "source"
    source.mkdir()
    old_wheel = source / "sameupgrade-1.whl"
    new_wheel = source / "sameupgrade-2.whl"
    _write_same_namespace_wheel(old_wheel, version=1)
    _write_same_namespace_wheel(new_wheel, version=2)

    def candidate(path: Path, version: int) -> AIcPackageCandidate:
        return AIcPackageCandidate(
            component_id="com.example.same-namespace",
            component_version=version,
            source_id="test",
            artifact_uri=str(path),
            artifact_filename=path.name,
            package_format="PYTHON_WHEEL",
            descriptor_path="sameupgrade/component.yml",
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            runtime_package="sameupgrade",
            verifier_id="test",
        )

    core = AIcApplicationComponentCore()
    manager = core.configure_package_management(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", AIcAcceptVerifier())
    old_package = manager.install(candidate(old_wheel, 1), manager.download(candidate(old_wheel, 1)))
    new_package = manager.install(candidate(new_wheel, 2), manager.download(candidate(new_wheel, 2)))
    manager.selections.select("app", old_package)
    sys.path.insert(0, old_package.artifact_path)
    try:
        core.install_python_package("sameupgrade", artifact_path=old_package.artifact_path)
        core.activate_application("app")
        assert core.plan_stored_package_upgrades("app", (new_package,)).compatible

        core.upgrade_stored_packages("app", (new_package,))

        selection = manager.selections.get("app", "com.example.same-namespace")
        assert selection is not None
        assert selection.component_version == 2
        assert core.installed("com.example.same-namespace").descriptor.version == 2
        instance = core.instances.find(component_id="com.example.same-namespace")[0]
        assert core.lifecycle.runtime(instance.id).marker == 2
        assert manager.package_store.find(
            "com.example.same-namespace", 1, old_package.sha256, AInStoredPackageState.OBSOLETE
        ) is not None
    finally:
        for path in (old_package.artifact_path, new_package.artifact_path):
            while path in sys.path:
                sys.path.remove(path)
        for name in tuple(sys.modules):
            if name == "sameupgrade" or name.startswith("sameupgrade."):
                sys.modules.pop(name, None)


def test_read_only_old_configuration_allows_upgrade_and_is_normalized_on_the_fly(tmp_path: Path):
    _write_migrating_component(tmp_path, "migrating_v1", version=1)
    _write_migrating_component(tmp_path, "migrating_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core, provider, request = _prepare_migrating_core(tmp_path)
        provider.read_only = True

        plan = core.plan_python_package_upgrades("app", ("migrating_v2",))
        assert plan.compatible
        outcome = core.upgrade_python_packages(
            "app", ("migrating_v2",), trusted_namespace_prefixes=("_AAC.",)
        )

        assert core.installed("com.example.migrating").descriptor.version == 2
        stored = provider.snapshot(request)
        assert stored.payload.configuration_schema_version == 1
        assert stored.payload.values == {"old_name": "configuration"}
        effective = core.resolve_component_scoped_configuration("com.example.migrating")
        assert effective.plain_values() == {"new_name": "configuration"}
        assert any("read-only" in note for note in outcome.diagnostics)
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("migrating_v1", "migrating_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)


def test_configuration_writeback_failure_does_not_rollback_upgrade_and_retries_later(tmp_path: Path):
    _write_migrating_component(tmp_path, "migrating_v1", version=1)
    _write_migrating_component(tmp_path, "migrating_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core, provider, request = _prepare_migrating_core(tmp_path)
        original_replace_payload = provider.replace_payload

        def fail_target_schema(request_arg, payload, expected_record_revision=None):
            if payload.configuration_schema_version == 2:
                raise OSError("simulated remote configuration outage")
            return original_replace_payload(request_arg, payload, expected_record_revision)

        provider.replace_payload = fail_target_schema
        outcome = core.upgrade_python_packages(
            "app", ("migrating_v2",), trusted_namespace_prefixes=("_AAC.",)
        )

        # The component cutover is final even though persistence convergence failed.
        assert core.installed("com.example.migrating").descriptor.version == 2
        stored = provider.snapshot(request)
        assert stored.payload.configuration_schema_version == 1
        assert any("simulated remote configuration outage" in note for note in outcome.diagnostics)

        # Runtime resolution still sees the target representation in memory and another failed
        # write-back attempt does not make configuration unreadable.
        effective = core.resolve_component_scoped_configuration("com.example.migrating")
        assert effective.plain_values() == {"new_name": "configuration"}
        assert provider.snapshot(request).payload.configuration_schema_version == 1

        # Once the provider is writable/reachable again, the next normal read converges it.
        provider.replace_payload = original_replace_payload
        effective = core.resolve_component_scoped_configuration("com.example.migrating")
        assert effective.plain_values() == {"new_name": "configuration"}
        stored = provider.snapshot(request)
        assert stored.payload.configuration_schema_version == 2
        assert stored.payload.values == {"new_name": "configuration"}
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("migrating_v1", "migrating_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)


def test_downgrade_is_a_fresh_replacement_and_unsupported_newer_configuration_is_degraded_not_blocking(tmp_path: Path):
    _write_migrating_component(tmp_path, "migrating_v1", version=1)
    _write_migrating_component(tmp_path, "migrating_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core, provider, request = _prepare_migrating_core(tmp_path)
        core.upgrade_aac_package("app", "migrating_v2")
        stored = provider.snapshot(request)
        assert stored.payload.configuration_schema_version == 2

        plan = core.plan_python_package_upgrades("app", ("migrating_v1",))
        assert plan.compatible
        assert any(
            item.code == "CONFIGURATION_UNSUPPORTED" and not item.blocking
            for item in plan.diagnostics
        )

        core.upgrade_aac_package("app", "migrating_v1")
        assert core.installed("com.example.migrating").descriptor.version == 1
        effective = core.resolve_component_scoped_configuration("com.example.migrating")
        assert effective.plain_values() == {}
        assert any("unsupported representation" in item for item in effective.diagnostics)
        # The newer payload is preserved losslessly even though the old component cannot use it.
        stored_after = provider.snapshot(request)
        assert stored_after.payload.configuration_schema_version == 2
        assert stored_after.payload.values == {"new_name": "configuration"}
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        for name in ("migrating_v1", "migrating_v2"):
            sys.modules.pop(name, None)
            sys.modules.pop(name + ".provider", None)
