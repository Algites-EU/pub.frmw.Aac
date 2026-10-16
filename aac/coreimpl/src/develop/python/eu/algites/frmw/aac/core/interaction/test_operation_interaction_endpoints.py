"""Regression coverage for the four concrete AAC interaction endpoint roles."""
from __future__ import annotations

import queue

from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController
from eu.algites.frmw.aac.core.invocation.api import (
    AIcNullOperationInteraction,
    AIcOperationInteractionProviderToCallerMessage,
    AIiOperationInteractionCallerToProviderOnCaller,
    AIiOperationInteractionCallerToProviderOnProvider,
    AIiOperationInteractionProviderToCallerOnCaller,
    AIiOperationInteractionProviderToCallerOnProvider,
)
from eu.algites.frmw.aac.core.runtime.aic_process_operation_interaction import (
    AIcProcessOperationInteraction,
)
from eu.algites.frmw.aac.core.runtime.aic_subinterpreter_operation_interaction import (
    AIcSubinterpreterOperationInteraction,
)


def test_controller_implements_all_four_distinct_endpoint_roles():
    controller = AIcOperationInteractionController()
    assert isinstance(controller, AIiOperationInteractionCallerToProviderOnCaller)
    assert isinstance(controller, AIiOperationInteractionCallerToProviderOnProvider)
    assert isinstance(controller, AIiOperationInteractionProviderToCallerOnProvider)
    assert isinstance(controller, AIiOperationInteractionProviderToCallerOnCaller)
    assert isinstance(AIcNullOperationInteraction(), AIiOperationInteractionProviderToCallerOnProvider)


def test_provider_send_message_remains_single_publication():
    received = []
    controller = AIcOperationInteractionController(received.extend)
    controller.send_message(AIcOperationInteractionProviderToCallerMessage(state_result_revision=1))
    controller.send_message(AIcOperationInteractionProviderToCallerMessage(state_result_revision=2))
    assert [message.interaction_revision for message in received] == [1, 2]
    assert [message.state_result_revision for message in received] == [1, 2]


def test_process_provider_serializes_full_message():
    class Channel:
        def __init__(self):
            self.frames = []

        def write(self, frame):
            self.frames.append(frame)

    channel = Channel()
    provider = AIcProcessOperationInteraction("invocation-12", channel)
    provider.send_message(AIcOperationInteractionProviderToCallerMessage(state_result_revision=5))
    assert channel.frames[0]["Kind"] == "operation_interaction_message"
    assert channel.frames[0]["InvocationId"] == "invocation-12"
    assert channel.frames[0]["Message"]["StateResultRevision"] == 5


def test_subinterpreter_provider_forwards_one_message():
    outgoing = queue.Queue()
    incoming = queue.Queue()
    provider = AIcSubinterpreterOperationInteraction(outgoing, incoming)
    message = AIcOperationInteractionProviderToCallerMessage(state_result_revision=7)
    provider.send_message(message)
    assert outgoing.get_nowait() == ("message", 0, message)
