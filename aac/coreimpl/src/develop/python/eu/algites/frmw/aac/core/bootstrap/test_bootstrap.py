import pytest

from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.bootstrap.loaders import AIcConfigurationBootstrapLoader, AIcEntitlementBootstrapLoader


CONFIG_BOOTSTRAP = """
ConfigurationBootstrap:
  SchemaVersion: 1
  DefaultConfigurationProfile: customer-project
  WorkspaceConfigurationProfiles: allowed_if_signed
  MandatoryConfigurationScopeDefinitionIds: [system]
  ConfigurationScopeResolvers:
    - Id: mapping
      Type: STATIC_CONTEXT
  ConfigurationProviders:
    - Id: system-config
      Type: file
    - Id: customer-config
      Type: HTTPS
  ConfigurationProfiles:
    - Id: customer-project
      Version: 1
      ConfigurationScopes:
        - Id: user
          Type: USER
          Resolver: mapping
        - Id: workspace
          Type: WORKSPACE
          Resolver: mapping
        - Id: customer
          Type: CUSTOMER
          Resolver: mapping
          ConfigurationProviders:
            - Id: customer-config
              Priority: 100
        - Id: system
          Type: SYSTEM
          Resolver: mapping
          Mandatory: true
          ConfigurationProviders:
            - Id: system-config
              Priority: 100
"""


def test_configuration_bootstrap_keeps_custom_scope_types_as_strings():
    bootstrap = AIcConfigurationBootstrapLoader.load_text(CONFIG_BOOTSTRAP)
    profile = bootstrap.profile()
    assert [item.configuration_scope_type for item in profile.configuration_scopes] == [
        "USER", "WORKSPACE", "CUSTOMER", "SYSTEM"
    ]
    assert bootstrap.workspace_configuration_profiles.value == "allowed_if_signed"


def test_configuration_bootstrap_schema_is_fixed_and_rejects_unknown_fields():
    with pytest.raises(AIxDescriptorError):
        AIcConfigurationBootstrapLoader.load_text(CONFIG_BOOTSTRAP.replace("SchemaVersion: 1", "SchemaVersion: 2"))


def test_entitlement_bootstrap_uses_separately_named_scopes_and_providers():
    bootstrap = AIcEntitlementBootstrapLoader.load_text("""
EntitlementBootstrap:
  SchemaVersion: 1
  DefaultEntitlementProfile: project
  LicensingScopeResolvers:
    - Id: mapping
      Type: STATIC_CONTEXT
  EntitlementProviders:
    - Id: licensing
      Type: HTTPS
  EntitlementProfiles:
    - Id: project
      Version: 1
      LicensingScopes:
        - Id: workspace
          Type: WORKSPACE
          Resolver: mapping
          EntitlementProviders:
            - Id: licensing
""")
    assert bootstrap.profile().licensing_scopes[0].licensing_scope_type == "WORKSPACE"
    assert bootstrap.entitlement_providers[0].id == "licensing"


def test_security_bootstrap_is_fixed_schema_and_configuration_provider_can_reference_auth_profile(tmp_path, monkeypatch):
    from eu.algites.frmw.aac.core.bootstrap.loaders import AIcSecurityBootstrapLoader
    from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore

    monkeypatch.setenv("AAC_REMOTE_TOKEN", "abc")
    security = AIcSecurityBootstrapLoader.load_text("""
SecurityBootstrap:
  SchemaVersion: 1
  SecretProviders:
    - Id: env
      Type: ENVIRONMENT
      BootstrapSafe: true
  AuthenticationProfiles:
    - Id: remote
      Mechanism: BEARER
      Parameters:
        token:
          SecretReference:
            SecretProviderId: env
            Key: AAC_REMOTE_TOKEN
""")
    config = AIcConfigurationBootstrapLoader.load_text(f"""
ConfigurationBootstrap:
  SchemaVersion: 1
  DefaultConfigurationProfile: p
  ConfigurationScopeResolvers:
    - Id: mapping2
      Type: MAPPING
  ConfigurationProviders:
    - Id: local
      Type: FILESYSTEM
      Settings:
        root: {str(tmp_path)!r}
    - Id: remote
      Type: HTTP
      AuthenticationProfileId: remote
      Settings:
        base_url: http://127.0.0.1:9/configuration
        read_only: true
  ConfigurationProfiles:
    - Id: p
      Version: 1
      ConfigurationScopes:
        - Id: system
          Type: SYSTEM
          Resolver: mapping2
          ConfigurationProviders:
            - Id: local
""")
    core = AIcApplicationComponentCore()
    core.apply_security_bootstrap(security)
    scopes = core.apply_configuration_bootstrap(config)
    assert scopes[0].configuration_scope.type == "SYSTEM"
    assert core.configuration_providers.contains("local")
    assert core.configuration_providers.contains("remote")


def test_configuration_provider_rejects_non_bootstrap_safe_authentication_profile(monkeypatch):
    from eu.algites.frmw.aac.core.bootstrap.loaders import AIcSecurityBootstrapLoader
    from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore

    monkeypatch.setenv("AAC_REMOTE_TOKEN", "abc")
    security = AIcSecurityBootstrapLoader.load_text("""
SecurityBootstrap:
  SchemaVersion: 1
  SecretProviders:
    - Id: env
      Type: ENVIRONMENT
      BootstrapSafe: false
  AuthenticationProfiles:
    - Id: remote
      Mechanism: BEARER
      Parameters:
        token:
          SecretReference:
            SecretProviderId: env
            Key: AAC_REMOTE_TOKEN
""")
    config = AIcConfigurationBootstrapLoader.load_text("""
ConfigurationBootstrap:
  SchemaVersion: 1
  DefaultConfigurationProfile: p
  ConfigurationScopeResolvers:
    - Id: mapping2
      Type: MAPPING
  ConfigurationProviders:
    - Id: remote
      Type: HTTP
      AuthenticationProfileId: remote
      Settings:
        base_url: http://127.0.0.1:9/configuration
  ConfigurationProfiles:
    - Id: p
      Version: 1
      ConfigurationScopes:
        - Id: system
          Type: SYSTEM
          Resolver: mapping2
""")
    core = AIcApplicationComponentCore()
    core.apply_security_bootstrap(security)
    with pytest.raises(ValueError, match="not bootstrap-safe"):
        core.apply_configuration_bootstrap(config)


def test_external_configuration_profile_can_be_loaded_from_trusted_file_source(tmp_path):
    from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore

    profile_path = tmp_path / "profile.yml"
    profile_path.write_text("""
ConfigurationProfile:
  Id: external
  Version: 1
  ConfigurationScopes:
    - Id: system
      Type: SYSTEM
      Resolver: mapping
      ConfigurationProviders:
        - Id: local
""", encoding="utf-8")
    bootstrap = AIcConfigurationBootstrapLoader.load_text(f"""
ConfigurationBootstrap:
  SchemaVersion: 1
  DefaultConfigurationProfile: external
  ConfigurationScopeResolvers:
    - Id: mapping
      Type: MAPPING
  ConfigurationProviders:
    - Id: local
      Type: FILESYSTEM
      Settings:
        root: {str(tmp_path / 'config')!r}
  ConfigurationProfileSources:
    - Id: external-source
      Uri: {str(profile_path)!r}
  ConfigurationProfiles:
    - Id: fallback
      Version: 1
      ConfigurationScopes:
        - Id: system
          Type: SYSTEM
          Resolver: mapping
""")
    core = AIcApplicationComponentCore()
    scopes = core.apply_configuration_bootstrap(bootstrap)
    assert core.configuration_bootstrap.profile().id == "external"
    assert scopes[0].configuration_providers[0].configuration_provider_id == "local"


def test_entitlement_bootstrap_loads_file_provider_and_trusted_issuer():
    bootstrap = AIcEntitlementBootstrapLoader.load_text('''
EntitlementBootstrap:
  SchemaVersion: 1
  DefaultEntitlementProfile: p
  LicensingScopeResolvers:
    - Id: mapping
      Type: MAPPING
  EntitlementProviders:
    - Id: licenses
      Type: file
      Settings: {root: /tmp/licenses, evidence_type: SIGSTORE}
  TrustedIssuers:
    - IssuerId: vendor.example
      ComponentIds: [vendor.foo]
      EvidenceTypes: [SIGSTORE]
      SignerIdentities: [release@example.test]
  EntitlementProfiles:
    - Id: p
      Version: 1
      LicensingScopes:
        - Id: workspace
          Type: WORKSPACE
          Resolver: mapping
          EntitlementProviders: [{Id: licenses}]
''')
    assert bootstrap.entitlement_providers[0].type == "file"
    assert bootstrap.trusted_issuers[0].issuer_id == "vendor.example"
    assert bootstrap.trusted_issuers[0].allows("vendor.foo", "SIGSTORE", "release@example.test")


def test_core_applies_file_entitlement_provider_and_trust_rule(tmp_path):
    from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
    bootstrap = AIcEntitlementBootstrapLoader.load_text(f'''
EntitlementBootstrap:
  SchemaVersion: 1
  DefaultEntitlementProfile: p
  LicensingScopeResolvers:
    - Id: _AAC.context.mapping
      Type: MAPPING
  EntitlementProviders:
    - Id: licenses
      Type: FILESYSTEM
      Settings:
        root: {str(tmp_path)!r}
        evidence_type: SIGSTORE
  TrustedIssuers:
    - IssuerId: vendor.example
      ComponentIds: [vendor.foo]
      EvidenceTypes: [SIGSTORE]
  EntitlementProfiles:
    - Id: p
      Version: 1
      LicensingScopes:
        - Id: workspace
          Type: WORKSPACE
          Resolver: _AAC.context.mapping
          EntitlementProviders: [{{Id: licenses}}]
''')
    core = AIcApplicationComponentCore()
    scopes = core.apply_entitlement_bootstrap(bootstrap, context={"WORKSPACE": {"Id": "ws-1", "DisplayName": "Project One"}})
    assert core.entitlement_providers.get("licenses").root == tmp_path
    assert scopes[0].subject.display_name == "Project One"
    assert core.trusted_entitlement_issuers.has_rules()
