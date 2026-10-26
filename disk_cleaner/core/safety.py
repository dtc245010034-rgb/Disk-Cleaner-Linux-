from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

PROJECT_MARKERS = (".git", "package.json", "requirements.txt", "pyproject.toml")
BUILD_NAMES = frozenset({"node_modules", "venv", ".venv", "__pycache__", "build", "dist"})
SYSTEM_BLOCKED = ("/", "/home", "/etc", "/usr", "/var", "/bin", "/sbin", "/lib",
                  "/opt", "/boot", "/root", "/tmp")
USER_BLOCKED = ("Documents", "Pictures", "Desktop", "Downloads", "Videos", "Music",
                ".ssh", ".gnupg", "Màn hình nền")


class SafetyError(Exception):
    """Đường dẫn bị từ chối xoá."""


def _blocked(home: Path) -> set[Path]:
    h = Path(os.path.realpath(home))
    return {Path(p) for p in SYSTEM_BLOCKED} | {h} | {h / n for n in USER_BLOCKED}


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def assert_deletable(path, allowed_roots: Iterable, home=None, check_project: bool = True) -> Path:
    """Trả về đường dẫn thật nếu được phép xoá, ngược lại ném SafetyError."""
    home = Path(home) if home else Path.home()
    real = Path(os.path.realpath(path))
    roots = [Path(os.path.realpath(r)) for r in allowed_roots]
    if not any(_is_inside(real, r) for r in roots):
        raise SafetyError(f"{real} nằm ngoài vùng được phép xoá")
    for b in _blocked(home):
        if _is_inside(b, real):  # real == b hoặc real là tổ tiên của b
            raise SafetyError(f"{real} nằm trong danh sách cấm xoá ({b})")
    if check_project and real.is_dir() and real.name not in BUILD_NAMES:
        if any((real / m).exists() for m in PROJECT_MARKERS) or any(real.glob("docker-compose*.yml")):
            raise SafetyError(f"{real} là thư mục dự án, không được xoá nguyên thư mục")
    return real


def is_user_content(path, home=None) -> bool:
    """True nếu path nằm trong thư mục của người dùng, không phải dữ liệu ứng dụng
    (thư mục ẩn cấp 1 của home hoặc ~/snap)."""
    h = Path(os.path.realpath(home or Path.home()))
    real = Path(os.path.realpath(path))
    try:
        rel = real.relative_to(h)
    except ValueError:
        return False
    if not rel.parts:
        return False
    first = rel.parts[0]
    return not (first.startswith(".") or first == "snap")
