import os

from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService, AIcEnvironmentSecretProvider
from eu.algites.frmw.aac.core.bootstrap.loaders import AIcSecurityBootstrapLoader
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore


SECURITY = """
SecurityBootstrap:
  SchemaVersion: 1
  SecretProviders:
    - Id: env
      Type: ENVIRONMENT
      BootstrapSafe: true
      Settings:
        prefix: AAC_TEST_
  AuthenticationProfiles:
    - Id: basic
      Mechanism: basic
      Parameters:
        username: alice
        password:
          SecretReference:
            SecretProviderId: env
            Key: PASSWORD
    - Id: bearer
      Mechanism: BEARER
      Parameters:
        token:
          SecretReference:
            SecretProviderId: env
            Key: TOKEN
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
    assert service.secret_providers.get("env").capabilities()[0].value == "read"
