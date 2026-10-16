# AAC Operation Interaction – version 2 migration notes

This document accompanies the canonical **Application-Component-Capability-Contract-Specification.md**, §III.6. It describes the newly implemented Python interface model and the transport obligations needed before enabling it on every runtime profile.

## Directional contracts

- **Provider2CallerOnProvider**: `AIiOperationInteractionProviderToCallerOnProvider`; each call publishes **one** logical message/revision.
- **Provider2CallerOnCaller**: `AIiOperationInteractionProviderToCallerOnCaller.receive_messages(tuple[message, ...])`; one callback gets the **ordered batch**, not a single message.
- **Caller2ProviderOnCaller**: `AIiOperationInteractionCallerToProviderOnCaller` exposes cancellation, reporting preferences, state-result requests and `send_message()` for a complete C2P message.
- **Caller2ProviderOnProvider**: `AIiOperationInteractionCallerToProviderOnProvider.receive_message()` accepts one C2P message and may return one P2C publication. The transport appends this response after previously queued P2C messages.

The two logical communication directions are independent. Only the Core controller may implement all four endpoints for an in-process invocation; the isolated or remote provider sees only its provider-side endpoints.

Existing caller listeners passed to `AIcOperationInteractionController(listener=...)` and `new_operation_interaction(listener=...)` now receive a **tuple**, including for a single message. Callers relying on a single-message callback MUST migrate; they MUST NOT fake batching by invoking the old callback repeatedly, as this permits host reactions between live deltas.

`AIcOperationInteractionDeliveryBuffer` is the **in-memory** reference FIFO; its producer enqueues every provider message and its caller side invokes `receive_messages(tuple)`. It does not persist messages across process crashes: remote transports claiming durable delivery MUST persist pending messages and delivery acknowledgments. Exactly-once business effects cannot be inferred from queue delivery.

## Cancellation

`cancellation_requested: bool` is replaced in the new Python DTO and v2 schema with `caller_interaction_revision` and `cancellation_schedule[reason]`. Every current record embeds the reason ID, the current timezone-aware deadline, first/last timestamps, count, last origin and message. Absence means no currently active request. After withdraw the reason is removed. Standard reasons are defined by `AInOperationCancellationReason`, but callers do not set their reason themselves. The caller API exposes `schedule_cancellation()`, `cancel_now()`, `withdraw_cancellation()`; legacy `request_cancellation()` delegates to `cancel_now()`.

`accept_cancellation(reasons)` is a **provider-local decision**. Evidence contains the full immutable caller snapshot on which the decision was made, selected reasons and provider timestamp. It is later published opportunistically and never awaits Core approval. Once accepted, later withdrawal cannot undo the provider's decision. Cancellation acceptance and terminal completion are distinct events.

Python uses timezone-aware `datetime` (UTC recommended), corresponding to Java `Instant`; naive values are invalid. A deadline causes cooperative cancellation **request**, not synchronous termination. `UNKNOWN` was not introduced as a terminal lifecycle state.

## Wire compatibility

The unchanged `/1` JSON/YAML/XML schemas retain their original wire meanings. Enhanced sender/receiver DTOs require canonical `/2` schemas plus `/2` event schema and the separate `/1` **batch envelope**; adapters must negotiate compatible versions. The new Python process/subinterpreter paths support local cancellation acceptance evidence, but legacy remote clients using v1 cannot represent the richer contract without protocol upgrade or explicit compatibility translation. Opaque state-result deltas may not be discarded or collapsed when batching.

## Test boundaries

Unit tests cover mapping sparsity/withdrawal, acceptance, snapshots, ordered batch delivery, no intermediate callback, and lossless state-result deltas. Actual network retry/durable queue guarantees require integration tests with real transport fault injection before those guarantees can be claimed for a remote runtime.

## Version 3: four endpoints and acknowledged transport

The four application endpoints are now explicitly named `CallerToProviderOnCaller`,
`CallerToProviderOnProvider`, `ProviderToCallerOnProvider` and
`ProviderToCallerOnCaller`. `receive_message` may return one additional P2C
publication; the sender's `send_message` publications remain independent.
An empty direct return means there is no direct response.

The Python reference transport classes are
`AIcOperationInteractionReliableProviderTransport` and
`AIcOperationInteractionReliableCallerTransport`, mirrored by the Java classes
with the same names. Provider-side queues are **ACK-retained** and caller-side
replays are suppressed using highest contiguous processed sequence. A C2P
revision successfully handled by the live reference transport is not processed
again after a retried HTTP request. A transport may poll without a C2P message.

Real process/remote transport adapters must wire these classes into their
actual wire loop, including durable persistence when crash recovery is claimed.
Existing Python process/subinterpreter bridges retain their original transport
logic; they have NOT been silently upgraded to ACK-retained delivery by the
addition of the reference transport classes. The new Java implementation
currently covers core invocation contracts, an in-process capability endpoint,
interaction model, controller and reference reliable transport; the wider AAC
catalog, authn/authz, solver, package management, runtime isolation and UI
subsystems remain Python-only. Java API is source compatible at the normative
protocol level but is not a complete production AAC port.

The transport wire envelope is described by
`operation-interaction-reliable-exchange_1` in the JSON, YAML and XML
schema trees. It does not supersede the semantic v2 C2P/P2C message schemas.
The v1/v2 historical schemas remain untouched.


### Directional interface migration (breaking)

The two non-endpoint interaction interfaces were removed, not kept as aliases.
Provider APIs now accept `AIiOperationInteractionProviderToCallerOnProvider`;
caller handles expose `AIiOperationInteractionCallerToProviderOnCaller`.
Use `AIiOperationInteractionCallerToProviderOnProvider.receive_message()` for inbound C2P
messages and `AIiOperationInteractionProviderToCallerOnCaller.receive_messages()`
for ordered P2C batches. No deprecated imports or compatibility shims are exported.

The two source files for the obsolete non-endpoint abstractions have been deleted.
Clients must migrate their type annotations and imports before upgrading.
