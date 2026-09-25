from eu.algites.frmw.aac.core.descriptor.api import AInComponentOrigin
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore


def test_product_shipped_component_is_admitted_as_first_class_builtin_component():
    core = AIcApplicationComponentCore()
    installed = core.register_builtin_python_component(
        "eu.algites.frmw.aac.observation.simpleaudit", trusted_namespace_prefixes=("_AAC.",)
    )
    assert installed.origin is AInComponentOrigin.BUILTIN
    assert core.installed("_AAC.component.simpleaudit").descriptor.name.fallback == "Simple audit observer"
    assert core.installed("_AAC.component.simpleaudit").descriptor.provider("observation").name.fallback == "Simple audit observation provider"
