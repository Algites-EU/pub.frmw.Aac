import pytest
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
from eu.algites.frmw.aac.core.namespace.policy import AIxNamespacePolicyError


def test_reserved_aac_namespace_requires_explicit_core_trust():
    core = AIcApplicationComponentCore()
    with pytest.raises(AIxNamespacePolicyError):
        core.install_python_package("eu.algites.frmw.aac.observation.simpleaudit")
    core.install_aac_package("eu.algites.frmw.aac.observation.simpleaudit")
