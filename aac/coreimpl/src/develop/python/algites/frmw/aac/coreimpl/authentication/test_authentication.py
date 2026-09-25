import os

from algites.frmw.aac.coreimpl.authentication import AIcAuthenticationService, AIcEnvironmentSecretProvider
from algites.frmw.aac.coreimpl.bootstrap import AIcSecurityBootstrapLoader
from algites.frmw.aac.coreimpl.core import AIcApplicationComponentCore


SECURITY = """
security_bootstrap:
  schema_version: 1
  secret_providers:
    - id: env
      type: ENVIRONMENT
      bootstrap_safe: true
      settings:
        prefix: AAC_TEST_
  authentication_profiles:
    - id: basic
      mechanism: BASIC
      parameters:
        username: alice
        password:
          secret_reference:
            secret_provider_id: env
            key: PASSWORD
    - id: bearer
      mechanism: BEARER
      parameters:
        token:
          secret_reference:
            secret_provider_id: env
            key: TOKEN
"""


def test_security_bootstrap_and_basic_bearer_material(monkeypatch):
    monkeypatch.setenv("AAC_TEST_PASSWORD", "secret")
    monkeypatch.setenv("AAC_TEST_TOKEN", "abc")
    core = AIcApplicationComponentCore()
    core.apply_security_bootstrap(AIcSecurityBootstrapLoader.load_text(SECURITY))
    basic = core.authentication.material("basic", transport_kind="HTTP")
    bearer = core.authentication.material("bearer", transport_kind="HTTP")
    assert basic.headers["Authorization"].startswith("Basic ")
    assert bearer.headers["Authorization"] == "Bearer abc"
    rendered = repr(core.security_bootstrap)
    assert "AAC_TEST_PASSWORD" not in rendered
    assert "token-actual-value" not in rendered


def test_environment_secret_provider_is_read_only(monkeypatch):
    monkeypatch.setenv("X", "value")
    service = AIcAuthenticationService()
    service.secret_providers.register("env", AIcEnvironmentSecretProvider())
    assert service.secret_providers.get("env").capabilities()[0].value == "READ"
