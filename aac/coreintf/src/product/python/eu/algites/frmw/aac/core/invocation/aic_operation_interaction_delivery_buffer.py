from __future__ import annotations
import copy
from collections import deque
from threading import RLock

from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage
from .aii_operation_interaction_provider_to_caller_on_caller import AIiOperationInteractionProviderToCallerOnCaller


class AIcOperationInteractionDeliveryBuffer:
    """Framework-owned FIFO for transports that cannot push provider messages.

    Every publication, including every state-result delta, is retained in order.
    Acknowledgment/retention beyond a drained batch belongs to the transport;
    a consumer exception does not silently discard queued publications.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._messages: deque[AIcOperationInteractionProviderToCallerMessage] = deque()
        self._last_enqueued_revision = 0

    def enqueue(self, message: AIcOperationInteractionProviderToCallerMessage) -> None:
        with self._lock:
            if message.interaction_revision <= self._last_enqueued_revision:
                raise ValueError("provider-to-caller message revisions must increase")
            self._messages.append(copy.deepcopy(message))
            self._last_enqueued_revision = message.interaction_revision

    def pending_count(self) -> int:
        with self._lock:
            return len(self._messages)

    def drain(self) -> tuple[AIcOperationInteractionProviderToCallerMessage, ...]:
        """Take the queued batch; transport must confirm durable delivery independently."""
        with self._lock:
            result = tuple(self._messages)
            self._messages.clear()
            return result

    def deliver_to(self, receiver: AIiOperationInteractionProviderToCallerOnCaller) -> int:
        """Deliver as ONE caller callback. Restore batch on receiver error."""
        messages = self.drain()
        if not messages:
            return 0
        try:
            receiver.receive_messages(messages)
        except BaseException:
            with self._lock:
                self._messages.extendleft(reversed(messages))
            raise
        return len(messages)
