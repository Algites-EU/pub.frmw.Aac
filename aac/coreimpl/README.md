# AAC Core Implementation

Reusable Python implementation of Algites Application Components.

Public import namespace: `algites.lib.aac.coreimpl`.

Production dependencies are `coreintf` plus generic runtime libraries. `simpleaudit` is a development/conformance dependency only and is never imported by production Core code.

The artifact implements:

- static package descriptor discovery, schema loading and reserved-namespace policy;
- Core-owned active capability-contract admission, canonical conflict detection and version negotiation;
- Core-owned provider-instance, binding, authorization and observation state;
- complete provider-instance graph resolution and DAG validation;
- provisioning and per-instance lifecycle orchestration;
- normalized invocation, contract input/output validation and PRE/POST observation dispatch;
- in-process, persistent PROCESS and CPython 3.14+ subinterpreter runtime profiles;
- filesystem/HTTP configuration providers, authentication/secret infrastructure and optimistic concurrency;
- explicit configuration and generic Data Entity compatibility, on-the-fly normalization, canonical schema registry and field-level Data Entity reference discovery;
- entitlement persistence, trusted issuer/evidence validation, temporal refresh and remediation/retry orchestration;
- filesystem package store, direct/manifest sources, query-oriented filesystem/HTTP catalog providers, authenticated catalog/artifact access, catalog-vs-descriptor verification, provenance, mandatory pre-promotion verification, workspace requirements/locks and package reconciliation;
- first-class provider/capability/component readiness evaluation, combining effective configuration/context requirements with optional runtime-reported readiness while remaining independent from activation state;
- complete target-state multi-component replacement with side-effect-free persisted-data interpretation/readiness preflight, unavailable-input fallback diagnostics, persistence-suppressed tentative activation, unified revisioned persistence, short-lived inter-process commit locking, generic durable journaling/active-set record revisions, startup recovery, package retirement and independent retryable post-cutover convergence.
- automatic compatible target-state solving over the active component population plus local/catalog candidates, preferring freshest compatible no-downgrade causal branches, rejecting unrelated changes, emitting structured explanations and offering only schema-identical downgrades as explicit alternatives.

A component replacement is validated against the final set of component versions. Intermediate one-at-a-time combinations do not have to be runnable.
