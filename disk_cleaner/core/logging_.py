from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import CleanResult


def default_log_path() -> Path:
    return Path.home() / ".local/state/disk-cleaner/cleanup.log"


def record(category_id: str, result: CleanResult, dry_run: bool, log_path=None) -> None:
    path = Path(log_path) if log_path else default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "DRY" if dry_run else "RUN"
    line = (f"{datetime.now().isoformat(timespec='seconds')}\t{mode}\t{category_id}"
            f"\tfreed={result.freed_bytes}\terrors={len(result.errors)}\tskipped={len(result.skipped)}")
    for err in result.errors:
        line += f"\n   ! {err}"
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
