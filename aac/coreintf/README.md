# AAC Core Interfaces

Python language binding of the technology-neutral Algites Application Components contracts.

Public import namespace: `algites.lib.aac.coreintf`.

This artifact is the dependency boundary for Python AAC components. It does not depend on `coreimpl` or any concrete provider implementation.

It defines the public models and SPIs for:

- component descriptors, provider definitions and provider instances;
- capability contracts, finite version sets, invocation and observation;
- Core-owned binding preferences and lifecycle/runtime interfaces;
- exact `COMPONENT` / `PROVIDER_INSTANCE` configuration targets, scopes, providers and atomic mutation contracts;
- persisted configuration schemas, versioned payloads and configuration migrators;
- Core-entity semantic extension envelopes, entity contexts, stores and extension-data migrators;
- authentication profiles, secret references and authorization contracts;
- first-class entitlement licensing-scope declarations (`AIcEntitlementLicensingScopeDescriptor`) with localized display metadata, provided-capability-version permissions with `possible_licensing_scopes`, resolver/evidence/trusted-subject contracts, remediation and refresh semantics;
- platform-neutral catalog query/models/provider SPI, catalog bootstrap metadata, package sources, package-store/Core-state layout, immutable provenance, workspace requirements/locks, unified mutable-record revisions, persistence capabilities/read-set/write-set contracts, active package-set revisions, generic crash-recovery transaction phases and transactional component-replacement plans/results with blocking vs. degradation diagnostics;
- typed `READY / DEGRADED / NOT_READY` operational-readiness models, structured reasons and declarative readiness requirements;
- target-state solver request/result models, structured causal explanations, bounded alternatives, entitlement/readiness diagnostics, and package-preparation selections;
- presentation metadata (`AIcDisplayText`) and generated-binding metadata.

Canonical versioned schemas now live in the technology-neutral `src/product/schema/algites/lib/aac/coreintf/<functional-area>/` source tree and are packaged into technology distributions during build. Current definitions include `component-descriptor_5.json`, `catalog_4.json`, `entitlement-document_2.json`, `entitlement-issuing-request_2.json`, `entitlement-bootstrap_2.json`, and `catalog-bootstrap_1.json`; older schema versions remain historical definitions and continue to be readable where compatibility is defined.

Component version is release provenance; persisted-data compatibility is governed by explicit schema identities/versions, direct-readable declarations and migration paths; runtime interpretation is independent from optional persistence convergence.

Mutable AAC persistence is independent from those payload-schema versions: Core/provider records carry a persistence-owned `record_revision`, whose representation is declared by the persistence contract (`MONOTONIC_INTEGER` or `OPAQUE_STRING`). Generic APIs use compare-and-swap and `READ / SINGLE_RECORD_CAS / MULTI_RECORD_TRANSACTION` capability declarations.
