from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from . import safety
from .fsutil import dir_size, remove_path
from .models import Category, CleanResult, Item, Risk

BIG_FILE_BYTES = 200 * 1024 * 1024


@dataclass
class Entry:
    path: Path
    size: int
    kind: str          # "file" hoặc "dir"
    atime: float
    deletable: bool


def _deletable(path: Path, home: Path) -> bool:
    if not safety.is_user_content(path, home):
        return False
    try:
        safety.assert_deletable(path, [home], home)
    except safety.SafetyError:
        return False
    return True


AMBIGUOUS_NAMES = frozenset({"build", "dist"})
BUILD_PARENT_MARKERS = ("package.json", "pyproject.toml", "setup.py", "Cargo.toml",
                        "Makefile", "CMakeLists.txt", "pom.xml", "build.gradle")


def _is_artifact_dir(path: Path) -> bool:
    """node_modules/venv/.venv/__pycache__ luôn là thư mục sinh ra. build/dist có thể là
    mã nguồn (vd. wp-includes/js/dist) nên chỉ tính khi thư mục cha là một dự án."""
    if path.name not in safety.BUILD_NAMES:
        return False
    if path.name in AMBIGUOUS_NAMES:
        return any((path.parent / m).exists() for m in BUILD_PARENT_MARKERS)
    return True


def find_big_files(root, min_bytes: int = BIG_FILE_BYTES, home=None) -> list[Entry]:
    home = Path(home) if home else Path.home()
    out: list[Entry] = []
    for dirpath, _dirs, files in os.walk(root, onerror=lambda _e: None):
        for name in files:
            p = Path(dirpath) / name
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_blocks * 512 < min_bytes:
                continue
            out.append(Entry(p, st.st_blocks * 512, "file", st.st_atime, _deletable(p, home)))
    return sorted(out, key=lambda e: -e.size)


def find_big_dirs(root, home=None, skip_hidden: bool = True, min_bytes: int = 0) -> list[Entry]:
    home = Path(home) if home else Path.home()
    root = Path(root)
    out: list[Entry] = []
    for dirpath, dirs, _files in os.walk(root, onerror=lambda _e: None):
        keep = []
        for d in dirs:
            p = Path(dirpath) / d
            if skip_hidden and Path(dirpath) == root and (d.startswith(".") or d == "snap"):
                continue
            if _is_artifact_dir(p) and not p.is_symlink():
                size = dir_size(p)
                if size >= min_bytes:
                    try:
                        atime = p.stat().st_atime
                    except OSError:
                        atime = 0.0
                    out.append(Entry(p, size, "dir", atime, _deletable(p, home)))
                continue  # không đi sâu vào thư mục đã ghi nhận
            keep.append(d)
        dirs[:] = keep
    return sorted(out, key=lambda e: -e.size)


class BigDirsCategory(Category):
    id = "big-dirs"
    title = "venv / node_modules bỏ quên"
    icon = "folder-symbolic"
    risk = Risk.RELOADABLE
    expandable = True
    description = "Thư mục môi trường trong dự án; tạo lại bằng requirements.txt / npm install"

    def __init__(self, home):
        self.home = Path(home)

    def scan(self) -> list[Item]:
        items = []
        for e in find_big_dirs(self.home, home=self.home):
            if not e.deletable:
                continue
            rel = e.path.relative_to(self.home)
            items.append(Item(id=f"bigdir:{e.path}", label=str(rel), size_bytes=e.size,
                              detail=e.path.name, path=str(e.path)))
        return items

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        for item in items:
            if dry_run:
                result.freed_bytes += item.size_bytes
                continue
            try:
                result.freed_bytes += remove_path(item.path, [self.home], self.home)
            except Exception as exc:
                result.errors.append(f"{item.path}: {exc}")
        return result
