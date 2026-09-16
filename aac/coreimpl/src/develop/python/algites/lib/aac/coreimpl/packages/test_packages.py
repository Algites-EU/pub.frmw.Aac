from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from algites.lib.aac.coreintf.descriptor import AIcCapabilityEntitlementDescriptor, AIcComponentDescriptor, AIcEntitlementLicensingScopeDescriptor, AIcPermissionDescriptor, AIcProviderDefinitionDescriptor
from algites.lib.aac.coreintf.packages import (
    AInPackageUpdatePolicy,
    AInStoredPackageState,
    AIcPackageAutomationPolicy,
    AIcPackageCandidate,
    AIcPackageStoreLayout,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentLockEntry,
    AIcWorkspaceComponentRequirement,
    AIcWorkspaceComponentRequirements,
)
from algites.lib.aac.coreintf.verification import AIcVerificationOutput, AIiPackageVerifier
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore
from algites.lib.aac.coreimpl.package_documents import AIcPackageBootstrapLoader, AIcWorkspaceComponentLockLoader, AIcWorkspaceComponentRequirementsLoader
from algites.lib.aac.coreimpl.packages import AIcPackageManager, AIcStaticPackageSource
from algites.lib.aac.coreimpl.persistence import AIcJsonFileStateStore


class RecordingVerifier(AIiPackageVerifier):
    def __init__(self):
        self.paths: list[str] = []

    def verify(self, verification_input):
        self.paths.append(str(verification_input.artifact_path))
        return AIcVerificationOutput(True, verifier_id="test-verifier", signer_identity="test-signer")


def make_wheel(root: Path, *, component_id="com.example.demo", version=1, filename="demo.whl") -> tuple[Path, str]:
    wheel = root / filename
    descriptor_path = "demo/component.yml"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(descriptor_path, f"component:\n  id: {component_id}\n  version: {version}\n")
    return wheel, descriptor_path


def candidate_for(wheel: Path, descriptor_path: str, *, version=1, verifier_id="test") -> AIcPackageCandidate:
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    return AIcPackageCandidate(
        component_id="com.example.demo", component_version=version, source_id="local",
        artifact_uri=str(wheel), artifact_filename=wheel.name, package_format="PYTHON_WHEEL",
        descriptor_path=descriptor_path, expected_sha256=digest, runtime_package="demo", verifier_id=verifier_id,
    )


def test_default_and_product_overridden_package_layout(tmp_path):
    default = AIcPackageStoreLayout(str(tmp_path))
    manager = AIcPackageManager(default)
    assert manager.package_store.downloaded_root == tmp_path / "plugins" / "downloaded"
    assert manager.package_store.installed_root == tmp_path / "plugins" / "installed"
    assert manager.package_store.obsolete_root == tmp_path / "plugins" / "obsolete"
    assert manager.selection_manifest_store.path == tmp_path / "aac-state" / "active-package-set.json"
    assert manager.transactions.transactions_root == tmp_path / "aac-state" / "transactions"

    custom = AIcPackageStoreLayout(str(tmp_path), "components", "incoming", "ready", "retired", "component-state", "tx")
    manager = AIcPackageManager(custom)
    assert manager.package_store.installed_root == tmp_path / "components" / "ready"
    assert manager.selection_manifest_store.path == tmp_path / "component-state" / "active-package-set.json"
    assert manager.transactions.transactions_root == tmp_path / "component-state" / "tx"



def test_legacy_package_selection_state_migrates_to_authoritative_manifest(tmp_path):
    product = tmp_path / "product"
    state_path = tmp_path / "core-state.json"
    store = AIcJsonFileStateStore(state_path)
    store.put("aac.packages.selection", "app:com.example.demo", {
        "component_version": 1,
        "sha256": "a" * 64,
        "selected_at": "2026-09-15T00:00:00+00:00",
        "previous_sha256": None,
        "previous_version": None,
    })

    manager = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=store)

    manifest = manager.selections.manifest()
    assert manifest.record_revision == 1
    assert len(manifest.selections) == 1
    assert manifest.selections[0].application_scope_id == "app"
    assert manifest.selections[0].component_id == "com.example.demo"
    assert manifest.selections[0].component_version == 1
    assert manager.selection_manifest_store.path.is_file()
    assert store.list("aac.packages.selection") == {}

def test_download_install_reverifies_destination_and_preserves_download(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source)
    candidate = candidate_for(wheel, descriptor_path)
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", verifier)

    downloaded = manager.download(candidate)
    installed = manager.install(candidate, downloaded)

    assert downloaded.state is AInStoredPackageState.DOWNLOADED
    assert installed.state is AInStoredPackageState.INSTALLED
    assert Path(downloaded.artifact_path).is_file()
    assert Path(installed.artifact_path).is_file()
    assert Path(downloaded.artifact_path) != Path(installed.artifact_path)
    assert len(verifier.paths) == 2
    assert verifier.paths[0] == downloaded.artifact_path
    # The mandatory second verification runs against the temporary install destination
    # immediately before atomic promotion; promotion renames those exact bytes into place.
    assert Path(verifier.paths[1]).name == Path(installed.artifact_path).name
    assert Path(verifier.paths[1]).parent.name.startswith("install-")
    assert installed.provenance.signer_identity == "test-signer"


def test_inactive_installed_artifact_is_not_obsolete_until_explicitly_moved(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", verifier)

    installed = []
    for version in (1, 2):
        wheel, descriptor_path = make_wheel(source, version=version, filename=f"demo-{version}.whl")
        candidate = candidate_for(wheel, descriptor_path, version=version)
        installed.append(manager.install(candidate, manager.download(candidate)))

    assert len(manager.package_store.records(AInStoredPackageState.INSTALLED, "com.example.demo")) == 2
    obsolete = manager.package_store.mark_obsolete(installed[0])
    assert obsolete.state is AInStoredPackageState.OBSOLETE
    assert len(manager.package_store.records(AInStoredPackageState.INSTALLED, "com.example.demo")) == 1
    restored = manager.package_store.restore_obsolete(obsolete)
    assert restored.state is AInStoredPackageState.INSTALLED
    assert len(manager.package_store.records(AInStoredPackageState.INSTALLED, "com.example.demo")) == 2


def test_selection_and_one_step_rollback_use_installed_artifacts(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", verifier)
    values = []
    for version in (1, 2):
        wheel, descriptor_path = make_wheel(source, version=version, filename=f"demo-{version}.whl")
        candidate = candidate_for(wheel, descriptor_path, version=version)
        values.append(manager.install(candidate, manager.download(candidate)))
    manager.selections.select("ws", values[0])
    current = manager.selections.select("ws", values[1])
    assert current.component_version == 2
    rolled = manager.selections.rollback("ws", "com.example.demo", manager.package_store)
    assert rolled.component_version == 1


def test_workspace_lock_selects_exact_digest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source, version=2)
    candidate = candidate_for(wheel, descriptor_path, version=2)
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_source("local", AIcStaticPackageSource("local", (candidate,)))
    requirements = AIcWorkspaceComponentRequirements(
        "ws", (AIcWorkspaceComponentRequirement("com.example.demo", (1, 2)),), AInPackageUpdatePolicy.AUTO_LOCKED
    )
    lock = AIcWorkspaceComponentLock("ws", (AIcWorkspaceComponentLockEntry(
        "com.example.demo", 2, candidate.expected_sha256, "local", candidate.artifact_uri,
        candidate.artifact_filename, candidate.package_format, candidate.descriptor_path,
        candidate.runtime_package, candidate.verifier_id,
    ),))
    plan = manager.plan_workspace(requirements, lock)
    assert plan.actions[0].action == "AUTO_INSTALL"
    assert plan.actions[0].candidate.expected_sha256 == candidate.expected_sha256


def test_paid_component_without_implicit_or_effective_permission_blocks_only_automatic_install():
    descriptor = AIcComponentDescriptor(
        "com.example.paid", 1,
        providers=(AIcProviderDefinitionDescriptor(
            "provider", "com.example.cap", (1,), "com.example:Provider"
        ),),
        entitlement_licensing_scopes=(AIcEntitlementLicensingScopeDescriptor("USER"),),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "com.example.cap", 1,
            (AIcPermissionDescriptor("PRO", possible_licensing_scope_types=("USER",)),),
        ),),
    )
    assert not AIcPackageManager.automatic_entitlement_allows(descriptor, set())
    assert AIcPackageManager.automatic_entitlement_allows(descriptor, {("com.example.cap", 1, "PRO")})

    free_descriptor = AIcComponentDescriptor(
        "com.example.free", 1,
        providers=(AIcProviderDefinitionDescriptor(
            "provider", "com.example.cap", (1,), "com.example:Provider"
        ),),
        provided_capability_entitlements=(AIcCapabilityEntitlementDescriptor(
            "com.example.cap", 1,
            (AIcPermissionDescriptor("BASIC"),),
        ),),
    )
    assert AIcPackageManager.automatic_entitlement_allows(free_descriptor, set())


def test_package_bootstrap_and_workspace_documents_load(tmp_path):
    bootstrap = AIcPackageBootstrapLoader.load_text(f"""
package_bootstrap:
  schema_version: 1
  layout:
    product_root: {tmp_path}
    package_store_subdirectory: components
  sources:
    - id: local
      uri: {tmp_path}/packages.yml
      verifier_id: sigstore
""")
    assert bootstrap.layout.package_store_subdirectory == "components"
    assert bootstrap.layout.downloaded_subdirectory == "downloaded"
    assert bootstrap.sources[0].verifier_id == "sigstore"

    requirements = AIcWorkspaceComponentRequirementsLoader.load_text("""
workspace_component_requirements:
  workspace_id: ws-1
  update_policy: AUTO_COMPATIBLE
  requirements:
    - component_id: com.example.demo
      versions: [1, 2]
""")
    assert requirements.update_policy is AInPackageUpdatePolicy.AUTO_COMPATIBLE

    digest = "a" * 64
    lock = AIcWorkspaceComponentLockLoader.load_text(f"""
workspace_component_lock:
  workspace_id: ws-1
  entries:
    - component_id: com.example.demo
      component_version: 2
      sha256: {digest}
      source_id: local
      artifact_uri: file:///demo.whl
      artifact_filename: demo.whl
      package_format: PYTHON_WHEEL
      descriptor_path: demo/component.yml
""")
    assert lock.entry("com.example.demo").sha256 == digest


def test_core_auto_reconciliation_downloads_installs_and_selects_free_component(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source)
    candidate = candidate_for(wheel, descriptor_path)
    verifier = RecordingVerifier()

    core = AIcApplicationComponentCore()
    core.configure_package_management(
        AIcPackageStoreLayout(str(tmp_path / "product")),
        automation_policy=AIcPackageAutomationPolicy(),
    )
    core.register_package_verifier("test", verifier)
    core.register_package_source("local", AIcStaticPackageSource("local", (candidate,)))
    requirements = AIcWorkspaceComponentRequirements(
        "ws", (AIcWorkspaceComponentRequirement("com.example.demo", (1,)),), AInPackageUpdatePolicy.AUTO_COMPATIBLE
    )
    result = core.reconcile_workspace_packages(requirements, execute_automatic=True)
    assert result.actions[0].action == "AUTO_INSTALLED"
    selection = core.package_manager.selections.get("ws", "com.example.demo")
    assert selection is not None and selection.component_version == 1


def test_tampered_download_is_rejected_before_install(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source)
    candidate = candidate_for(wheel, descriptor_path)
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", verifier)
    downloaded = manager.download(candidate)
    Path(downloaded.artifact_path).write_bytes(b"tampered")
    with pytest.raises(Exception):
        manager.install(candidate, downloaded)


def test_selected_package_cannot_be_marked_obsolete(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source)
    candidate = candidate_for(wheel, descriptor_path)
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    manager.register_verifier("test", verifier)
    installed = manager.install(candidate, manager.download(candidate))
    manager.selections.select("ws", installed)
    with pytest.raises(Exception):
        manager.mark_obsolete(installed)


def test_manifest_package_source_resolves_relative_artifact_uri(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    wheel, descriptor_path = make_wheel(source)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    manifest = source / "packages.yml"
    manifest.write_text(f"""
format_version: 1
packages:
  - component_id: com.example.demo
    component_version: 1
    artifact_uri: demo.whl
    artifact_filename: demo.whl
    package_format: PYTHON_WHEEL
    descriptor_path: {descriptor_path}
    sha256: {digest}
    runtime_package: demo
    verifier_id: test
""", encoding="utf-8")
    from algites.lib.aac.coreimpl.packages import AIcManifestPackageSource
    package_source = AIcManifestPackageSource("repo", str(manifest))
    requirement = AIcWorkspaceComponentRequirement("com.example.demo", (1,))
    candidates = package_source.candidates(requirement)
    assert len(candidates) == 1
    assert Path(candidates[0].artifact_uri) == wheel
    assert candidates[0].source_uri == str(manifest)


def test_package_bootstrap_registers_manifest_source(tmp_path):
    manifest = tmp_path / "packages.yml"
    manifest.write_text("format_version: 1\npackages: []\n", encoding="utf-8")
    bootstrap = AIcPackageBootstrapLoader.load_text(f"""
package_bootstrap:
  schema_version: 1
  layout:
    product_root: {tmp_path}/product
  sources:
    - id: repo
      uri: {manifest}
      priority: 10
""")
    core = AIcApplicationComponentCore()
    core.apply_package_bootstrap(bootstrap)
    assert core.package_manager is not None
    assert core.package_manager.sources.get("repo").candidates(AIcWorkspaceComponentRequirement("missing")) == ()


def test_single_active_component_version_is_enforced_across_scopes(tmp_path):
    source = tmp_path / "source-single-active"
    source.mkdir()
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product-single-active")))
    manager.register_verifier("test", verifier)
    installed = []
    for version in (1, 2):
        wheel, descriptor_path = make_wheel(source, version=version, filename=f"demo-active-{version}.whl")
        candidate = candidate_for(wheel, descriptor_path, version=version)
        installed.append(manager.install(candidate, manager.download(candidate)))
    manager.selections.select("ws-a", installed[0])
    with pytest.raises(Exception, match="different active artifact"):
        manager.selections.select("ws-b", installed[1])
    manager.selections.select("ws-b", installed[0])


def test_replacement_commit_retires_old_unselected_artifact(tmp_path):
    source = tmp_path / "source-replace"
    source.mkdir()
    verifier = RecordingVerifier()
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product-replace")))
    manager.register_verifier("test", verifier)
    installed = []
    for version in (1, 2):
        wheel, descriptor_path = make_wheel(source, version=version, filename=f"demo-replace-{version}.whl")
        candidate = candidate_for(wheel, descriptor_path, version=version)
        installed.append(manager.install(candidate, manager.download(candidate)))
    manager.selections.select("ws", installed[0])
    previous, retired = manager.activate_replacements("ws", (installed[1],))
    assert previous["com.example.demo"].component_version == 1
    assert manager.selections.get("ws", "com.example.demo").component_version == 2
    assert any(item.component_version == 1 for item in retired)
    assert manager.package_store.find("com.example.demo", 1, installed[0].sha256) is None
    assert manager.package_store.find("com.example.demo", 1, installed[0].sha256, AInStoredPackageState.OBSOLETE) is not None



def _installed_demo_versions(tmp_path: Path, manager: AIcPackageManager):
    source = tmp_path / "source-crash"
    source.mkdir(exist_ok=True)
    manager.register_verifier("test", RecordingVerifier())
    result = []
    for version in (1, 2):
        wheel, descriptor_path = make_wheel(source, version=version, filename=f"crash-demo-{version}.whl")
        candidate = candidate_for(wheel, descriptor_path, version=version)
        result.append(manager.install(candidate, manager.download(candidate)))
    return tuple(result)


def test_active_package_set_record_revision_is_field_not_versioned_filename(tmp_path):
    manager = AIcPackageManager(AIcPackageStoreLayout(str(tmp_path / "product")))
    old, new = _installed_demo_versions(tmp_path, manager)
    assert manager.selections.manifest().record_revision == 0
    manager.selections.select("app", old)
    assert manager.selections.manifest().record_revision == 1
    manager.selections.select("app", new)
    manifest = manager.selections.manifest()
    assert manifest.record_revision == 2
    assert manager.selection_manifest_store.path.name == "active-package-set.json"
    assert list(manager.selection_manifest_store.path.parent.glob("active-package-set.*.json")) == []


def test_interrupted_precommit_transaction_restores_source_core_state_on_startup(tmp_path):
    product = tmp_path / "product"
    state_path = tmp_path / "core-state.json"
    store = AIcJsonFileStateStore(state_path)
    manager = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=store)
    old, new = _installed_demo_versions(tmp_path, manager)
    manager.selections.select("app", old)
    store.put("test", "marker", {"value": "source"})
    snapshot = store.snapshot()

    tx = manager.begin_replacement_transaction("app", (new,), snapshot)
    manager.mark_replacement_cutover_started(tx)
    store.put("test", "marker", {"value": "target-uncommitted"})

    recovered_store = AIcJsonFileStateStore(state_path)
    recovered = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=recovered_store)
    assert recovered.transaction_recovery is not None
    assert recovered.transaction_recovery.action == "RESTORED_SOURCE_STATE"
    assert recovered_store.get("test", "marker") == {"value": "source"}
    selection = recovered.selections.get("app", "com.example.demo")
    assert selection is not None and selection.component_version == 1
    assert not recovered.transactions.active_pointer.exists()
    assert recovered.package_store.find("com.example.demo", 2, new.sha256) is not None


def test_interrupted_postcommit_transaction_recovers_forward_and_finishes_cleanup(tmp_path):
    product = tmp_path / "product"
    state_path = tmp_path / "core-state.json"
    store = AIcJsonFileStateStore(state_path)
    manager = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=store)
    old, new = _installed_demo_versions(tmp_path, manager)
    manager.selections.select("app", old)
    store.put("test", "marker", {"value": "source"})
    tx = manager.begin_replacement_transaction("app", (new,), store.snapshot())
    manager.mark_replacement_cutover_started(tx)
    store.put("test", "marker", {"value": "target"})
    committed, _ = manager.commit_replacement_selections(tx)
    assert committed.last_transaction_id == tx.transaction_id
    assert manager.package_store.find("com.example.demo", 1, old.sha256) is not None

    recovered_store = AIcJsonFileStateStore(state_path)
    recovered = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=recovered_store)
    assert recovered.transaction_recovery is not None
    assert recovered.transaction_recovery.action == "COMPLETED_TARGET_CLEANUP"
    assert recovered_store.get("test", "marker") == {"value": "target"}
    selection = recovered.selections.get("app", "com.example.demo")
    assert selection is not None and selection.component_version == 2
    assert recovered.package_store.find("com.example.demo", 1, old.sha256) is None
    assert recovered.package_store.find(
        "com.example.demo", 1, old.sha256, AInStoredPackageState.OBSOLETE
    ) is not None
    assert recovered.package_store.find("com.example.demo", 2, new.sha256) is not None
    assert not recovered.transactions.active_pointer.exists()


def test_package_bootstrap_v2_can_override_core_transaction_state_folders(tmp_path):
    text = f"""package_bootstrap:
  schema_version: 2
  layout:
    product_root: {tmp_path / 'product'}
    core_state_subdirectory: durable-aac
    transactions_subdirectory: replacement-journal
"""
    bootstrap = AIcPackageBootstrapLoader.load_text(text)
    assert bootstrap.layout.core_state_subdirectory == "durable-aac"
    assert bootstrap.layout.transactions_subdirectory == "replacement-journal"


def test_replacement_cutover_revalidates_core_state_before_first_mutation(tmp_path):
    from algites.lib.aac.coreimpl.errors import AIxPersistenceRevisionConflict

    product = tmp_path / "product"
    state_path = tmp_path / "core-state.json"
    store = AIcJsonFileStateStore(state_path)
    manager = AIcPackageManager(AIcPackageStoreLayout(str(product)), store=store)
    old, new = _installed_demo_versions(tmp_path, manager)
    manager.selections.select("app", old)
    store.put("test", "marker", {"value": "source"})
    transaction = manager.begin_replacement_transaction("app", (new,), store.snapshot())

    second_process_view = AIcJsonFileStateStore(state_path)
    second_process_view.put("test", "marker", {"value": "concurrent"})

    with pytest.raises(AIxPersistenceRevisionConflict):
        manager.mark_replacement_cutover_started(transaction)

    assert store.get("test", "marker") == {"value": "concurrent"}
    manager.rollback_replacement_transaction(transaction, ("pre-cutover conflict",))
