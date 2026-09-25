from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageStoreLayout:
    """Product-supplied filesystem layout for AAC-managed package artifacts.

    AAC recommends ``plugins/downloaded``, ``plugins/installed`` and ``plugins/obsolete``
    below the product-owned root, but every relative name remains product-overridable.
    """

    product_root: str
    package_store_subdirectory: str = "plugins"
    downloaded_subdirectory: str = "downloaded"
    installed_subdirectory: str = "installed"
    obsolete_subdirectory: str = "obsolete"
    core_state_subdirectory: str = "aac-state"
    transactions_subdirectory: str = "transactions"
    core_lock_filename: str = "core.lock"

    def __post_init__(self) -> None:
        if not self.product_root:
            raise ValueError("package store product_root must not be empty")
        for name, value in (
            ("package_store_subdirectory", self.package_store_subdirectory),
            ("downloaded_subdirectory", self.downloaded_subdirectory),
            ("installed_subdirectory", self.installed_subdirectory),
            ("obsolete_subdirectory", self.obsolete_subdirectory),
            ("core_state_subdirectory", self.core_state_subdirectory),
            ("transactions_subdirectory", self.transactions_subdirectory),
            ("core_lock_filename", self.core_lock_filename),
        ):
            if not value:
                raise ValueError(f"{name} must not be empty")
            if value.startswith(("/", "\\")) or ".." in value.replace("\\", "/").split("/"):
                raise ValueError(f"{name} must be a relative path without parent traversal")
