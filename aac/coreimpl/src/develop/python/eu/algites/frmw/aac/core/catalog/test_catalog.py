from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from eu.algites.frmw.aac.core.catalog.api import (
    AIcCatalogQuery,
    AInCatalogPersistentSchemaKind,
)
from eu.algites.frmw.aac.core.packages.api import AIcPackageStoreLayout, AInStoredPackageState
from eu.algites.frmw.aac.core.verification.api import AIcVerificationOutput, AIiPackageVerifier
from eu.algites.frmw.aac.core.bootstrap.loaders import AIcCatalogBootstrapLoader
from eu.algites.frmw.aac.core.catalog.loading import AIcCatalogDocumentLoader, AIcFilesystemCatalogProvider
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore


class _Verifier(AIiPackageVerifier):
    def verify(self, verification_input):
        return AIcVerificationOutput(True, verifier_id="test", signer_identity="catalog-test")


def _wheel(root: Path) -> tuple[Path, str, str]:
    root.mkdir(parents=True, exist_ok=True)
    wheel = root / "demo.whl"
    descriptor_path = "demo/component.yml"
    descriptor = '''Component:
  Id: com.example.demo
  Version: 2
  CapabilityProviders:
    - Id: main
      Capabilities:
        - Id: com.example.cap
          Versions: [1, 2]
      ImplementationClasses:
      - TechnologyKind: python
        ClassName: demo:Provider
      Requirements:
        - Id: storage
          Capability: com.example.storage
          Versions: [3]
          Mandatory: true
  EntitlementLicensingScopes:
    - Type: USER
      Name: User
      Description: One identified user.
    - Type: ORGANIZATION
      Name: Organization
      Description: One organization.
  ProvidedCapabilityEntitlements:
    - Capability:
        Id: com.example.cap
        Version: 2
      Permissions:
        - Id: basic
        - Id: PRO
          PossibleLicensingScopes: [USER, ORGANIZATION]
'''
    with ZipFile(wheel, "w") as archive:
        archive.writestr(descriptor_path, descriptor)
    return wheel, descriptor_path, hashlib.sha256(wheel.read_bytes()).hexdigest()


def _catalog_text(wheel: Path, descriptor_path: str, digest: str) -> str:
    return f'''Catalog:
  FormatVersion: 1
  ProductId: eu.algites.app.orchestrator
  TechnologyId: PYTHON
  Components:
    - ComponentId: com.example.demo
      Name: Demo component
      Description: Test catalog component
      Publisher:
        Id: com.example
        Name: Example Inc.
      HomepageUrl: https://example.invalid/demo
      DocumentationUrl: https://example.invalid/demo/docs
      EntitlementInfoUrl: https://example.invalid/demo/license
      Icon:
        Url: https://example.invalid/demo/icon.png
      Categories: [integration]
      Tags: [demo, test]
      Releases:
        - Version: 2
          Provides:
            - Capability: com.example.cap
              Versions: [1, 2]
          Requires:
            - Id: storage
              Capability: com.example.storage
              Versions: [3]
              Mandatory: true
          EntitlementLicensingScopes:
            - Type: USER
              Name: User
              Description: One identified user.
            - Type: ORGANIZATION
              Name: Organization
              Description: One organization.
          ProvidedCapabilityEntitlements:
            - Capability:
                Id: com.example.cap
                Version: 2
              Permissions:
                - Id: basic
                - Id: PRO
                  PossibleLicensingScopes: [USER, ORGANIZATION]
          Artifacts:
            - Id: universal-wheel
              Locator:
                Type: uri
                Uri: {wheel.name}
              ArtifactFilename: demo.whl
              PackageFormat: PYTHON_WHEEL
              DescriptorPath: {descriptor_path}
              Sha256: {digest}
              RuntimePackage: demo
              VerifierId: test
'''


def test_catalog_query_is_scoped_by_product_and_technology_and_filters_locally(tmp_path):
    wheel, descriptor_path, digest = _wheel(tmp_path)
    text = _catalog_text(wheel, descriptor_path, digest)
    document = AIcCatalogDocumentLoader.load_text(text, source="catalog.yml", source_uri=str(tmp_path / "catalog.yml"))
    provider = AIcFilesystemCatalogProvider("local", str(tmp_path / "catalog.yml"))
    (tmp_path / "catalog.yml").write_text(text, encoding="utf-8")

    assert document.product_id == "eu.algites.app.orchestrator"
    assert document.technology_id == "PYTHON"
    results = provider.query(AIcCatalogQuery(
        "eu.algites.app.orchestrator", "PYTHON", text="demo", provides_capability_id="com.example.cap"
    ))
    assert len(results) == 1
    assert results[0].component_id == "com.example.demo"
    assert results[0].component.entitlement_info_url.endswith("/license")
    assert [scope.type for scope in results[0].release.entitlement_licensing_scopes] == ["USER", "ORGANIZATION"]
    assert results[0].release.entitlement_licensing_scopes[0].name.text == "User"
    assert results[0].release.provided_capability_entitlements[0].permission("basic").implicit
    assert results[0].release.provided_capability_entitlements[0].permission("PRO").possible_licensing_scope_types == ("USER", "ORGANIZATION")
    assert Path(results[0].release.artifacts[0].locator.uri) == wheel
    assert provider.query(AIcCatalogQuery("other.product", "PYTHON")) == ()
    assert provider.query(AIcCatalogQuery("eu.algites.app.orchestrator", "JAVA")) == ()



def test_catalog_exposes_persistent_schema_summary_for_solver(tmp_path):
    wheel, descriptor_path, digest = _wheel(tmp_path)
    text = _catalog_text(wheel, descriptor_path, digest)
    text = text.replace(
        "          Artifacts:\n",
        "          PersistentSchemas:\n"
        "            - Kind: component_configuration\n"
        "              SchemaId: com.example.demo.config\n"
        "              WriteVersion: 2\n"
        "            - Kind: provider_configuration\n"
        "              ProviderId: main\n"
        "              SchemaId: com.example.demo.main.config\n"
        "              WriteVersion: 4\n"
        "            - Kind: data_entity\n"
        "              SchemaId: com.example.demo.site-data\n"
        "              ReadableVersions: [1, 2]\n"
        "              WritableVersions: [2]\n"
        "              PreferredWriteVersion: 2\n"
        "          Artifacts:\n",
        1,
    )
    document = AIcCatalogDocumentLoader.load_text(text, source="catalog.yml")
    release = document.components[0].releases[0]
    assert [(item.kind, item.identity[1], item.schema_id, item.write_version) for item in release.persistent_schemas] == [
        (AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, None, "com.example.demo.config", 2),
        (AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION, "main", "com.example.demo.main.config", 4),
        (AInCatalogPersistentSchemaKind.DATA_ENTITY, "com.example.demo.site-data", "com.example.demo.site-data", None),
    ]
    data_entity = release.persistent_schemas[2]
    assert data_entity.readable_versions == (1, 2)
    assert data_entity.writable_versions == (2,)
    assert data_entity.preferred_write_version == 2

def test_catalog_bootstrap_registers_filesystem_provider_and_core_can_download_install_without_entitlement(tmp_path):
    wheel, descriptor_path, digest = _wheel(tmp_path)
    catalog_path = tmp_path / "catalog.yml"
    catalog_path.write_text(_catalog_text(wheel, descriptor_path, digest), encoding="utf-8")
    bootstrap = AIcCatalogBootstrapLoader.load_text(f'''CatalogBootstrap:
  SchemaVersion: 1
  ProductId: eu.algites.app.orchestrator
  TechnologyId: PYTHON
  Sources:
    - Id: local
      Type: FILESYSTEM
      Uri: {catalog_path}
''')

    core = AIcApplicationComponentCore()
    core.configure_package_management(AIcPackageStoreLayout(str(tmp_path / "product")))
    core.register_package_verifier("test", _Verifier())
    core.apply_catalog_bootstrap(bootstrap)

    entries = core.query_default_catalog(text="demo")
    assert len(entries) == 1
    installed = core.install_catalog_package(
        "local", "eu.algites.app.orchestrator", "PYTHON", "com.example.demo", 2, "universal-wheel"
    )
    assert installed.state is AInStoredPackageState.INSTALLED
    assert core.package_manager.package_store.records(AInStoredPackageState.DOWNLOADED, "com.example.demo")
    # PRO requires an entitlement licensing scope, but absence of a grant does not block package installation.
    assert entries[0].release.provided_capability_entitlements[0].permission("PRO").possible_licensing_scope_types


def test_catalog_metadata_mismatch_is_rejected_after_download(tmp_path):
    wheel, descriptor_path, digest = _wheel(tmp_path)
    text = _catalog_text(wheel, descriptor_path, digest).replace("Versions: [1, 2]", "Versions: [1]", 1)
    catalog_path = tmp_path / "catalog.yml"
    catalog_path.write_text(text, encoding="utf-8")
    core = AIcApplicationComponentCore()
    core.configure_package_management(AIcPackageStoreLayout(str(tmp_path / "product")))
    core.register_package_verifier("test", _Verifier())
    core.apply_catalog_bootstrap(AIcCatalogBootstrapLoader.load_text(f'''CatalogBootstrap:
  SchemaVersion: 1
  ProductId: eu.algites.app.orchestrator
  TechnologyId: PYTHON
  Sources:
    - Id: local
      Type: FILESYSTEM
      Uri: {catalog_path}
'''))
    with pytest.raises(ValueError, match="provides metadata"):
        core.download_catalog_package(
            "local", "eu.algites.app.orchestrator", "PYTHON", "com.example.demo", 2, "universal-wheel"
        )


def test_http_catalog_provider_reads_same_document_and_resolves_relative_artifact_uri(tmp_path):
    import contextlib
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    wheel, descriptor_path, digest = _wheel(tmp_path)
    catalog_path = tmp_path / "catalog.yml"
    catalog_path.write_text(_catalog_text(wheel, descriptor_path, digest), encoding="utf-8")

    class _QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    handler = functools.partial(_QuietHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from eu.algites.frmw.aac.core.catalog.loading import AIcHttpCatalogProvider

        base = f"http://127.0.0.1:{server.server_port}/"
        provider = AIcHttpCatalogProvider("http", base + "catalog.yml")
        (entry,) = provider.query(AIcCatalogQuery("eu.algites.app.orchestrator", "PYTHON", text="Demo"))
        assert entry.source_id == "http"
        assert entry.release.artifacts[0].locator.uri == base + "demo.whl"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_catalog_uses_explicit_persistent_schema_discriminators_and_provided_entitlements():
    text = """
Catalog:
  FormatVersion: 1
  ProductId: p
  TechnologyId: python
  Components:
    - ComponentId: com.example.foo
      Releases:
        - Version: 1
          Provides:
            - Capability: com.example.repository
              Versions: [1]
          EntitlementLicensingScopes:
            - Type: USER
          ProvidedCapabilityEntitlements:
            - Capability: {Id: com.example.repository, Version: 1}
              Permissions:
                - Id: write
                  PossibleLicensingScopes: [USER]
          PersistentSchemas:
            - Kind: component_configuration
              SchemaId: foo.configuration
              WriteVersion: 1
            - Kind: provider_configuration
              ProviderId: repository
              SchemaId: foo.repository.configuration
              WriteVersion: 2
            - Kind: data_entity
              SchemaId: foo.site-data
              ReadableVersions: [2, 3]
              WritableVersions: [3]
              PreferredWriteVersion: 3
            - Kind: data_entity
              SchemaId: foo.service-def-data
              ReadableVersions: [1, 2]
              WritableVersions: [2]
              PreferredWriteVersion: 2
          Artifacts:
            - Id: py
              Locator: {Type: uri, Uri: file:///tmp/foo.whl}
              ArtifactFilename: foo.whl
              PackageFormat: wheel
              DescriptorPath: component.yml
              Sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    """
    document = AIcCatalogDocumentLoader.load_text(text)
    release = document.components[0].releases[0]
    assert release.provided_capability_entitlements[0].permission("write").possible_licensing_scope_types == ("USER",)
    assert [item.identity for item in release.persistent_schemas] == [
        ("component_configuration", None),
        ("provider_configuration", "repository"),
        ("data_entity", "foo.site-data"),
        ("data_entity", "foo.service-def-data"),
    ]


def test_catalog_persistent_schema_discriminator_fields_are_strict():
    import pytest
    from eu.algites.frmw.aac.core.catalog.api import AIcCatalogPersistentSchema, AInCatalogPersistentSchemaKind
    with pytest.raises(ValueError):
        AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.COMPONENT_CONFIGURATION, "x", 1, provider_id="p")
    with pytest.raises(ValueError):
        AIcCatalogPersistentSchema(AInCatalogPersistentSchemaKind.PROVIDER_CONFIGURATION, "x", 1)
    with pytest.raises(ValueError):
        AIcCatalogPersistentSchema(
            AInCatalogPersistentSchemaKind.DATA_ENTITY, "x", write_version=1, readable_versions=(1,)
        )
    with pytest.raises(ValueError):
        AIcCatalogPersistentSchema(
            AInCatalogPersistentSchemaKind.DATA_ENTITY, "x", readable_versions=(1,), writable_versions=(2,),
            preferred_write_version=3,
        )
