from __future__ import annotations
from collections.abc import Iterator, Mapping
from typing import Generic, TypeVar

T = TypeVar("T")


class AIcImmutableCancellationMap(Mapping[str, T], Generic[T]):
    """Pickle/deepcopy-safe immutable value mapping for operation snapshots."""

    def __init__(self, values: Mapping[str, T] | None = None) -> None:
        self._entries = tuple(sorted((str(key), value) for key, value in (values or {}).items()))

    def __getitem__(self, key: str) -> T:
        for candidate, value in self._entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __reduce__(self):
        return (type(self), (dict(self._entries),))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._entries)!r})"
