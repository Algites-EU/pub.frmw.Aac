from __future__ import annotations

import sys
from pathlib import Path

from algites.lib.aac.coreintf.instances import AInProviderInstanceState
from algites.lib.aac.coreintf.readiness import AInReadinessState
from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore


def _write_component(root: Path, package: str, *, version: int = 1, dynamic: str = "READY", requirement_state: str = "NOT_READY") -> None:
    pkg = root / package
    (pkg / "schemas").mkdir(parents=True)
    (pkg / "contracts").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "provider.py").write_text(
        "from algites.lib.aac.coreintf.runtime import AIiProviderRuntime\n"
        "from algites.lib.aac.coreintf.readiness import AInReadinessState, AIcReadinessReason, AIcReadinessResult\n"
        "class Provider(AIiProviderRuntime):\n"
        "    def __init__(self, configuration): self.configuration = configuration\n"
        f"    def readiness(self):\n"
        f"        state = AInReadinessState.{dynamic}\n"
        "        if state is AInReadinessState.READY: return AIcReadinessResult()\n"
        "        return AIcReadinessResult(state, (AIcReadinessReason('RUNTIME_TEST', 'runtime reported reduced readiness', state),))\n",
        encoding="utf-8",
    )
    (pkg / "contracts" / "ready_1.yml").write_text(
        "capability:\n  id: com.example.ready\n  version: 1\noperations:\n  - id: ping\n    input: Object\n    output: Object\n",
        encoding="utf-8",
    )
    (pkg / "schemas" / "ready-config_1.json").write_text(
        '{"type":"object","properties":{"endpoint":{"type":"string"}}}', encoding="utf-8"
    )
    (pkg / "component.yml").write_text(
        "component:\n"
        "  id: com.example.readiness\n"
        f"  version: {version}\n"
        "  component_configuration_schema:\n"
        "    id: ready-config\n"
        "    write_version: 1\n"
        "    readable_versions: [1]\n"
        "    resource: ready-config_1.json\n"
        "  contracts:\n"
        "    - contracts/ready_1.yml\n"
        "  providers:\n"
        "    - id: main\n"
        "      capability:\n"
        "        id: com.example.ready\n"
        "        version: 1\n"
        f"      implementation_class: {package}.provider:Provider\n"
        "      readiness_requirements:\n"
        "        - id: endpoint\n"
        "          source: COMPONENT_CONFIGURATION\n"
        "          key: endpoint\n"
        f"          missing_state: {requirement_state}\n"
        "      initial_instances:\n"
        "        - name: default\n"
        "          configuration: {}\n",
        encoding="utf-8",
    )


def test_missing_configuration_affects_readiness_but_not_activation(tmp_path: Path):
    _write_component(tmp_path, "ready_static")
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("ready_static")
        core.activate_application("app")
        instance = core.instances.find(component_id="com.example.readiness")[0]
        report = core.provider_readiness("app", instance.id)
        assert core.instances.get(instance.id).state is AInProviderInstanceState.ACTIVE
        assert report is not None and report.state is AInReadinessState.NOT_READY
        assert report.reasons[0].code == "CONFIGURATION_UNDEFINED"
        assert core.component_readiness("app", "com.example.readiness").state is AInReadinessState.NOT_READY
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("ready_static", "ready_static.provider"):
            sys.modules.pop(name, None)


def test_dynamic_runtime_readiness_combines_with_static_readiness(tmp_path: Path):
    _write_component(tmp_path, "ready_dynamic", dynamic="DEGRADED", requirement_state="DEGRADED")
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("ready_dynamic")
        core.activate_application("app")
        instance = core.instances.find(component_id="com.example.readiness")[0]
        report = core.provider_readiness("app", instance.id)
        assert report is not None and report.state is AInReadinessState.DEGRADED
        assert {reason.code for reason in report.reasons} == {"CONFIGURATION_UNDEFINED", "RUNTIME_TEST"}
        capabilities = core.capability_readiness("app")
        assert capabilities[0].capability_id == "com.example.ready"
        assert capabilities[0].state is AInReadinessState.DEGRADED
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("ready_dynamic", "ready_dynamic.provider"):
            sys.modules.pop(name, None)


def test_upgrade_preflight_reports_nonblocking_target_readiness(tmp_path: Path):
    _write_component(tmp_path, "ready_v1", version=1)
    _write_component(tmp_path, "ready_v2", version=2)
    sys.path.insert(0, str(tmp_path))
    try:
        core = AIcApplicationComponentCore()
        core.install_python_package("ready_v1")
        core.activate_application("app")
        plan = core.plan_python_package_upgrades("app", ("ready_v2",))
        assert plan.compatible
        warnings = [item for item in plan.diagnostics if item.code == "READINESS_NOT_READY"]
        assert len(warnings) == 1
        assert not warnings[0].blocking
        assert "endpoint" in warnings[0].message
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("ready_v1", "ready_v1.provider", "ready_v2", "ready_v2.provider"):
            sys.modules.pop(name, None)
