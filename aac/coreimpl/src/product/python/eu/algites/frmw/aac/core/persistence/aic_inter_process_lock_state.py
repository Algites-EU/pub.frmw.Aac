from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping, Any

class AIcInterProcessLockState:
    def __init__(self) -> None:
        from threading import RLock
        self.thread_lock = RLock()
        self.depth = 0
        self.stream = None
