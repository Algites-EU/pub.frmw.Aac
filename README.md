# <Project Name>

Short description of the project.

> Public Algites project.

---

## 📦 Overview

Describe:
- what this project is,
- what problem it solves,
- who it is for.

Example:
This repository contains the implementation of **<Project Name>**, a <library/tool/framework/platform/app>
that is part of the Algites ecosystem.

---

## 🧱 Modules & Structure

Briefly describe the structure, for example:

```
.
├── README.md
└──(module/root/path - custom, sometimes even empty)
          ├── README.md
          └── (module-name)
                    ├── run/
                    ├── src/
                    |    ├── product/
                    |    |      ├── python/
                    |    |      └── (other-tech-specific-folder)/
                    |    └── develop/
                    |           ├── python/
                    |           └── (other-tech-specific-folder)/
                    ├── doc/
                    └── README.md
```

Adjust this section to your project specifics.

---

## 🚀 Build

### Gradle

```bash
./gradlew build
```

### Maven

```bash
mvn clean verify
```

---

## 🔄 Continuous Integration (Algites CI)

This repository uses the **Algites unified GitHub Actions CI pipeline** (build/test/publish rules are centralized).

For exact usage and naming of the branches to utilize fully the defined possibilities, see
https://github.com/Algites-EU/pub.gov.Algites.specs/blob/main/ci/Algites-Github-CI-Policy.md

---

## 📥 Usage

Describe:
- how to consume the library/tool,
- example dependency coordinates,
- or how to run the application.

Example (pip):

```bash
python -m pip install algites-...
```

Example (`pyproject.toml`):

```toml
[project]
dependencies = [
    "algites-...>=1.0.0",
]
```

Example (`requirements.txt`):

```text
algites-...>=1.0.0
```

Example with custom package index:

```bash
python -m pip install --index-url https://.../simple/ algites-...
```

---

## Content

Reusable implementation of the **Algites Application Components (AAC)** architecture.

This repository contains the realization of the language-neutral AAC rules and its Python implementation: descriptors, capability contracts, provider instances, Core-owned graph resolution, configuration and entitlement infrastructure, isolated runtime profiles, package management, transactional component replacement, and the reusable administration UI. Platform-neutral semantics belong in the general AAC specifications; this README focuses on how those semantics are represented and executed in Python.

### I. Repository and artifacts

The repository currently publishes eight AAC artifacts:

- `aac/coreintf` — public Python contracts, ABCs, DTOs, enums and technology-profile types. It must not depend on `coreimpl` or concrete providers.
- `aac/coreimpl` — reusable Core implementation. Its production dependency is `coreintf`; reference components are development/conformance dependencies only.
- `aac/simpleaudit` — minimal `_AAC.capability.observation/1` provider used as a real component and conformance fixture.
- `components/dataentity/yamlfsdes` — YAML File-System Data Entity Storage component implementing the generic Data Entity storage, storage-support, and backup/restore capabilities over a durable data/schema tree with revision/CAS enforcement and recoverable journals.
- `aac/verify/sigstore` — optional Sigstore implementation of package and entitlement-evidence verification SPIs. Core does not depend on Sigstore.
- `aac/uiintf` — technology-neutral administration controller contract and normalized UI models.
- `aac/uiqt` — PySide6 administration widget and Core-backed controller.
- `devtools` — first-class development-tool artifact; its Python sources live under `devtools/src/product/python`.

Authoritative source lives below each artifact's `src/` tree. Generated/runtime/build output lives below `run/` and is not authoritative source.

Reusable concrete components live under `components/<functional-area>/<artifact>`, while AAC framework/runtime artifacts remain under `aac/`. Each component directory is still a normal Algites artifact and follows the same source conventions.

The source layout is intentionally multi-technology capable. An artifact may carry one or more technology trees such as `src/product/python`, `src/product/java`, or technology-neutral `src/product/schema`, with corresponding development trees under `src/develop/<technology>`. A build may target all supported technologies or a selected subset; technology-specific publication destinations remain independently configurable. The `devtools` artifact follows the same layout instead of using a repository-special top-level `tools/` source exception.

The repository version is defined by `algites-source-repository.yml`. `devtools/src/product/python/sync_versions.py` maps the Algites repository version to PEP 440 versions and checks internal dependency pins. The current `1.0-SNAPSHOT` context maps to `1.0.dev0`.

All artifacts require Python 3.13 or newer. The optional CPython subinterpreter profile requires CPython 3.14+ because it uses `concurrent.interpreters`.

### II. Python naming and physical resources

Production Python types follow the Algites naming convention:

- `AIi...` — interface / ABC;
- `AIc...` — concrete class or data class;
- `AIn...` — enum;
- `AIx...` — exception;
- `AIig..._N` — generated interface, version-qualified by its canonical contract;
- `AIcg..._N` — generated non-data class;
- `AIcgd..._N` — generated data-object/DTO class (`d` is used only when the class is explicitly a data object).

Generated types expose canonical-source ID/version metadata and, where available, the canonical resource path; the same provenance is repeated in their docstring. DTO names are derived from the canonical schema identity, not merely from the operation position that references the schema, so one shared schema yields one generated type identity. `devtools/src/product/python/check_conventions.py` checks the production tree.

Versioned Algites-controlled schema/resource files use the `<name>_<version>` form, for example:

```text
component-descriptor_1.json
configuration-persisted-payload_1.json
capability-contract_1.json
```

A schema version is independent of a component release version. Persisted configuration and Data Entities use explicit canonical schema identity/version metadata. Data Entity support separately declares readable versions, writable versions, a preferred write version and migration paths.

Canonical AAC JSON schemas are technology-neutral source resources under `aac/coreintf/src/product/schema/algites/lib/aac/coreintf/<functional-area>/`. Functional areas mirror the Python API where practical (`catalog`, `descriptor`, `contracts`, `configuration`, `entitlement`, `packages`, and so on); truly cross-cutting schemas belong under `common`. The Python build packages these same canonical files into the `coreintf` wheel as importable resources. This layout prepares later Java/MPS bindings to consume the same schema sources without making Python the owner of the definitions.

### III. Component descriptors and capability contracts

Component descriptors are packaged YAML resources loaded without executing arbitrary component business logic. The descriptor field for component-declared capability implementation roles is explicitly named `capability_providers`; it does not represent data-source instances. Each entry is a capability provider definition from which Core may create configured provider instances. A descriptor can declare:

- stable component identity and component version;
- capability provider definitions and initial provider instances;
- provided capability IDs and finite supported contract versions;
- consumer requirements, cardinality and mandatory/optional semantics;
- requested capability authorizations;
- component and provider-instance configuration schemas;
- capability-contract resources;
- first-class entitlement licensing-scope declarations with display name/description/resource keys, plus `provided_capability_entitlements` capability-version permission declarations using `possible_licensing_scopes` (an empty set means no external entitlement evidence is required);
- generic `data_entity_support`, Data Entity requirements and migration metadata;
- runtime/lifecycle metadata and presentation metadata;
- declarative provider readiness requirements over effective component configuration, provider configuration and application context.

The active capability-contract catalog is Core-owned. Built-in contracts and validated dynamically supplied contract resources are admitted into one canonical catalog. The same `(capability id, version)` cannot silently resolve to two different definitions.

Provider selection and contract-version negotiation are separate. A binding is valid only for versions in the finite intersection of consumer support, provider support, the Core active catalog and lifecycle policy.

The normalized invocation layer validates contract-declared inputs and outputs and carries invocation correlation metadata. Every operation also declares its supported Operation Interaction state-result delivery modes. Simple synchronous calls use an invocation-local `ON_DEMAND_COMPLETE` no-op interaction; interactive/non-blocking calls may exchange directional provider-to-caller and caller-to-provider messages carrying lifecycle state, revisions, partial/complete operation-specific results, progress/diagnostic events, cancellation and foreground/background preferences. Core routes the protocol and owns `PENDING -> RUNNING -> COMPLETED|FAILED|CANCELLED`, but does not interpret complete/delta result semantics, replay policy or provider buffering. PRE/POST observation is dispatched by Core; observation delivery cannot recursively observe itself.

### IV. Provider instances, graph resolution and lifecycle

Capability provider definitions are implementation templates. Concrete providers in the runtime graph are **Core-managed provider instances** with immutable generated IDs, editable display names, configuration and lifecycle state. One capability provider definition/instance may expose multiple capability/version sets on the same runtime object; a provider instance is not duplicated per capability. Instances also carry `READ_ONLY`/`READ_WRITE` access mode for domains that enforce mutating versus non-mutating use.

Consumer requirements belong to the capability provider definition that consumes the capability. Core resolves requirements against concrete provider instances and persists explicit binding preferences by provider-instance ID.

The resolved runtime graph is a provider-instance DAG. Declarative component relationships may be cyclic, but the concrete resolved provider-instance graph must not contain invocation cycles; direct self-binding is the length-one case of the same rule.

The reusable lifecycle performs the staged sequence conceptually equivalent to:

```text
DISCOVER -> RESOLVE -> INSTANTIATE -> WIRE -> ACTIVATABLE -> ACTIVATE
```

Core creates capability handles from resolved bindings and injects them into consumers. Components do not rediscover or silently replace providers behind Core. The runtime hook `prepare_activation()` completes post-wiring local preparation; successful return establishes lifecycle `ACTIVATABLE`, after which `activate()` may transition the instance to `ACTIVE`. This lifecycle barrier is independent of operational readiness `READY / DEGRADED / NOT_READY`.

Operational readiness is a separate Core-owned model from lifecycle activation. Provider instances/capabilities use `READY`, `DEGRADED`, and `NOT_READY` with structured reasons. A provider can remain lifecycle `ACTIVE` while one capability is degraded or not ready. Static descriptor requirements are evaluated against effective configuration/context (`UNDEFINED` means missing; a concrete fallback/default satisfies the requirement) and are conservatively combined with an optional runtime `readiness()` result. Existing runtimes default to dynamic `READY`. Core exposes provider, capability and component readiness queries and re-evaluates active readiness after Core-mediated configuration mutation.

### V. Python runtime profiles and dependency isolation

The baseline in-process profile constructs the statically declared Python provider runtime or factory and keeps private component implementation details outside public AAC contracts.

AAC also contains two isolation profiles:

- **PROCESS** — one persistent child process and JSON-lines IPC channel per provider instance. Core owns lifecycle, invocation and reverse `core_invoke` calls to already-resolved consumed capabilities. A component may use a private Python environment or a non-Python executable implementing the protocol.
- **SUBINTERPRETER** — CPython 3.14+ endpoint based on `concurrent.interpreters`, transferring normalized/copyable invocation data across interpreter boundaries and bridging live Operation Interaction through cross-interpreter queues while execution runs on a separate thread.

Neither profile is presented as a hostile-code security sandbox. Native Python extensions used with subinterpreters require explicit compatibility validation.

### VI. Configuration, authentication and authorization

Configuration is Core-mediated and has exact `COMPONENT` and `PROVIDER_INSTANCE` targets. Configuration providers expose normalized contributions, capabilities and optionally versioned snapshots with optimistic-concurrency revisions.

Reference providers include:

- read/write filesystem persistence using the common AAC `record_revision` CAS contract, short-lived inter-process locking, temporary files, fsync and atomic rename;
- HTTP persistence with GET plus PATCH or full-document PUT semantics, mapping opaque `record_revision` tokens to ETag/If-Match where applicable.

Configuration scopes and providers are selected through fixed bootstrap/profile documents. External configuration profiles may be loaded from trusted file or HTTP(S) resources.

Authentication, secret storage and authorization are separate contracts:

- authentication profiles resolve mechanisms such as NONE, BASIC, BEARER and client certificate;
- secret references are resolved through pluggable secret providers such as environment or filesystem providers;
- capability authorization uses canonical contract-declared permission IDs, consumer-requested authorizations and Core-owned grants; optional current-principal authorization is enforced at the Core invocation bridge.

Schema-driven configuration reads validate persisted payloads before their values enter ordinary configuration resolution.

### VII. Data Entities, schema identity and migration

Data Entities are a first-class AAC Core concept rather than a special "Core-entity extension" mechanism. Logical identity is `(schema_id, uid)` and the normalized `AIcDataEntityEnvelope` carries `schema_version`, `record_revision`, `state` (`ACTIVE` or `TOMBSTONE`) and payload.

Every canonical JSON Schema explicitly declares `x-aac-schema-id` and `x-aac-schema-version`; Core never derives identity from a filename. `AIcSchemaRegistry` indexes canonical definitions by `(schema_id, version)` while retaining the technical resource location.

Components declare `data_entity_support` with readable/writable version sets, `preferred_write_version`, migration steps and `data_entity_requirements`. This creates a type-level compatibility graph that works equally for Core-owned and component-owned data.

Concrete record relationships are declared only in the canonical schema at the referencing field through `x-aac-data-entity-reference`. The annotation identifies the target schema ID; the field value supplies the target UID. References therefore survive target schema-version migration.

Data Entity migration is semantic and side-effect-free. `AIcDataEntityMigrationService` classifies representations as `DIRECT`, `TRANSFORMED` or `UNSUPPORTED` and can normalize toward the preferred write version in memory while preserving UID, record revision and ACTIVE/TOMBSTONE state. Physical Data Entity access is standardized through built-in loading, storing, storage-management, and storage-backup/restore capability groups. Backup/restore is provider-specific physical disaster recovery and is intentionally distinct from logical Data Entity export/import.

The Python runtime also contains the first typed Data Entity facade layer. A provider instance may expose several storage capabilities at once and is always selected explicitly; `READ_ONLY`/`READ_WRITE` is stored per instance. `(schema_id, schema_version)` may register a generated versioned view interface plus codec, while `schema_id` registers the current implementation/factory and canonical storage version. A stored older payload is decoded through its stored-version codec into the current polymorphic implementation, and consumers may receive that same object through another explicitly supported versioned view. Saving always uses the current canonical codec rather than the consumer view.

Configuration retains its separate scoped/provider semantics but shares the same separation between semantic schema version and persistence `record_revision`.

### VIII. Entitlements and trusted evidence

Entitlements are independent from technical capability compatibility and from invocation authorization.

The Python implementation provides:

- capability-version permission declarations;
- entitlement aggregation with effective validity and provenance;
- file-based entitlement discovery;
- pluggable evidence verification;
- trusted issuer rules constraining issuer IDs, components, evidence types and signer identities;
- stable subject metadata and entitlement-issuing request correlation;
- temporal refresh planning based on the next known validity transition;
- one Core-owned remediation attempt with transparent retry only when the provider explicitly declares the failed operation safe after entitlement change.

`AIcEntitlementLicensingScope` is distinct from `AIcConfigurationScope`. Licensing-scope type identifiers are component-declared rather than a closed Core enum; registered licensing-scope resolvers derive concrete subjects and define identity-continuity semantics. `WORKSPACE` may therefore be database-backed, while a component may separately declare a `SOURCE_REPOSITORY` scope resolved from VCS lineage evidence.

### IX. Package management and provenance

`AIcPackageStoreLayout` receives a product-owned root. AAC recommends separate package-byte and Core-owned package-state areas:

```text
<product-root>/plugins/downloaded
<product-root>/plugins/installed
<product-root>/plugins/obsolete

<product-root>/aac-state/active-package-set.json
<product-root>/aac-state/active-transaction.json
<product-root>/aac-state/transactions/<transaction-uuid>/...
```

`plugins`, its three lifecycle subdirectories, `aac-state`, the transaction-journal subdirectory, and the Core mutation-lock filename are product-overridable. The state area is not part of the plugin artifact store: it contains Core-owned mutable state and recovery metadata and therefore should live on durable product/user/service state storage. The sole current package-bootstrap schema, version `1`, exposes these state/journal/lock overrides. Development-time historical package-bootstrap schema revisions are not retained as compatibility formats.

The authoritative active package set is one atomically replaced mutable record. It uses the same monotonic-integer `record_revision` contract as other Core-owned persisted state; package selection no longer has a separate `generation` concurrency concept. A short-lived inter-process `core.lock` serializes only the actual revalidation/commit or cutover interval. Download, solver search and preflight run outside the lock and the complete read set is revalidated after the lock is acquired.

Stored package identity is immutable:

```text
(component_id, component_version, SHA-256)
```

Package records retain source/artifact provenance, verification metadata and signer identity where available. A source URI is provenance, not trust.

The package pipeline supports direct/static sources plus the AAC Catalog discovery layer. Catalog queries are scoped by mandatory `product_id` and `technology_id`; the reference filesystem and HTTP providers load the current catalog format (`format_version: 1`) and filter through the query-oriented Catalog SPI. Release metadata includes persistent component/provider configuration summaries and generic Data Entity support summaries used by the automatic target-state solver, plus entitlement licensing-scope declarations, `provided_capability_entitlements`, presentation metadata, release `provides`/`requires`, and artifact locators. The catalog is discovery metadata rather than trust authority: after download, Core verifies the artifact and compares its actual descriptor metadata with the catalog release before installation.

Artifact retrieval can use authenticated file/HTTP(S) locations independently from catalog authentication. Missing runtime entitlement does not prevent storage/installation; permissions with no `possible_licensing_scopes` need no external entitlement, while externally grantable permissions are resolved later by the ordinary entitlement subsystem. Downloaded bytes are digested; installation copies the artifact and detached sidecars into a temporary installed-tree destination, re-verifies those exact bytes, rechecks the digest and atomically promotes the directory.

Only one package artifact for a component identity may be **active/selected** across the scopes managed by one Core/package store. A second version may physically exist temporarily while it is staged for an upgrade, but it is not concurrently active. After a successful replacement, superseded unselected installed artifacts are moved to `obsolete`. Returning later to an obsolete artifact is a new replacement transaction and must pass fresh persisted-data and target-graph preflight; retention of the bytes does not guarantee downgrade compatibility.

Automatic package reconciliation can additionally apply product policy and entitlement-aware restrictions; manual installation remains a separate policy decision. Licensing-service mechanics are intentionally outside the catalog baseline; component-level `entitlement_info_url` is informational discovery metadata only.

### X. Transactional multi-component replacement

Component replacement is modeled as a transaction over a **complete target component state**, not as a sequence of independently valid single-plugin upgrades. The same primitive supports upgrades and downgrades; a later return to an older component version is a fresh replacement transaction evaluated against current state.

Before runtime deactivation, Core constructs the hypothetical target state by replacing every selected component at once. It then:

1. rebuilds the active contract catalog from the complete target component set;
2. projects current provider instances onto target descriptors and includes target initial instances;
3. resolves every mandatory consumer requirement against the target providers;
4. validates explicit provider-instance preferences and the resulting provider-instance DAG;
5. classifies relevant persisted configuration and Data Entity schemas as `DIRECT`, `TRANSFORMED` or `UNSUPPORTED`;
6. executes only required `TRANSFORMED` paths in memory, without provider writes;
7. resolves effective target configuration using usable contributions while preserving unsupported contributions as unavailable input;
8. validates the resulting available values without treating missing top-level context-dependent values as an automatic Core failure;
9. returns blocking incompatibilities separately from non-blocking degradation/warning diagnostics.

Intermediate component combinations are intentionally irrelevant. For example, `A/2 + B/1` and `A/1 + B/2` may both be invalid while the atomic target `A/2 + B/2` is valid.

During tentative commit Core sets `AIcConfigurationReadService.persist_migrations = False`, writes a durable replacement journal, deactivates the affected runtime, admits all target descriptors/contracts/schemas, reconciles provider instances and activates the complete target graph. No configuration provider or Data Entity storage is rewritten while transaction rollback may still be required.

Package replacement binds to the generic durable AAC transaction journal. The journal UUID is solely a transaction identity/correlation value; its descriptor carries a revisioned read set, a write set, the source/target package-set plan and recovery material. Generic recovery phases are `PREPARED`, `COMMIT_STARTED`, `COMMITTED`, `CLEANUP_COMPLETED` and `ABORTED`. Atomic replacement of `active-package-set.json` is the durable commit boundary. Therefore a process/host crash yields only two authoritative cases on next startup:

- source `record_revision`/selection still active -> restore the recorded source Core state and abort the interrupted cutover;
- target `record_revision` plus transaction id active -> keep the target committed and idempotently finish package cleanup such as `installed -> obsolete`.

A crash after the active-set commit never causes Core to guess a partial component combination. Likewise, a crash before the commit never promotes the tentative target merely because some target runtime/state mutations had already occurred.

If activation fails normally before the manifest commit, Core performs the same rollback in-process. If journal cleanup cannot finish after the manifest commit, the replacement remains committed and startup recovery completes cleanup later.

After successful cutover, configuration and Data Entity persistence convergence are independent and retryable. Data Entity convergence uses the generic storage capabilities and remains outside the tentative component-cutover rollback boundary; Core owns semantic validation/migration policy while the explicitly selected provider instance owns physical representation and atomic changesets.

A newer persisted representation does not automatically block a later downgrade. If the older target component cannot interpret a provider contribution, that contribution becomes unavailable; resolution may fall back to other providers/defaults/`UNDEFINED`. The replacement plan remains compatible when these are degradation warnings rather than true target-graph or activation blockers.

### XI. Automatic compatible target-state solver

`AIcCompatibleTargetStateSolver` plans coordinated version changes for the currently active component population using local package candidates plus the configured AAC Catalog. Requests may select an exact version, an allowed set, or the latest compatible release. Explicit requests and workspace requirements/locks are hard constraints.

The solver forms the mandatory capability dependency closure caused by requested changes. Inside that actual closure it prefers the freshest compatible no-downgrade branch, while rejecting non-requested component changes that can be reverted to the current version without breaking compatibility. It therefore does not turn one requested upgrade into an unrelated global update.

Downgrades are intentionally never recommended. They may be returned only as explicit alternatives when the relevant persistent component/provider configuration and Data Entity support summaries satisfy the conservative downgrade-safety policy. Configuration uses its schema/write identity; Data Entities compare schema identity together with readable/writable/preferred-write support. Core verifies catalog summaries against the authoritative descriptor after download.

Solver results carry structured causal explanations, package download/install preparation flags, entitlement diagnostics and currently predictable readiness diagnostics. Missing entitlement remains a nonblocking licensing/remediation diagnostic. Applying a selected solution prepares required artifacts and delegates the actual active-set change to the existing crash-safe multi-component replacement transaction.

### XII. Package administration UI

The technology-neutral UI contract exposes components, provider instances, bindings, observation topology, entitlement status and package/upgrade state.

The PySide6 administration widget includes a **Packages** view split into catalog browsing and stored-package administration. It can:

- query configured catalogs by product/technology scope plus text filters and show release capability/requirement and entitlement summaries;
- solve a selected catalog release into a complete compatible target set, distinguishing requested changes from automatically required causal changes;
- show a recommended no-downgrade solution plus bounded alternatives, causal explanations, entitlement/readiness diagnostics and required download/install preparation;
- require explicit confirmation before applying any solver alternative that contains a schema-safe downgrade;
- download or install a selected catalog artifact without implicitly activating it or granting entitlement;
- show downloaded, installed and obsolete artifacts with digest, provenance and active scope information;
- restore obsolete artifacts into the installed store;
- select multiple installed target artifacts;
- validate the complete target-state transaction without changing the live runtime;
- display compatibility diagnostics for affected components/capabilities, including non-blocking projected readiness warnings;
- apply the same selected set as one transactional replacement;
- report post-cutover persistence convergence separately from the already committed component replacement;
- display lifecycle state and `READY / DEGRADED / NOT_READY` operational readiness separately for components/provider instances, including readiness reasons.

The host product owns the `QApplication` and event loop. AAC supplies reusable widgets/controllers rather than imposing an application shell.

### XIII. Generated bindings and presentation metadata

Canonical capability contracts may define operation request/result schemas and authorization requirements. `AIcPythonCapabilityBindingGenerator` and `devtools/src/product/python/generate_capability_bindings.py` generate Python interfaces/DTOs from those contracts, including operation IDs and authorization metadata. Generated behavioral interfaces and their methods are capability-version-qualified (`AIig..._N`, `operation_N(...)`) so one provider object can safely implement several versions/capabilities at once. `AIcPythonDataEntityBindingGenerator` similarly generates versioned Data Entity view interfaces with version-suffixed field accessors plus version-specific codecs.

`AIcDisplayText` provides localization-ready presentation metadata with fallback text, opaque resource key, or both. JSON Schema-driven fields can use AAC presentation extensions with standard JSON Schema title/description as fallback.

### XIV. Verification and development commands

Repository checks are intentionally runnable in small functional blocks.

```bash
python devtools/src/product/python/sync_versions.py --check
python devtools/src/product/python/check_conventions.py
python devtools/src/product/python/test_all.py
python devtools/src/product/python/build_all.py
```

`devtools/src/product/python/test_all.py` executes artifact and Core functional suites separately to keep individual test runs bounded. `devtools/src/product/python/build_all.py` creates wheel and source-distribution outputs in each artifact's `run/bld` directory.

For local development, the artifact source roots can be placed on `PYTHONPATH`, or individual artifacts can be installed as normal Python distributions.

### XV. Architectural boundaries

The Python repository deliberately does not redefine product-neutral AAC semantics. In particular:

- host products decide where authoritative bootstrap resources come from;
- package/configuration/entitlement transports do not create trust merely by being reachable;
- host products own their Core-domain entity migration semantics;
- dependency isolation is not a security sandbox;
- Java and other language profiles have their own runtime/type-identity mechanisms even when they implement the same AAC contracts;
- external commerce/subscription services and anti-cloning DRM are outside this library.

The general AAC governance and technical documents remain authoritative for cross-language rules; this repository is the current Python technology realization of those rules.

#### General AAC component-replacement documentation

Platform-neutral persistence, optimistic-concurrency, transaction/recovery, replacement and convergence rules are maintained in the shared AAC specification set rather than duplicated in this Python repository.


## 🤝 Contributing

Contributions are welcome.

Please:
- open an issue to discuss changes,
- follow the Algites coding and naming standards,
- ensure CI passes before submitting a PR.

---

## 📜 License

This project is licensed under the terms of the license specified in the `LICENSE` file.

---

## 🌍 About Algites

Algites develops platforms, tools, and applications based on strong governance,
modeling, and automation principles.

See:
- https://github.com/Algites-EU/pub.gov.Algites.specs

---

**© Algites**
