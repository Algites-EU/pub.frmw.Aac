import pytest
from datetime import datetime, timedelta, timezone
import pickle
import copy

from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationExecutionState,
    AInOperationCancellationReason,
    AIcOperationInteractionDeliveryBuffer,
    AIcOperationInteractionProviderToCallerMessage,
    AIcOperationCancellationAcceptance,
    AIcOperationCancellationReasonRecord,
    accept_cancellation_locally,
    AInOperationInteractionDetailLevel,
    AInOperationInteractionEventType,
    AInOperationInteractionFailureDetailLevel,
    AInOperationInteractionMode,
    AInStateResultDeliveryMode,
    AIcOperationInteractionEvent,
    AIcOperationInteractionFeatures,
)


def features(*modes: AInStateResultDeliveryMode) -> AIcOperationInteractionFeatures:
    return AIcOperationInteractionFeatures(
        progress_reporting=True,
        cancellation=True,
        detail_level=True,
        reporting_interval=True,
        supported_state_result_delivery_modes=modes or (AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,),
    )


def test_initial_revisions_are_zero_and_first_publication_is_one():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)

    initial = controller.provider_snapshot()
    assert initial.interaction_revision == 0
    assert initial.state_result_revision == 0
    assert initial.execution_state is AInOperationExecutionState.PENDING

    controller.declare_features(features())
    assert messages[-1].interaction_revision == 1
    assert messages[-1].state_result_revision == 0

    revision = controller.state_result_changed()
    assert revision == 1
    assert messages[-1].interaction_revision == 2
    assert messages[-1].state_result_revision == 1
    assert not messages[-1].state_result_included


def test_caller_controls_are_separate_from_provider_messages():
    controller = AIcOperationInteractionController()
    controller.declare_features(features(
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        AInStateResultDeliveryMode.ON_CHANGE_DELTA,
    ))

    controller.set_interaction_mode(AInOperationInteractionMode.BACKGROUND)
    controller.set_detail_level(AInOperationInteractionDetailLevel.DETAILED)
    controller.set_reporting_interval_ms(750)
    controller.set_failure_detail_level(AInOperationInteractionFailureDetailLevel.STACK_TRACE)
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)
    controller.request_state_result()
    controller.request_cancellation()

    caller = controller.caller_snapshot()
    assert caller.interaction_mode is AInOperationInteractionMode.BACKGROUND
    assert caller.detail_level is AInOperationInteractionDetailLevel.DETAILED
    assert caller.reporting_interval_ms == 750
    assert caller.failure_detail_level is AInOperationInteractionFailureDetailLevel.STACK_TRACE
    assert caller.state_result_delivery_mode is AInStateResultDeliveryMode.ON_CHANGE_DELTA
    assert caller.state_result_request_id == 1
    assert "caller_request" in caller.cancellation_schedule


def test_controls_reject_features_not_declared_by_provider():
    controller = AIcOperationInteractionController()
    # A caller may schedule an initial deadline before the provider declares features.
    initial = controller.schedule_cancellation(datetime.now(timezone.utc) + timedelta(hours=1))
    assert "caller_request" in initial.cancellation_schedule
    controller.declare_features(AIcOperationInteractionFeatures())
    with pytest.raises(ValueError, match="cancellation"):
        controller.request_cancellation()
    with pytest.raises(ValueError, match="detail-level"):
        controller.set_detail_level(AInOperationInteractionDetailLevel.DETAILED)
    with pytest.raises(ValueError, match="reporting-interval"):
        controller.set_reporting_interval_ms(1000)
    with pytest.raises(ValueError, match="delivery mode"):
        controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)

    caller = controller.set_interaction_mode(AInOperationInteractionMode.BACKGROUND)
    assert caller.interaction_mode is AInOperationInteractionMode.BACKGROUND


def test_delta_result_revisions_can_be_accepted_with_gaps():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)
    controller.declare_features(features(
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        AInStateResultDeliveryMode.ON_CHANGE_DELTA,
    ))
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)

    assert controller.update_state_result({"frame": 15}) == 1
    assert controller.update_state_result({"frame": 16}) == 2
    assert controller.update_state_result({"frame": 17}) == 3

    controller.accept_state_result_revision(1)
    controller.accept_state_result_revision(3)
    assert controller.caller_snapshot().last_accepted_state_result_revision == 3

    payload_messages = [message for message in messages if message.state_result_included]
    assert [message.state_result_payload_revision for message in payload_messages] == [1, 2, 3]


def test_on_demand_mode_reports_revision_without_payload_and_can_deliver_buffered_revision():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)
    controller.declare_features(features())

    assert controller.state_result_changed() == 1
    assert messages[-1].state_result_revision == 1
    assert not messages[-1].state_result_included

    controller.deliver_state_result({"chunk": "first"}, revision=1)
    assert messages[-1].state_result_revision == 1
    assert messages[-1].state_result_payload_revision == 1
    assert messages[-1].state_result == {"chunk": "first"}


def test_state_result_payload_is_snapshotted_at_publication_boundary():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)
    controller.declare_features(features(
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
    ))
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_COMPLETE)

    value = {"items": [1]}
    controller.update_state_result(value)
    value["items"].append(2)

    assert messages[-1].state_result == {"items": [1]}


def test_multiple_progress_events_are_published_atomically():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)
    controller.declare_features(features())
    before = controller.provider_snapshot().interaction_revision

    controller.report_events((
        AIcOperationInteractionEvent(
            AInOperationInteractionEventType.PROGRESS,
            progress_id="overall",
            current=15,
            total=100,
        ),
        AIcOperationInteractionEvent(
            AInOperationInteractionEventType.PROGRESS,
            progress_id="current-item",
            parent_progress_id="overall",
            current=0,
            total=100,
        ),
    ))

    message = messages[-1]
    assert message.interaction_revision == before + 1
    assert len(message.events) == 2
    assert message.events[1].parent_progress_id == "overall"


def test_terminal_transition_is_atomic_and_wait_returns_terminal_result():
    controller = AIcOperationInteractionController()
    controller.core_transition(AInOperationExecutionState.RUNNING)
    controller.core_transition(
        AInOperationExecutionState.COMPLETED,
        state_result={"answer": 42},
        has_state_result=True,
    )

    terminal = controller.wait_for_terminal_state(timeout=0.1)
    assert terminal.execution_state is AInOperationExecutionState.COMPLETED
    assert terminal.state_result_revision == 1
    assert terminal.state_result_payload_revision == 1
    assert terminal.state_result == {"answer": 42}

@pytest.mark.parametrize(
    "mode",
    (
        AInStateResultDeliveryMode.ON_CHANGE_COMPLETE,
        AInStateResultDeliveryMode.ON_CHANGE_DELTA,
        AInStateResultDeliveryMode.ALWAYS_COMPLETE,
    ),
)
def test_changed_without_payload_is_rejected_when_delivery_mode_requires_payload(mode):
    controller = AIcOperationInteractionController()
    controller.declare_features(features(AInStateResultDeliveryMode.ON_DEMAND_COMPLETE, mode))
    controller.set_state_result_delivery_mode(mode)

    with pytest.raises(ValueError, match="requires update_state_result"):
        controller.state_result_changed()


def test_always_complete_repeats_latest_complete_result_on_every_publication():
    messages = []
    controller = AIcOperationInteractionController(messages.extend)
    controller.declare_features(features(
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        AInStateResultDeliveryMode.ALWAYS_COMPLETE,
    ))
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ALWAYS_COMPLETE)

    revision = controller.update_state_result({"value": 1})
    controller.report(AIcOperationInteractionEvent(
        AInOperationInteractionEventType.STATUS,
        code="still-running",
    ))

    assert revision == 1
    assert messages[-1].state_result_payload_revision == 1
    assert messages[-1].state_result == {"value": 1}


def test_cancellation_schedule_is_sparse_reason_keyed_and_caller_revisioned():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    assert dict(controller.caller_snapshot().cancellation_schedule) == {}
    deadline = datetime.now(timezone.utc) + timedelta(minutes=20)
    first = controller.schedule_cancellation(deadline, origin="session-a")
    assert first.caller_interaction_revision == 1
    record = first.cancellation_schedule["caller_request"]
    assert record.reason == "caller_request"
    assert record.current_deadline == deadline
    assert record.last_origin == "session-a"
    later = deadline + timedelta(minutes=30)
    second = controller.schedule_cancellation(later, origin="session-b")
    assert second.caller_interaction_revision == 2
    assert second.cancellation_schedule["caller_request"].request_count == 2
    assert second.cancellation_schedule["caller_request"].first_requested_at == record.first_requested_at
    assert second.cancellation_schedule["caller_request"].current_deadline == later
    withdrawn = controller.withdraw_cancellation()
    assert withdrawn.caller_interaction_revision == 3
    assert not withdrawn.cancellation_schedule
    assert first.cancellation_schedule["caller_request"] == record  # old immutable snapshot
    assert controller.withdraw_cancellation().caller_interaction_revision == 3  # no change


def test_framework_reason_cannot_be_set_through_caller_methods():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    deadline = datetime.now(timezone.utc) + timedelta(hours=1)
    state = controller.schedule_framework_cancellation(AInOperationCancellationReason.ENGINE_SHUTDOWN, deadline)
    assert set(state.cancellation_schedule) == {"engine_shutdown"}
    controller.cancel_now(origin="ui")
    assert set(controller.caller_snapshot().cancellation_schedule) == {"caller_request", "engine_shutdown"}
    controller.withdraw_cancellation()
    assert set(controller.caller_snapshot().cancellation_schedule) == {"engine_shutdown"}
    controller.withdraw_framework_cancellation(AInOperationCancellationReason.ENGINE_SHUTDOWN)
    assert not controller.caller_snapshot().cancellation_schedule
    with pytest.raises(ValueError, match="CALLER_REQUEST"):
        controller.schedule_framework_cancellation(AInOperationCancellationReason.CALLER_REQUEST, deadline)


def test_provider_accepts_local_snapshot_without_round_trip_and_cannot_be_un_cancelled():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    state = controller.cancel_now(origin="session-a")
    acceptance = controller.accept_cancellation(frozenset({"caller_request"}))
    assert acceptance.accepted_reasons == frozenset({"caller_request"})
    assert acceptance.accepted_interaction_snapshot == state
    assert controller.provider_snapshot().cancellation_acceptance == acceptance
    assert controller.withdraw_cancellation() == state
    assert controller.schedule_cancellation(datetime.now(timezone.utc) + timedelta(hours=1)) == state
    assert controller.accept_cancellation(frozenset({"caller_request"})) == acceptance


def test_provider_cannot_accept_absent_or_not_yet_due_reasons():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    controller.schedule_cancellation(datetime.now(timezone.utc) + timedelta(hours=1))
    with pytest.raises(ValueError, match="not effective"):
        controller.accept_cancellation(frozenset({"caller_request"}))
    with pytest.raises(ValueError, match="exist"):
        controller.accept_cancellation(frozenset({"engine_shutdown"}))
    assert controller.provider_snapshot().cancellation_acceptance is None


def test_cancellation_snapshots_are_deepcopy_and_pickle_safe():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    state = controller.cancel_now(origin="user")
    copied = copy.deepcopy(state)
    restored = pickle.loads(pickle.dumps(state))
    assert copied.cancellation_schedule["caller_request"] == state.cancellation_schedule["caller_request"]
    assert restored.cancellation_schedule["caller_request"] == state.cancellation_schedule["caller_request"]
    with pytest.raises(TypeError):
        state.cancellation_schedule["caller_request"] = None
    with pytest.raises(ValueError, match="timezone-aware"):
        controller.schedule_cancellation(datetime(2026, 10, 15, 20, 0))


def test_multiple_provider_messages_are_delivered_as_one_ordered_caller_batch():
    batches = []
    buffer = AIcOperationInteractionDeliveryBuffer()
    producer = AIcOperationInteractionController(listener=lambda items: [buffer.enqueue(m) for m in items])
    producer.declare_features(features(AInStateResultDeliveryMode.ON_DEMAND_COMPLETE, AInStateResultDeliveryMode.ON_CHANGE_DELTA))
    producer.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)
    producer.update_state_result({"chunk": "one"})
    producer.update_state_result({"chunk": "two"})
    producer.update_state_result({"chunk": "three"})
    class Receiver:
        def receive_messages(self, messages):
            # The host gets ONE callback, after all individual publications arrive.
            batches.append(tuple(messages))
    assert buffer.pending_count() == 4
    assert buffer.deliver_to(Receiver()) == 4
    assert len(batches) == 1
    assert [m.state_result["chunk"] for m in batches[0] if m.state_result_included] == ["one", "two", "three"]
    assert [m.interaction_revision for m in batches[0]] == [1, 2, 3, 4]
    assert all(m.published_at is not None for m in batches[0])
    assert buffer.pending_count() == 0


def test_batch_receipt_requeues_on_exception_instead_of_dropping_revisions():
    buffer = AIcOperationInteractionDeliveryBuffer()
    buffer.enqueue(AIcOperationInteractionProviderToCallerMessage(interaction_revision=1))
    buffer.enqueue(AIcOperationInteractionProviderToCallerMessage(interaction_revision=2))
    class FailingReceiver:
        def receive_messages(self, messages):
            raise IOError("transport interrupted")
    with pytest.raises(IOError, match="transport"):
        buffer.deliver_to(FailingReceiver())
    assert [m.interaction_revision for m in buffer.drain()] == [1, 2]


def test_caller_receiver_processes_all_messages_before_external_reaction():
    phases = []
    class Receiver:
        def receive_messages(self, messages):
            for message in messages:
                phases.append(("apply", message.interaction_revision))
            phases.append(("react", messages[-1].interaction_revision))
    buffer = AIcOperationInteractionDeliveryBuffer()
    for rev in range(1, 4):
        buffer.enqueue(AIcOperationInteractionProviderToCallerMessage(interaction_revision=rev))
    assert buffer.deliver_to(Receiver()) == 3
    assert phases == [("apply", 1), ("apply", 2), ("apply", 3), ("react", 3)]


def test_stale_caller_batch_rejected_as_whole_without_partial_update():
    controller = AIcOperationInteractionController()
    controller.receive_messages((AIcOperationInteractionProviderToCallerMessage(interaction_revision=1),))
    with pytest.raises(ValueError, match="out-of-order"):
        controller.receive_messages((
            AIcOperationInteractionProviderToCallerMessage(interaction_revision=2),
            AIcOperationInteractionProviderToCallerMessage(interaction_revision=2),
        ))
    assert controller.provider_snapshot().interaction_revision == 1


def test_asynchronous_cancellation_acceptance_can_be_reported_after_local_decision():
    controller = AIcOperationInteractionController()
    controller.declare_features(features())
    snap = controller.cancel_now()
    locally = accept_cancellation_locally(snap, {"caller_request"})
    controller.record_cancellation_acceptance(locally)
    assert controller.provider_snapshot().cancellation_acceptance == locally
    assert controller.withdraw_cancellation() == snap


def test_nonpush_controller_buffers_all_publications_even_when_ui_listener_fails():
    delivery = AIcOperationInteractionDeliveryBuffer()
    def broken_ui(_messages):
        raise RuntimeError("UI is unavailable")
    controller = AIcOperationInteractionController(listener=broken_ui, delivery_buffer=delivery)
    controller.declare_features(features(
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE, AInStateResultDeliveryMode.ON_CHANGE_DELTA,
    ))
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)
    controller.update_state_result({"part": 1})
    controller.update_state_result({"part": 2})
    class Receiver:
        def __init__(self):
            self.messages = ()
        def receive_messages(self, messages):
            self.messages = messages
    remote = Receiver()
    assert delivery.deliver_to(remote) == 3
    assert [message.state_result["part"] for message in remote.messages if message.state_result_included] == [1, 2]
