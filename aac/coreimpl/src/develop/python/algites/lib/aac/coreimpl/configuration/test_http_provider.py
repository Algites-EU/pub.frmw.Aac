import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from algites.lib.aac.coreintf.authentication import AIcAuthenticationParameter, AIcAuthenticationProfile, AIcSecretReference
from algites.lib.aac.coreintf.configuration import (
    AInConfigurationMutationOperation,
    AInConfigurationTargetKind,
    AIcConfigurationChange,
    AIcConfigurationChangeSet,
    AIcConfigurationProviderRequest,
    AIcConfigurationTarget,
)
from algites.lib.aac.coreintf.context import AIcConfigurationScope
from algites.lib.aac.coreintf.persistence import AInPersistenceCapability
from algites.lib.aac.coreimpl.authentication import AIcAuthenticationService, AIcEnvironmentSecretProvider
from algites.lib.aac.coreimpl.configuration_providers import AIcHttpConfigurationProvider
from algites.lib.aac.coreimpl.errors import AIxConfigurationRevisionConflict


class _State:
    document = None
    revision = 0
    authorization = None


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _auth(self):
        _State.authorization = self.headers.get("Authorization")
        return _State.authorization == "Bearer token-1"

    def do_GET(self):
        if not self._auth():
            self.send_response(401); self.end_headers(); return
        if _State.document is None:
            self.send_response(404); self.end_headers(); return
        body = json.dumps(_State.document).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("ETag", f'"{_State.record_revision}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_PATCH(self):
        if not self._auth():
            self.send_response(401); self.end_headers(); return
        expected = self.headers.get("If-Match")
        if _State.document is not None and expected != f'"{_State.record_revision}"':
            self.send_response(412); self.send_header("ETag", f'"{_State.record_revision}"'); self.end_headers(); return
        raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))["configuration_change_set"]
        if _State.document is None:
            _State.document = {
                "format_version": 1,
                "configuration_scope": raw["configuration_scope"],
                "configuration_target": raw["configuration_target"],
                "revision": 0,
                "payload": {
                    "configuration_schema_id": raw["configuration_schema_id"],
                    "configuration_schema_version": raw["configuration_schema_version"],
                    "written_by_component_version": raw["written_by_component_version"],
                    "values": {}, "policies": {}, "metadata": {}
                }
            }
        for change in raw["changes"]:
            if change["operation"] == "SET_VALUE":
                _State.document["payload"]["values"][change["property_id"]] = change.get("value")
        _State.record_revision += 1
        _State.document["revision"] = _State.record_revision
        body = json.dumps({"revision": _State.record_revision}).encode()
        self.send_response(200); self.send_header("ETag", f'"{_State.record_revision}"')
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


@pytest.fixture
def server():
    _State.document = None; _State.record_revision = 0; _State.authorization = None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/configuration"
    finally:
        httpd.shutdown(); thread.join(timeout=2)


def _provider(server, monkeypatch):
    monkeypatch.setenv("AAC_HTTP_TOKEN", "token-1")
    auth = AIcAuthenticationService()
    auth.secret_providers.register("env", AIcEnvironmentSecretProvider())
    auth.register_profile(AIcAuthenticationProfile("remote", "BEARER", {
        "token": AIcAuthenticationParameter(secret_reference=AIcSecretReference("env", "AAC_HTTP_TOKEN"))
    }))
    return AIcHttpConfigurationProvider(server, authentication=auth, authentication_profile_id="remote")


def _target():
    return AIcConfigurationTarget(AInConfigurationTargetKind.COMPONENT, "vendor.foo")


def _change(expected=None, value="one"):
    return AIcConfigurationChangeSet(
        AIcConfigurationScope("WORKSPACE", "w"), "http", _target(),
        (AIcConfigurationChange("mode", AInConfigurationMutationOperation.SET_VALUE, value, True),),
        expected_record_revision=expected,
        configuration_schema_id="foo-component-config", configuration_schema_version=1,
        written_by_component_version=1, actor_context={"component_id": "vendor.foo"},
    )


def test_http_patch_provider_uses_auth_and_etag(server, monkeypatch):
    provider = _provider(server, monkeypatch)
    first = provider.apply_changes(_change())
    assert first.record_revision == 1
    assert _State.authorization == "Bearer token-1"
    snap = provider.snapshot(AIcConfigurationProviderRequest(_target(), AIcConfigurationScope("WORKSPACE", "w")))
    assert snap.record_revision == 1
    assert snap.payload.values["mode"] == "one"
    second = provider.apply_changes(_change(1, "two"))
    assert second.record_revision == 2


def test_http_provider_reports_stale_etag(server, monkeypatch):
    provider = _provider(server, monkeypatch)
    provider.apply_changes(_change())
    with pytest.raises(AIxConfigurationRevisionConflict):
        provider.apply_changes(_change(0, "stale"))


def test_http_patch_provider_does_not_claim_multi_record_transaction(server, monkeypatch):
    provider = _provider(server, monkeypatch)
    request = AIcConfigurationProviderRequest(_target(), AIcConfigurationScope("WORKSPACE", "w"))
    assert provider.persistence_capabilities(request) == (
        AInPersistenceCapability.READ,
        AInPersistenceCapability.SINGLE_RECORD_CAS,
    )

