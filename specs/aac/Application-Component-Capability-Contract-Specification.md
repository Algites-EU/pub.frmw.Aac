# Application Component Capability Contract Specification

**Status:** Draft public specification  
**Scope:** Capability contracts, operations, invocation identity, and generic invocation observation in application component architectures  
**Audience:** Core implementers, component/plugin authors, SDK authors, technology-profile authors, and third-party integration developers  
**Companion documents:** `Application-Component-Architecture-Governance.md`, `Application-Component-Architecture-Technical-Notes.md`, `Application-Component-Lifecycle-and-Provisioning-Specification.md`, `Application-Component-Upgrade-Transaction-Specification.md`

---

# I. Purpose and Architectural Position

## I.1 Purpose

This specification defines the structure and runtime meaning of an Algites capability contract.

A capability is not merely a named interface. A canonical capability contract defines a versioned behavioral surface consisting of one or more **operations**, together with the schemas and semantics required to invoke those operations across component boundaries.

This specification also defines a generic **capability invocation observation** mechanism. Observation is intentionally modeled as another capability rather than as a product-specific debug hook.

The model is product-independent. A product profile may assign product-owned capability identifiers and reserved namespaces, but the concepts in this document are reusable across Algites products.

## I.2 Relationship to Governance

`Application-Component-Architecture-Governance.md` defines architectural invariants such as:

- Core-owned capability resolution;
- canonical contract identity;
- provider-instance binding;
- finite supported contract versions;
- provider selection before version negotiation;
- runtime dependency isolation.

This document refines the **capability contract** itself and defines how operation and observation metadata participate in that architecture. Component installation, provisioning, entitlement evaluation, activation, suspension, and unprovisioning are defined by `Application-Component-Lifecycle-and-Provisioning-Specification.md`.

## I.3 Relationship to technology profiles

This document is language-neutral.

A Java, Python, process, RPC, or other technology profile may represent the same contract differently, but MUST preserve the logical identities and semantics defined here.

For example:

```text
logical capability operation
        |
        +-- Java method on a shared interface
        +-- Python proxy method
        +-- RPC method/message pair
        +-- process IPC request
```

The technology binding is not the canonical identity. The capability contract is.

---

# II. Capability Contract Model

## II.1 Capability identity

A capability has a stable globally meaningful identifier.

Conceptually:

```yaml
capability:
  id: "algites.object-store"
  version: 3
  group_id: "algites.storage"
```

Product profiles may reserve their own namespaces.

Third-party components SHOULD use identifiers from namespaces they control and MUST NOT claim a product-reserved namespace.


## II.2 Capability groups

Every capability contract MUST identify exactly one **capability group** through `capability.group_id`. Capability groups are organizational and presentation metadata only; they MUST NOT affect provider discovery, binding, version negotiation, authorization, invocation routing, lifecycle state, or runtime compatibility.

A capability group has:

```text
id
optional parent_group_id
name: AIcDisplayText
optional description: AIcDisplayText
optional metadata
```

Groups may form an arbitrary nested hierarchy. A group without `parent_group_id` is a root group. The same group may contain capabilities from many components and capability versions. A capability contract references only the stable group ID; it does not duplicate the group's display definition.

Group IDs are globally meaningful within the active AAC environment and follow the same namespace ownership rules as other framework/component identities. Group display text uses the normal `AIcDisplayText` representation (`text` plus optional `resource_key`) and therefore does not introduce parallel localization fields.

Components that introduce their own groups declare static `capability_groups` resources in their component descriptor. Core admits those group definitions before the component's `capability` resources. Repeated identical group definitions may be deduplicated; conflicting canonical definitions for the same group ID MUST be rejected. A child group MUST reference a parent that has already been admitted from built-ins or the target component set.

Framework groups currently include:

```text
_AAC.data-entity
    _AAC.data-entity.loading
    _AAC.data-entity.storing
    _AAC.data-entity.storage-management

_AAC.runtime
    _AAC.runtime.observation
```

The grouping hierarchy is intentionally not a capability taxonomy with behavioral inheritance. Parent/child relations exist only for navigation, display, filtering, and administration UI.

The following diagram separates canonical capability metadata from the component implementation and from configured runtime instances:

```mermaid
flowchart LR
    GROUP["Capability Group"] -->|organizes| CONTRACT["Capability Contract<br/>id + version"]
    CONTRACT --> OPS["Operation(s)<br/>input/output schemas"]

    COMPONENT["Component Descriptor"] --> PDEF["Capability Provider Definition"]
    PDEF --> IMPL["Implementation Class"]
    PDEF -->|provides exact version(s)| CONTRACT
    PDEF --> PINST["Provider Instance(s)"]
    PINST -. "runs implementation" .-> IMPL

    REQ["Consumer Requirement"] -->|accepts version(s)| CONTRACT
    CORE["Core Resolver / Invocation Bridge"] --> REQ
    CORE --> PINST
```

The capability contract remains independently canonical even when several components provide it. A component descriptor declares which contracts a capability provider definition implements; Core later creates/configures concrete provider instances and binds consumers to those instances.

## II.3 Contract version

Each capability is versioned independently.

A version denotes a specific behavioral contract, including its operation set and operation semantics.

A component advertises only finite, explicitly known versions that it intentionally supports.

Technology bindings MUST make coexisting contract versions unambiguous. For generated behavioral interfaces, the canonical capability version is therefore part of both the generated interface name and every generated operation method name. Contract version `N` maps to an interface such as `AIigExample_N`, and canonical operation `run` maps to a binding method such as `run_N(...)`. The suffix is binding-level disambiguation; the canonical operation ID remains `run` and its canonical identity remains `(capability id, capability version, operation id)`.

One runtime provider object MAY implement several versions of the same capability and several different capabilities at once. The Core bridge MUST dispatch against the exact `(capability id, capability version)` interface rather than relying on language method-resolution order.

## II.4 Capability operations

A capability contract contains one or more **operations**.

Conceptually:

```yaml
capability:
  id: "algites.secrets.store"
  version: 2
  group_id: "algites.security"

operations:
  - id: get
    interactions:
      - kind: INPUT
        schema: {id: algites.secrets.store.get.request, version: 2}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: algites.secrets.store.get.result, version: 2}

  - id: put
    interactions:
      - kind: INPUT
        schema: {id: algites.secrets.store.put.request, version: 2}
      - kind: FINAL_SUCCESS_STATE_RESULT
        schema: {id: algites.secrets.store.put.result, version: 2}

  - id: delete
    interactions:
      - kind: INPUT
        schema: {id: algites.secrets.store.delete.request, version: 2}
```

A capability MAY contain only one operation when that is the natural contract boundary.

A capability MUST NOT be forced to one operation merely to make operation identity globally unique.

Each operation defines zero or more normalized `interactions[]`. Every interaction has a fixed `kind` from `CapabilityOperationInteractionKind` and a portable schema reference `{id, version}`. Each kind may occur at most once per operation. The baseline kinds are:

```text
INPUT
RUNNING_COMPLETE_STATE_RESULT
RUNNING_DELTA_STATE_RESULT
FINAL_SUCCESS_STATE_RESULT
FINAL_CANCELLED_STATE_RESULT
FINAL_FAILED_STATE_RESULT_EXTENSION
```

All interaction kinds are optional. Absence of `INPUT` means the operation accepts no portable input. Absence of `FINAL_SUCCESS_STATE_RESULT` means a successful operation returns no operation-specific terminal value. `FINAL_FAILED_STATE_RESULT_EXTENSION` extends the common AAC failure envelope rather than replacing it.

The interaction schema identity, not a physical schema filename, is part of the portable operation contract. If the operation changes any referenced interaction schema or its semantics incompatibly, the owning capability contract MUST move to a new capability version. An unchanged schema version may be reused by a later capability version.

## II.5 Operation identity is scoped to the capability contract

Operation identifiers are **not global identifiers**.

The canonical operation identity is the tuple:

```text
(capability id, capability version, operation id)
```

Therefore these are distinct operations:

```text
algites.vcs.repository / v1 / commit
example.database.transaction / v4 / commit
```

No global `AllKnownOperations` enum or equivalent registry is required or recommended.

The authoritative operation list belongs to each canonical capability contract definition.

## II.6 Operation IDs are stable within a contract version

An operation `id` is machine identity, not display text.

It SHOULD be concise, stable, and independent of implementation language.

For example:

```yaml
id: commit
```

A Java binding for capability contract version 4 might expose:

```java
CommitResult commit_4(CommitRequest request);
```

but the Java method name is a technology binding of the canonical operation `id`; reflection-visible method identity is not the architecture's source of truth.

## II.7 Operation schema

Each operation SHOULD define, where applicable:

- input/request schema;
- output/result schema;
- structured error schema or error taxonomy;
- nullability/optionality rules;
- ordering guarantees;
- concurrency/threading expectations;
- cancellation semantics;
- timeout/blocking semantics;
- transaction semantics;
- idempotency semantics;
- resource ownership/lifetime;
- sensitive/redacted fields;
- compatibility expectations.

A contract MAY use shared DTO/schema definitions across several operations.

## II.8 Operation-set changes and capability versions

Adding, removing, renaming, or behaviorally changing an operation may require a new capability contract version.

A change is breaking whenever an existing consumer that correctly implements the old contract cannot safely use the new definition under the same version identity.

The same `(capability id, version, operation id)` MUST NOT silently acquire incompatible semantics.

## II.9 Canonical contract definition

The canonical contract bundle for a capability version MUST provide enough information for Core to know its operation surface before runtime binding.

At minimum Core must be able to establish:

```text
capability id
contract version
operation ids
canonical contract identity
technology binding metadata required by the active runtime profile
```

Where generic invocation/observation is supported, Core MUST also have normalized input/output schema information sufficient to produce the normalized invocation representation defined in this specification.

---

## II.10 Capability provider definitions and multi-capability implementations

A capability provider definition is an implementation role, not a synonym for one capability. One capability provider definition and each of its concrete provider instances MAY provide any finite set of capability/version pairs. For example, one filesystem Data Entity provider instance may implement loading, storing and storage-management capabilities on the same runtime object.

In the component descriptor, these definitions are declared under the explicit `capability_providers` field. The name distinguishes general capability-provider definitions from domain-specific data, configuration, catalog, entitlement or other provider concepts. `capability_providers` describes implementation definitions; concrete configured provider instances remain separate Core-managed runtime state.

Conceptually:

```text
provider instance P
    provides capability A / versions 1,2
    provides capability B / version 1
    provides capability C / versions 2,3
```

Invocation is still addressed to one explicit provider instance and one explicit capability/version. Core MUST NOT reinterpret a multi-capability provider as several provider identities. Conversely, support for capability A does not imply support for B merely because both belong to the same capability provider definition.

A concrete provider instance MAY additionally be configured with an access policy such as `READ_ONLY` or `READ_WRITE` when the relevant domain defines such a policy. That policy constrains which of the provider's technically implemented operations Core may use; it does not change the canonical set of interfaces implemented by the provider class.

---


## II.11 Capability-provider operation metadata and parameters

A canonical capability operation defines the **portable** interaction payload contracts and behavior shared by every provider of that capability version. A concrete capability provider MUST declare provider-operation metadata for each implemented `(capability id, capability version, operation id)`. That metadata declares the concrete provider's Operation Interaction support and MAY additionally declare **operation parameters** when its implementation has meaningful choices that are not portable properties of the canonical capability contract.

Provider-operation `interaction.supported_state_result_delivery_modes` is implementation capability metadata. It MUST NOT be placed in the canonical capability operation because different providers of the same capability may support different delivery modes. The canonical operation merely defines which portable `RUNNING_*` result schemas exist; the provider chooses the subset of delivery modes it can actually realize.

Operation parameters are provider-specific implementation controls, not additional canonical operation arguments. They MUST NOT redefine the portable outcome of the capability operation or be used to hide a separate capability behind an implementation-specific switch.

A provider-operation descriptor therefore has the conceptual shape:

```yaml
operations:
  - capability: <capability-id>
    capability_version: <version>
    operation: <operation-id>
    interaction:
      supported_state_result_delivery_modes: [...]
      progress_reporting: false
      cancellation: false
      detail_level: false
      reporting_interval: false
    parameters: [...]
```

A capability-provider operation-parameter definition contains:

- stable parameter `id`;
- `name` as `AIcDisplayText`;
- `description` as `AIcDisplayText`;
- an inline JSON Schema `value_schema` defining the parameter value;
- optional display metadata for enum values, with enum `name` and optional `description` also represented as `AIcDisplayText`;
- `required` and optional definition `default`;
- `component_configurable`;
- `instance_configurable`;
- `invocation_overridable`.

Example:

```yaml
operations:
  - capability: _AAC.vcs.distributed-repository-synchronization
    capability_version: 1
    operation: pull
    interaction:
      supported_state_result_delivery_modes: [ON_DEMAND_COMPLETE]
    parameters:
      - id: integration_strategy
        name:
          text: Integration strategy
          resource_key: vcs.pull.integrationStrategy.name
        description:
          text: Determines how retrieved revisions are integrated.
          resource_key: vcs.pull.integrationStrategy.description
        value_schema:
          type: string
          enum: [MERGE, REBASE, FAST_FORWARD_ONLY]
        enum_values:
          - value: MERGE
            name:
              text: Merge
            description:
              text: Merge the histories.
          - value: REBASE
            name:
              text: Rebase
            description:
              text: Reapply local revisions on top of the retrieved history.
        default: MERGE
        component_configurable: true
        instance_configurable: true
        invocation_overridable: true
```

The effective value precedence is:

```text
definition default
    < component-configured value
        < provider-instance-configured value
            < invocation override
```

A more specific level may provide a value only when the corresponding configurability flag permits it. `required: true` means that an effective value MUST exist after this resolution. Every effective value MUST validate against `value_schema`.

Operation parameters do **not** have their own version axis. Operations are versioned by the owning capability contract; provider-specific operation parameters evolve with the capability provider/component implementation. Adding or changing an operation parameter therefore does not by itself create a new canonical capability version when the portable capability contract is unchanged.

An incompatible change to an operation-parameter definition MUST, however, be delivered as a newer component version. If persisted component-level or provider-instance-level values may no longer be valid or retain the same meaning, that component version MUST migrate its own operation-parameter configuration during upgrade before the new provider implementation becomes active. A component MUST NOT silently reinterpret persisted values written for an older parameter definition.

Provider implementations receive the **effective operation-parameter map** through Core invocation context separately from the canonical operation input. Consequently a technology binding MUST NOT add provider-specific parameters to the generated canonical capability method signature.

# III. Invocation Model

## III.1 Invocation identity

A capability invocation is an execution of one canonical operation against one resolved provider binding.

Conceptually:

```text
consumer
    -> capability id/version
        -> operation id
            -> selected provider instance
```

Each invocation SHOULD receive a Core-generated correlation identifier:

```text
invocation_id
```

The identifier is runtime correlation metadata and is not a persistent provider or domain identity.

## III.1.1 Core bridge is mandatory

A consumer MUST invoke another component only through a Core-owned capability handle/proxy. It MUST NOT hold the provider implementation/runtime object directly, even for an in-process profile.

Every cross-component call therefore passes through the Core invocation dispatcher, which preserves binding identity, contract/version identity, normalized validation, invocation/parent identity, observation/redaction, isolation transport and standardized error/remediation semantics.

Technology profiles may optimize dispatch but MUST NOT expose a bypass path around Core mediation.

## III.2 Invocation target must preserve the resolved instance DAG

A capability invocation is valid only through a binding that belongs to the Core-resolved acyclic extension provider-instance graph.

Conceptually:

```text
consumer instance A1 -> capability X -> provider instance A1    INVALID
consumer instance A1 -> capability X -> provider instance B1    potentially valid
```

Two distinct instances of the same implementation are distinct graph nodes and may bind to one another when doing so does not create a cycle elsewhere in the graph. The lifecycle specification owns the normative DAG validation rules.

## III.3 One authoritative result for SINGLE bindings

For a `SINGLE` consumer requirement, one provider instance is authoritative for the invocation.

Observation does not change this rule.

For example:

```text
consumer
    -> VCS/main-repository
        -> commit(...)
            -> one authoritative CommitResult
```

Attaching ten observers does not create ten VCS providers and does not create ten competing commit results.

## III.4 MULTIPLE capability semantics

A capability may intentionally define `MULTIPLE` consumer binding semantics where several provider instances are meaningful recipients.

Examples include:

```text
notifications
observation
tracing
auditing
metrics/event sinks
```

The exact aggregation, ordering, and failure semantics MUST belong to the capability contract.

## III.5 Nested invocations

An invocation may cause another capability invocation.

Core SHOULD make nested invocation relationships observable through correlation metadata where the runtime profile can provide them.

Conceptually:

```yaml
invocation_id: "..."
parent_invocation_id: "..."
```

This is useful for tracing a logical call graph without exposing implementation-private stack frames.

## III.6 Operation Interaction

Every capability invocation has a Core-mediated **Operation Interaction** context in addition to its portable operation input and effective provider operation parameters. Operation Interaction is generic invocation infrastructure; it MUST NOT be added separately to individual portable operation input schemas or generated capability method signatures.

The baseline execution lifecycle is Core-owned:

```text
PENDING
   ↓
RUNNING
   ├──────────→ COMPLETED
   ├──────────→ FAILED
   └──────────→ CANCELLED
```

The provider does not directly declare a terminal execution state. Core derives terminal state from the actual invocation outcome. A provider that supports cooperative cancellation observes the caller-side cancellation request at safe checkpoints and aborts through the standardized cancellation path; Core then performs the `RUNNING -> CANCELLED` transition.

Operation Interaction is one logical bidirectional protocol with two explicitly directional message models:

```text
provider operation ── OperationInteractionProviderToCallerMessage ──> caller
provider operation <── OperationInteractionCallerToProviderMessage ── caller
```

The provider-to-caller direction carries execution/result observations and telemetry. The caller-to-provider direction carries user/host interaction choices and result-consumption information. Core routes these messages and owns the execution lifecycle, but it MUST NOT interpret operation-specific state-result payload semantics.

### III.6.1 Provider-to-caller state and revisions

Each provider-to-caller publication carries at least:

```text
interaction_revision
execution_state
state_result_revision
optional state_result_payload_revision + state_result
events[]
interaction features
```

`interaction_revision` starts at `0` before any provider-to-caller publication. The first published interaction message has revision `1`; each subsequent atomic provider-to-caller publication increments it monotonically.

`state_result_revision` also starts at `0`. Value `0` means that no logical state result has yet been published. The first logical state-result change has revision `1`; every subsequent logical state-result change increments it monotonically. A message can therefore advertise that a newer state result exists even when its payload is intentionally omitted by the selected delivery mode.

When a message carries a state-result payload, `state_result_payload_revision` identifies the result revision represented by that payload. It MAY be lower than the latest `state_result_revision`, for example when a provider re-delivers a buffered operation-specific result revision. Core MUST NOT infer dependency, merge, replay or error semantics from gaps between result revisions.

Revision gaps are observable, not inherently erroneous. A video/live-preview operation may legitimately accept revision 17 even when revision 16 was not consumed; another operation may define sequential deltas that cannot be applied across a gap. Such semantics belong exclusively to the capability operation contract and its consumer/provider implementations.

### III.6.2 Immutable state-result publication

A state-result payload is an immutable publication snapshot. After a provider publishes an object through Operation Interaction it MUST NOT mutate that published object. Any logical change MUST be represented by a new state-result revision. Technology bindings SHOULD defensively snapshot/canonicalize mutable in-process values at the publication boundary where practical, so `IN_PROCESS` behavior does not accidentally differ from isolated runtimes.

Changing execution state and the associated state result MUST be atomic. Conceptually Core provides a transition equivalent to:

```text
transition(state=COMPLETED, state_result=final_result)
```

A provider may publish a new intermediate result without changing execution state through an operation equivalent to:

```text
update_state_result(partial_result)
```

For `ON_CHANGE_COMPLETE`, `ON_CHANGE_DELTA`, and `ALWAYS_COMPLETE`, a logical result change MUST be published together with its payload. A payload-less result-revision advance is meaningful only for on-demand delivery modes, where the provider may retain or reconstruct the corresponding payload itself.

The caller MUST NOT observe a new execution state paired with an obsolete state result solely because the transition was applied in several local assignments.

### III.6.3 State-result delivery modes

State-result delivery modes are **provider-operation capabilities**, not mandatory properties of the portable capability operation. A canonical capability operation defines the portable interaction payload kinds/schemas that may exist; each concrete capability provider operation declares which delivery modes it actually supports. The baseline modes are:

```text
ON_DEMAND_COMPLETE
ON_DEMAND_DELTA
ON_CHANGE_COMPLETE
ON_CHANGE_DELTA
ALWAYS_COMPLETE
```

Their semantics are:

- `ON_DEMAND_COMPLETE`: intermediate state-result payloads are not automatically attached. The caller may request a complete current representation when the operation provides one. A simple synchronous invocation without an explicit interaction callback/controller runs internally in this mode; its final normal operation output is returned when execution completes.
- `ON_DEMAND_DELTA`: operation-defined result fragments/deltas are retained or otherwise made available by the provider according to its own policy and are delivered when requested by the caller. The provider need not materialize an aggregate complete running result.
- `ON_CHANGE_COMPLETE`: whenever the logical running state result changes, the provider publishes a complete representation of the new state result.
- `ON_CHANGE_DELTA`: whenever the logical running state result changes, the provider publishes an operation-defined delta/fragment representation. AAC defines no generic delta language and Core MUST NOT interpret, merge or reconstruct such payloads.
- `ALWAYS_COMPLETE`: every provider-to-caller interaction publication includes the current complete result representation when one exists. This mode may intentionally trade bandwidth/serialization cost for a simpler caller that does not retain the previously received complete state result.

Every capability-provider operation MUST support `ON_DEMAND_COMPLETE` so the ordinary synchronous invocation remains available without requiring an interaction callback. This does not imply that the provider can produce a meaningful complete **intermediate RUNNING** snapshot. If the canonical capability operation defines no `RUNNING_COMPLETE_STATE_RESULT` interaction, a complete result may first exist at `FINAL_SUCCESS_STATE_RESULT`, or the operation may complete successfully without any result when that interaction kind is absent as well.

A capability provider may declare `ON_DEMAND_DELTA` or `ON_CHANGE_DELTA` only when the canonical capability operation defines `RUNNING_DELTA_STATE_RESULT`. A provider may declare complete delivery modes without a running-complete interaction; in that case it simply cannot publish a portable complete running result before a defined terminal result exists. Delta semantics, including whether revisions depend on earlier revisions, what the initial/no-result state means, and whether missing revisions are tolerable, remain operation-specific contract semantics.

The selected delivery mode changes transport/publication behavior only. It does not change the portable operation input or business meaning of the terminal output.

### III.6.4 Caller acceptance and provider buffering

Caller-to-provider interaction state contains `last_accepted_state_result_revision`. It starts at `0` and identifies the latest state-result revision that the caller has successfully received and incorporated into its own operation-specific usable state.

This field is deliberately **not** defined as a cumulative network-style acknowledgement. It does not assert that every lower revision was consumed. Whether a caller may accept a later revision after missing an earlier one is operation-specific. Core MUST NOT reject gaps, request replay, merge deltas, implement result buffering policy or otherwise mediate those semantics.

A provider MAY use `last_accepted_state_result_revision` to release buffered result data, retain/replay unaccepted data, spill it to external storage, throttle its own computation or apply another operation-specific policy. Such memory/backpressure/replay policy belongs to the provider/caller or reusable libraries above/below Core, not to AAC Core itself. Provider-specific tuning MAY be exposed through the normal provider operation-parameter mechanism where useful.

`last_accepted_state_result_revision` is useful for all delivery modes, including complete and on-demand delivery. For example, an on-demand complete result may be transported successfully but fail during caller-side deserialization or incorporation; the accepted revision then remains unchanged and provides useful diagnostic state.

### III.6.5 On-demand requests

Caller-to-provider interaction state includes a monotonic `state_result_request_id`, initially `0`. Incrementing it requests another state-result delivery under the selected on-demand mode. A provider can compare the current request ID with the last request it handled; repeated requests therefore remain distinguishable without Core understanding the requested payload.

### III.6.6 Events and hierarchical progress

State results are operation-domain data. Interaction events are telemetry describing what the running operation is doing. The baseline event families are `STATUS`, `PROGRESS`, `DETAIL`, and `DIAGNOSTIC`.

One provider-to-caller publication carries `events[]`, not a single event, so related telemetry changes can be emitted atomically. A progress event has a stable `progress_id` and MAY have `parent_progress_id`, permitting independent and hierarchical progress such as:

```text
Overall migration
└── Database 3/12
    └── Table 18/50
        └── Records 43,211/120,000
```

Human-facing event names/descriptions use `AIcDisplayText`. Intermediate telemetry may be throttled/coalesced according to host/provider policy because it is not itself the operation-specific state result. Listener/rendering failure MUST NOT by itself fail the provider operation.

### III.6.7 Caller-to-provider interaction controls

Caller-to-provider state includes at least:

```text
last_accepted_state_result_revision
interaction_mode
cancellation_requested
detail_level
reporting_interval_ms
failure_detail_level
state_result_delivery_mode
state_result_request_id
```

`interaction_mode` has baseline values `FOREGROUND` and `BACKGROUND`. It is owned by the caller/host and describes the user's interaction/attention mode, not provider execution placement. `FOREGROUND -> BACKGROUND` does not change execution state, create a new process/thread or detach reporting. A host may keep the same running invocation visible in a task/status area while permitting unrelated work and later restore a foreground presentation.

Cancellation is cooperative. A provider that declares cancellation support MUST observe `cancellation_requested` at safe interruption points and preserve its own transaction/consistency guarantees. Cancellation MUST NOT imply rollback across an irreversible commit boundary.

`reporting_interval_ms` and `detail_level` are interaction preferences, not portable business parameters. A provider may use them to avoid expensive detail/progress production. A host may independently reduce its own rendering frequency.

### III.6.8 Locale and failure state

The invocation context carries an optional locale (normally a BCP-47 language tag such as `cs-CZ` or `en-US`). It allows an in-process, isolated or remote provider to prepare user-facing text in the caller's requested language when it has appropriate resources. AAC Core does not assume that it owns the provider's localization resources.

A standardized FAILED state result contains at least technical `system_message` and `exception_type`; it may additionally contain user-facing `AIcDisplayText user_message`, `error_code`, `stack_trace`, and an operation-specific extension. `system_message` is suitable for technical diagnostics/logging and need not be localized. `user_message.text`, when supplied, SHOULD be directly displayable without requiring the caller to resolve the optional `resource_key`.

The caller's `failure_detail_level` controls whether expensive/sensitive failure detail such as a formatted stack trace should be materialized and transported where the runtime can avoid doing so. It does not guarantee that the originating language runtime avoided all stack-capture cost internally.

`FINAL_SUCCESS_STATE_RESULT`, when present, is the `COMPLETED` terminal result schema. `FAILED` always has the generic AAC failure base and MAY define `FINAL_FAILED_STATE_RESULT_EXTENSION`. `CANCELLED` MAY define `FINAL_CANCELLED_STATE_RESULT`. A cooperative provider that has such a cancellation result returns it through the standardized cancellation path; Core performs one atomic `RUNNING -> CANCELLED` transition with that optional result rather than requiring the provider to publish a separate terminal state.

### III.6.9 Runtime boundaries and synchronous/asynchronous use

A caller that only needs the final result may use the ordinary synchronous capability invocation without creating an explicit interaction controller. Core supplies a fresh invocation-local no-op/default interaction context using `ON_DEMAND_COMPLETE` and returns the normal terminal output. Even this no-op context starts its result revision at `0` for each invocation; it is not shared as mutable execution state between unrelated calls.

A caller that needs live progress, partial results, cancellation, foreground/background interaction, diagnostics or non-blocking execution attaches/receives an Operation Interaction controller. Asynchronous start and `FOREGROUND/BACKGROUND` are orthogonal: an invocation may execute asynchronously while still presented as foreground, then switch to background without changing execution semantics.

Isolation/RPC profiles MUST bridge the same directional Operation Interaction protocol rather than attempting to pass toolkit callbacks or process-local mutable objects across the boundary. The reference Python `PROCESS` profile bridges the protocol over its Core/runtime channel. The Python 3.14+ `SUBINTERPRETER` profile uses cross-interpreter queues plus a separate execution thread to bridge live messages while preserving interpreter isolation. Nested Core-mediated invocations SHOULD inherit the current interaction context unless the caller explicitly supplies another one.

The canonical interaction models are `_AAC.schema.operation-interaction-provider-to-caller-message/1`, `_AAC.schema.operation-interaction-caller-to-provider-message/1`, `_AAC.schema.operation-interaction-event/1`, and `_AAC.schema.operation-failure/1`.

---

# IV. Normalized Invocation Representation

## IV.1 Purpose

Cross-technology tracing, auditing, diagnostics, and generic tooling must not depend on arbitrary Java objects, Python objects, private implementation classes, or process-local pointers.

Core therefore needs a technology-neutral normalized representation for generic invocation metadata.

## IV.2 Baseline normalized values

A baseline normalized representation SHOULD support at least:

```text
null
boolean
integer
decimal/string-encoded numeric where precision requires it
string
bytes
list
map/record
schema-identified structured value
```

A technology profile MAY define an efficient binary representation as long as its logical meaning is equivalent.

## IV.3 Contract-driven normalization

Normalization MUST be driven by the canonical capability contract, not by arbitrary reflection over provider implementation objects.

This allows Core to know which fields are:

- part of the public contract;
- optional;
- sensitive;
- structured DTO members;
- safe to expose to generic tooling.

## IV.4 Sensitive data

Operation schemas MUST be able to identify fields that must not be exposed verbatim through generic observation.

Conceptually:

```yaml
fields:
  token:
    type: string
    sensitive: true
```

Core MUST apply redaction before handing a normalized event to an observer that is not explicitly authorized for sensitive data.

The default generic representation SHOULD therefore contain:

```yaml
token: "<redacted>"
```

rather than the secret.

Redaction is a Core responsibility because generic observer plugins must not be trusted to redact values after receiving them.

---

# IV.A Standard Permission Failure and Remediation

## IV.A.1 Permission denial is a normalized invocation outcome

A provider may reject an operation according to its current Core-validated entitlement context. The normalized error category is:

```text
PERMISSION_DENIED
```

Language profiles may map this to a typed exception such as `AIxPermissionDenied`.

The error may carry a capability-owned diagnostic permission identifier and remediation/offer metadata. The permission identifier is interpreted in the namespace of the invoked `(component, capability id, capability version)`. Consumers are not required to understand that provider permission vocabulary.

## IV.A.2 Capability binding is not entitlement-tier binding

A consumer requires a capability/version, not another component's commercial permission level. Therefore ordinary permission changes do not alter the resolved binding. The same provider remains the target; an operation may succeed or return `PERMISSION_DENIED` according to current provider entitlement context.

Entitlement licensing scope subject identity, grant validity, entitlement-document/bundle structure, and entitlement-provider provenance are evaluated outside the invocation contract according to `Application-Component-Context-Configuration-and-Entitlement-Specification.md`. A single signed entitlement document may carry grant sections for multiple components; invocation semantics see only the effective permission context for the invoked provider/capability. The presence, absence, or semantic invalidity of another component entry in that bundle does not become part of this capability's invocation contract. The owning component descriptor declares its entitlement licensing-scope types, and the provided capability/version declares its permission vocabulary plus references to those types through `possible_licensing_scopes`. Capability consumers MUST NOT depend on which applicable entitlement licensing scope/provider supplied the effective permission.

## IV.A.3 Core remediation

Because the invocation bridge sees standardized permission failures, Core may attempt a product-defined entitlement remediation flow before exposing the failure to the consumer.

After successful remediation Core updates the target provider's entitlement context. Core MAY transparently retry the original invocation only when retry safety is explicitly established by the provider/contract failure semantics.

A technology binding may expose an `AIiEntitlementRemediator`-equivalent service. Core passes normalized context such as target capability/version, provider-instance identity, missing permission identifier when supplied, and remediation hint. The remediation service does not receive authority to bypass issuer verification; successful remediation means new/changed evidence is available and Core must re-evaluate it before retry. Baseline Core performs at most one transparent remediation retry per original invocation.

A permission failure SHOULD include a retry disposition equivalent to:

```text
SAFE_AFTER_ENTITLEMENT_CHANGE
DO_NOT_RETRY
```

`SAFE_AFTER_ENTITLEMENT_CHANGE` means the authorization failure occurred before externally visible business effects, or the operation is otherwise safe to repeat according to the contract's idempotency semantics.

## IV.A.4 No unsafe transparent retry

If retry safety is absent/unknown, Core MUST NOT silently repeat the operation. It may report that entitlement remediation succeeded but the caller/user must initiate the operation again.

---

# IV.B. Capability Authorization Contracts

## IV.B.1 Authorization is distinct from entitlement

Capability **authorization** answers which operations a consumer component and the current application principal are allowed to invoke through an already-resolved capability binding. It is distinct from entitlement:

- entitlement permissions are capability-owned commercial/use rights delivered to the provider; Core may treat their identifiers as opaque;
- authorization permissions are part of the canonical capability contract and therefore are understood by Core, the provider binding, and the consumer admission process.

`provides`/`consumes` establishes topology and contract compatibility. It does not by itself authorize every operation of the capability.

## IV.B.2 Canonical authorization vocabulary

A capability version MAY publish an authorization vocabulary. Every authorization permission intended for user/admin interaction MUST carry stable machine identity and presentation metadata:

```yaml
capability:
  id: _AO.core.siteManagement
  version: 1
  name:
    text: Site management
    resource_key: ao.siteManagement.name
  description:
    text: Read and modify Orchestrator Site entities.
    resource_key: ao.siteManagement.description

authorization_permissions:
  - id: VIEW_SITE
    name:
      text: View sites
      resource_key: ao.siteManagement.authorization.view.name
    description:
      text: Allows the component to read Site data.

  - id: EDIT_SITE
    name:
      text: Edit sites
      resource_key: ao.siteManagement.authorization.edit.name
    description:
      text: Allows the component to modify writable Site attributes.
```

`id` is the stable semantic identity. `name` and `description` are presentation metadata and MUST NOT be used as identity. A display text MAY contain direct `text`, an opaque `resource_key`, or both. When both are present, direct text is the baseline fallback. AAC does not require a localization engine in the baseline specification.

## IV.B.3 Operation authorization requirements

Each operation MAY reference authorization permissions declared by that same capability version. The baseline authorization expression contains only two flat constructs:

```yaml
authorization:
  all_of: [EDIT_SITE]
  any_of: [STANDARD_EDITOR, ADVANCED_EDITOR]
```

Semantics are:

1. every permission in `all_of` MUST be effective;
2. when `any_of` is non-empty, at least one permission in `any_of` MUST be effective;
3. both conditions apply when both constructs are present.

AAC v1 does not define `NOT`, nesting, or a general expression language. Capability designers SHOULD prefer meaningful denormalized permissions where doing so produces a clearer administrative contract.

Every referenced permission ID MUST exist in the capability-version authorization vocabulary. This is a contract-admission validation rule.

## IV.B.4 Consumer-requested authorization

A consumer requirement MAY request a subset of the authorization vocabulary of the negotiated capability version:

```yaml
consumes:
  capability: _AO.core.siteManagement
  version: 1
  requested_authorizations:
    - VIEW_SITE
    - EDIT_SITE
```

The request expresses least-privilege intent. It does not itself grant access. Product/system policy, administrator approval, installation/admission policy, or another Core authorization authority grants an allowed subset.

A component MUST NOT be granted an authorization permission it did not request for that requirement. A request containing an identifier not declared by the negotiated capability version is invalid.

## IV.B.5 Runtime enforcement

Before invoking a protected provider operation, the Core bridge MUST verify the operation's canonical authorization requirement against the consumer-instance/requirement grant. When the product uses current-principal authorization, Core MUST additionally verify the same required permissions against the current application principal.

Conceptually:

```text
canonical operation authorization
        ⊆ component authorization grant
        AND
canonical operation authorization
        ⊆ current-principal authorization, when configured
```

Authorization failure MUST be rejected by Core before provider business logic is entered.

## IV.B.6 Product/Core capabilities use the same model

A host product SHOULD expose reusable Core/domain/UI services as normal capabilities of one or more built-in product components. External and built-in consumers call them through the same Core bridge.

For example, an Orchestrator map component may consume `_AO.core.siteManagement/1` to read/update Site data and a UI capability to invoke the standard Site editor. Its map coordinates may be modeled as a separate component-supported Data Entity referencing the Site UID, while changes to `display_name` remain Site mutations mediated by the appropriate capability.

Built-in components may be pre-authorized by product trust policy, but they SHOULD NOT bypass the capability bridge merely because their implementation ships with the product.

# V. Generic Capability Invocation Observation

## V.1 Observation is a capability

Generic observation is modeled as a normal versioned capability.

The logical capability is referred to in this document as:

```text
capability observation
```

A product profile assigns the concrete capability identifier.

For the Algites Orchestrator profile, the intended built-in identifier is:

```text
_AAC.capability.observation
```

The observation capability has its own independent contract version.

Conceptually:

```yaml
provides:
  _AAC.capability.observation:
    versions: [1]
```

## V.2 Why observation is not per-capability

Generic observation MUST NOT require a parallel observation capability for every business capability.

Do not require patterns such as:

```text
vcs.status.observation
vcs.commit.observation
configuration.change-plan.observation
...
```

A generic tracer, auditor, or metrics collector needs a common invocation envelope, not a duplicate interface tree.

Domain-specific event capabilities MAY still exist where a product intentionally defines semantic events rather than generic invocation observation.

## V.3 Observation phases

Version 1 defines two logical phases:

```text
PRE
POST
```

`PRE` means Core has resolved the invocation and emits the observation event before the provider operation begins.

`POST` means the provider operation has completed with either success or failure and Core emits the resulting outcome.

A separate `ERROR` phase is not required in the baseline model; provider failure is represented by a `POST` event containing a failure outcome.

## V.4 PRE event

A PRE event SHOULD contain at least:

```yaml
invocation_id: "..."
parent_invocation_id: "..."   # optional
phase: PRE

capability:
  id: "example.vcs.repository"
  version: 1

operation:
  id: commit

consumer:
  component_id: "..."
  logical_scope_id: "..."     # optional

provider:
  component_id: "..."
  provider_definition_id: "..."
  instance_id: "..."

arguments:
  ... normalized and redacted contract values ...

timestamp: "..."
```

The exact serialized field names may be formalized by a schema specification, but the semantic information above is baseline contract material.

## V.5 POST event

A POST event SHOULD contain the same invocation identity and routing context plus the operation outcome.

Success example:

```yaml
invocation_id: "..."
phase: POST

capability:
  id: "example.vcs.repository"
  version: 1

operation:
  id: commit

arguments:
  ...

outcome:
  success: true
  result:
    ... normalized and redacted result ...
  error: null

duration_ms: 37
timestamp: "..."
```

Failure example:

```yaml
outcome:
  success: false
  result: null
  error:
    contract_error_id: "..."
    message: "..."
    details:
      ... normalized and redacted values ...
```

Technology-private stack traces MUST NOT be assumed to be part of the portable contract. A product may expose privileged diagnostic metadata separately.

## V.6 Observer operation

The observation provider exposes an operation conceptually equivalent to:

```text
observe(ObservationInput) -> ObservationOutput
```

The operation input schema is the `ObservationInput` object itself. The invocation payload MUST NOT add a second transport-only wrapper such as `{ "observation_input": ... }`; the normalized fields of `ObservationInput` are the operation arguments validated by the canonical observation input schema.

`ObservationOutput` confirms delivery/processing status only.

It MUST NOT contain:

```text
replacement arguments
replacement result
allow/deny decision
transaction decision
```

An observer is read-only with respect to the observed invocation.

## V.7 Observer failure isolation

Failure of an observer MUST NOT by default change the result, transaction status, or success/failure state of the observed provider invocation.

For example:

```text
VCS commit succeeds
Tracer/file fails because disk is full
```

The VCS commit remains successful. Core records an observer-delivery diagnostic separately.

A future policy profile may define stricter audit-delivery requirements, but such behavior must be explicit and must not be confused with baseline observation semantics.

## V.8 Observer versus interceptor

An observer reads an invocation; it does not control it.

Any future mechanism that may:

- rewrite arguments;
- veto execution;
- replace results;
- convert success into failure;

is an **interceptor/policy** mechanism and requires a separate capability contract with explicit transaction and ordering semantics.

It MUST NOT be added implicitly to the observation capability.

---

# VI. Observation Binding

## VI.1 Binding is Core-owned topology

Observer instance configuration answers:

```text
How does this observer behave?
```

Observation binding answers:

```text
Which invocations does this observer receive?
```

These are separate concerns.

For example, an observer instance may contain:

```yaml
id: "4b8e6d8d-6c7f-4de7-8e2f-..."
name: "stdout"
configuration:
  output: stdout
  pretty_print: true
```

while Core-owned topology contains:

```yaml
observer_instance_id: "4b8e6d8d-6c7f-4de7-8e2f-..."
observes:
  - capability: "example.vcs.repository"
    operations: [commit, push]
    phases: [PRE, POST]
```

The observer plugin MUST NOT silently invent or persist hidden observation targets outside Core-owned binding state.

## VI.2 Selector structure

A baseline observation selector has the conceptual structure:

```text
capability selector
optional finite version selector
optional operation selector
phase selector
```

Conceptually:

```yaml
observes:
  - capability: "example.vcs.repository"
    versions: [1, 2]
    operations: [commit, push]
    phases: [PRE, POST]
```

## VI.3 Operation selectors reference the capability contract

The `operations` field does **not** reference a global operation registry.

Every operation ID is interpreted in the scope of the selector's capability and selected capability version(s).

Thus:

```yaml
capability: "example.vcs.repository"
operations: [commit]
```

means:

```text
operation `commit` defined by example.vcs.repository
```

not every operation named `commit` in the system.

## VI.4 Omitted operations

If `operations` is omitted, the selector applies to every operation of the selected capability/version set.

Therefore:

```yaml
- capability: "example.vcs.repository"
  phases: [PRE, POST]
```

is equivalent to observing all operations of that capability.

## VI.5 Capability wildcard

A product MAY support a capability wildcard for generic tracers:

```yaml
- capability: "*"
  phases: [PRE, POST]
```

This means all **observable** admitted capability invocations, subject to mandatory exclusions and security policy.

Namespace/prefix selectors such as:

```text
example.vcs.*
```

MAY be supported by the binding schema if the product can define deterministic matching rules. They are convenience selectors, not capability identities.

## VI.6 Version selection

For semantic observers that interpret specific DTO fields, explicit finite contract versions SHOULD be declared.

Generic structural tracers MAY be allowed to omit the version selector and observe any currently admitted version that Core can normalize.

An observer MUST NOT infer semantics of a contract version it has not declared or otherwise been defined to understand.

## VI.7 Selector validation

When a selector names a concrete capability/version/operation, Core SHOULD validate it against the active or install-time contract catalog.

Invalid example:

```yaml
capability: "example.vcs.repository"
versions: [1]
operations: [nonexistent-operation]
```

Core should report a configuration error rather than silently ignore the unknown operation.

For wildcard selectors, matching is evaluated against the admitted runtime catalog.

## VI.8 Observation-delivery exclusion

The observation capability itself MUST NOT be observable through its own generic observation mechanism. This is an explicit meta-capability rule in addition to the resolved-instance DAG invariant; framework observation dispatch must not recursively generate observation events for its own delivery calls.

Otherwise:

```text
observation delivery
    -> observation invocation
        -> observation delivery
            -> ...
```

would recurse indefinitely.

Therefore the wildcard set is always conceptually:

```text
all observable capabilities
minus the observation capability itself
```

## VI.9 Additional exclusions

A product MAY exclude internal bootstrap, contract-admission, recovery, or security-sensitive operations from generic observation.

Such exclusions MUST be explicit product/runtime policy and SHOULD be diagnosable to administrators.

---

# VII. Runtime Dispatch Semantics

## VII.1 Baseline sequence

For an observed successful invocation, the logical sequence is:

```text
1. resolve consumer binding and operation
2. normalize/redact PRE arguments
3. emit PRE observation to matching observer instances
4. invoke the authoritative provider instance through the Core bridge
5. capture success result
6. normalize/redact POST result
7. emit POST observation to matching observer instances
8. return the authoritative provider result to the consumer
```

For provider failure:

```text
1. ... PRE as above
2. provider fails
3. normalize/redact structured failure
4. emit POST observation with success=false
5. propagate the provider failure according to the original capability contract
```

Observer delivery failure is handled separately from provider failure.

## VII.2 Multiple observers

Several provider instances may provide the observation capability:

```text
Tracer / stdout
Tracer / vcs-log-file
Audit / default
Metrics / debug
```

Core may bind all matching instances under the observation capability's `MULTIPLE` semantics.

## VII.3 Ordering

Unless the observation contract version explicitly guarantees ordering, observers MUST NOT depend on a stable ordering relative to other observers.

A product implementation MAY invoke observers sequentially or concurrently.

The PRE/POST relationship is defined relative to the observed provider invocation, not as a global ordering among observer instances.

## VII.4 Delivery synchronization

A runtime profile may support synchronous or asynchronous observer delivery.

However:

- PRE event creation occurs logically before the provider operation;
- POST event creation occurs after the provider operation outcome exists;
- asynchronous delivery MUST preserve the event's phase and timestamps;
- observer backlog MUST NOT silently mutate the observed operation's result.

If a product exposes selectable delivery policy, that policy belongs to Core/runtime configuration and must be visible to diagnostics.

## VII.5 Timeouts and backpressure

Observer processing can be slow or unavailable.

The runtime SHOULD define:

- observer invocation timeout;
- queue/backpressure policy for asynchronous delivery;
- diagnostic/drop policy;
- shutdown flushing behavior where applicable.

These operational policies MUST remain separate from the semantic result of the observed operation unless a stricter explicitly documented product profile says otherwise.

## VII.6 Reentrancy

Delivery of the observation capability itself is never observed.

If an observer implementation performs ordinary capability calls while handling an event, those calls are normal invocations. To prevent accidental self-recursion, Core SHOULD suppress delivery of nested observations back to the same observer instance while that instance is processing the parent observation, unless an explicitly safe profile defines otherwise.

Other observer instances may still receive those nested invocations according to their bindings.

---

# VIII. Technology Binding Requirements

## VIII.1 Java

Java language bindings SHOULD be generated from the canonical capability contract rather than manually duplicating operation/security/interaction metadata. Portable data types are generated deterministically from interaction schema identity `(schema id, schema version)`. Operation-specific failure exception types and their default factories are generated deterministically from `(capability id, capability version, operation id)`.

A generated provider interface receives the provider-facing interaction view only. Conceptually:

```java
public interface AIigRestoreStorageBackup_1 {
    AIcgdRestoreStorageBackupResult_1 restoreBackup_1(
        AIcgdRestoreStorageBackupRequest_1 input,
        AIiOperationInteractionProviderToCaller interaction
    );
}
```

The generated caller-facing binding uses `AIiOperationInteractionCallerToProvider<E>` where `E` is the generated operation-specific failure exception base. Its completion result distinguishes `SUCCESS` and `CANCELLED`; `FAILED` is materialized as an exception. Conceptually:

```java
AIcOperationCompletion<
    AIcgdRestoreStorageBackupResult_1,
    AIcgdRestoreStorageBackupCancelledResult_1
> restoreBackup_1(
    AIcgdRestoreStorageBackupRequest_1 input,
    AIiOperationInteractionCallerToProvider<AIxgRestoreStorageBackupFailed_1> interaction
) throws AIxgRestoreStorageBackupFailed_1;
```

Java permits a bounded type variable in a `throws` clause, but generated operation bindings SHOULD normally expose the concrete generated operation exception because a capability may contain several operations with independent failure contracts. A caller MAY install a caller-local exception factory on `AIiOperationInteractionCallerToProvider<E>`; every exception produced by that factory MUST be `E` or a subclass of `E`. This permits application code to derive several local exception subclasses from the generated operation exception and select among them according to portable failure data.

The factory is caller-local technology binding state. It is never serialized or sent to the provider. If the caller does not install a custom factory, the generated typed binding installs the generated default factory. A typed generated binding MUST NOT silently fall back to the more general `AIxCapabilityOperationFailed`, because that would violate the generated `throws` contract. Absence of the required typed binding/factory is a framework/binding error. The generic `AIxCapabilityOperationFailed` fallback is reserved for dynamic/untyped invocation APIs.

`FINAL_FAILED_STATE_RESULT_EXTENSION` is first normalized/materialized from its declared schema identity. The generated/default exception factory then combines the common AAC failure envelope with that typed additional data to instantiate the generated operation exception.

Java annotations use the `AIa` prefix. They are generated language-binding metadata, not an independent source of authorization truth. The implementation implements the generated interface and MUST NOT redefine a conflicting operation/authorization mapping. Shared generated interfaces and DTOs follow the Core-owned class-loader identity rules defined in the Java runtime profile.

## VIII.2 Python

Python bindings SHOULD likewise be generated from the canonical capability contract. Generated interfaces use `AIig..._N`; generated non-data classes use `AIcg..._N`; generated DTO/data-object classes use `AIcgd..._N`. The `g` marker denotes generated source. The optional `d` marker is used only for a type that is explicitly a data object/DTO and MUST NOT be added to a generated behavioral class merely because it is generated. Equivalent generated enum/interface forms follow the same type-letter + `g` rule (for example `AIng..._N` and `AIig..._N`).

The generated Python provider method receives `AIiOperationInteractionProviderToCaller`. The generated caller facade accepts `AIiOperationInteractionCallerToProvider[GeneratedOperationFailure]`, installs the generated default failure factory when the caller has not supplied one, materializes `SUCCESS`/`CANCELLED` payloads into their generated schema types, and raises the generated operation-specific exception for `FAILED`. Python has no checked-exception declaration analogous to Java `throws`, but the runtime exception class and typed `additional_data` follow the same portable contract. A custom caller factory must return the generated operation exception or one of its subclasses.

`_N` is the version of the canonical definition that directly defines the generated program type, not automatically the containing component or capability version. A DTO generated from schema version 1 therefore remains `..._1` even when capability version 2 reuses that unchanged schema. Multiple versions such as `AIcgdRepositoryIdentity_1` and `AIcgdRepositoryIdentity_2` MUST be able to coexist in one runtime.

Generated types MUST expose the canonical source ID and source version as machine-readable provenance. They SHOULD additionally expose the canonical resource path. The same provenance MUST be visibly stated in generated Javadoc/docstrings together with a do-not-edit indication. Source kind is not required: canonical source identity is `(source id, source version)`, while the resource path is provenance/location rather than identity.

A generated method SHOULD accept one normalized/generated input DTO and return one output DTO rather than expanding schema properties into a fragile variable method signature. Its Python name carries the capability-contract suffix as well, for example `get_site_1(...)` for canonical operation `get_site` in capability version 1. Generated decorators/metadata map that versioned binding method back to the unsuffixed canonical operation ID and authorization requirement. The canonical contract remains authoritative; generated Python metadata is only the binding representation.

This approach preserves identical contract identity across in-process, subinterpreter and process/RPC profiles and allows the same input/output schemas to drive validation and, where appropriate, generic UI forms.

A canonical capability contract is defined once by its owning contract artifact and may be implemented by multiple independent providers, including providers written in different technologies. Consumers and providers share the canonical contract identity; they do not copy provider-private interface definitions. Technology-neutral schema/contract sources may therefore live under an artifact's `src/product/schema` tree while Java, Python, or other bindings are generated under their respective technology trees.

## VIII.3 Process/RPC profiles

A process-isolated profile may map capability/operation identity directly to an IPC/RPC method identifier. The same operation tuple remains authoritative regardless of wire encoding.

In the baseline AAC process profile the process boundary belongs to a concrete provider instance. Core owns a persistent endpoint for that instance and transmits normalized invocation envelopes over the process channel. If the provider itself consumes another capability, its process-local consumer handle sends a reverse request to Core identifying the already injected requirement/handle; Core remains responsible for selecting and invoking the resolved target. A process provider MUST NOT use IPC addresses as an alternative binding/discovery mechanism.

Correlation/causal metadata such as invocation and parent-invocation identity MUST survive the process boundary so observation/tracing remains one logical invocation chain.

---

## VIII.4 User-visible metadata

Definitions that may be presented to users or administrators SHOULD carry `name` and `description` presentation metadata in addition to their stable technical IDs. This applies at least to components, capability provider definitions, consumer requirements, capabilities, operations, authorization permissions, entitlement permissions, configuration profiles/scopes/providers, authentication profiles, and Data Entity support declarations when those definitions appear in product UI.

The common display-text shape permits:

```yaml
name:
  text: Edit sites
  resource_key: ao.authorization.editSite.name
```

or either field alone. `resource_key` is intentionally opaque to AAC v1; a product-localization engine MAY resolve it. No localization engine is required by this specification. `text` is the baseline fallback when available.

For schema-driven configuration fields, products MAY use equivalent schema presentation extensions such as `x-aac-name` and `x-aac-description`, while ordinary JSON Schema `title`/`description` remain valid fallback metadata.

# IX. Descriptor and Contract-Bundle Considerations

## IX.1 Static operation discovery

All operation identities required for mandatory graph/runtime preparation MUST be knowable from static contract metadata without executing arbitrary provider business logic.

Core should not need to instantiate a component merely to ask which methods a capability has.

## IX.2 Contract-bundle admission

When an extension component introduces a capability contract unknown to the original Core build, its canonical contract bundle may define new operation IDs.

The flow is:

```text
plugin package contains capability-group/contract resources
    -> Core admits referenced capability groups
    -> Core discovers contract
    -> Core validates/adopts canonical capability version
    -> operation set becomes known to active contract catalog
    -> binding and observation selectors may reference those operations
```

This permits third-party components to communicate through new capability contracts without requiring a global Core release containing every future operation name.

During a component replacement transaction, capability-group and contract admission is evaluated against the complete target component set. Core MUST rebuild the target active group/contract catalogs from built-in definitions plus canonical resources supplied by the target set; it MUST NOT merely union new candidate resources into the current catalog. A contract or group supplied only by a replaced/removed component therefore disappears from the target catalog unless another target source supplies the same canonical definition. Contract admission MUST reject a `group_id` that is not present in that target capability-group catalog.

## IX.3 Unknown-at-build-time does not mean unknown-at-binding-time

A capability and its operations may be unknown when the Core binary was built.

They MUST NOT remain semantically unknown to Core at the point where Core establishes a governed cross-component binding.

Core must first admit enough canonical contract information to mediate the binding and technology runtime safely.

---

# X. AAC Framework Contract Profile

## X.1 Reserved framework namespace

Algites Application Components reserves:

```text
_AAC.*
```

for stable framework-owned cross-language contracts and identities. Products using AAC MUST use a separate namespace for product-specific business capabilities. Third-party components MUST use their own stable namespace.

## X.2 `_AAC.capability.observation/v1`

The framework generic observation contract is grouped under `_AAC.runtime.observation` and is:

```text
_AAC.capability.observation / 1
```

with a provider operation conceptually named `observe` and Core-owned observation bindings selecting which invocations each observer instance receives.

## X.3 Generic tracing plugin example

A diagnostic component may declare an observer capability provider definition with several Core-managed instances:

```text
instance GUID A
name: stdout
configuration:
    output: stdout

instance GUID B
name: vcs-log-file
configuration:
    output: file
    path: ...
```

The corresponding Core-owned observation bindings may select all capabilities for the first instance and a product-specific VCS capability namespace for the second. The observer implementation remains reusable because it processes the normalized observation envelope rather than product-private runtime objects.

Product-specific namespaces such as Algites Orchestrator `_AO.*` belong in separate product profiles.

# XI. Security and Privacy Requirements

## XI.1 Least exposure

Generic observation is powerful and can expose operation arguments and results across component boundaries.

Core MUST treat observer attachment as a privileged topology/configuration action according to product security policy.

## XI.2 Redaction before dispatch

Sensitive contract fields MUST be redacted or omitted before observation dispatch unless an explicitly privileged observer context is authorized to receive them.

## XI.3 No private implementation leakage

Observation MUST NOT expose:

- provider-private implementation objects;
- raw memory identities;
- private dependency types;
- arbitrary reflection dumps;
- secrets merely because they occur in implementation state.

Only canonical contract data and explicitly allowed runtime metadata belong in the generic envelope.

## XI.4 Diagnostic metadata

A product may expose additional privileged diagnostic fields, but such fields should be separately classified and must not silently become part of the portable capability contract.

---

## XI.5 Persistence-migration failures remain Core-mediated

Configuration and Data Entity migrations are not ordinary direct component-to-storage calls. Technology bindings MUST preserve the general AAC rule that component-owned persisted payload transformations are invoked under Core control; components do not bypass Core persistence merely because migration code runs in-process. Detailed schema/migration semantics are defined by `Application-Component-Context-Configuration-and-Entitlement-Specification.md` and `Application-Component-Lifecycle-and-Provisioning-Specification.md`.

## XI.6 External-service authentication is not capability entitlement

Authentication to an external HTTP/service endpoint and AAC entitlement permission are separate concepts. A capability provider may use a shared AAC authentication profile/secret reference to reach an external service while independently interpreting Core-validated entitlement permissions for its own capability operations. Consumers MUST NOT receive or depend on the provider's external credential material.

Core invocation mediation MUST NOT leak resolved passwords, bearer tokens, private keys, or equivalent authentication material into normalized observation events.

# XII. Conformance Requirements

## XII.1 Capability-contract tests

Conformance tooling SHOULD test:

- unique operation IDs within each capability/version;
- stable capability/version identity;
- exactly one admitted `group_id` per capability contract;
- canonical capability-group identity, parent linkage and duplicate/conflict handling;
- valid request/result schemas;
- declared error semantics;
- sensitive-field metadata;
- technology-binding completeness;
- canonical contract digest/identity consistency.

## XII.2 Observation-selector tests

Test at least:

- one capability / all operations;
- one capability / selected operations;
- selected finite versions;
- PRE only;
- POST only;
- PRE + POST;
- wildcard capability selector;
- invalid operation selector rejection;
- exclusion of observation capability itself.

## XII.3 Runtime observation tests

Test at least:

- PRE arrives before provider execution logically begins;
- POST success contains normalized result;
- POST failure contains normalized error;
- observer failure does not alter provider result;
- several observer instances can receive one invocation;
- sensitive values are redacted;
- observation delivery does not recursively observe itself;
- nested capability calls carry correlation where supported;
- provider remains singular/authoritative for a `SINGLE` business capability;
- in-process consumers still invoke through the Core bridge/proxy rather than a provider object;
- `PERMISSION_DENIED` is normalized consistently;
- safe entitlement remediation may retry when explicitly allowed;
- unsafe/unknown retry disposition is never transparently retried.

## XII.4 Dynamic contract tests

Test a plugin-supplied capability unknown to the original Core build:

```text
plugin A supplies canonical capability X/v1 with operations [foo, bar]
plugin B consumes X/v1
observer selects X/foo
```

Core must:

1. admit X/v1;
2. know `foo` and `bar` from the canonical contract;
3. resolve the provider/consumer binding;
4. validate the observation selector;
5. deliver normalized PRE/POST events for `foo`.

No global Core operation enum should need modification.

---

# XIII. Architectural Invariants

1. **Every capability belongs to exactly one admitted capability group, and grouping has no binding/runtime semantics.**
2. **A capability version defines one or more canonical operations.**
3. **Operation IDs are scoped to capability/version, not globally.**
4. **The canonical operation identity is `(capability id, version, operation id)`.**
5. **Operation schemas belong to the capability contract.**
6. **Core can admit new capability contracts and operation sets supplied by extension components.**
7. **Generic observation is a normal independently versioned capability.**
8. **Observation bindings are Core-owned topology, separate from observer-instance configuration.**
9. **Observation selectors may filter by capability, version, operation, and PRE/POST phase.**
10. **Operation selectors are interpreted through the selected capability contract, never a global operation enum.**
11. **Observers are read-only and do not alter the authoritative invocation result.**
12. **Observer failure is isolated from observed-provider success/failure by default.**
13. **The observation capability never observes itself.**
14. **Sensitive contract values are redacted before generic observer dispatch unless explicitly authorized.**
15. **Generic observation uses canonical normalized contract data, not private implementation objects.**
16. **Product-specific capability namespaces, such as Orchestrator `_AO.*`, are profiles of the general model rather than changes to the general architecture.**
17. **Every cross-component invocation passes through a Core-owned capability handle/proxy and invocation bridge, including in-process profiles.**
18. **A consumer binds to capability/version rather than another provider's commercial permission tier.**
19. **`PERMISSION_DENIED` is a standardized runtime invocation outcome; permission identifiers are capability-version-owned diagnostic/provider semantics and are not consumer dependency requirements.**
20. **Core may remediate a permission failure centrally, but transparent retry requires explicit retry safety.**
21. **Component replacement rebuilds the active contract catalog from the complete target component set before target binding resolution; removed suppliers do not leave stale target contract definitions behind.**

# Package identity versus capability identity

Package resolution and capability contract negotiation use different identities. A package store/lock may distinguish component package version, exact artifact digest/build, source, and signer provenance. None of those fields changes the canonical operation identity:

```text
(capability_id, capability_version, operation_id)
```

Two different artifact digests may therefore implement the same capability version. Core verifies/adopts package artifacts according to package policy, then independently admits/deduplicates canonical capability definitions according to capability-contract rules. A workspace package lock MUST NOT be interpreted as a new capability contract version.
