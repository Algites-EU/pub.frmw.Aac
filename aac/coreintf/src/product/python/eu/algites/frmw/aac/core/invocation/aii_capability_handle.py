from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Mapping
from ..instances.api import AIcBinding
from .interaction import (
    AIcOperationFailure, AIiOperationFailureExceptionFactory, AIiOperationInteractionProviderToCaller,
    AIiOperationInteractionCallerToProvider, AIxCapabilityOperationFailed,
)
from .models import AInOperationCompletionState, AIcInvocationOutput, AIcOperationCompletion

class AIiCapabilityHandle(ABC):
    """Core-owned consumer-side handle for one resolved provider-instance binding."""

    @property
    @abstractmethod
    def binding(self) -> AIcBinding: ...

    @abstractmethod
    def invoke(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionProviderToCaller | None = None,
        locale: str | None = None,
    ) -> AIcInvocationOutput: ...


    def new_operation_interaction(
        self, *,
        listener: Callable[[object], None] | None = None,
        exception_factory: AIiOperationFailureExceptionFactory | None = None,
    ) -> AIiOperationInteractionCallerToProvider:
        raise NotImplementedError("this capability handle cannot create a caller interaction controller")

    def invoke_completion(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionCallerToProvider | None = None,
        locale: str | None = None,
    ) -> AIcOperationCompletion:
        output = self.invoke(
            operation_id, arguments, operation_parameters=operation_parameters,
            operation_interaction=operation_interaction, locale=locale,
        )
        if output.success:
            return AIcOperationCompletion(AInOperationCompletionState.SUCCESS, success_result=output.result)
        error = dict(output.error or {})
        if error.get("type") == "OPERATION_CANCELLED":
            return AIcOperationCompletion(
                AInOperationCompletionState.CANCELLED,
                cancelled_result=error.get("state_result") if error.get("has_state_result") else None,
            )
        failure = AIcOperationFailure(
            system_message=str(error.pop("message", "operation failed")),
            exception_type=str(error.pop("type", "AAC.OperationFailure")),
            error_code=(str(error.pop("error_code")) if error.get("error_code") is not None else None),
            stack_trace=(str(error.pop("stack_trace")) if error.get("stack_trace") is not None else None),
            extension=error or None,
        )
        factory = operation_interaction.exception_factory() if operation_interaction is not None else None
        if factory is not None:
            raise factory.create(failure)
        raise AIxCapabilityOperationFailed(failure)

    @abstractmethod
    def start(
        self, operation_id: str, arguments: Mapping[str, object] | None = None, *,
        operation_parameters: Mapping[str, object] | None = None,
        operation_interaction: AIiOperationInteractionCallerToProvider | None = None,
        locale: str | None = None,
    ) -> AIiOperationInteractionCallerToProvider: ...
