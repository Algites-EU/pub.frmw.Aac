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

def _extract_context(text: str) -> AIcVersionContext | None:
    marker=re.search(r"(?m)^versionContext:\s*$", text)
    if not marker:
        return None
    block=text[marker.end():]
    lines=[]
    for line in block.splitlines():
        if line and not line[0].isspace():
            break
        lines.append(line)
    block='\n'.join(lines)
    def val(key:str, default:str='') -> str:
        m=re.search(rf'(?m)^\s+{re.escape(key)}:\s*["\']?([^"\'\n#]+)', block)
        return m.group(1).strip() if m else default
    return AIcVersionContext(val('releaseLine'), int(val('revision','0')), val('qualifierKind','RELEASE'), val('qualifierLabel',''))

def repository_context(root: Path) -> AIcVersionContext:
    ctx=_extract_context((root/'algites-source-repository.yml').read_text(encoding='utf-8'))
    if ctx is None:
        raise ValueError('root algites-source-repository.yml has no versionContext')
    return ctx

def artifact_context(root: Path, artifact: Path) -> AIcVersionContext:
    p=artifact/'algites-artifact.yml'
    ctx=_extract_context(p.read_text(encoding='utf-8')) if p.exists() else None
    return ctx or repository_context(root)
