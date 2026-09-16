# Application Component Catalog Specification

## I. Purpose and scope

The AAC Catalog is the technology-neutral discovery index for Application Components. It allows a Core/product to discover component releases and package artifacts before those artifacts are downloaded or admitted into the runtime.

A catalog is **not** the artifact repository, **not** the runtime active-contract catalog, and **not** the entitlement/licensing service. These concerns remain separate:

```text
AAC Catalog
    discovery metadata + artifact locators

Artifact repository/storage
    package bytes + optional download authorization

Component artifact descriptor
    authoritative component contract after download

Entitlement infrastructure
    permission grants/evidence/remediation at runtime
```

Catalog metadata is sufficient for browsing and for the compatible target-state solver, but the downloaded artifact remains authoritative. Core MUST verify package identity/integrity and compare catalog-declared component contract metadata with the actual component descriptor before installation/admission.

## II. Mandatory catalog scope

Every catalog query MUST specify:

```text
product_id
technology_id
```

`product_id` identifies the host product for which components are being discovered. `technology_id` identifies the AAC technology/runtime profile, for example `PYTHON`, `JAVA`, or `MPS`.

Component identity/version is interpreted inside that technology scope. Equal component IDs and version strings in different technologies are independent releases and do not imply synchronized capabilities, requirements, release cadence, implementation, or licensing.

Therefore:

```text
(PYTHON, eu.algites.foo, version 3)
```

and

```text
(JAVA, eu.algites.foo, version 3)
```

are independent catalog releases.

AAC package-management queries do not browse across technologies. A marketplace or administrative portal MAY aggregate multiple technology-scoped queries for presentation, but cross-technology aggregation is outside the Core catalog query contract.

## III. Catalog document header

A baseline catalog document repeats its query scope in the document header:

```yaml
catalog:
  format_version: 4
  product_id: eu.algites.app.orchestrator
  technology_id: PYTHON
```

The repeated `product_id` and `technology_id` are a sanity/integrity check for source configuration. A provider queried for another scope MUST NOT return entries from a mismatching document as valid results.

The baseline document MAY additionally contain generation/publication metadata, but those fields do not replace package digests, artifact signatures, or component descriptors as trust authorities.

## IV. Component presentation metadata

Each catalog component entry MUST have a stable `component_id` and MAY provide discovery/presentation metadata:

```yaml
component_id: eu.algites.foo
name:
  text: Foo Integration
description:
  text: Integration with Foo services.
publisher:
  id: eu.algites
  name:
    text: Algites
homepage_url: https://...
documentation_url: https://...
support_url: https://...
entitlement_info_url: https://...
icon:
  url: https://...
categories: [integration]
tags: [foo, repository]
```

The catalog is a discovery/presentation index, so name/description/publisher and useful URLs are appropriate catalog data even though they are not runtime capability contracts.

`entitlement_info_url` is informational. It may lead to vendor licensing/pricing/trial/help information. The catalog does not define the licensing service/provider/protocol used to obtain entitlement evidence.

The baseline defines one icon URL. Rich marketplace media such as screenshots, videos, reviews, pricing tables, or merchandising are outside the AAC Catalog baseline and may be added by higher-level services.

## V. Releases

A component contains independently versioned releases:

```yaml
releases:
  - version: 3
    published_at: ...
    release_notes_url: ...
```

A catalog release describes the complete technical metadata needed for discovery and target-state solving in the catalog scope.

### V.1 Provided capabilities

`provides` enumerates capability IDs and contract versions supplied by the release:

```yaml
provides:
  - capability: eu.algites.foo.repository
    versions: [1, 2]
```

Catalog `provides` metadata MUST describe the actual component descriptor accurately. Core MUST reject/admonish a downloaded candidate whose authoritative descriptor disagrees.

### V.2 Requirements

`requires` declares consumer requirements relevant to compatibility solving:

```yaml
requires:
  - id: storage
    capability: _AAC.storage
    versions: [2, 3]
    cardinality: SINGLE
    mandatory: true
```

The baseline records capability, versions, cardinality, and mandatory/optional status. A future solver may use these values without first downloading every candidate artifact.

Catalog requirements do not replace the actual component descriptor. Target-state preflight after download/admission uses authoritative descriptor/contracts and ordinary Core resolution rules.

### V.3 Persistent schema summary

Catalog format version 2 introduced a release-level `persistent_schemas` summary used by the automatic target-state solver to decide whether a downgrade is safe enough to offer as an explicit alternative before downloading every candidate artifact. Catalog format version 4 makes the discriminator-specific identity fields explicit rather than overloading one generic `owner_id`.

Example:

```yaml
persistent_schemas:
  - kind: COMPONENT_CONFIGURATION
    schema_id: eu.algites.foo.configuration
    write_version: 4
  - kind: PROVIDER_CONFIGURATION
    provider_id: repository
    schema_id: eu.algites.foo.repository.configuration
    write_version: 2
  - kind: ENTITY_EXTENSION
    entity_type_id: _AO.entity.site
    schema_id: eu.algites.foo.site-extension
    write_version: 3
  - kind: ENTITY_EXTENSION
    entity_type_id: _AO.entity.service-def
    schema_id: eu.algites.foo.service-def-extension
    write_version: 2
```

`kind` is one of `COMPONENT_CONFIGURATION`, `PROVIDER_CONFIGURATION`, or `ENTITY_EXTENSION`. The identity selector is strict and depends on `kind`:

- `COMPONENT_CONFIGURATION` MUST NOT declare `provider_id` or `entity_type_id`;
- `PROVIDER_CONFIGURATION` MUST declare exactly `provider_id` and MUST NOT declare `entity_type_id`;
- `ENTITY_EXTENSION` MUST declare exactly `entity_type_id` and MUST NOT declare `provider_id`.

The same `kind` may occur more than once when its discriminator-specific identity differs. In particular, one component may extend multiple Core entity types, so multiple `ENTITY_EXTENSION` records with different `entity_type_id` values are valid. A release MUST NOT repeat the same `(kind, provider_id/entity_type_id)` identity.

Catalog formats 2 and 3 used the legacy field `owner_id` for both provider and entity-extension selectors. Readers may normalize those historical documents, but format 4 uses the semantic fields above.

The summary is not a migration instruction and does not make catalog metadata authoritative. After download, Core MUST derive the same summary from the component descriptor and reject the candidate when catalog and artifact metadata disagree.

Catalog format version 1 remains a valid discovery format but lacks the persistent-schema information needed for safe automatic downgrade alternatives. A solver MAY still use v1 releases for upgrade-only solutions.

## VI. Entitlement discovery metadata

Catalog format v3 introduced both the component's entitlement licensing-scope declarations and its capability-version permission declarations so browsing/package UI can explain licensing before the artifact is downloaded. Catalog format v4 names the latter `provided_capability_entitlements` to make explicit that the declarations apply to capabilities provided by this component.

Example:

```yaml
entitlement_licensing_scopes:
  - type: USER
    name:
      text: User
      resource_key: entitlement.licensing_scope.user.name
  - type: SOURCE_REPOSITORY
    name:
      text: Source repository
      resource_key: entitlement.licensing_scope.source_repository.name
    description:
      text: One logical source-control repository lineage.
      resource_key: entitlement.licensing_scope.source_repository.description

provided_capability_entitlements:
  - capability:
      id: eu.algites.foo.repository
      version: 1
    permissions:
      - id: read
      - id: write
        possible_licensing_scopes:
          - USER
          - SOURCE_REPOSITORY
```

A permission with no `possible_licensing_scopes` is available without external entitlement evidence; a non-empty list identifies the declared licensing-scope types through which it may be granted. Catalog licensing-scope declarations provide presentation/semantic metadata only. They do not say which concrete subject currently exists, which resolver/provider supplies it, how a grant is purchased, or whether it is effective.

After download, the component descriptor is authoritative. Core MUST compare catalog licensing-scope declarations and provided-capability-entitlement declarations with the artifact descriptor and reject material disagreement rather than silently rewriting either side.

Catalog format 3 used the earlier field name `capability_entitlements`; format 4 readers/writers use `provided_capability_entitlements`. The semantic identity remains component + provided capability id + provided capability version + permission id.

The catalog MUST NOT embed user/customer-specific grants or bind a component to one licensing-service implementation. `entitlement_info_url` remains sufficient baseline discovery information for licensing instructions.

## VII. Artifacts and locators

A technology-scoped release contains one or more artifact variants. Technology is not an artifact-variant dimension because it is already mandatory catalog scope.

Multiple artifact variants within one technology MAY exist for platform, architecture, packaging format, or another technology-specific deployment constraint:

```yaml
artifacts:
  - id: universal-wheel
    platforms: [linux, windows, macos]
    architectures: [x86_64, aarch64]
    package_format: PYTHON_WHEEL
    descriptor_path: foo/component.yml
    artifact_filename: foo.whl
    sha256: ...
```

Every artifact has a locator. Baseline locator types are:

```text
URI
REPOSITORY
```

A `URI` locator contains a directly fetchable URI (absolute or relative to the catalog source). A `REPOSITORY` locator identifies a repository adapter and technology-specific coordinates. Core can expose a repository locator even when the current product has no adapter capable of downloading it; attempted installation then fails with a clear unsupported-locator diagnostic rather than treating catalog discovery as invalid.

Artifact metadata MAY specify package verifier, authentication profile, detached sidecars and technology-specific metadata. Download/repository authorization is separate from entitlement-to-use.

### VII.1 Artifact variants are not cross-technology releases

A Python wheel and a Java JAR are not artifact variants of one AAC release merely because they have similar functionality. They live in independent `(product_id, technology_id)` catalog scopes. Cross-technology product presentation is a higher-level marketplace concern.

## VIII. Catalog provider SPI

AAC defines a query-oriented catalog provider SPI conceptually equivalent to:

```text
query(CatalogQuery) -> CatalogEntry[]
```

`CatalogQuery.product_id` and `CatalogQuery.technology_id` are mandatory. Additional filters MAY include:

```text
component_id
component version(s)
free-text search
provided capability
required capability
category
tag
```

The SPI is query-oriented even when a simple reference provider internally loads a complete JSON document and filters it locally. A future server-backed provider can perform filtering remotely without changing Core/UI contracts.

Provider implementations MUST preserve source provenance in returned entries.

## IX. Baseline providers

AAC defines reference behavior for:

```text
filesystem catalog provider
HTTP(S) catalog provider
```

Both consume the same versioned catalog document structure. The filesystem provider reads from product/local storage. The HTTP provider may reuse AAC authentication profiles and secret references.

The baseline does not require a dedicated catalog server. A static versioned document on an ordinary HTTP server is sufficient for development and small deployments.

Future providers MAY use REST APIs, databases, pagination, Python package indexes, Maven repositories, organization services, or other discovery mechanisms while implementing the same Catalog SPI.

## X. Multiple catalog sources

A Core/product MAY register multiple catalog sources, for example:

```text
Algites public
organization/private
local development
```

Query results retain source identity and source priority/provenance. Core MUST NOT silently merge conflicting metadata from two sources into one synthetic release. If the same component/version/artifact identity appears with different metadata, source provenance remains visible and the artifact/descriptor verification step remains authoritative.

Exact duplicate entries MAY be deduplicated for presentation, but conflict handling MUST remain deterministic and explainable.

## XI. Catalog trust and post-download verification

Catalog reachability does not establish trust. The package pipeline MUST continue to apply the ordinary digest/signature/verifier policy.

After download Core MUST verify at least:

```text
component_id
component version
provided capabilities/versions
required capabilities/versions/cardinality/mandatory status
entitlement licensing-scope declarations plus capability entitlement permission declarations and `possible_licensing_scopes`
```

against the authoritative component descriptor when those values are represented by the catalog.

A mismatch MUST block installation/admission of that candidate. The correct response is not to rewrite the descriptor to match the catalog or vice versa.

## XII. Package-management relationship

Catalog discovery and package storage/activation are distinct states:

```text
AVAILABLE IN CATALOG
        |
        v
DOWNLOADED
        |
        v
INSTALLED CANDIDATE
        |
        | target-state replacement/selection
        v
ACTIVE/SELECTED
```

Downloading or installing a package does not activate it. Installation without commercial entitlement is allowed by baseline AAC.

Entitlement is evaluated as runtime/contextual permissions. A component may be installed and active with only permissions that require no external entitlement, or with a reduced permission set/readiness. Product policy may choose stricter automation behavior, but manual package storage is not generically forbidden by missing entitlement.

## XIII. Package administration UI

A baseline package UI SHOULD separate:

```text
Browse catalog
Stored packages
```

Browse SHOULD support mandatory product/technology scope plus text/filtering and show, where available:

```text
name / component ID / release
publisher
artifact variant
provided capabilities
requirements
entitlement permission/scopes summary
entitlement_info_url
available/downloaded/installed state
catalog source provenance
```

Actions SHOULD include:

```text
Search
Download
Install
Restore obsolete
Validate replacement
Apply replacement
```

Install MUST NOT be presented as equivalent to activation. Entitlement acquisition/remediation SHOULD be shown as a separate concern, with `entitlement_info_url` as baseline informational navigation and product-specific remediation integrations where available.

## XIV. Solver relationship

The AAC automatic target-state solver consumes catalog release metadata inside one `(product_id, technology_id)` scope. It uses `provides`, `requires`, available versions, artifact availability and (in catalog format v2) persistent-schema summaries to find compatible upgrade sets before downloading all candidates. The normative solver policy is defined by `Application-Component-Target-State-Solver-Specification.md`.

Entitlement availability is not the same as technical compatibility. A technically compatible solution may be reported together with entitlement/remediation diagnostics rather than being discarded as "no compatible solution" solely because a commercial permission is not currently granted.

A downgrade candidate is subject to stricter automatic-solver policy than manual replacement. The solver may offer it only as an explicit alternative when catalog/descriptor metadata proves that relevant persistent schema identities/write versions are unchanged.

After artifacts are downloaded, normal artifact verification, descriptor comparison and target-state preflight remain mandatory.

## XV. Baseline invariants

1. Every catalog query is scoped by mandatory `product_id` and `technology_id`.
2. Equal component IDs/versions in different technologies are independent.
3. Catalog documents repeat product/technology scope in their header.
4. Catalog is discovery metadata, not artifact repository, entitlement service, or runtime contract catalog.
5. Component releases declare capability provides/requires sufficiently for discovery/solver use.
6. Catalog format v3 carries entitlement licensing-scope declarations plus permission `possible_licensing_scopes`; permissions with an empty list need no external entitlement evidence.
7. Licensing-service/provider details are outside catalog baseline; `entitlement_info_url` is informational discovery metadata.
8. Technology-specific artifact variants may differ by platform/architecture/format but not by technology scope.
9. Catalog provider SPI is query-oriented; simple filesystem/HTTP providers may filter a whole document locally.
10. Catalog source provenance is preserved and conflicting source metadata is not silently merged.
11. Downloaded artifact descriptor and verification policy are authoritative over catalog metadata.
12. Missing entitlement does not generally prevent package download/installation.
13. Package browsing/install UI and the target-state solver use the same catalog contract.
14. Catalog format v2 introduced persistent-schema summaries for solver downgrade safety; format v3 additionally carries first-class entitlement licensing-scope declarations, and all repeated metadata is verified against the downloaded descriptor.
