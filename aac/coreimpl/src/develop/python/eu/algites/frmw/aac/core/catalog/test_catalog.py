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
    descriptor = '''component:
  id: com.example.demo
  version: 2
  capability_providers:
    - id: main
      capabilities:
        - id: com.example.cap
          versions: [1, 2]
      implementation_classes:
      - technology-kind: python
        class-name: demo:Provider
      requirements:
        - id: storage
          capability: com.example.storage
          versions: [3]
          mandatory: true
  entitlement_licensing_scopes:
    - type: USER
      name: User
      description: One identified user.
    - type: ORGANIZATION
      name: Organization
      description: One organization.
  provided_capability_entitlements:
    - capability:
        id: com.example.cap
        version: 2
      permissions:
        - id: BASIC
        - id: PRO
          possible_licensing_scopes: [USER, ORGANIZATION]
'''
    with ZipFile(wheel, "w") as archive:
        archive.writestr(descriptor_path, descriptor)
    return wheel, descriptor_path, hashlib.sha256(wheel.read_bytes()).hexdigest()


def _catalog_text(wheel: Path, descriptor_path: str, digest: str) -> str:
    return f'''catalog:
  format_version: 1
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
  components:
    - component_id: com.example.demo
      name: Demo component
      description: Test catalog component
      publisher:
        id: com.example
        name: Example Inc.
      homepage_url: https://example.invalid/demo
      documentation_url: https://example.invalid/demo/docs
      entitlement_info_url: https://example.invalid/demo/license
      icon:
        url: https://example.invalid/demo/icon.png
      categories: [integration]
      tags: [demo, test]
      releases:
        - version: 2
          provides:
            - capability: com.example.cap
              versions: [1, 2]
          requires:
            - id: storage
              capability: com.example.storage
              versions: [3]
              mandatory: true
          entitlement_licensing_scopes:
            - type: USER
              name: User
              description: One identified user.
            - type: ORGANIZATION
              name: Organization
              description: One organization.
          provided_capability_entitlements:
            - capability:
                id: com.example.cap
                version: 2
              permissions:
                - id: BASIC
                - id: PRO
                  possible_licensing_scopes: [USER, ORGANIZATION]
          artifacts:
            - id: universal-wheel
              locator:
                type: URI
                uri: {wheel.name}
              artifact_filename: demo.whl
              package_format: PYTHON_WHEEL
              descriptor_path: {descriptor_path}
              sha256: {digest}
              runtime_package: demo
              verifier_id: test
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
    assert results[0].release.provided_capability_entitlements[0].permission("BASIC").implicit
    assert results[0].release.provided_capability_entitlements[0].permission("PRO").possible_licensing_scope_types == ("USER", "ORGANIZATION")
    assert Path(results[0].release.artifacts[0].locator.uri) == wheel
    assert provider.query(AIcCatalogQuery("other.product", "PYTHON")) == ()
    assert provider.query(AIcCatalogQuery("eu.algites.app.orchestrator", "JAVA")) == ()



def test_catalog_exposes_persistent_schema_summary_for_solver(tmp_path):
    wheel, descriptor_path, digest = _wheel(tmp_path)
    text = _catalog_text(wheel, descriptor_path, digest)
    text = text.replace(
        "          artifacts:\n",
        "          persistent_schemas:\n"
        "            - kind: COMPONENT_CONFIGURATION\n"
        "              schema_id: com.example.demo.config\n"
        "              write_version: 2\n"
        "            - kind: PROVIDER_CONFIGURATION\n"
        "              provider_id: main\n"
        "              schema_id: com.example.demo.main.config\n"
        "              write_version: 4\n"
        "            - kind: DATA_ENTITY\n"
        "              schema_id: com.example.demo.site-data\n"
        "              readable_versions: [1, 2]\n"
        "              writable_versions: [2]\n"
        "              preferred_write_version: 2\n"
        "          artifacts:\n",
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
    bootstrap = AIcCatalogBootstrapLoader.load_text(f'''catalog_bootstrap:
  schema_version: 1
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
  sources:
    - id: local
      type: FILESYSTEM
      uri: {catalog_path}
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
    text = _catalog_text(wheel, descriptor_path, digest).replace("versions: [1, 2]", "versions: [1]", 1)
    catalog_path = tmp_path / "catalog.yml"
    catalog_path.write_text(text, encoding="utf-8")
    core = AIcApplicationComponentCore()
    core.configure_package_management(AIcPackageStoreLayout(str(tmp_path / "product")))
    core.register_package_verifier("test", _Verifier())
    core.apply_catalog_bootstrap(AIcCatalogBootstrapLoader.load_text(f'''catalog_bootstrap:
  schema_version: 1
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
  sources:
    - id: local
      type: FILESYSTEM
      uri: {catalog_path}
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
catalog:
  format_version: 1
  product_id: p
  technology_id: python
  components:
    - component_id: com.example.foo
      releases:
        - version: 1
          provides:
            - capability: com.example.repository
              versions: [1]
          entitlement_licensing_scopes:
            - type: USER
          provided_capability_entitlements:
            - capability: {id: com.example.repository, version: 1}
              permissions:
                - id: WRITE
                  possible_licensing_scopes: [USER]
          persistent_schemas:
            - kind: COMPONENT_CONFIGURATION
              schema_id: foo.configuration
              write_version: 1
            - kind: PROVIDER_CONFIGURATION
              provider_id: repository
              schema_id: foo.repository.configuration
              write_version: 2
            - kind: DATA_ENTITY
              schema_id: foo.site-data
              readable_versions: [2, 3]
              writable_versions: [3]
              preferred_write_version: 3
            - kind: DATA_ENTITY
              schema_id: foo.service-def-data
              readable_versions: [1, 2]
              writable_versions: [2]
              preferred_write_version: 2
          artifacts:
            - id: py
              locator: {type: URI, uri: file:///tmp/foo.whl}
              artifact_filename: foo.whl
              package_format: wheel
              descriptor_path: component.yml
              sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    """
    document = AIcCatalogDocumentLoader.load_text(text)
    release = document.components[0].releases[0]
    assert release.provided_capability_entitlements[0].permission("WRITE").possible_licensing_scope_types == ("USER",)
    assert [item.identity for item in release.persistent_schemas] == [
        ("COMPONENT_CONFIGURATION", None),
        ("PROVIDER_CONFIGURATION", "repository"),
        ("DATA_ENTITY", "foo.site-data"),
        ("DATA_ENTITY", "foo.service-def-data"),
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
