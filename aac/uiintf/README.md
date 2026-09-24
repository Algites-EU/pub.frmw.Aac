# AAC UI Interfaces

Technology-neutral administration and presentation UI contracts for AAC. This artifact has no GUI toolkit dependency.

It models:

- installed components and provider instances;
- schema-driven configuration forms and scoped provider edit targets;
- binding/authorization editors and observation topology;
- effective entitlement status/provenance;
- catalog browse results plus downloaded/installed/obsolete package artifacts and active scopes;
- multi-component target-state replacement plans with blocking vs. non-blocking degradation/readiness diagnostics;
- component/provider-instance operational readiness state and structured reason projection separate from lifecycle state;
- toolkit-neutral display blocks and nested panels/containers.

All human-facing names, descriptions, labels and choice captions use the shared `AIcDisplayText` model (`text` plus optional `resource_key`). Longer bodies use `AIcDisplayContent`, which supports multi-line `PLAIN_TEXT`, `MARKDOWN` and `HTML`. HTML is display content only; concrete renderers remain responsible for sanitization and active-content policy.

Long-running capability operations are not modeled by private widget callbacks. A product may attach the generic Core-owned Operation Interaction channel to an invocation and render its progress/status/detail/diagnostic events, cooperative cancellation and foreground/background interaction state with any toolkit.

All mutations are routed through the controller/Core contracts and therefore remain Core-owned operations.
