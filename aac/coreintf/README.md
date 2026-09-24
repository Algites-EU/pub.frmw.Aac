# AAC Core Interfaces

Python language binding of the technology-neutral Algites Application Components contracts.

Public import namespace: `algites.lib.aac.coreintf`.

This artifact is the dependency boundary for Python AAC components. It does not depend on `coreimpl` or any concrete provider implementation.

It defines the public models and SPIs for:

- component descriptors, multi-capability provider definitions/instances, and per-instance READ_ONLY/READ_WRITE access mode;
- capability contracts, mandatory nested capability groups, finite version sets, invocation, and generic directional Operation Interaction with Core-owned execution lifecycle, `interaction_revision` / `state_result_revision`, operation-declared complete/delta delivery modes, caller acceptance tracking, progress/status/detail/diagnostic events, cooperative cancellation and foreground/background interaction mode;
- Core-owned binding preferences and lifecycle/runtime interfaces;
- exact `COMPONENT` / `PROVIDER_INSTANCE` configuration targets, scopes, providers and atomic mutation contracts;
- persisted configuration schemas, versioned payloads and configuration migrators;
- generic Data Entity identity/envelopes, ACTIVE/TOMBSTONE state, typed polymorphic view/codec binding contracts, field-level reference metadata, Data Entity migrator contracts, and canonical direct storage capability schemas;
- authentication profiles, secret references and authorization contracts;
- first-class entitlement licensing-scope declarations (`AIcEntitlementLicensingScopeDescriptor`) with localized display metadata, provided-capability-version permissions with `possible_licensing_scopes`, resolver/evidence/trusted-subject contracts, remediation and refresh semantics;
- platform-neutral catalog query/models/provider SPI, catalog bootstrap metadata, package sources, package-store/Core-state layout, immutable provenance, workspace requirements/locks, unified mutable-record revisions, persistence capabilities/read-set/write-set contracts, active package-set revisions, generic crash-recovery transaction phases and transactional component-replacement plans/results with blocking vs. degradation diagnostics;
- typed `READY / DEGRADED / NOT_READY` operational-readiness models, structured reasons and declarative readiness requirements;
- target-state solver request/result models, structured causal explanations, bounded alternatives, entitlement/readiness diagnostics, and package-preparation selections;
- presentation metadata (`AIcDisplayText`) and generated-binding metadata.

Canonical schemas live in the technology-neutral `src/product/schema/algites/lib/aac/coreintf/<functional-area>/` source tree and are packaged into technology distributions during build. Because AAC is not yet deployed, internal AAC document formats currently have one authoritative revision, version `1` (for example `component-descriptor_1.json`, `catalog_1.json`, `entitlement-document_1.json`, and `catalog-bootstrap_1.json`); development-time historical variants are not retained as compatibility layers. Every JSON Schema self-identifies through `x-aac-schema-id` and `x-aac-schema-version`.

Component version is release provenance; persisted-data compatibility is governed by explicit schema identities/versions, direct-readable declarations and migration paths; runtime interpretation is independent from optional persistence convergence.

Mutable AAC persistence is independent from those payload-schema versions: Core/provider records carry a persistence-owned `record_revision`, whose representation is declared by the persistence contract (`MONOTONIC_INTEGER` or `OPAQUE_STRING`). Generic APIs use compare-and-swap and `READ / SINGLE_RECORD_CAS / MULTI_RECORD_TRANSACTION` capability declarations.
