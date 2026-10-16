from __future__ import annotations
import copy
from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from typing import Callable

from eu.algites.frmw.aac.core.invocation.api import (
    AIcOperationInteractionCallerToProviderMessage,
    AIcOperationInteractionProviderToCallerMessage,
    AIiOperationInteractionProviderToCallerOnCaller,
    AIiOperationInteractionCallerToProviderOnProvider,
)


class AIcOperationInteractionReliableProviderTransport:
    """Per-invocation ordered, ACK-retained P2C publication channel.

    send_message appends one immutable publication. exchange(ack, caller_message)
    processes ACK before optionally invoking the provider endpoint, then returns
    ALL unacknowledged messages, including any single direct response.

    A transport invocation serializes receive_message with send_message so the
    direct response is sequenced after earlier publications. Each C2P revision
    is executed at most once in this live channel. On reconnect after a crash,
    a persistent implementation MUST restore this state from durable storage.
    """

    def __init__(self, provider: AIiOperationInteractionCallerToProviderOnProvider) -> None:
        self._provider = provider
        self._lock = RLock()
        self._pending: dict[int, AIcOperationInteractionProviderToCallerMessage] = {}
        self._next_sequence = 1
        self._last_sent_sequence = 0
        self._last_caller_revision = -1
        self._last_ack = 0

    def send_message(self, message: AIcOperationInteractionProviderToCallerMessage) -> int:
        with self._lock:
            if not isinstance(message, AIcOperationInteractionProviderToCallerMessage):
                raise TypeError("expected provider-to-caller message")
            sequence = self._next_sequence
            self._next_sequence += 1
            frozen = copy.deepcopy(message)
            frozen = replace(frozen, interaction_revision=sequence,
                             published_at=frozen.published_at or datetime.now(timezone.utc))
            self._pending[sequence] = frozen
            return sequence

    def exchange(self, acknowledged_revision: int = 0,
                 caller_message: AIcOperationInteractionCallerToProviderMessage | None = None,
                 ) -> tuple[AIcOperationInteractionProviderToCallerMessage, ...]:
        """Return ordered UNACKED publications, even after earlier failed responses.

        The caller can poll with caller_message=None. ACK means contiguous
        successfully processed revisions, not merely bytes received by socket.
        """
        with self._lock:
            if not isinstance(acknowledged_revision, int) or acknowledged_revision < self._last_ack or acknowledged_revision > self._last_sent_sequence:
                raise ValueError("invalid provider-to-caller cumulative acknowledgment")
            if acknowledged_revision > self._last_ack:
                for seq in tuple(self._pending):
                    if seq <= acknowledged_revision:
                        del self._pending[seq]
                self._last_ack = acknowledged_revision
            if caller_message is not None:
                revision = caller_message.caller_interaction_revision
                if revision > self._last_caller_revision:
                    direct = self._provider.receive_message(copy.deepcopy(caller_message))
                    # Mark handled only after successful completion; transport-level
                    # retries cannot re-execute a successful receive_message.
                    self._last_caller_revision = revision
                    if direct is not None:
                        self.send_message(direct)
            batch = tuple(copy.deepcopy(x) for x in self._pending.values())
            if batch:
                self._last_sent_sequence = max(self._last_sent_sequence, batch[-1].interaction_revision)
            return batch

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def last_acknowledged_revision(self) -> int:
        with self._lock:
            return self._last_ack


class AIcOperationInteractionReliableCallerTransport:
    """Deduplicate replayed P2C publications and deliver one ordered caller batch.

    last_received_revision may be sent on the NEXT request only after the
    receiver returned successfully; on receiver failure ACK does not advance.
    Caller effects need idempotency on process crashes (transport is at-least-once).
    """

    def __init__(self, receiver: AIiOperationInteractionProviderToCallerOnCaller) -> None:
        self._receiver = receiver
        self._lock = RLock()
        self._last_received_revision = 0

    def receive_messages(self, messages: tuple[AIcOperationInteractionProviderToCallerMessage, ...]) -> None:
        with self._lock:
            fresh = []
            next_revision = self._last_received_revision + 1
            for message in messages:
                revision = message.interaction_revision
                if revision < next_revision:
                    continue
                if revision != next_revision:
                    raise ValueError(f"provider-to-caller message gap: expected {next_revision}, got {revision}")
                fresh.append(message)
                next_revision += 1
            if not fresh:
                return
            self._receiver.receive_messages(tuple(copy.deepcopy(fresh)))
            self._last_received_revision = next_revision - 1

    def last_received_revision(self) -> int:
        with self._lock:
            return self._last_received_revision
