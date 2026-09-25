import pytest
from algites.frmw.aac.coreimpl.core import AIcApplicationComponentCore
from algites.frmw.aac.coreimpl.namespace import AIxNamespacePolicyError


def test_reserved_aac_namespace_requires_explicit_core_trust():
    core = AIcApplicationComponentCore()
    with pytest.raises(AIxNamespacePolicyError):
        core.install_python_package("algites.frmw.aac.simpleaudit")
    core.install_aac_package("algites.frmw.aac.simpleaudit")
