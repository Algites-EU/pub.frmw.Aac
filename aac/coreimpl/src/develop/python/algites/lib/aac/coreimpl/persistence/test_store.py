from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore
from algites.lib.aac.coreimpl.persistence import AIcJsonFileStateStore


def test_provider_instance_identity_survives_core_recreation(tmp_path):
    path = tmp_path / "aac-state.json"
    first = AIcApplicationComponentCore(store=AIcJsonFileStateStore(path))
    installed = first.install_aac_package("algites.lib.aac.simpleaudit")
    outcome = first.provisioning.provision("app", installed.descriptor)
    instance_id = outcome.created_instance_ids[0]

    second = AIcApplicationComponentCore(store=AIcJsonFileStateStore(path))
    restored = second.instances.get(instance_id)
    assert restored.id == instance_id
    assert restored.component_id == "_AAC.component.simpleaudit"
