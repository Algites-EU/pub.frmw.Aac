import pytest

from algites.lib.aac.coreintf.errors import AIxDescriptorError
from algites.lib.aac.coreimpl.bootstrap import AIcConfigurationBootstrapLoader, AIcEntitlementBootstrapLoader


CONFIG_BOOTSTRAP = """
configuration_bootstrap:
  schema_version: 1
  default_configuration_profile: customer-project
  workspace_configuration_profiles: ALLOWED_IF_SIGNED
  mandatory_configuration_scope_definition_ids: [system]
  configuration_scope_resolvers:
    - id: mapping
      type: STATIC_CONTEXT
  configuration_providers:
    - id: system-config
      type: FILE
    - id: customer-config
      type: HTTPS
  configuration_profiles:
    - id: customer-project
      version: 1
      configuration_scopes:
        - id: user
          type: USER
          resolver: mapping
        - id: workspace
          type: WORKSPACE
          resolver: mapping
        - id: customer
          type: CUSTOMER
          resolver: mapping
          configuration_providers:
            - id: customer-config
              priority: 100
        - id: system
          type: SYSTEM
          resolver: mapping
          mandatory: true
          configuration_providers:
            - id: system-config
              priority: 100
"""


def test_configuration_bootstrap_keeps_custom_scope_types_as_strings():
    bootstrap = AIcConfigurationBootstrapLoader.load_text(CONFIG_BOOTSTRAP)
    profile = bootstrap.profile()
    assert [item.configuration_scope_type for item in profile.configuration_scopes] == [
        "USER", "WORKSPACE", "CUSTOMER", "SYSTEM"
    ]
    assert bootstrap.workspace_configuration_profiles.value == "ALLOWED_IF_SIGNED"


def test_configuration_bootstrap_schema_is_fixed_and_rejects_unknown_fields():
    with pytest.raises(AIxDescriptorError):
        AIcConfigurationBootstrapLoader.load_text(CONFIG_BOOTSTRAP.replace("schema_version: 1", "schema_version: 2"))


def test_entitlement_bootstrap_uses_separately_named_scopes_and_providers():
    bootstrap = AIcEntitlementBootstrapLoader.load_text("""
entitlement_bootstrap:
  schema_version: 2
  default_entitlement_profile: project
  licensing_scope_resolvers:
    - id: mapping
      type: STATIC_CONTEXT
  entitlement_providers:
    - id: licensing
      type: HTTPS
  entitlement_profiles:
    - id: project
      version: 1
      licensing_scopes:
        - id: workspace
          type: WORKSPACE
          resolver: mapping
          entitlement_providers:
            - id: licensing
""")
    assert bootstrap.profile().licensing_scopes[0].licensing_scope_type == "WORKSPACE"
    assert bootstrap.entitlement_providers[0].id == "licensing"


def test_security_bootstrap_is_fixed_schema_and_configuration_provider_can_reference_auth_profile(tmp_path, monkeypatch):
    from algites.lib.aac.coreimpl.bootstrap import AIcSecurityBootstrapLoader
    from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore

    monkeypatch.setenv("AAC_REMOTE_TOKEN", "abc")
    security = AIcSecurityBootstrapLoader.load_text("""
security_bootstrap:
  schema_version: 1
  secret_providers:
    - id: env
      type: ENVIRONMENT
      bootstrap_safe: true
  authentication_profiles:
    - id: remote
      mechanism: BEARER
      parameters:
        token:
          secret_reference:
            secret_provider_id: env
            key: AAC_REMOTE_TOKEN
""")
    config = AIcConfigurationBootstrapLoader.load_text(f"""
configuration_bootstrap:
  schema_version: 1
  default_configuration_profile: p
  configuration_scope_resolvers:
    - id: mapping2
      type: MAPPING
  configuration_providers:
    - id: local
      type: FILESYSTEM
      settings:
        root: {str(tmp_path)!r}
    - id: remote
      type: HTTP
      authentication_profile_id: remote
      settings:
        base_url: http://127.0.0.1:9/configuration
        read_only: true
  configuration_profiles:
    - id: p
      version: 1
      configuration_scopes:
        - id: system
          type: SYSTEM
          resolver: mapping2
          configuration_providers:
            - id: local
""")
    core = AIcApplicationComponentCore()
    core.apply_security_bootstrap(security)
    scopes = core.apply_configuration_bootstrap(config)
    assert scopes[0].configuration_scope.type == "SYSTEM"
    assert core.configuration_providers.contains("local")
    assert core.configuration_providers.contains("remote")


def test_configuration_provider_rejects_non_bootstrap_safe_authentication_profile(monkeypatch):
    from algites.lib.aac.coreimpl.bootstrap import AIcSecurityBootstrapLoader
    from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore

    monkeypatch.setenv("AAC_REMOTE_TOKEN", "abc")
    security = AIcSecurityBootstrapLoader.load_text("""
security_bootstrap:
  schema_version: 1
  secret_providers:
    - id: env
      type: ENVIRONMENT
      bootstrap_safe: false
  authentication_profiles:
    - id: remote
      mechanism: BEARER
      parameters:
        token:
          secret_reference:
            secret_provider_id: env
            key: AAC_REMOTE_TOKEN
""")
    config = AIcConfigurationBootstrapLoader.load_text("""
configuration_bootstrap:
  schema_version: 1
  default_configuration_profile: p
  configuration_scope_resolvers:
    - id: mapping2
      type: MAPPING
  configuration_providers:
    - id: remote
      type: HTTP
      authentication_profile_id: remote
      settings:
        base_url: http://127.0.0.1:9/configuration
  configuration_profiles:
    - id: p
      version: 1
      configuration_scopes:
        - id: system
          type: SYSTEM
          resolver: mapping2
""")
    core = AIcApplicationComponentCore()
    core.apply_security_bootstrap(security)
    with pytest.raises(ValueError, match="not bootstrap-safe"):
        core.apply_configuration_bootstrap(config)


def test_external_configuration_profile_can_be_loaded_from_trusted_file_source(tmp_path):
    from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore

    profile_path = tmp_path / "profile.yml"
    profile_path.write_text("""
configuration_profile:
  id: external
  version: 1
  configuration_scopes:
    - id: system
      type: SYSTEM
      resolver: mapping
      configuration_providers:
        - id: local
""", encoding="utf-8")
    bootstrap = AIcConfigurationBootstrapLoader.load_text(f"""
configuration_bootstrap:
  schema_version: 1
  default_configuration_profile: external
  configuration_scope_resolvers:
    - id: mapping
      type: MAPPING
  configuration_providers:
    - id: local
      type: FILESYSTEM
      settings:
        root: {str(tmp_path / 'config')!r}
  configuration_profile_sources:
    - id: external-source
      uri: {str(profile_path)!r}
  configuration_profiles:
    - id: fallback
      version: 1
      configuration_scopes:
        - id: system
          type: SYSTEM
          resolver: mapping
""")
    core = AIcApplicationComponentCore()
    scopes = core.apply_configuration_bootstrap(bootstrap)
    assert core.configuration_bootstrap.profile().id == "external"
    assert scopes[0].configuration_providers[0].configuration_provider_id == "local"


def test_entitlement_bootstrap_loads_file_provider_and_trusted_issuer():
    bootstrap = AIcEntitlementBootstrapLoader.load_text('''
entitlement_bootstrap:
  schema_version: 2
  default_entitlement_profile: p
  licensing_scope_resolvers:
    - id: mapping
      type: MAPPING
  entitlement_providers:
    - id: licenses
      type: FILE
      settings: {root: /tmp/licenses, evidence_type: SIGSTORE}
  trusted_issuers:
    - issuer_id: vendor.example
      component_ids: [vendor.foo]
      evidence_types: [SIGSTORE]
      signer_identities: [release@example.test]
  entitlement_profiles:
    - id: p
      version: 1
      licensing_scopes:
        - id: workspace
          type: WORKSPACE
          resolver: mapping
          entitlement_providers: [{id: licenses}]
''')
    assert bootstrap.entitlement_providers[0].type == "FILE"
    assert bootstrap.trusted_issuers[0].issuer_id == "vendor.example"
    assert bootstrap.trusted_issuers[0].allows("vendor.foo", "SIGSTORE", "release@example.test")


def test_core_applies_file_entitlement_provider_and_trust_rule(tmp_path):
    from algites.lib.aac.coreimpl.core import AIcApplicationComponentCore
    bootstrap = AIcEntitlementBootstrapLoader.load_text(f'''
entitlement_bootstrap:
  schema_version: 2
  default_entitlement_profile: p
  licensing_scope_resolvers:
    - id: _AAC.context.mapping
      type: MAPPING
  entitlement_providers:
    - id: licenses
      type: FILESYSTEM
      settings:
        root: {str(tmp_path)!r}
        evidence_type: SIGSTORE
  trusted_issuers:
    - issuer_id: vendor.example
      component_ids: [vendor.foo]
      evidence_types: [SIGSTORE]
  entitlement_profiles:
    - id: p
      version: 1
      licensing_scopes:
        - id: workspace
          type: WORKSPACE
          resolver: _AAC.context.mapping
          entitlement_providers: [{{id: licenses}}]
''')
    core = AIcApplicationComponentCore()
    scopes = core.apply_entitlement_bootstrap(bootstrap, context={"WORKSPACE": {"id": "ws-1", "display_name": "Project One"}})
    assert core.entitlement_providers.get("licenses").root == tmp_path
    assert scopes[0].subject.display_name == "Project One"
    assert core.trusted_entitlement_issuers.has_rules()
