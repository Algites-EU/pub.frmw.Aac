from algites.lib.aac.coreintf.descriptor import AInComponentOrigin
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore


def test_product_shipped_component_is_admitted_as_first_class_builtin_component():
    core = AIcApplicationComponentCore()
    installed = core.register_builtin_python_component(
        "algites.lib.aac.simpleaudit", trusted_namespace_prefixes=("_AAC.",)
    )
    assert installed.origin is AInComponentOrigin.BUILTIN
    assert core.installed("_AAC.component.simpleaudit").descriptor.name.fallback == "Simple audit observer"
    assert core.installed("_AAC.component.simpleaudit").descriptor.provider("observation").name.fallback == "Simple audit observation provider"
