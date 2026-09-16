# Application Component Readiness Specification

## I. Purpose

This specification defines AAC readiness independently from component admission and lifecycle activation. A component or provider instance may be safely installed, resolved, instantiated, wired and `ACTIVE` while some or all of its advertised functionality is temporarily unavailable or degraded.

Readiness is runtime-operational information. It does not replace contract compatibility, lifecycle state, entitlement evaluation, configuration resolution, or health/monitoring.

## II. Baseline readiness states

AAC defines exactly three baseline readiness states:

```text
READY
DEGRADED
NOT_READY
```

`READY` means the assessed functionality is usable under the currently resolved inputs.

`DEGRADED` means the functionality remains usable but with a known limitation, fallback, reduced quality, missing optional dependency/input, or component-reported restriction.

`NOT_READY` means the assessed functionality is not currently usable, although the component/provider MAY remain activated so that other independent functionality can continue to operate and so readiness can recover without component reinstall/replacement.

Readiness MUST NOT be represented merely by the lifecycle `ACTIVE`/`INACTIVE` state.

## III. Readiness scope

The narrowest practical readiness scope SHOULD be used. Baseline AAC supports readiness at least for:

- provider instances;
- the capability provided by a provider instance;
- aggregate capability availability across provider instances;
- aggregate component readiness.

A technology/product MAY additionally expose operation-level readiness when useful. Operation-level readiness is an extension of the same model and MUST NOT change the meaning of the three baseline states.

## IV. Activation and readiness are independent

Successful activation proves that the runtime can safely participate in the Core-managed graph. It does not prove that every business function is currently usable.

Therefore this is valid:

```text
component lifecycle: ACTIVE
provider A readiness: READY
provider B readiness: NOT_READY
component readiness: DEGRADED
```

Missing contextual values, unavailable configuration contributions, absent optional resources, expired non-mandatory entitlement permissions, or runtime conditions SHOULD reduce readiness at the narrowest affected scope instead of automatically deactivating the whole component.

A product profile MAY declare a minimum readiness policy for a particular operation or deployment, but this is distinct from AAC technical activation compatibility.

## V. Structured readiness reasons

Every non-`READY` assessment MUST carry one or more structured reasons. A reason SHOULD contain at least:

```text
code
state impact: DEGRADED | NOT_READY
human-readable diagnostic
```

When applicable it SHOULD also identify:

```text
readiness requirement id
configuration/context key
provider instance
capability
related external dependency
```

Reason codes are stable machine-oriented identifiers. Human-readable text is presentation metadata and MAY be localized by a technology/product binding.

## VI. Declarative readiness requirements

A provider definition MAY declare static readiness requirements for values whose absence can be determined by Core without invoking component business logic.

Baseline sources are:

```text
COMPONENT_CONFIGURATION
PROVIDER_CONFIGURATION
CONTEXT
```

A requirement identifies a stable value/key and declares the readiness state produced when the value is unavailable:

```yaml
readiness_requirements:
  - id: smtp-endpoint
    source: COMPONENT_CONFIGURATION
    key: smtp.server
    missing_state: NOT_READY

  - id: optional-region
    source: CONTEXT
    key: deployment.region
    missing_state: DEGRADED
```

`missing_state` MUST be `DEGRADED` or `NOT_READY`. Absence can never produce `READY`.

For configuration, a value resolved as `UNDEFINED` is unavailable. A schema/default/policy fallback that produces a concrete effective value satisfies the requirement.

For context, the product-specific context resolver determines whether the named value is present. A component MUST NOT assume a contextual value exists merely because it normally exists in one product deployment.

## VII. Runtime-reported readiness

Static declarations cannot express every operational condition. A provider runtime MAY report additional dynamic readiness after wiring/initial preparation and MAY be re-evaluated later.

Examples include:

- an external server is unreachable;
- a credential is present but rejected;
- local storage is temporarily read-only;
- a consumed optional capability reports reduced availability;
- a runtime-specific consistency check fails.

The runtime report uses the same `READY / DEGRADED / NOT_READY` states and structured reasons.

Core combines declarative and runtime readiness conservatively: the effective provider-instance readiness is the worst state reported by either source, and all relevant reasons are retained.

A runtime that does not implement an explicit dynamic readiness mechanism is treated as dynamically `READY`; declarative/Core-known requirements still apply.

## VIII. Aggregation

Provider-instance readiness is authoritative for that instance.

For one capability offered by multiple instances/providers, baseline aggregate readiness is:

```text
READY       if at least one provider instance is READY
DEGRADED    if none is READY and at least one is DEGRADED
NOT_READY   if all known providers are NOT_READY
```

Component aggregate readiness is diagnostic rather than a replacement for capability-level information. Baseline aggregation is:

```text
READY       if all provider instances are READY
NOT_READY   if all provider instances are NOT_READY
DEGRADED    otherwise
```

A component with no provider instances is `READY` unless a product profile defines another component-level readiness source.

Consumers SHOULD use capability/provider readiness rather than only component aggregate readiness when deciding whether a specific operation can proceed.

## IX. Configuration, `UNDEFINED`, and unsupported contributions

Readiness consumes the **effective resolved configuration**, not raw provider payloads.

An unsupported persisted provider contribution is unavailable input. Resolution proceeds through other providers, applicable policy/defaults, schema defaults, and finally `UNDEFINED` as defined by the Context/Configuration specification.

Readiness therefore observes the result:

```text
concrete effective value -> requirement satisfied
UNDEFINED                -> requirement missing
```

The fact that one underlying provider contribution was unsupported MAY still be exposed as a separate diagnostic warning, but it MUST NOT independently force `NOT_READY` when another usable contribution/default supplies the required value.

## X. Replacement preflight

Component replacement preflight SHOULD evaluate all declarative/Core-computable readiness for the complete target state after target configuration/context resolution.

Readiness diagnostics are distinct from structural compatibility blockers.

By default:

- `READY` produces no readiness warning;
- `DEGRADED` produces a non-blocking target-state warning;
- `NOT_READY` produces a non-blocking target-state warning describing unavailable functionality.

A product profile MAY impose a stricter **minimum target readiness policy** and promote selected readiness conditions to replacement blockers. Such policy MUST be explicit; AAC baseline does not treat `NOT_READY` functionality as equivalent to an invalid target component graph.

Dynamic runtime readiness that cannot safely be known before tentative activation is evaluated during/after activation and is reported as runtime readiness, not guessed by the static preflight checker.

## XI. Re-evaluation

Core SHOULD re-evaluate readiness when inputs known to affect it change, including as applicable:

- effective configuration changes;
- application/context values change;
- entitlement context changes;
- consumed bindings change;
- runtime explicitly reports a changed condition;
- component replacement or activation occurs.

Re-evaluation MUST NOT require reinstalling the component.

## XII. UI requirements

Administration UI SHOULD display readiness separately from lifecycle state.

At minimum it SHOULD show:

```text
component/provider lifecycle state
readiness state
structured reason(s)
```

Package/replacement validation SHOULD show projected readiness warnings alongside compatibility diagnostics and clearly distinguish warnings from transaction blockers.

A UI MUST NOT label a component as failed merely because one capability is `NOT_READY` while independent functionality remains usable.

## XIII. Technology binding requirements

A technology binding MUST provide a typed representation of the three readiness states and structured reasons.

It SHOULD support:

- declarative readiness requirements in component descriptors;
- a runtime callback/reporting mechanism with a default `READY` behavior for existing providers;
- Core queries for provider, capability and component readiness;
- UI projection without requiring renderer-specific business logic.

Technology bindings MAY differ in how dynamic runtime readiness crosses isolation boundaries, but the Core-owned semantics above remain authoritative.
