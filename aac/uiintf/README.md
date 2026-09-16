# AAC UI Interfaces

Technology-neutral administration UI contracts for AAC. This artifact has no GUI toolkit dependency.

It models:

- installed components and provider instances;
- schema-driven configuration forms and scoped provider edit targets;
- binding/authorization editors and observation topology;
- effective entitlement status/provenance;
- catalog browse results plus downloaded/installed/obsolete package artifacts and active scopes;
- multi-component target-state replacement plans with blocking vs. non-blocking degradation/readiness diagnostics;
- component/provider-instance operational readiness state and structured reason projection separate from lifecycle state.

All mutations are routed through the controller contract and therefore remain Core-owned operations.
