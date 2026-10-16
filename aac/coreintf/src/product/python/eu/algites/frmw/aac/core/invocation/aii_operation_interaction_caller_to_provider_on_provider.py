from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage


C2PM = TypeVar("C2PM", bound=AIcOperationInteractionCallerToProviderMessage)
P2CM = TypeVar("P2CM", bound=AIcOperationInteractionProviderToCallerMessage)


class AIiOperationInteractionCallerToProviderOnProvider(Generic[C2PM, P2CM], ABC):
    """Provider receives ONE caller snapshot; it MAY return ONE response publication.

    The transport queues prior send_message publications, appends the optional
    direct return and delivers the entire ordered P2C batch to the caller.
    None means no direct response. A response and a separately published message
    are separate logical messages and MUST NOT be used for the same publication.
    """

    @abstractmethod
    def receive_message(
        self, message: C2PM
    ) -> P2CM | None: ...
