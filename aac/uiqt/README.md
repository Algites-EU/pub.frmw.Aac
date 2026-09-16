# AAC Qt UI

PySide6 implementation of the AAC administration UI contract.

The reusable widget renders Core-owned components, provider instances, bindings, observation topology, entitlement state and package management without allowing extension components to inject native Qt widgets.

Configuration forms expose scoped configuration providers, keep read-only targets visible for provenance and enable writes only when Core authorizes them.

The **Packages** tab separates **Browse catalog** from **Stored packages**. Catalog browsing queries mandatory product/technology scope, displays component/release/capability/entitlement metadata and can download or install selected artifacts without implicitly activating them or granting entitlement. Stored-package administration shows provenance/state, can restore obsolete artifacts, permits selecting several installed target artifacts, validates the complete target component state, distinguishes blocking errors from unsupported-contribution/readiness warnings, and applies the selected set as one transactional replacement (upgrade or downgrade). Catalog rows can also invoke the automatic target-state solver: the UI separates requested and automatically required changes, displays causal explanations/download-install work/entitlement/readiness diagnostics, offers bounded alternatives, and requires explicit confirmation for a schema-safe downgrade alternative. Persistence-convergence diagnostics are post-cutover status and do not turn an already committed component replacement into a failed upgrade.

Component and provider-instance tables display lifecycle state separately from operational `READY / DEGRADED / NOT_READY` state and show structured readiness reasons.

The host product owns the `QApplication`, application shell and localization-resource resolution.
