from dataclasses import replace
from datetime import datetime, timezone

import pytest

from eu.algites.frmw.aac.core.invocation.api import (
    AIcOperationInteractionCallerToProviderMessage as C2P,
    AIcOperationInteractionProviderToCallerMessage as P2C,
)
from eu.algites.frmw.aac.core.interaction.aic_operation_interaction_reliable_transport import (
    AIcOperationInteractionReliableCallerTransport,
    AIcOperationInteractionReliableProviderTransport,
)
from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController


class Provider:
    def __init__(self):
        self.calls = []

    def receive_message(self, message):
        self.calls.append(message.caller_interaction_revision)
        return P2C(state_result_revision=10 + len(self.calls))


class Caller:
    def __init__(self):
        self.batches = []

    def receive_messages(self, messages):
        self.batches.append(tuple(message.interaction_revision for message in messages))


def test_ack_resend_deduplicate_and_response_append():
    provider = Provider()
    link = AIcOperationInteractionReliableProviderTransport(provider)
    caller = Caller()
    client = AIcOperationInteractionReliableCallerTransport(caller)
    link.send_message(P2C(state_result_revision=1))
    link.send_message(P2C(state_result_revision=2))
    first = link.exchange(0, C2P(caller_interaction_revision=1))
    assert [msg.interaction_revision for msg in first] == [1, 2, 3]
    assert [msg.state_result_revision for msg in first] == [1, 2, 11]
    client.receive_messages(first)
    assert caller.batches == [(1, 2, 3)]
    # Lost ACK: retransmit the entire batch, with no repeated caller effects.
    client.receive_messages(link.exchange(0, C2P(caller_interaction_revision=1)))
    assert caller.batches == [(1, 2, 3)]
    assert provider.calls == [1]
    assert client.last_received_revision() == 3
    assert link.exchange(client.last_received_revision()) == ()
    assert link.pending_count() == 0
    link.send_message(P2C(state_result_revision=9))
    client.receive_messages(link.exchange(3))
    assert caller.batches[-1] == (4,)


def test_gap_rejected_and_failed_callback_not_acked():
    class Broken(Caller):
        def receive_messages(self, messages):
            raise RuntimeError("listener failed")
    client = AIcOperationInteractionReliableCallerTransport(Broken())
    with pytest.raises(ValueError, match="gap"):
        client.receive_messages((P2C(interaction_revision=2),))
    with pytest.raises(RuntimeError, match="listener"):
        client.receive_messages((P2C(interaction_revision=1),))
    assert client.last_received_revision() == 0


def test_caller_receives_every_delta_in_order():
    provider = Provider()
    link = AIcOperationInteractionReliableProviderTransport(provider)
    caller = Caller()
    client = AIcOperationInteractionReliableCallerTransport(caller)
    for n in (1, 2, 3):
        link.send_message(P2C(state_result_revision=n, state_result_payload_revision=n, state_result={"delta":n}))
    client.receive_messages(link.exchange())
    assert caller.batches == [(1,2,3)]
    assert client.last_received_revision() == 3


def test_ack_cannot_confirm_messages_never_sent_and_cannot_go_backwards():
    link = AIcOperationInteractionReliableProviderTransport(Provider())
    link.send_message(P2C())
    with pytest.raises(ValueError):
        link.exchange(1)
    link.exchange()
    link.exchange(1)
    with pytest.raises(ValueError):
        link.exchange(0)
    with pytest.raises(ValueError):
        link.exchange(2)


def test_controller_supports_message_endpoints():
    controller = AIcOperationInteractionController()
    assert controller.receive_message(C2P(caller_interaction_revision=1)) is None
    assert controller.caller_snapshot().caller_interaction_revision == 1
    assert controller.receive_message(C2P(caller_interaction_revision=1)) is None
    assert controller.caller_snapshot().caller_interaction_revision == 1
