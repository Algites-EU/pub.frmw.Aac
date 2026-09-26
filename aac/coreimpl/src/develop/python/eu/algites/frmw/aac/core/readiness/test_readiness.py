from __future__ import annotations

import sys
from pathlib import Path

from eu.algites.frmw.aac.core.instances.api import AInProviderInstanceState
from eu.algites.frmw.aac.core.readiness.api import AInReadinessState
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore


def _write_component(root: Path, package: str, *, version: int = 1, dynamic: str = "ready", requirement_state: str = "not_ready") -> None:
    pkg = root / package
    (pkg / "schemas").mkdir(parents=True)
    (pkg / "capability").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "provider.py").write_text(
        "from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime\n"
        "from eu.algites.frmw.aac.core.readiness.api import AInReadinessState, AIcReadinessReason, AIcReadinessResult\n"
        "class Provider(AIiProviderRuntime):\n"
        "    def __init__(self, configuration): self.configuration = configuration\n"
        f"    def readiness(self):\n"
        f"        state = AInReadinessState.{dynamic.upper()}\n"
        "        if state is AInReadinessState.READY: return AIcReadinessResult()\n"
        "        return AIcReadinessResult(state, (AIcReadinessReason('RUNTIME_TEST', 'runtime reported reduced readiness', state),))\n",
        encoding="utf-8",
    )
    (pkg / "capability" / "ready_1.yml").write_text(
        "Capability:\n  Id: com.example.ready\n  Version: 1\n  GroupId: _AAC.runtime\nOperations:\n  - Id: ping\n",
        encoding="utf-8",
    )
    (pkg / "schemas" / "ready-config_1.json").write_text(
        '{"x-aac-schema-id":"ready-config","x-aac-schema-version":1,"type": "object","properties":{"Endpoint":{"type": "string"}}}', encoding="utf-8"
    )
    (pkg / "component.yml").write_text(
        "Component:\n"
        "  Id: com.example.readiness\n"
        f"  Version: {version}\n"
        "  ComponentConfigurationSchema:\n"
        "    Id: ready-config\n"
        "    WriteVersion: 1\n"
        "    ReadableVersions: [1]\n"
        "    Resource: ready-config_1.json\n"
        "  Capability:\n"
        "    - capability/ready_1.yml\n"
        "  CapabilityProviders:\n"
        "    - Id: main\n"
        "      Capabilities:\n"
        "        - Id: com.example.ready\n"
        "          Versions: [1]\n"
        f"      ImplementationClasses:\n        - TechnologyKind: python\n          ClassName: {package}.provider:Provider\n"
        "      Operations:\n"
        "        - Capability: com.example.ready\n"
        "          CapabilityVersion: 1\n"
        "          Operation: ping\n"
        "          Interaction:\n"
        "            SupportedStateResultDeliveryModes: [on_demand_complete]\n"
        "      ReadinessRequirements:\n"
        "        - Id: endpoint\n"
        "          Source: component_configuration\n"
        "          Key: Endpoint\n"
        f"          MissingState: {requirement_state}\n"
        "      InitialInstances:\n"
        "        - Name: default\n"
        "          Configuration: {}\n",
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
    _write_component(tmp_path, "ready_dynamic", dynamic="degraded", requirement_state="degraded")
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
        assert "Endpoint" in warnings[0].message
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("ready_v1", "ready_v1.provider", "ready_v2", "ready_v2.provider"):
            sys.modules.pop(name, None)
