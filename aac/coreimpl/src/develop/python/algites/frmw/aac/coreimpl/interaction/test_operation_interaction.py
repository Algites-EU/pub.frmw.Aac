import pytest

from algites.frmw.aac.coreimpl.operation_interaction import AIcOperationInteractionController
from algites.frmw.aac.coreintf.invocation import (
    AInOperationExecutionState,
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
    controller = AIcOperationInteractionController(messages.append)

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
    assert caller.cancellation_requested


def test_controls_reject_features_not_declared_by_provider():
    controller = AIcOperationInteractionController()

    with pytest.raises(ValueError, match="cancellation"):
        controller.request_cancellation()
    with pytest.raises(ValueError, match="detail-level"):
        controller.set_detail_level(AInOperationInteractionDetailLevel.DETAILED)
    with pytest.raises(ValueError, match="reporting-interval"):
        controller.set_reporting_interval_ms(1000)
    controller.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)

    caller = controller.set_interaction_mode(AInOperationInteractionMode.BACKGROUND)
    assert caller.interaction_mode is AInOperationInteractionMode.BACKGROUND


def test_delta_result_revisions_can_be_accepted_with_gaps():
    messages = []
    controller = AIcOperationInteractionController(messages.append)
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
    controller = AIcOperationInteractionController(messages.append)
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
    controller = AIcOperationInteractionController(messages.append)
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
    controller = AIcOperationInteractionController(messages.append)
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
    controller = AIcOperationInteractionController(messages.append)
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
