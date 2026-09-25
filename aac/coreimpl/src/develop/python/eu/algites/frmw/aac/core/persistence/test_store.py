from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
from eu.algites.frmw.aac.core.persistence.aic_json_file_state_store import AIcJsonFileStateStore


def test_provider_instance_identity_survives_core_recreation(tmp_path):
    path = tmp_path / "aac-state.json"
    first = AIcApplicationComponentCore(store=AIcJsonFileStateStore(path))
    installed = first.install_aac_package("eu.algites.frmw.aac.observation.simpleaudit")
    outcome = first.provisioning.provision("app", installed.descriptor)
    instance_id = outcome.created_instance_ids[0]

    second = AIcApplicationComponentCore(store=AIcJsonFileStateStore(path))
    restored = second.instances.get(instance_id)
    assert restored.id == instance_id
    assert restored.component_id == "_AAC.component.simpleaudit"
