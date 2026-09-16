import pytest
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore
from algites.lib.aac.coreimpl.namespace import AIxNamespacePolicyError


def test_reserved_aac_namespace_requires_explicit_core_trust():
    core = AIcApplicationComponentCore()
    with pytest.raises(AIxNamespacePolicyError):
        core.install_python_package("algites.lib.aac.simpleaudit")
    core.install_aac_package("algites.lib.aac.simpleaudit")
