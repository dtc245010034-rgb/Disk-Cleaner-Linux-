from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import safety


def dir_size(path) -> int:
    """Dung lượng thật trên đĩa (theo block), bỏ qua symlink và thư mục không đọc được."""
    p = Path(path)
    try:
        if p.is_symlink():
            return 0
        st = p.lstat()
    except OSError:
        return 0
    if not p.is_dir():
        return st.st_blocks * 512
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda _e: None):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_blocks * 512
            except OSError:
                pass
    return total


def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def free_bytes(path: str = "/") -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return p.returncode, p.stdout, p.stderr


def remove_path(path, allowed_roots, home=None, check_project: bool = True) -> int:
    """Xoá một file/thư mục sau khi qua safety. Symlink: chỉ xoá chính link."""
    p = Path(path)
    if p.is_symlink():
        safety.assert_deletable(p.parent, allowed_roots, home, check_project=False)
        p.unlink()
        return 0
    real = safety.assert_deletable(p, allowed_roots, home, check_project=check_project)
    size = dir_size(real)
    if real.is_dir():
        shutil.rmtree(real)
    else:
        real.unlink()
    return size


def remove_contents(root, allowed_roots, home=None, check_project: bool = True) -> tuple[int, list[str]]:
    """Xoá nội dung bên trong root (giữ lại root). Trả (byte giải phóng, danh sách lỗi)."""
    freed, errors = 0, []
    root = Path(root)
    if not root.is_dir():
        return 0, errors
    for child in root.iterdir():
        try:
            freed += remove_path(child, allowed_roots, home, check_project=check_project)
        except (safety.SafetyError, OSError) as exc:
            errors.append(f"{child}: {exc}")
    return freed, errors
