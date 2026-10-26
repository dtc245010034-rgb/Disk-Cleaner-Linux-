from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Risk(Enum):
    SAFE = "safe"                # An toàn
    RELOADABLE = "reloadable"    # Tải lại được
    DANGEROUS = "dangerous"      # Có thể mất dữ liệu


@dataclass
class Item:
    id: str
    label: str
    size_bytes: int
    detail: str = ""
    locked: bool = False
    path: str | None = None
    data: dict = field(default_factory=dict)


@dataclass
class CleanResult:
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


class Category:
    id = ""
    title = ""
    icon = "folder-symbolic"
    risk = Risk.SAFE
    needs_root = False
    expandable = False
    description = ""

    def available(self) -> bool:
        return True

    def scan(self) -> list[Item]:
        raise NotImplementedError

    def clean(self, items: list[Item], dry_run: bool) -> CleanResult:
        raise NotImplementedError

    def root_ops(self, items: list[Item]) -> list[list[str]]:
        return []
