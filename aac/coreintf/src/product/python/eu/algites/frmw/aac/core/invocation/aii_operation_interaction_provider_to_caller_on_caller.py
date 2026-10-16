from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage


P2CM = TypeVar("P2CM", bound=AIcOperationInteractionProviderToCallerMessage)


class AIiOperationInteractionProviderToCallerOnCaller(Generic[P2CM], ABC):
    """Caller receives an ordered batch; EVERY non-duplicate message is significant.

    The transport deduplicates redelivery and must deliver only contiguous
    revisions. Process ALL messages before dispatching caller reactions.
    """

    @abstractmethod
    def receive_messages(self, messages: tuple[P2CM, ...]) -> None: ...
