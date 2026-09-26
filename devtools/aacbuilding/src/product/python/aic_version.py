from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class AIcVersionContext:
    release_line: str
    revision: int
    qualifier_kind: str
    qualifier_label: str

    @property
    def algites(self) -> str:
        base=f"{self.release_line}.{self.revision}"
        if self.qualifier_kind.upper() in {"", "NONE", "RELEASE", "FINAL"}:
            return base
        return f"{base}-{self.qualifier_label or self.qualifier_kind}"

    @property
    def pep440(self) -> str:
        base=f"{self.release_line}.{self.revision}"
        kind=self.qualifier_kind.upper()
        if kind in {"", "NONE", "RELEASE", "FINAL"}:
            return base
        if kind == "SNAPSHOT":
            return f"{base}.dev0"
        if kind in {"RC", "RELEASE_CANDIDATE"}:
            m=re.search(r"(\d+)$", self.qualifier_label)
            return f"{base}rc{m.group(1) if m else '0'}"
        raise ValueError(f"unsupported qualifierKind {self.qualifier_kind!r} for Python packaging")
