#!/usr/bin/env python3
from __future__ import annotations
import argparse,re
from pathlib import Path
from versioning import artifact_context
ROOT=Path(__file__).resolve().parents[4]

def expected_text(path: Path) -> str:
    artifact=path.parent
    version=artifact_context(ROOT, artifact).pep440
    text=path.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^version\s*=\s*"[^"]+"\s*$', f'version = "{version}"', text, count=1)
    text=re.sub(r'(algites-aac-[A-Za-z0-9_-]+)==[^"\s,]+', rf'\1=={version}', text)
    return text

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); a=ap.parse_args()
    bad=[]
    for p in sorted([*(ROOT/'aac').rglob('pyproject.toml'), *(ROOT/'components').rglob('pyproject.toml'), ROOT/'devtools/pyproject.toml']):
        exp=expected_text(p); cur=p.read_text(encoding='utf-8')
        if exp!=cur:
            if a.check: bad.append(str(p.relative_to(ROOT)))
            else: p.write_text(exp,encoding='utf-8')
    if bad:
        raise SystemExit('version metadata not synchronized with repository versionContext: '+', '.join(bad))
if __name__=='__main__': main()
