from __future__ import annotations

from dataclasses import asdict
from importlib import import_module
from typing import Mapping

from algites.lib.aac.coreintf.invocation import AIiCapabilityEndpoint, AIcInvocationInput, AIcInvocationOutput

from .errors import AIxSubinterpreterUnavailableError


def subinterpreter_available() -> bool:
    try:
        from concurrent import interpreters  # type: ignore[attr-defined]
    except ImportError:
        return False
    return hasattr(interpreters, "create")


def _invoke_entrypoint(entrypoint: str, payload: Mapping[str, object]) -> object:
    module_name, sep, attr_name = entrypoint.partition(":")
    if not sep:
        raise ValueError("subinterpreter entrypoint must use 'module:function'")
    target = getattr(import_module(module_name), attr_name)
    return target(str(payload["operation_id"]), dict(payload.get("arguments", {})))


class AIcSubinterpreterCapabilityEndpoint(AIiCapabilityEndpoint):
    """CPython 3.14+ capability endpoint using ``concurrent.interpreters``.

    The target is a module-level ``module:function`` entrypoint receiving
    ``(operation_id, arguments)``. Only normalized/copyable data crosses the interpreter boundary.
    Subinterpreters are an isolation/dependency profile, not a hostile-code security sandbox.
    """

    def __init__(self, entrypoint: str) -> None:
        try:
            from concurrent import interpreters  # type: ignore[attr-defined]
        except ImportError as exc:
            raise AIxSubinterpreterUnavailableError(
                "CPython concurrent.interpreters is unavailable; Python 3.14+ is required"
            ) from exc
        self.entrypoint = entrypoint
        self._interpreters = interpreters
        self._interpreter = interpreters.create()

    def invoke(self, invocation_input: AIcInvocationInput) -> AIcInvocationOutput:
        payload = asdict(invocation_input)
        try:
            result = self._interpreter.call(_invoke_entrypoint, self.entrypoint, payload)
            return AIcInvocationOutput(True, result=result)
        except Exception as exc:
            return AIcInvocationOutput(False, error={"type": type(exc).__name__, "message": str(exc)})

    def close(self) -> None:
        interpreter = getattr(self, "_interpreter", None)
        if interpreter is not None:
            interpreter.close()
            self._interpreter = None
