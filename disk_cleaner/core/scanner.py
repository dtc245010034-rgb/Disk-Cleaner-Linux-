from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from .models import Category, Item


@dataclass
class ScanOutcome:
    category: Category
    items: list[Item]
    error: str | None = None


def scan_all(categories: Iterable[Category]) -> Iterator[ScanOutcome]:
    """Quét lần lượt từng nhóm (chỉ đọc). Lỗi của một nhóm không làm dừng các nhóm khác."""
    for cat in categories:
        try:
            if not cat.available():
                continue
            outcome = ScanOutcome(cat, cat.scan())
        except Exception as exc:
            outcome = ScanOutcome(cat, [], f"{type(exc).__name__}: {exc}")
        yield outcome
