# Disk Cleaner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ứng dụng desktop GTK3 (Python) để quét, hiển thị và dọn dung lượng ổ đĩa Ubuntu/XFCE theo nhóm, kèm khám phá đĩa (treemap), tìm file lớn và xem tổng quan hệ thống.

**Architecture:** `core/` (không import GTK) chứa mô hình, quy tắc an toàn, các nhóm dọn (scanner/cleaner) và thông tin hệ thống; `ui/` (GTK3) chỉ gọi `core/`; thao tác cần root đi qua `root_helper.py` chạy bằng `pkexec`, chỉ nhận danh sách thao tác cố định. Quét/dọn chạy luồng nền.

**Tech Stack:** Python 3.12, PyGObject (GTK 3.24, Cairo, Pango — đã có sẵn trên máy), pytest (cài trong `.venv`), `pkexec`.

**Spec:** `docs/superpowers/specs/2026-10-26-disk-cleaner-design.md`

**Tinh chỉnh so với spec (do kiểm tra thực tế máy ngày 2026-10-26):**
- `categories.py` tách thành 3 module cho gọn: `categories.py` (nhóm xoá thư mục + Claude cũ), `tools.py` (npm/pip/docker), `syscats.py` (apt/journal/kernel/snap) + `registry.py` gom lại.
- Dung lượng Docker volume lấy từ `docker system df -v --format '{{json .}}'` (không cần image phụ trợ như busybox; sai số do định dạng "46.4MB").
- Nhóm "Cache APT" đo `/var/cache/apt/archives` (phần `apt-get clean` thực sự xoá).
- Icon: bỏ SVG đóng gói kèm; `widgets.icon()` có chuỗi dự phòng (tên symbolic → tên thường → `image-missing`). Có thể bổ sung SVG sau nếu cần.
- `root_helper.py` nhận **một** chuỗi JSON chứa danh sách thao tác (một lần `pkexec` cho cả lượt dọn).

## Global Constraints

- Python 3.12; giao diện GTK 3 (`gi.require_version("Gtk", "3.0")`).
- `core/` **không** import GTK; `ui/` chỉ gọi `core/`.
- `root_helper.py` chỉ dùng thư viện chuẩn, không `shell=True`, chỉ nhận op: `apt-clean`, `journal-vacuum`, `kernel-purge`, `snap-remove`.
- Kernel đang chạy và kernel mới nhất luôn `locked`; bị `root_helper` từ chối kernel đang chạy.
- Cache Chrome: **không** đụng cookie, mật khẩu, IndexedDB, extension, `ScriptCache`.
- Journal cắt xuống `100M`.
- Bản Claude Code cũ: giữ bản mới nhất trong mỗi thư mục và mọi bản đang có tiến trình chạy.
- Mọi lệnh xoá đi qua `safety.assert_deletable`; mức `DANGEROUS` mặc định không tích và phải gõ `XOA` để xác nhận; mức `SAFE` tích sẵn.
- Steam chỉ hiển thị dung lượng, không có hành động xoá.
- File lớn: ngưỡng 200 MB; thư mục bỏ quên: `node_modules`, `venv`, `.venv`, `__pycache__`, `build`, `dist`.
- Tab Hệ thống tự làm mới mỗi 2 giây khi đang hiển thị.
- Log xoá: `~/.local/state/disk-cleaner/cleanup.log`.
- Giao diện tiếng Việt; icon Adwaita symbolic (`emblem-ok-symbolic`, `dialog-warning-symbolic`, `dialog-error-symbolic`, `edit-clear-all-symbolic`, `drive-harddisk-symbolic`, `system-search-symbolic`, `computer-symbolic`, `user-trash-symbolic`, `folder-symbolic`, `package-x-generic-symbolic`, `view-list-symbolic`, `security-high-symbolic`, `view-refresh-symbolic`, `edit-delete-symbolic`).
- Git: commit với danh tính cục bộ của repo (`dtc245010034-rgb <dtc245010034@ictu.edu.vn>`), **không** thêm dòng đồng tác giả/trailer; push lên `origin main` sau mỗi task.

## Review Focus

Các tình huống spec ngụ ý nhưng dễ bị bỏ sót (mỗi dòng có test ở task sở hữu code):
1. **Symlink trong thư mục cache trỏ ra ngoài** (ví dụ tới `~/Documents`): chỉ xoá link, không xoá đích — test ở Task 1.
2. **Thư mục không đọc được** (permission denied) khi đo dung lượng: bỏ qua, không crash — test ở Task 1.
3. **Docker daemon tắt** (`docker` có nhưng lệnh lỗi): các nhóm Docker ẩn đi, không crash — test ở Task 3.
4. **Chỉ có một kernel cài** (kernel đang chạy cũng là mới nhất): mọi mục đều `locked`, không có gì để gỡ — test ở Task 4.
5. **Người dùng huỷ hộp mật khẩu `pkexec`**: các mục root được đánh dấu "bỏ qua", không coi là lỗi, không báo đã giải phóng — test ở Task 2.

---

## File Structure

```
disk-cleaner/
├── pyproject.toml
├── requirements-dev.txt
├── README.md
├── disk-cleaner.desktop.in
├── disk_cleaner/
│   ├── __init__.py
│   ├── __main__.py
│   ├── root_helper.py            # stdlib only; chạy bằng pkexec
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py             # Risk, Item, CleanResult, Category
│   │   ├── safety.py             # assert_deletable, is_user_content, SafetyError
│   │   ├── fsutil.py             # dir_size, human, run, free_bytes, remove_path, remove_contents
│   │   ├── logging_.py           # ghi cleanup.log
│   │   ├── categories.py         # DirsCategory, chrome_dirs, fs_categories, ClaudeOldVersions
│   │   ├── tools.py              # CommandCache (npm/pip), DockerDangling/UnusedImages/Volumes
│   │   ├── syscats.py            # AptCache, JournalLogs, OldKernels, OldSnaps
│   │   ├── registry.py           # build_categories()
│   │   ├── scanner.py            # scan_all -> ScanOutcome
│   │   ├── cleaner.py            # run_cleanup
│   │   ├── rootrunner.py         # RootRunner (pkexec)
│   │   ├── bigfiles.py           # find_big_files/find_big_dirs, BigDirsCategory
│   │   ├── diskmap.py            # list_children, squarify
│   │   └── sysinfo.py            # RAM/CPU/nhiệt độ/tiến trình/phân vùng/autostart
│   └── ui/
│       ├── __init__.py
│       ├── app.py                # MainWindow, load_css, run
│       ├── widgets.py            # icon, RiskBadge, UsageBar, CategoryCard, confirm
│       ├── cleanup_tab.py
│       ├── system_tab.py
│       ├── bigfiles_tab.py
│       ├── diskmap_tab.py
│       └── style.css
└── tests/
    ├── core/ (test_safety, test_fsutil, test_categories_fs, test_scanner_cleaner, test_tools,
    │          test_root_helper, test_rootrunner, test_syscats, test_registry, test_bigfiles,
    │          test_diskmap, test_sysinfo)
    └── ui/test_widgets.py
```

---

### Task 1: Khung dự án, mô hình, tiện ích file và `safety`

**Files:**
- Create: `pyproject.toml`, `requirements-dev.txt`, `disk_cleaner/__init__.py`, `disk_cleaner/core/__init__.py`, `disk_cleaner/core/models.py`, `disk_cleaner/core/safety.py`, `disk_cleaner/core/fsutil.py`
- Test: `tests/core/test_safety.py`, `tests/core/test_fsutil.py`

**Interfaces:**
- Produces:
  - `models.Risk` (`SAFE`, `RELOADABLE`, `DANGEROUS`), `models.Item(id, label, size_bytes, detail="", locked=False, path=None, data={})`, `models.CleanResult(freed_bytes=0, errors=[], skipped=[])`, `models.Category` (thuộc tính `id,title,icon,risk,needs_root,expandable,description`; phương thức `available()`, `scan()`, `clean(items, dry_run)`, `root_ops(items)`).
  - `safety.SafetyError`, `safety.assert_deletable(path, allowed_roots, home=None, check_project=True) -> Path`, `safety.is_user_content(path, home=None) -> bool`.
  - `fsutil.dir_size(path) -> int`, `fsutil.human(n) -> str`, `fsutil.run(cmd, timeout=60) -> (rc, out, err)`, `fsutil.free_bytes(path="/") -> int`, `fsutil.remove_path(path, allowed_roots, home=None, check_project=True) -> int`, `fsutil.remove_contents(root, allowed_roots, home=None, check_project=True) -> (freed, errors)`.

- [ ] **Step 1: Tạo venv, cấu hình pytest**

```bash
cd ~/disk-cleaner
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pytest
printf 'pytest\n' > requirements-dev.txt
mkdir -p disk_cleaner/core disk_cleaner/ui tests/core tests/ui
touch disk_cleaner/__init__.py disk_cleaner/core/__init__.py disk_cleaner/ui/__init__.py
```

Tạo `pyproject.toml`:

```toml
[project]
name = "disk-cleaner"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Viết test `safety` (sẽ fail)**

`tests/core/test_safety.py`:

```python
import pytest

from disk_cleaner.core.safety import SafetyError, assert_deletable, is_user_content


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    for d in ("Documents", ".cache", "proj/node_modules"):
        (h / d).mkdir(parents=True)
    (h / "proj" / ".git").mkdir()
    return h


def test_allows_child_of_allowed_root(home):
    target = home / ".cache" / "x"
    target.mkdir()
    assert assert_deletable(target, [home / ".cache"], home) == target.resolve()


def test_rejects_outside_roots(home, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(SafetyError):
        assert_deletable(other, [home / ".cache"], home)


def test_rejects_home_itself_and_documents(home):
    with pytest.raises(SafetyError):
        assert_deletable(home, [home], home)
    with pytest.raises(SafetyError):
        assert_deletable(home / "Documents", [home], home)


def test_rejects_ancestor_of_blocked_path(home, tmp_path):
    with pytest.raises(SafetyError):
        assert_deletable(tmp_path, [tmp_path], home)


def test_rejects_project_root_but_allows_its_node_modules(home):
    with pytest.raises(SafetyError):
        assert_deletable(home / "proj", [home], home)
    assert assert_deletable(home / "proj" / "node_modules", [home], home)


def test_check_project_false_allows_dir_with_package_json(home):
    d = home / ".cache" / "x"
    d.mkdir()
    (d / "package.json").write_text("{}")
    assert_deletable(d, [home / ".cache"], home, check_project=False)
    with pytest.raises(SafetyError):
        assert_deletable(d, [home / ".cache"], home)


def test_symlink_escape_is_rejected(home):
    link = home / ".cache" / "link"
    link.symlink_to(home / "Documents")
    with pytest.raises(SafetyError):
        assert_deletable(link, [home / ".cache"], home)


def test_is_user_content(home):
    assert is_user_content(home / "proj" / "node_modules", home)
    assert not is_user_content(home / ".config" / "x", home)
    assert not is_user_content(home / "snap" / "code", home)
    assert not is_user_content(home, home)
```

- [ ] **Step 3: Viết test `fsutil` (sẽ fail)**

`tests/core/test_fsutil.py`:

```python
from disk_cleaner.core import fsutil


def _home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_dir_size_counts_files_and_ignores_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_bytes(b"x" * 50000)
    d = tmp_path / "d"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 10000)
    (d / "link").symlink_to(outside)
    size = fsutil.dir_size(d)
    assert 10000 <= size < 50000


def test_dir_size_skips_unreadable_directory(tmp_path):  # Review Focus 2
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "f").write_bytes(b"x" * 5000)
    (tmp_path / "ok").write_bytes(b"x" * 5000)
    locked.chmod(0)
    try:
        assert fsutil.dir_size(tmp_path) >= 5000
    finally:
        locked.chmod(0o755)


def test_human():
    assert fsutil.human(512) == "512 B"
    assert fsutil.human(1536) == "1.5 KB"
    assert fsutil.human(5 * 1024**3) == "5.0 GB"


def test_free_bytes_positive():
    assert fsutil.free_bytes("/") > 0


def test_run_missing_command_returns_127():
    rc, out, err = fsutil.run(["definitely-not-a-command-xyz"])
    assert rc == 127 and out == ""


def test_remove_contents_keeps_root(tmp_path):
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "f").write_bytes(b"x" * 4000)
    (root / "top").write_bytes(b"x" * 4000)
    freed, errors = fsutil.remove_contents(root, [root], home)
    assert root.is_dir() and list(root.iterdir()) == []
    assert errors == [] and freed >= 8000


def test_remove_path_symlink_removes_only_link(tmp_path):  # Review Focus 1
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    root.mkdir(parents=True)
    target = home / "Documents"
    target.mkdir()
    (target / "keep").write_text("1")
    link = root / "l"
    link.symlink_to(target)
    fsutil.remove_path(link, [root], home)
    assert not link.is_symlink()
    assert (target / "keep").exists()


def test_remove_contents_reports_safety_errors_and_continues(tmp_path):
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    proj = root / "proj"
    (proj / ".git").mkdir(parents=True)
    (root / "junk").write_bytes(b"x" * 100)
    freed, errors = fsutil.remove_contents(root, [root], home)
    assert proj.exists() and not (root / "junk").exists()
    assert len(errors) == 1
```

- [ ] **Step 4: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: lỗi `ModuleNotFoundError` / `ImportError` (chưa có `safety`, `fsutil`).

- [ ] **Step 5: Viết `models.py`**

`disk_cleaner/core/models.py`:

```python
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
```

- [ ] **Step 6: Viết `safety.py`**

`disk_cleaner/core/safety.py`:

```python
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
```

- [ ] **Step 7: Viết `fsutil.py`**

`disk_cleaner/core/fsutil.py`:

```python
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
```

- [ ] **Step 8: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS (15 test).

- [ ] **Step 9: Commit và push**

```bash
git add pyproject.toml requirements-dev.txt disk_cleaner tests
git commit -m "feat(core): mô hình dữ liệu, safety và tiện ích file"
git push
```

---

### Task 2: Nhóm xoá thư mục, Claude cũ, scanner, cleaner, log

**Files:**
- Create: `disk_cleaner/core/logging_.py`, `disk_cleaner/core/categories.py`, `disk_cleaner/core/scanner.py`, `disk_cleaner/core/cleaner.py`
- Test: `tests/core/test_categories_fs.py`, `tests/core/test_scanner_cleaner.py`

**Interfaces:**
- Consumes: Task 1 (`Category`, `Item`, `CleanResult`, `Risk`, `fsutil.*`, `safety.SafetyError`).
- Produces:
  - `logging_.record(category_id, result, dry_run, log_path=None)`
  - `categories.DirsCategory(id, title, description, dirs, home, icon="folder-symbolic")`
  - `categories.chrome_dirs(home) -> list[Path]`, `categories.fs_categories(home) -> list[Category]`
  - `categories.ClaudeOldVersions(home, running_exes=None)`
  - `scanner.ScanOutcome(category, items, error=None)`, `scanner.scan_all(categories) -> Iterator[ScanOutcome]`
  - `cleaner.run_cleanup(selection, dry_run, root_runner=None, log_path=None) -> dict[str, CleanResult]` với `selection: list[tuple[Category, list[Item]]]`; `root_runner.run(ops: list[list[str]]) -> list[dict]` (mỗi dict có `ok`, `error?`, `cancelled?`).

- [ ] **Step 1: Viết test nhóm xoá thư mục + Claude cũ (sẽ fail)**

`tests/core/test_categories_fs.py`:

```python
from pathlib import Path

from disk_cleaner.core import categories as cats
from disk_cleaner.core.models import Risk


def test_dirs_category_hides_when_empty(tmp_path):
    d = tmp_path / ".cache" / "x"
    d.mkdir(parents=True)
    assert cats.DirsCategory("x", "X", "d", [d], tmp_path).scan() == []


def test_dirs_category_scan_and_dry_run(tmp_path):
    d = tmp_path / ".cache" / "x"
    d.mkdir(parents=True)
    (d / "f").write_bytes(b"x" * 8000)
    c = cats.DirsCategory("x", "X", "d", [d], tmp_path)
    items = c.scan()
    assert len(items) == 1 and items[0].size_bytes >= 8000 and c.risk == Risk.SAFE
    res = c.clean(items, dry_run=True)
    assert res.freed_bytes >= 8000 and (d / "f").exists()


def test_dirs_category_clean_removes_contents_keeps_dir(tmp_path):
    d = tmp_path / ".cache" / "x"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f").write_bytes(b"x" * 8000)
    c = cats.DirsCategory("x", "X", "d", [d], tmp_path)
    res = c.clean(c.scan(), dry_run=False)
    assert d.is_dir() and list(d.iterdir()) == [] and res.freed_bytes >= 8000


def test_dirs_category_cleans_dir_containing_package_json(tmp_path):
    d = tmp_path / ".cache" / "ts"
    (d / "6.0").mkdir(parents=True)
    (d / "6.0" / "package.json").write_text("{}")
    (d / "6.0" / "big").write_bytes(b"x" * 5000)
    c = cats.DirsCategory("ts", "TS", "d", [d], tmp_path)
    res = c.clean(c.scan(), dry_run=False)
    assert res.errors == [] and not (d / "6.0").exists()


def test_chrome_clean_keeps_cookies_indexeddb_and_scriptcache(tmp_path):
    home = tmp_path
    prof = home / ".config/google-chrome/Default"
    cs = prof / "Service Worker/CacheStorage/a"
    cs.mkdir(parents=True)
    (cs / "f").write_bytes(b"x" * 5000)
    (prof / "Service Worker/ScriptCache").mkdir(parents=True)
    (prof / "Service Worker/ScriptCache/s").write_bytes(b"x" * 100)
    (prof / "Cookies").write_bytes(b"c")
    (prof / "IndexedDB").mkdir()
    (prof / "IndexedDB/db").write_bytes(b"d")
    (home / ".cache/google-chrome").mkdir(parents=True)
    (home / ".cache/google-chrome/c").write_bytes(b"x" * 5000)
    cat = cats.DirsCategory("chrome-cache", "Cache Chrome", "", cats.chrome_dirs(home), home)
    cat.clean(cat.scan(), dry_run=False)
    assert (prof / "Cookies").exists()
    assert (prof / "IndexedDB/db").exists()
    assert (prof / "Service Worker/ScriptCache/s").exists()
    assert not cs.exists()
    assert not (home / ".cache/google-chrome/c").exists()


def test_fs_categories_ids(tmp_path):
    ids = {c.id for c in cats.fs_categories(tmp_path)}
    assert {"trash", "chrome-cache", "vscode-cache", "puppeteer-cache", "misc-cache"} <= ids


def test_claude_old_versions_keeps_newest_and_running(tmp_path):
    home = tmp_path
    g = home / ".local/share/claude/versions"
    g.mkdir(parents=True)
    for v in ("2.1.2", "2.1.9", "2.1.10"):
        (g / v).write_bytes(b"x" * 5000)
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/agy.123.old").write_bytes(b"x" * 5000)
    running = {str((g / "2.1.9").resolve())}
    c = cats.ClaudeOldVersions(home, running_exes=lambda: running)
    names = sorted(Path(i.path).name for i in c.scan())
    assert names == ["2.1.2", "agy.123.old"]
    res = c.clean(c.scan(), dry_run=False)
    assert res.errors == []
    assert not (g / "2.1.2").exists()
    assert (g / "2.1.9").exists() and (g / "2.1.10").exists()


def test_claude_old_versions_rechecks_running_at_clean_time(tmp_path):
    g = tmp_path / ".local/share/claude/versions"
    g.mkdir(parents=True)
    for v in ("2.1.2", "2.1.10"):
        (g / v).write_bytes(b"x" * 5000)
    state = {"running": set()}
    c = cats.ClaudeOldVersions(tmp_path, running_exes=lambda: state["running"])
    items = c.scan()
    state["running"] = {str((g / "2.1.2").resolve())}
    res = c.clean(items, dry_run=False)
    assert (g / "2.1.2").exists() and len(res.skipped) == 1
```

- [ ] **Step 2: Viết test scanner/cleaner (sẽ fail)**

`tests/core/test_scanner_cleaner.py`:

```python
from disk_cleaner.core import cleaner, safety, scanner
from disk_cleaner.core.models import Category, CleanResult, Item, Risk


class Fake(Category):
    def __init__(self, id, items=None, needs_root=False, scan_error=None,
                 clean_error=None, available=True, risk=Risk.SAFE):
        self.id, self.title = id, id
        self._items = items if items is not None else [Item(id, id, 1000)]
        self.needs_root = needs_root
        self._scan_error, self._clean_error, self._available = scan_error, clean_error, available
        self.risk = risk
        self.clean_calls = []

    def available(self):
        return self._available

    def scan(self):
        if self._scan_error:
            raise self._scan_error
        return self._items

    def clean(self, items, dry_run):
        self.clean_calls.append(dry_run)
        if self._clean_error:
            raise self._clean_error
        return CleanResult(freed_bytes=sum(i.size_bytes for i in items))

    def root_ops(self, items):
        return [["apt-clean"]]


class FakeRunner:
    def __init__(self, ok=True, cancelled=False):
        self.ok, self.cancelled, self.calls = ok, cancelled, []

    def run(self, ops):
        self.calls.append(ops)
        if self.cancelled:
            return [{"ok": False, "cancelled": True, "error": "huỷ"} for _ in ops]
        if self.ok:
            return [{"ok": True} for _ in ops]
        return [{"ok": False, "error": "apt lỗi"} for _ in ops]


def test_scan_all_isolates_errors_and_skips_unavailable():
    cats = [Fake("a"), Fake("b", scan_error=RuntimeError("boom")),
            Fake("c", available=False), Fake("d")]
    out = list(scanner.scan_all(cats))
    assert [o.category.id for o in out] == ["a", "b", "d"]
    assert out[1].error and "boom" in out[1].error and out[1].items == []
    assert out[0].error is None


def test_run_cleanup_non_root(tmp_path):
    cat = Fake("a")
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=tmp_path / "log")
    assert res["a"].freed_bytes == 1000 and cat.clean_calls == [False]


def test_dry_run_never_calls_root_runner(tmp_path):
    cat, runner = Fake("r", needs_root=True), FakeRunner()
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=True, root_runner=runner,
                              log_path=tmp_path / "log")
    assert runner.calls == [] and res["r"].freed_bytes == 1000


def test_root_ops_are_batched_into_single_runner_call(tmp_path):
    a, b = Fake("a", needs_root=True), Fake("b", needs_root=True)
    runner = FakeRunner()
    res = cleaner.run_cleanup([(a, a._items), (b, b._items)], dry_run=False,
                              root_runner=runner, log_path=tmp_path / "log")
    assert len(runner.calls) == 1 and len(runner.calls[0]) == 2
    assert res["a"].freed_bytes == 1000 and res["b"].errors == []


def test_pkexec_cancel_is_skipped_not_error(tmp_path):  # Review Focus 5
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False,
                              root_runner=FakeRunner(cancelled=True), log_path=tmp_path / "log")
    assert res["r"].errors == [] and res["r"].freed_bytes == 0 and res["r"].skipped


def test_root_failure_reports_error_and_no_freed(tmp_path):
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False,
                              root_runner=FakeRunner(ok=False), log_path=tmp_path / "log")
    assert res["r"].errors == ["apt lỗi"] and res["r"].freed_bytes == 0


def test_root_without_runner_is_skipped(tmp_path):
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=tmp_path / "log")
    assert res["r"].skipped


def test_safety_error_is_captured_and_logged(tmp_path):
    log = tmp_path / "state" / "cleanup.log"
    cat = Fake("bad", clean_error=safety.SafetyError("cấm"))
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=log)
    assert "cấm" in res["bad"].errors[0]
    text = log.read_text(encoding="utf-8")
    assert "bad" in text and "RUN" in text


def test_empty_selection_is_ignored(tmp_path):
    cat = Fake("a")
    assert cleaner.run_cleanup([(cat, [])], dry_run=False, log_path=tmp_path / "log") == {}
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_categories_fs.py tests/core/test_scanner_cleaner.py -q`
Expected: `ImportError` (chưa có `categories`, `scanner`, `cleaner`).

- [ ] **Step 4: Viết `logging_.py`**

`disk_cleaner/core/logging_.py`:

```python
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
```

- [ ] **Step 5: Viết `categories.py`**

`disk_cleaner/core/categories.py`:

```python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

from .fsutil import dir_size, remove_contents, remove_path
from .models import Category, CleanResult, Item, Risk


class DirsCategory(Category):
    """Xoá nội dung các thư mục cache cố định (giữ lại chính thư mục)."""

    def __init__(self, id, title, description, dirs, home, icon="folder-symbolic"):
        self.id, self.title, self.description, self.icon = id, title, description, icon
        self.dirs = [Path(d) for d in dirs]
        self.home = Path(home)
        self.risk = Risk.SAFE

    def scan(self) -> list[Item]:
        size = sum(dir_size(d) for d in self.dirs if d.is_dir())
        if size <= 0:
            return []
        return [Item(id=self.id, label=self.title, size_bytes=size, detail=self.description)]

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        if not items:
            return result
        for d in self.dirs:
            if not d.is_dir():
                continue
            if dry_run:
                result.freed_bytes += dir_size(d)
                continue
            freed, errors = remove_contents(d, [d], self.home, check_project=False)
            result.freed_bytes += freed
            result.errors += errors
        return result


def chrome_dirs(home) -> list[Path]:
    """Chỉ các thư mục cache của Chrome; không gồm cookie, IndexedDB, extension, ScriptCache."""
    home = Path(home)
    cfg = home / ".config/google-chrome"
    dirs = [home / ".cache/google-chrome"]
    for profile in sorted(cfg.glob("*")):
        if profile.is_dir() and (profile.name == "Default" or profile.name.startswith("Profile ")):
            for sub in ("Service Worker/CacheStorage", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache"):
                dirs.append(profile / sub)
    for name in ("GraphiteDawnCache", "component_crx_cache", "extensions_crx_cache"):
        dirs.append(cfg / name)
    return dirs


def fs_categories(home) -> list[Category]:
    home = Path(home)
    return [
        DirsCategory("trash", "Thùng rác", "Các file đã xoá đang nằm trong Thùng rác",
                     [home / ".local/share/Trash/files", home / ".local/share/Trash/info",
                      home / ".local/share/Trash/expunged"], home, icon="user-trash-symbolic"),
        DirsCategory("chrome-cache", "Cache Chrome",
                     "Cache trình duyệt; giữ nguyên đăng nhập, mật khẩu và lịch sử",
                     chrome_dirs(home), home),
        DirsCategory("vscode-cache", "Cache VS Code", "Gói extension đã tải và cache giao diện",
                     [home / ".config/Code/CachedExtensionVSIXs", home / ".config/Code/Cache"], home),
        DirsCategory("puppeteer-cache", "Cache Puppeteer", "Chrome tải kèm Puppeteer, tải lại khi cần",
                     [home / ".cache/puppeteer"], home),
        DirsCategory("misc-cache", "Thumbnails và shader cache",
                     "Ảnh thu nhỏ, shader, cache font/typescript/matplotlib",
                     [home / ".cache" / n for n in ("thumbnails", "mesa_shader_cache", "gstreamer-1.0",
                                                    "matplotlib", "typescript")], home),
    ]


def _ver_key(name: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", name))


def _running_exes() -> set[str]:
    out = set()
    for link in Path("/proc").glob("[0-9]*/exe"):
        try:
            out.add(os.path.realpath(os.readlink(link)))
        except OSError:
            pass
    return out


class ClaudeOldVersions(Category):
    id = "claude-old"
    title = "Bản Claude Code cũ"
    icon = "package-x-generic-symbolic"
    risk = Risk.SAFE
    expandable = True
    description = "Giữ bản mới nhất và bản đang chạy, xoá các bản cũ"

    def __init__(self, home, running_exes: Callable[[], set[str]] | None = None):
        self.home = Path(home)
        self._running = running_exes or _running_exes

    def _groups(self) -> list[Path]:
        h = self.home
        groups = [h / ".local/share/claude/versions", h / ".config/Claude/claude-code"]
        groups += sorted(h.glob("snap/code/*/.local/share/claude/versions"))
        return [g for g in groups if g.is_dir()]

    def _roots(self) -> list[Path]:
        return self._groups() + [self.home / ".local/bin"]

    @staticmethod
    def _in_use(entry: Path, running: set[str]) -> bool:
        real = os.path.realpath(entry)
        return any(exe == real or exe.startswith(real + os.sep) for exe in running)

    def scan(self) -> list[Item]:
        running = self._running()
        items: list[Item] = []
        for g in self._groups():
            entries = sorted(g.iterdir(), key=lambda p: _ver_key(p.name))
            for entry in entries[:-1]:
                if self._in_use(entry, running):
                    continue
                items.append(Item(id=f"claude-old:{entry}", label=f"Claude Code {entry.name}",
                                  detail=str(entry.parent), size_bytes=dir_size(entry), path=str(entry)))
        bindir = self.home / ".local/bin"
        if bindir.is_dir():
            for f in sorted(bindir.glob("agy.*.old")):
                items.append(Item(id=f"claude-old:{f}", label=f.name, detail=str(bindir),
                                  size_bytes=dir_size(f), path=str(f)))
        return items

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        running = self._running()
        roots = self._roots()
        for item in items:
            entry = Path(item.path)
            if self._in_use(entry, running):
                result.skipped.append(f"{entry.name}: đang được chạy")
                continue
            if dry_run:
                result.freed_bytes += item.size_bytes
                continue
            try:
                result.freed_bytes += remove_path(entry, roots, self.home, check_project=False)
            except Exception as exc:  # SafetyError hoặc OSError: ghi lỗi, tiếp tục mục khác
                result.errors.append(f"{entry}: {exc}")
        return result
```

- [ ] **Step 6: Viết `scanner.py` và `cleaner.py`**

`disk_cleaner/core/scanner.py`:

```python
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
```

`disk_cleaner/core/cleaner.py`:

```python
from __future__ import annotations

from . import logging_, safety
from .models import Category, CleanResult, Item


def run_cleanup(selection: list[tuple[Category, list[Item]]], dry_run: bool,
                root_runner=None, log_path=None) -> dict[str, CleanResult]:
    results: dict[str, CleanResult] = {}
    pending: list[tuple[Category, list[Item]]] = []
    for cat, items in selection:
        if not items:
            continue
        if cat.needs_root:
            if dry_run:
                results[cat.id] = CleanResult(freed_bytes=sum(i.size_bytes for i in items),
                                              skipped=["dry-run"])
            else:
                pending.append((cat, items))
            continue
        try:
            results[cat.id] = cat.clean(items, dry_run)
        except safety.SafetyError as exc:
            results[cat.id] = CleanResult(errors=[f"Bị chặn bởi safety: {exc}"])
        except Exception as exc:
            results[cat.id] = CleanResult(errors=[f"{type(exc).__name__}: {exc}"])
    if pending:
        results.update(_run_root(pending, root_runner))
    for cid, res in results.items():
        logging_.record(cid, res, dry_run, log_path)
    return results


def _run_root(pending, runner) -> dict[str, CleanResult]:
    out: dict[str, CleanResult] = {}
    if runner is None:
        for cat, _ in pending:
            out[cat.id] = CleanResult(skipped=["Không có công cụ cấp quyền root"])
        return out
    flat: list[list[str]] = []
    spans = []
    for cat, items in pending:
        ops = cat.root_ops(items)
        spans.append((cat, items, len(flat), len(flat) + len(ops)))
        flat.extend(ops)
    answers = runner.run(flat) if flat else []
    for cat, items, a, b in spans:
        chunk = answers[a:b]
        if any(x.get("cancelled") for x in chunk):
            out[cat.id] = CleanResult(skipped=["Đã huỷ xác thực quyền root"])
            continue
        errors = [x.get("error", "lỗi không rõ") for x in chunk if not x.get("ok")]
        if len(chunk) < b - a:
            errors.append("Thiếu kết quả từ root helper")
        freed = 0 if errors else sum(i.size_bytes for i in items)
        out[cat.id] = CleanResult(freed_bytes=freed, errors=errors)
    return out
```

- [ ] **Step 7: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 8: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat(core): nhóm xoá thư mục, Claude cũ, scanner, cleaner và log"
git push
```

---

### Task 3: Nhóm lệnh ngoài (npm, pip, Docker)

**Files:**
- Create: `disk_cleaner/core/tools.py`
- Test: `tests/core/test_tools.py`

**Interfaces:**
- Consumes: Task 1/2 (`Category`, `Item`, `CleanResult`, `Risk`, `fsutil.run`, `fsutil.dir_size`).
- Produces:
  - `tools.parse_size(text) -> int` (hệ thập phân: `kB`=1000, `MB`=1000², …)
  - `tools.CommandCache(id, title, description, path, command, tool)`, `tools.npm_cache(home)`, `tools.pip_cache(home)`
  - `tools.docker_df() -> dict | None`
  - `tools.DockerDangling`, `tools.DockerUnusedImages`, `tools.DockerVolumes` (đều là `Category`)

- [ ] **Step 1: Viết test (sẽ fail)**

`tests/core/test_tools.py`:

```python
import json

import pytest

from disk_cleaner.core import tools
from disk_cleaner.core.models import Risk

DF = {
    "Images": [
        {"ID": "sha256:aaa", "Repository": "<none>", "Tag": "<none>", "Containers": "0", "UniqueSize": "10MB"},
        {"ID": "sha256:bbb", "Repository": "grafana/grafana", "Tag": "13", "Containers": "0", "UniqueSize": "483MB"},
        {"ID": "sha256:ccc", "Repository": "mysql", "Tag": "8.4", "Containers": "1", "UniqueSize": "254MB"},
    ],
    "Volumes": [
        {"Name": "proj_db", "Links": "0", "Size": "206.7MB",
         "Labels": "com.docker.compose.project=proj,com.docker.compose.volume=db"},
        {"Name": "abc123", "Links": "0", "Size": "46.4MB", "Labels": ""},
        {"Name": "inuse", "Links": "1", "Size": "1MB", "Labels": "com.docker.compose.project=p"},
    ],
}


@pytest.fixture
def docker(monkeypatch):
    calls = []

    def _run(cmd, timeout=60):
        calls.append(cmd)
        if cmd[:3] == ["docker", "system", "df"]:
            return 0, json.dumps(DF), ""
        return 0, "", ""

    monkeypatch.setattr(tools, "run", _run)
    return calls


def test_parse_size():
    assert tools.parse_size("46.4MB") == 46_400_000
    assert tools.parse_size("127kB") == 127_000
    assert tools.parse_size("0B") == 0
    assert tools.parse_size("N/A") == 0
    assert tools.parse_size("") == 0


def test_docker_dangling_only_untagged_unused(docker):
    items = tools.DockerDangling().scan()
    assert len(items) == 1 and items[0].size_bytes == 10_000_000
    tools.DockerDangling().clean(items, dry_run=False)
    assert ["docker", "image", "prune", "-f"] in docker


def test_docker_unused_images_excludes_used_and_untagged(docker):
    cat = tools.DockerUnusedImages()
    items = cat.scan()
    assert [i.label for i in items] == ["grafana/grafana:13"]
    assert cat.risk == Risk.RELOADABLE and cat.expandable
    res = cat.clean(items, dry_run=False)
    assert ["docker", "rmi", "grafana/grafana:13"] in docker
    assert res.freed_bytes == 483_000_000


def test_docker_volumes_project_label_and_locked(docker):
    cat = tools.DockerVolumes()
    items = {i.id: i for i in cat.scan()}
    assert items["docker-volume:proj_db"].detail == "Project: proj"
    assert items["docker-volume:abc123"].detail == "Không rõ project"
    assert items["docker-volume:inuse"].locked is True
    assert cat.risk == Risk.DANGEROUS
    cat.clean([items["docker-volume:abc123"]], dry_run=False)
    assert ["docker", "volume", "rm", "abc123"] in docker


def test_docker_dry_run_does_not_run_destructive_commands(docker):
    cat = tools.DockerVolumes()
    cat.clean(cat.scan(), dry_run=True)
    assert not any(c[:2] in (["docker", "volume"], ["docker", "rmi"]) for c in docker)


def test_docker_daemon_down_hides_all_docker_categories(monkeypatch):  # Review Focus 3
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (1, "", "Cannot connect to the Docker daemon"))
    assert tools.DockerDangling().scan() == []
    assert tools.DockerUnusedImages().scan() == []
    assert tools.DockerVolumes().scan() == []


def test_docker_bad_json_is_handled(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (0, "not json", ""))
    assert tools.docker_df() is None


def test_command_cache_dry_run_and_clean(tmp_path, monkeypatch):
    d = tmp_path / ".npm"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 9000)
    calls = []

    def _run(cmd, timeout=60):
        calls.append(cmd)
        (d / "f").unlink()
        return 0, "", ""

    monkeypatch.setattr(tools, "run", _run)
    cat = tools.CommandCache("npm-cache", "Cache npm", "d", d, ["npm", "cache", "clean", "--force"], "npm")
    items = cat.scan()
    assert items[0].size_bytes >= 9000
    assert cat.clean(items, dry_run=True).freed_bytes >= 9000 and calls == []
    res = cat.clean(items, dry_run=False)
    assert calls == [["npm", "cache", "clean", "--force"]] and res.freed_bytes >= 9000


def test_command_cache_failure_reports_error(tmp_path, monkeypatch):
    d = tmp_path / ".npm"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 9000)
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (1, "", "npm lỗi"))
    cat = tools.CommandCache("npm-cache", "Cache npm", "d", d, ["npm"], "npm")
    res = cat.clean(cat.scan(), dry_run=False)
    assert res.errors == ["npm lỗi"] and res.freed_bytes == 0
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_tools.py -q`
Expected: `ImportError` (chưa có `tools`).

- [ ] **Step 3: Viết `tools.py`**

`disk_cleaner/core/tools.py`:

```python
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .fsutil import dir_size, run
from .models import Category, CleanResult, Item, Risk

_UNITS = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}


def parse_size(text: str) -> int:
    """Đổi chuỗi của docker như '46.4MB', '127kB' sang byte (hệ thập phân)."""
    m = re.fullmatch(r"\s*([\d.]+)\s*([kKMGT]?B)\s*", text or "")
    return int(float(m.group(1)) * _UNITS[m.group(2).upper()]) if m else 0


class CommandCache(Category):
    """Cache do một công cụ quản lý; dọn bằng lệnh chính thức của công cụ đó."""

    risk = Risk.SAFE

    def __init__(self, id, title, description, path, command, tool, icon="folder-symbolic"):
        self.id, self.title, self.description, self.icon = id, title, description, icon
        self.path, self.command, self.tool = Path(path), command, tool

    def available(self) -> bool:
        return shutil.which(self.tool) is not None

    def scan(self) -> list[Item]:
        size = dir_size(self.path)
        if size <= 0:
            return []
        return [Item(id=self.id, label=self.title, size_bytes=size, detail=self.description)]

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        if not items:
            return result
        before = dir_size(self.path)
        if dry_run:
            result.freed_bytes = before
            return result
        rc, _out, err = run(self.command, timeout=300)
        if rc != 0:
            result.errors.append(err.strip() or f"lệnh thất bại (rc={rc})")
        else:
            result.freed_bytes = max(0, before - dir_size(self.path))
        return result


def npm_cache(home) -> CommandCache:
    return CommandCache("npm-cache", "Cache npm", "Gói npm đã tải (npm cache clean)",
                        Path(home) / ".npm", ["npm", "cache", "clean", "--force"], "npm")


def pip_cache(home) -> CommandCache:
    return CommandCache("pip-cache", "Cache pip", "Gói pip đã tải (pip cache purge)",
                        Path(home) / ".cache/pip", ["pip", "cache", "purge"], "pip")


def docker_df() -> dict | None:
    rc, out, _err = run(["docker", "system", "df", "-v", "--format", "{{json .}}"], timeout=120)
    if rc != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


class _DockerBase(Category):
    def available(self) -> bool:
        return shutil.which("docker") is not None


class DockerDangling(_DockerBase):
    id = "docker-dangling"
    title = "Docker: image rác (dangling)"
    icon = "package-x-generic-symbolic"
    risk = Risk.SAFE
    description = "Image không có tên/tag và không container nào dùng"

    def scan(self) -> list[Item]:
        df = docker_df()
        if not df:
            return []
        size = sum(parse_size(i.get("UniqueSize", "")) for i in df.get("Images", [])
                   if i.get("Repository") == "<none>" and i.get("Containers") == "0")
        if size <= 0:
            return []
        return [Item(id=self.id, label=self.title, size_bytes=size, detail=self.description)]

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        if not items:
            return result
        if dry_run:
            result.freed_bytes = sum(i.size_bytes for i in items)
            return result
        rc, _o, err = run(["docker", "image", "prune", "-f"], timeout=300)
        if rc != 0:
            result.errors.append(err.strip() or f"docker lỗi (rc={rc})")
        else:
            result.freed_bytes = sum(i.size_bytes for i in items)
        return result


class DockerUnusedImages(_DockerBase):
    id = "docker-images"
    title = "Docker: image không dùng"
    icon = "package-x-generic-symbolic"
    risk = Risk.RELOADABLE
    expandable = True
    description = "Image có tên nhưng không container nào dùng; tải/build lại được"

    def scan(self) -> list[Item]:
        df = docker_df()
        if not df:
            return []
        items = []
        for img in df.get("Images", []):
            if img.get("Containers") != "0" or img.get("Repository") == "<none>":
                continue
            ref = f"{img['Repository']}:{img['Tag']}"
            items.append(Item(id=f"docker-image:{img['ID']}", label=ref,
                              size_bytes=parse_size(img.get("UniqueSize", "")),
                              data={"ref": ref, "id": img["ID"]}))
        return sorted(items, key=lambda i: -i.size_bytes)

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        for item in items:
            if dry_run:
                result.freed_bytes += item.size_bytes
                continue
            rc, _o, err = run(["docker", "rmi", item.data["ref"]], timeout=300)
            if rc != 0:
                result.errors.append(f"{item.label}: {err.strip() or f'rc={rc}'}")
            else:
                result.freed_bytes += item.size_bytes
        return result


def _label(labels: str, key: str) -> str | None:
    for part in (labels or "").split(","):
        k, _, v = part.partition("=")
        if k == key:
            return v
    return None


class DockerVolumes(_DockerBase):
    id = "docker-volumes"
    title = "Docker: volume (dữ liệu)"
    icon = "package-x-generic-symbolic"
    risk = Risk.DANGEROUS
    expandable = True
    description = "Có thể chứa database/dữ liệu thật; xoá là mất vĩnh viễn"

    def scan(self) -> list[Item]:
        df = docker_df()
        if not df:
            return []
        items = []
        for v in df.get("Volumes", []):
            proj = _label(v.get("Labels", ""), "com.docker.compose.project")
            detail = f"Project: {proj}" if proj else "Không rõ project"
            items.append(Item(id=f"docker-volume:{v['Name']}", label=v["Name"],
                              size_bytes=parse_size(v.get("Size", "")), detail=detail,
                              locked=v.get("Links", "0") != "0", data={"name": v["Name"]}))
        return sorted(items, key=lambda i: -i.size_bytes)

    def clean(self, items, dry_run) -> CleanResult:
        result = CleanResult()
        for item in items:
            if item.locked:
                result.skipped.append(f"{item.label}: đang được container dùng")
                continue
            if dry_run:
                result.freed_bytes += item.size_bytes
                continue
            rc, _o, err = run(["docker", "volume", "rm", item.data["name"]], timeout=120)
            if rc != 0:
                result.errors.append(f"{item.label}: {err.strip() or f'rc={rc}'}")
            else:
                result.freed_bytes += item.size_bytes
        return result
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 5: Kiểm tra với Docker thật (chỉ đọc)**

Run:
```bash
.venv/bin/python -I - <<'EOF'
import sys; sys.path.insert(0, ".")
from disk_cleaner.core import tools
from disk_cleaner.core.fsutil import human
for c in (tools.DockerDangling(), tools.DockerUnusedImages(), tools.DockerVolumes()):
    print(c.title, [(i.label, human(i.size_bytes), i.detail, i.locked) for i in c.scan()])
EOF
```
Expected: in ra các image/volume thật còn lại trên máy, không lỗi, không xoá gì.

- [ ] **Step 6: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat(core): nhóm npm/pip và Docker (image, volume)"
git push
```

---

### Task 4: `root_helper`, `RootRunner`, nhóm cần root và registry

**Files:**
- Create: `disk_cleaner/root_helper.py`, `disk_cleaner/core/rootrunner.py`, `disk_cleaner/core/syscats.py`, `disk_cleaner/core/registry.py`
- Test: `tests/core/test_root_helper.py`, `tests/core/test_rootrunner.py`, `tests/core/test_syscats.py`, `tests/core/test_registry.py`

**Interfaces:**
- Consumes: Task 1–3.
- Produces:
  - `root_helper.validate(op, args, running_version=None) -> list[str]` (argv an toàn; ném `ValueError`), `root_helper.execute(ops, running_version=None) -> list[dict]`, `root_helper.main(argv) -> int`
  - `rootrunner.RootRunner(helper=HELPER, prefix=("pkexec", "/usr/bin/python3"))` với `.run(ops) -> list[dict]`
  - `syscats.AptCache`, `syscats.JournalLogs`, `syscats.OldKernels(running_release=None)`, `syscats.OldSnaps(snaps_dir="/var/lib/snapd/snaps")`
  - `registry.build_categories(home=None) -> list[Category]`

- [ ] **Step 1: Viết test `root_helper` (sẽ fail)**

`tests/core/test_root_helper.py`:

```python
import pytest

from disk_cleaner import root_helper as rh


def test_apt_clean():
    assert rh.validate("apt-clean", []) == ["apt-get", "clean"]


def test_journal_vacuum_valid_and_invalid():
    assert rh.validate("journal-vacuum", ["100M"]) == ["journalctl", "--vacuum-size=100M"]
    for bad in ("100", "5G;rm", "-1M", "0M", "100M --all", ""):
        with pytest.raises(ValueError):
            rh.validate("journal-vacuum", [bad])


def test_kernel_purge_valid():
    argv = rh.validate("kernel-purge",
                       ["linux-image-7.0.0-34-generic", "linux-headers-7.0.0-34-generic",
                        "linux-headers-7.0.0-34"], running_version="7.0.0-38")
    assert argv == ["apt-get", "purge", "-y", "linux-image-7.0.0-34-generic",
                    "linux-headers-7.0.0-34-generic", "linux-headers-7.0.0-34"]


def test_kernel_purge_rejects_running_kernel():
    with pytest.raises(ValueError):
        rh.validate("kernel-purge", ["linux-image-7.0.0-38-generic"], running_version="7.0.0-38")


def test_kernel_purge_rejects_injection_and_other_packages():
    for bad in ("linux-image-1.0; rm -rf /", "bash", "linux-image-generic-hwe-24.04",
                "linux-image-7.0.0-34-generic extra", "--force-yes", "../etc"):
        with pytest.raises(ValueError):
            rh.validate("kernel-purge", [bad], running_version="7.0.0-38")
    with pytest.raises(ValueError):
        rh.validate("kernel-purge", [], running_version="7.0.0-38")


def test_snap_remove():
    assert rh.validate("snap-remove", ["firefox", "1234"]) == ["snap", "remove", "firefox", "--revision=1234"]
    for args in (["Firefox", "1"], ["firefox", "1a"], ["firefox"], ["fire fox", "1"], ["-x", "1"]):
        with pytest.raises(ValueError):
            rh.validate("snap-remove", args)


def test_unknown_op_rejected():
    with pytest.raises(ValueError):
        rh.validate("rm", ["-rf", "/"])


def test_execute_reports_invalid_ops_without_running():
    out = rh.execute([["rm", "-rf", "/"], []], running_version="7.0.0-38")
    assert [o["ok"] for o in out] == [False, False]
    assert "không hợp lệ" in out[0]["error"].lower() or "không được phép" in out[0]["error"].lower()
```

- [ ] **Step 2: Viết test `RootRunner` (sẽ fail)**

`tests/core/test_rootrunner.py`:

```python
import json
import os
import sys

from disk_cleaner.core.rootrunner import RootRunner


def _helper(tmp_path, body):
    h = tmp_path / "helper.py"
    h.write_text(body)
    h.chmod(0o644)
    return h


def test_parses_helper_json(tmp_path):
    h = _helper(tmp_path, "import json,sys\nprint(json.dumps([{'ok': True}]))\n")
    r = RootRunner(helper=h, prefix=(sys.executable,))
    assert r.run([["apt-clean"]]) == [{"ok": True}]


def test_passes_ops_as_single_json_argument(tmp_path):
    h = _helper(tmp_path, "import json,sys\nops=json.loads(sys.argv[1])\n"
                          "print(json.dumps([{'ok': True, 'n': len(ops)}]))\n")
    r = RootRunner(helper=h, prefix=(sys.executable,))
    assert r.run([["a"], ["b"]])[0]["n"] == 2


def test_pkexec_cancel_marks_all_ops_cancelled(tmp_path):
    h = _helper(tmp_path, "pass\n")
    r = RootRunner(helper=h, prefix=("sh", "-c", "exit 126", "--"))
    out = r.run([["apt-clean"], ["journal-vacuum", "100M"]])
    assert len(out) == 2 and all(o["cancelled"] for o in out)


def test_group_writable_helper_is_refused(tmp_path):
    h = _helper(tmp_path, "print('[]')\n")
    h.chmod(0o666)
    out = RootRunner(helper=h, prefix=(sys.executable,)).run([["apt-clean"]])
    assert out[0]["ok"] is False and "quyền ghi" in out[0]["error"]


def test_garbage_output_becomes_error(tmp_path):
    h = _helper(tmp_path, "print('oops')\n")
    out = RootRunner(helper=h, prefix=(sys.executable,)).run([["apt-clean"]])
    assert out[0]["ok"] is False


def test_empty_ops_returns_empty(tmp_path):
    assert RootRunner(helper=_helper(tmp_path, "pass\n"), prefix=(sys.executable,)).run([]) == []
```

- [ ] **Step 3: Viết test `syscats` và `registry` (sẽ fail)**

`tests/core/test_syscats.py`:

```python
from disk_cleaner.core import syscats
from disk_cleaner.core.models import Item, Risk

DPKG = (
    "linux-headers-7.0.0-28-generic||un \n"
    "linux-headers-7.0.0-34-generic|31260|ii \n"
    "linux-headers-7.0.0-34|8000|ii \n"
    "linux-headers-7.0.0-38-generic|31337|ii \n"
    "linux-image-7.0.0-31-generic||rc \n"
    "linux-image-7.0.0-34-generic|16629|ii \n"
    "linux-image-7.0.0-38-generic|16649|ii \n"
)


def _kernels(monkeypatch, out, running="7.0.0-38-generic"):
    monkeypatch.setattr(syscats, "run", lambda cmd, timeout=60: (0, out, ""))
    return syscats.OldKernels(running_release=running)


def test_kernels_group_by_version_and_lock_running_and_newest(monkeypatch):
    items = {i.id: i for i in _kernels(monkeypatch, DPKG).scan()}
    assert set(items) == {"kernel:7.0.0-31", "kernel:7.0.0-34", "kernel:7.0.0-38"}
    assert items["kernel:7.0.0-38"].locked and not items["kernel:7.0.0-34"].locked
    assert items["kernel:7.0.0-34"].size_bytes == (31260 + 8000 + 16629) * 1024
    assert sorted(items["kernel:7.0.0-34"].data["pkgs"]) == sorted([
        "linux-headers-7.0.0-34-generic", "linux-headers-7.0.0-34", "linux-image-7.0.0-34-generic"])


def test_kernels_root_ops_skip_locked(monkeypatch):
    cat = _kernels(monkeypatch, DPKG)
    items = cat.scan()
    ops = cat.root_ops(items)
    assert len(ops) == 1 and ops[0][0] == "kernel-purge"
    assert "linux-image-7.0.0-38-generic" not in ops[0]
    assert "linux-image-7.0.0-34-generic" in ops[0]
    assert "linux-image-7.0.0-31-generic" in ops[0]


def test_single_kernel_is_fully_locked(monkeypatch):  # Review Focus 4
    out = ("linux-image-7.0.0-38-generic|16649|ii \n"
           "linux-headers-7.0.0-38-generic|31337|ii \n")
    cat = _kernels(monkeypatch, out)
    items = cat.scan()
    assert len(items) == 1 and items[0].locked
    assert cat.root_ops(items) == []


def test_kernels_empty_output(monkeypatch):
    assert _kernels(monkeypatch, "").scan() == []


def test_journal_reclaim_over_target(monkeypatch):
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (
        0, "Archived and active journals take up 300.0M in the file system.\n", ""))
    cat = syscats.JournalLogs()
    items = cat.scan()
    assert items[0].size_bytes == 200 * 1024 * 1024
    assert cat.root_ops(items) == [["journal-vacuum", "100M"]]


def test_journal_hidden_when_under_target(monkeypatch):
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (
        0, "Archived and active journals take up 45.0M in the file system.\n", ""))
    assert syscats.JournalLogs().scan() == []


def test_apt_cache(tmp_path):
    (tmp_path / "a.deb").write_bytes(b"x" * 9000)
    cat = syscats.AptCache(path=tmp_path)
    items = cat.scan()
    assert items[0].size_bytes >= 9000 and cat.needs_root and cat.root_ops(items) == [["apt-clean"]]


def test_snaps_only_disabled(monkeypatch, tmp_path):
    out = ("Name  Version  Rev  Tracking  Publisher  Notes\n"
           "core20  1.0  2922  latest/stable  canonical**  base\n"
           "core20  1.0  2900  latest/stable  canonical**  base,disabled\n"
           "code    abc  267   latest/stable  vscode**     classic\n")
    (tmp_path / "core20_2900.snap").write_bytes(b"x" * 7000)
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (0, out, ""))
    cat = syscats.OldSnaps(snaps_dir=tmp_path)
    items = cat.scan()
    assert [i.id for i in items] == ["snap:core20:2900"]
    assert items[0].size_bytes == 7000
    assert cat.risk == Risk.RELOADABLE
    assert cat.root_ops(items) == [["snap-remove", "core20", "2900"]]


def test_snaps_none_disabled(monkeypatch):
    out = "Name  Version  Rev  Tracking  Publisher  Notes\ncode  abc  267  latest/stable  vscode**  classic\n"
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (0, out, ""))
    assert syscats.OldSnaps().scan() == []
```

`tests/core/test_registry.py`:

```python
from disk_cleaner.core.registry import build_categories


def test_registry_ids_unique_and_complete(tmp_path):
    cats = build_categories(tmp_path)
    ids = [c.id for c in cats]
    assert len(ids) == len(set(ids))
    for c in cats:
        assert c.title and c.icon and c.risk
    assert {"trash", "chrome-cache", "npm-cache", "apt-cache", "journal", "kernels",
            "snaps", "docker-volumes"} <= set(ids)
```

- [ ] **Step 4: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_root_helper.py tests/core/test_rootrunner.py tests/core/test_syscats.py tests/core/test_registry.py -q`
Expected: `ImportError`.

- [ ] **Step 5: Viết `root_helper.py`**

`disk_cleaner/root_helper.py`:

```python
#!/usr/bin/python3
"""Chạy với quyền root qua pkexec. Chỉ nhận một danh sách thao tác cố định (JSON);
chỉ dùng thư viện chuẩn, không dùng shell."""
import json
import os
import re
import subprocess
import sys

PKG_RE = re.compile(r"^linux-(?:image|headers)-[0-9][A-Za-z0-9.\-]*$")
PKG_VER_RE = re.compile(r"^linux-(?:image|headers)-(\d+\.\d+\.\d+-\d+)")
SIZE_RE = re.compile(r"^[1-9][0-9]{0,4}[MG]$")
SNAP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,39}$")
REV_RE = re.compile(r"^[0-9]{1,8}$")
RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+-\d+")


def _running_version() -> str:
    release = os.uname().release
    m = RELEASE_RE.match(release)
    return m.group(0) if m else release


def validate(op, args, running_version=None):
    """Trả về argv an toàn cho op, hoặc ném ValueError."""
    running = running_version or _running_version()
    if op == "apt-clean" and not args:
        return ["apt-get", "clean"]
    if op == "journal-vacuum" and len(args) == 1 and SIZE_RE.match(args[0]):
        return ["journalctl", f"--vacuum-size={args[0]}"]
    if op == "kernel-purge" and args:
        for pkg in args:
            if not PKG_RE.match(pkg):
                raise ValueError(f"Tên gói không hợp lệ: {pkg!r}")
            m = PKG_VER_RE.match(pkg)
            if m and m.group(1) == running:
                raise ValueError(f"Không được gỡ kernel đang chạy: {pkg}")
        return ["apt-get", "purge", "-y", *args]
    if op == "snap-remove" and len(args) == 2 and SNAP_NAME_RE.match(args[0]) and REV_RE.match(args[1]):
        return ["snap", "remove", args[0], f"--revision={args[1]}"]
    raise ValueError(f"Thao tác không được phép hoặc tham số không hợp lệ: {op} {args!r}")


def execute(ops, running_version=None):
    results = []
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C.UTF-8"}
    for op in ops:
        name = op[0] if isinstance(op, list) and op else "?"
        try:
            if not isinstance(op, list) or not op or not all(isinstance(a, str) for a in op):
                raise ValueError("Thao tác không hợp lệ")
            argv = validate(op[0], op[1:], running_version)
        except ValueError as exc:
            results.append({"op": name, "ok": False, "error": str(exc)})
            continue
        try:
            p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=1800)
            err = (p.stderr or p.stdout or "").strip()[-300:]
            results.append({"op": name, "ok": p.returncode == 0, "error": "" if p.returncode == 0 else err})
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"op": name, "ok": False, "error": str(exc)})
    return results


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: root_helper.py '<json ops>'", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print(json.dumps([{"ok": False, "error": "cần quyền root"}]))
        return 2
    try:
        ops = json.loads(argv[1])
        if not isinstance(ops, list):
            raise ValueError
    except ValueError:
        print(json.dumps([{"ok": False, "error": "JSON thao tác không hợp lệ"}]))
        return 2
    print(json.dumps(execute(ops)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 6: Viết `rootrunner.py`**

`disk_cleaner/core/rootrunner.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

from .fsutil import run

HELPER = Path(__file__).resolve().parent.parent / "root_helper.py"
DEFAULT_PREFIX = ("pkexec", "/usr/bin/python3")


class RootRunner:
    """Chạy root_helper bằng pkexec: một lần xác thực cho cả danh sách thao tác."""

    def __init__(self, helper=HELPER, prefix=DEFAULT_PREFIX):
        self.helper = Path(helper)
        self.prefix = tuple(prefix)

    def _check_helper(self) -> None:
        st = self.helper.stat()
        if st.st_mode & 0o022:
            raise RuntimeError("root_helper.py có quyền ghi cho nhóm/người khác, từ chối chạy")
        if st.st_uid not in (0, os.getuid()):
            raise RuntimeError("root_helper.py không thuộc về bạn hoặc root, từ chối chạy")

    def run(self, ops: list[list[str]]) -> list[dict]:
        if not ops:
            return []
        try:
            self._check_helper()
        except (RuntimeError, OSError) as exc:
            return [{"ok": False, "error": str(exc)} for _ in ops]
        rc, out, err = run([*self.prefix, str(self.helper), json.dumps(ops)], timeout=3600)
        if rc in (126, 127):
            return [{"ok": False, "cancelled": True, "error": "Đã huỷ hoặc không có pkexec"} for _ in ops]
        try:
            data = json.loads(out)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        msg = (err or out).strip()[-300:] or f"root helper lỗi (rc={rc})"
        return [{"ok": False, "error": msg} for _ in ops]
```

- [ ] **Step 7: Viết `syscats.py`**

`disk_cleaner/core/syscats.py`:

```python
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .fsutil import dir_size, run
from .models import Category, Item, Risk


class AptCache(Category):
    id = "apt-cache"
    title = "Cache APT"
    icon = "package-x-generic-symbolic"
    risk = Risk.SAFE
    needs_root = True
    description = "Gói .deb đã tải về (apt-get clean)"

    def __init__(self, path="/var/cache/apt/archives"):
        self.path = Path(path)

    def scan(self) -> list[Item]:
        size = dir_size(self.path)
        if size <= 0:
            return []
        return [Item(id=self.id, label=self.title, size_bytes=size, detail=self.description)]

    def root_ops(self, items) -> list[list[str]]:
        return [["apt-clean"]] if items else []


class JournalLogs(Category):
    id = "journal"
    title = "Log hệ thống (journal)"
    icon = "view-list-symbolic"
    risk = Risk.SAFE
    needs_root = True
    description = "Cắt log journald xuống 100 MB"
    TARGET = 100 * 1024 * 1024

    def available(self) -> bool:
        return shutil.which("journalctl") is not None

    def scan(self) -> list[Item]:
        rc, out, _err = run(["journalctl", "--disk-usage"])
        m = re.search(r"take up ([\d.]+)\s*([KMGT])", out)
        if rc != 0 or not m:
            return []
        usage = int(float(m.group(1)) * 1024 ** ("KMGT".index(m.group(2)) + 1))
        reclaim = usage - self.TARGET
        if reclaim <= 0:
            return []
        return [Item(id=self.id, label=self.title, size_bytes=reclaim, detail=self.description)]

    def root_ops(self, items) -> list[list[str]]:
        return [["journal-vacuum", "100M"]] if items else []


_KVER_RE = re.compile(r"^linux-(?:image|headers)-(\d+\.\d+\.\d+-\d+)")
_REL_RE = re.compile(r"^\d+\.\d+\.\d+-\d+")


def _vkey(version: str) -> tuple:
    return tuple(int(p) for p in re.split(r"[.\-]", version))


class OldKernels(Category):
    id = "kernels"
    title = "Kernel cũ"
    icon = "package-x-generic-symbolic"
    risk = Risk.RELOADABLE
    needs_root = True
    expandable = True
    description = "Gỡ kernel và header cũ; luôn giữ kernel đang chạy và mới nhất"

    def __init__(self, running_release: str | None = None):
        rel = running_release or os.uname().release
        m = _REL_RE.match(rel)
        self.running = m.group(0) if m else rel

    def available(self) -> bool:
        return shutil.which("dpkg-query") is not None

    def scan(self) -> list[Item]:
        _rc, out, _err = run(["dpkg-query", "-W", "-f=${Package}|${Installed-Size}|${db:Status-Abbrev}\\n",
                              "linux-image-[0-9]*", "linux-headers-[0-9]*"])
        groups: dict[str, dict] = {}
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) != 3 or parts[2].strip() not in ("ii", "rc"):
                continue
            m = _KVER_RE.match(parts[0])
            if not m:
                continue
            g = groups.setdefault(m.group(1), {"pkgs": [], "size": 0})
            g["pkgs"].append(parts[0])
            g["size"] += int(parts[1] or 0) * 1024
        if not groups:
            return []
        newest = max(groups, key=_vkey)
        items = []
        for ver in sorted(groups, key=_vkey):
            g = groups[ver]
            detail = "đang chạy" if ver == self.running else ("mới nhất" if ver == newest else "")
            items.append(Item(id=f"kernel:{ver}", label=f"Kernel {ver}", size_bytes=g["size"],
                              detail=detail, locked=ver in (self.running, newest),
                              data={"pkgs": g["pkgs"]}))
        return items

    def root_ops(self, items) -> list[list[str]]:
        pkgs = [p for it in items if not it.locked for p in it.data["pkgs"]]
        return [["kernel-purge", *pkgs]] if pkgs else []


class OldSnaps(Category):
    id = "snaps"
    title = "Snap bản cũ (disabled)"
    icon = "package-x-generic-symbolic"
    risk = Risk.RELOADABLE
    needs_root = True
    expandable = True
    description = "Các revision snap không còn dùng"

    def __init__(self, snaps_dir="/var/lib/snapd/snaps"):
        self.snaps_dir = Path(snaps_dir)

    def available(self) -> bool:
        return shutil.which("snap") is not None

    def scan(self) -> list[Item]:
        rc, out, _err = run(["snap", "list", "--all"])
        if rc != 0:
            return []
        items = []
        for line in out.splitlines()[1:]:
            cols = line.split()
            if len(cols) < 6 or "disabled" not in cols[-1]:
                continue
            name, rev = cols[0], cols[2]
            try:
                size = (self.snaps_dir / f"{name}_{rev}.snap").stat().st_size
            except OSError:
                size = 0
            items.append(Item(id=f"snap:{name}:{rev}", label=f"{name} (rev {rev})",
                              size_bytes=size, data={"name": name, "rev": rev}))
        return items

    def root_ops(self, items) -> list[list[str]]:
        return [["snap-remove", it.data["name"], it.data["rev"]] for it in items]
```

- [ ] **Step 8: Viết `registry.py`**

`disk_cleaner/core/registry.py`:

```python
from __future__ import annotations

from pathlib import Path

from .categories import ClaudeOldVersions, fs_categories
from .models import Category
from .syscats import AptCache, JournalLogs, OldKernels, OldSnaps
from .tools import DockerDangling, DockerUnusedImages, DockerVolumes, npm_cache, pip_cache


def build_categories(home=None) -> list[Category]:
    """Thứ tự hiển thị: từ an toàn tới rủi ro."""
    home = Path(home) if home else Path.home()
    return [
        *fs_categories(home),
        npm_cache(home),
        pip_cache(home),
        ClaudeOldVersions(home),
        AptCache(),
        JournalLogs(),
        DockerDangling(),
        OldKernels(),
        OldSnaps(),
        DockerUnusedImages(),
        DockerVolumes(),
    ]
```

- [ ] **Step 9: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 10: Kiểm tra quét thật (chỉ đọc)**

Run:
```bash
.venv/bin/python -I - <<'EOF'
import sys; sys.path.insert(0, ".")
from disk_cleaner.core.registry import build_categories
from disk_cleaner.core.scanner import scan_all
from disk_cleaner.core.fsutil import human
for o in scan_all(build_categories()):
    total = sum(i.size_bytes for i in o.items)
    print(f"{o.category.risk.value:11} {o.category.title:34} {human(total):>10}  {o.error or ''}")
EOF
```
Expected: danh sách các nhóm với dung lượng sát với `du` trên máy (Docker volume, kernel `7.0.0-34` không bị `locked`, kernel `-38` bị `locked`). Không có lỗi `Traceback`.

- [ ] **Step 11: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat(core): root helper (pkexec), nhóm apt/journal/kernel/snap và registry"
git push
```

---

### Task 5: Khung giao diện GTK và tab Dọn dẹp

**Files:**
- Create: `disk_cleaner/__main__.py`, `disk_cleaner/ui/app.py`, `disk_cleaner/ui/widgets.py`, `disk_cleaner/ui/cleanup_tab.py`, `disk_cleaner/ui/style.css`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: `registry.build_categories`, `scanner.scan_all`, `cleaner.run_cleanup`, `rootrunner.RootRunner`, `fsutil.human/free_bytes`, `models.*`.
- Produces:
  - `widgets.icon(name, size=Gtk.IconSize.MENU) -> Gtk.Image`
  - `widgets.RiskBadge(risk)`, `widgets.UsageBar(path="/")` (có `.refresh()`)
  - `widgets.CategoryCard(cat, items, on_changed, error=None)` với `.master`, `.child_checks`, `.selected_items() -> list[Item]`, `.selected_size() -> int`
  - `widgets.confirm(parent, title, body, require_text=None) -> bool`
  - `cleanup_tab.CleanupTab(on_changed=None)`
  - `app.MainWindow(app)` có `.notebook`, `.add_tab(widget, title, icon)`; `app.run() -> int`

- [ ] **Step 1: Viết test `CategoryCard` (sẽ fail)**

`tests/ui/test_widgets.py`:

```python
import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

_init = Gtk.init_check()
_ok = _init[0] if isinstance(_init, tuple) else _init
pytestmark = pytest.mark.skipif(not _ok, reason="không có display")

from disk_cleaner.core.models import Category, Item, Risk  # noqa: E402
from disk_cleaner.ui.widgets import CategoryCard  # noqa: E402


class Cat(Category):
    id, title, icon, description = "c", "C", "folder-symbolic", "mô tả"
    expandable = True

    def __init__(self, risk):
        self.risk = risk


def _items():
    return [Item("a", "a", 100), Item("b", "b", 200), Item("k", "k", 300, locked=True)]


def test_safe_default_selects_unlocked_children():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    assert [i.id for i in card.selected_items()] == ["a", "b"]
    assert card.selected_size() == 300


def test_reloadable_default_selects_nothing_and_master_selects_all_unlocked():
    card = CategoryCard(Cat(Risk.RELOADABLE), _items(), lambda: None)
    assert card.selected_items() == []
    card.master.set_active(True)
    assert [i.id for i in card.selected_items()] == ["a", "b"]
    card.master.set_active(False)
    assert card.selected_items() == []


def test_dangerous_default_selects_nothing():
    card = CategoryCard(Cat(Risk.DANGEROUS), _items(), lambda: None)
    assert card.selected_items() == []


def test_locked_item_checkbox_is_insensitive():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    locked = [chk for it, chk in card.child_checks if it.locked][0]
    assert not locked.get_sensitive() and not locked.get_active()


def test_partial_child_selection_sets_master_inconsistent():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    card.child_checks[0][1].set_active(False)
    assert card.master.get_inconsistent()
    assert [i.id for i in card.selected_items()] == ["b"]


def test_on_changed_called_when_toggled():
    calls = []
    card = CategoryCard(Cat(Risk.RELOADABLE), _items(), lambda: calls.append(1))
    card.master.set_active(True)
    assert calls


def test_error_card_is_not_selectable():
    card = CategoryCard(Cat(Risk.SAFE), [], lambda: None, error="Lỗi: boom")
    assert card.selected_items() == [] and not card.master.get_sensitive()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/ui -q`
Expected: `ImportError` (chưa có `disk_cleaner.ui.widgets`).

- [ ] **Step 3: Viết `style.css`**

`disk_cleaner/ui/style.css`:

```css
.card {
  background-color: alpha(@theme_fg_color, 0.04);
  border: 1px solid alpha(@theme_fg_color, 0.12);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 4px 12px;
}
.card-title { font-weight: 600; }
.dim { opacity: 0.65; font-size: 0.9em; }
.size-label { font-weight: 700; }
.item-row { padding: 2px 0 2px 28px; }

.risk-badge { border-radius: 999px; padding: 1px 9px; font-size: 0.85em; font-weight: 600; }
.risk-safe { background-color: alpha(#2ec27e, 0.18); color: #26a269; }
.risk-reloadable { background-color: alpha(#e5a50a, 0.22); color: #b07d00; }
.risk-dangerous { background-color: alpha(#e01b24, 0.18); color: #c01c28; }

.usage-box { padding: 10px 14px; border-bottom: 1px solid alpha(@theme_fg_color, 0.12); }
progressbar.usage-bar trough { min-height: 10px; border-radius: 6px; }
progressbar.usage-bar progress { min-height: 10px; border-radius: 6px; background-image: none; }
progressbar.usage-ok progress { background-color: #2ec27e; }
progressbar.usage-warn progress { background-color: #e5a50a; }
progressbar.usage-crit progress { background-color: #e01b24; }

.footer { padding: 8px 12px; border-top: 1px solid alpha(@theme_fg_color, 0.12); }
.error-text { color: #c01c28; }
```

- [ ] **Step 4: Viết `widgets.py`**

`disk_cleaner/ui/widgets.py`:

```python
from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..core.fsutil import human  # noqa: E402
from ..core.models import Category, Item, Risk  # noqa: E402

RISK_INFO = {
    Risk.SAFE: ("An toàn", "emblem-ok-symbolic", "risk-safe"),
    Risk.RELOADABLE: ("Tải lại được", "dialog-warning-symbolic", "risk-reloadable"),
    Risk.DANGEROUS: ("Nguy hiểm", "dialog-error-symbolic", "risk-dangerous"),
}


def icon(name: str, size=Gtk.IconSize.MENU) -> Gtk.Image:
    """Icon theo theme; dự phòng tên không symbolic rồi image-missing."""
    theme = Gtk.IconTheme.get_default()
    for candidate in (name, name.removesuffix("-symbolic"), "image-missing"):
        if theme.has_icon(candidate):
            return Gtk.Image.new_from_icon_name(candidate, size)
    return Gtk.Image.new_from_icon_name("image-missing", size)


class RiskBadge(Gtk.Box):
    def __init__(self, risk: Risk):
        super().__init__(spacing=4)
        text, icon_name, css = RISK_INFO[risk]
        ctx = self.get_style_context()
        ctx.add_class("risk-badge")
        ctx.add_class(css)
        self.pack_start(icon(icon_name), False, False, 0)
        self.pack_start(Gtk.Label(label=text), False, False, 0)
        self.set_valign(Gtk.Align.CENTER)


class UsageBar(Gtk.Box):
    def __init__(self, path: str = "/"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.path = path
        self.get_style_context().add_class("usage-box")
        top = Gtk.Box(spacing=8)
        top.pack_start(icon("drive-harddisk-symbolic", Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
        self.label = Gtk.Label(xalign=0)
        top.pack_start(self.label, True, True, 0)
        self.pack_start(top, False, False, 0)
        self.bar = Gtk.ProgressBar()
        self.bar.get_style_context().add_class("usage-bar")
        self.pack_start(self.bar, False, False, 0)
        self.refresh()

    def refresh(self) -> None:
        st = os.statvfs(self.path)
        free = st.f_bavail * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        frac = used / max(1, used + free)
        ctx = self.bar.get_style_context()
        for c in ("usage-ok", "usage-warn", "usage-crit"):
            ctx.remove_class(c)
        ctx.add_class("usage-crit" if frac > 0.9 else "usage-warn" if frac > 0.8 else "usage-ok")
        self.bar.set_fraction(frac)
        self.label.set_markup(
            f"<b>{GLib.markup_escape_text(self.path)}</b>   {human(used)} / {human(used + free)} "
            f"({frac:.0%})   ·   Trống <b>{human(free)}</b>")


class CategoryCard(Gtk.Box):
    """Một thẻ nhóm dọn: checkbox chính + (nếu expandable) danh sách mục con."""

    def __init__(self, cat: Category, items: list[Item], on_changed, error: str | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.cat, self.items, self.on_changed = cat, items, on_changed
        self.child_checks: list[tuple[Item, Gtk.CheckButton]] = []
        self._syncing = False
        self.get_style_context().add_class("card")

        selectable = error is None and any(not i.locked for i in items)
        default_on = selectable and cat.risk == Risk.SAFE

        head = Gtk.Box(spacing=10)
        self.master = Gtk.CheckButton()
        self.master.set_sensitive(selectable)
        self.master.set_active(default_on)
        self.master.connect("toggled", self._on_master)
        head.pack_start(self.master, False, False, 0)
        head.pack_start(icon(cat.icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=cat.title, xalign=0)
        title.get_style_context().add_class("card-title")
        desc = Gtk.Label(label=error or cat.description, xalign=0, wrap=True)
        desc.get_style_context().add_class("error-text" if error else "dim")
        text.pack_start(title, False, False, 0)
        text.pack_start(desc, False, False, 0)
        head.pack_start(text, True, True, 0)

        head.pack_start(RiskBadge(cat.risk), False, False, 0)
        if cat.needs_root:
            lock = icon("security-high-symbolic")
            lock.set_tooltip_text("Cần quyền root (hỏi mật khẩu khi dọn)")
            head.pack_start(lock, False, False, 0)
        size = Gtk.Label(label=human(sum(i.size_bytes for i in items)) if not error else "")
        size.get_style_context().add_class("size-label")
        head.pack_start(size, False, False, 6)

        self.revealer = None
        if cat.expandable and items:
            toggle = Gtk.ToggleButton()
            toggle.set_relief(Gtk.ReliefStyle.NONE)
            toggle.add(icon("pan-down-symbolic"))
            toggle.connect("toggled", lambda b: self.revealer.set_reveal_child(b.get_active()))
            head.pack_end(toggle, False, False, 0)
        self.pack_start(head, False, False, 0)

        if cat.expandable and items:
            self.revealer = Gtk.Revealer()
            rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for item in items:
                rows.pack_start(self._item_row(item, default_on), False, False, 0)
            self.revealer.add(rows)
            self.pack_start(self.revealer, False, False, 0)

    def _item_row(self, item: Item, default_on: bool) -> Gtk.Box:
        row = Gtk.Box(spacing=8)
        row.get_style_context().add_class("item-row")
        chk = Gtk.CheckButton(label=item.label)
        chk.set_sensitive(not item.locked)
        chk.set_active(default_on and not item.locked)
        chk.connect("toggled", self._on_child)
        self.child_checks.append((item, chk))
        row.pack_start(chk, False, False, 0)
        if item.detail:
            d = Gtk.Label(label=item.detail, xalign=0)
            d.get_style_context().add_class("dim")
            row.pack_start(d, True, True, 0)
        if item.locked:
            row.pack_start(icon("changes-prevent-symbolic"), False, False, 0)
        sz = Gtk.Label(label=human(item.size_bytes))
        sz.get_style_context().add_class("dim")
        row.pack_end(sz, False, False, 0)
        return row

    def _on_master(self, _btn) -> None:
        if self._syncing:
            return
        if self.revealer is not None:
            self._syncing = True
            self.master.set_inconsistent(False)
            for item, chk in self.child_checks:
                if not item.locked:
                    chk.set_active(self.master.get_active())
            self._syncing = False
        self.on_changed()

    def _on_child(self, _btn) -> None:
        if self._syncing:
            return
        unlocked = [chk.get_active() for item, chk in self.child_checks if not item.locked]
        self._syncing = True
        if unlocked and all(unlocked):
            self.master.set_inconsistent(False)
            self.master.set_active(True)
        elif not any(unlocked):
            self.master.set_inconsistent(False)
            self.master.set_active(False)
        else:
            self.master.set_active(False)
            self.master.set_inconsistent(True)
        self._syncing = False
        self.on_changed()

    def selected_items(self) -> list[Item]:
        if self.revealer is not None:
            return [item for item, chk in self.child_checks if chk.get_active() and not item.locked]
        return list(self.items) if self.master.get_active() else []

    def selected_size(self) -> int:
        return sum(i.size_bytes for i in self.selected_items())


def confirm(parent, title: str, body: str, require_text: str | None = None) -> bool:
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.WARNING,
                            buttons=Gtk.ButtonsType.NONE, text=title)
    dlg.format_secondary_text(body)
    dlg.add_button("Huỷ", Gtk.ResponseType.CANCEL)
    ok = dlg.add_button("Dọn", Gtk.ResponseType.OK)
    ok.get_style_context().add_class("destructive-action")
    if require_text:
        entry = Gtk.Entry()
        entry.set_placeholder_text(f"Gõ {require_text} để xác nhận")
        dlg.get_message_area().pack_start(entry, False, False, 6)
        ok.set_sensitive(False)
        entry.connect("changed", lambda e: ok.set_sensitive(e.get_text().strip() == require_text))
    dlg.show_all()
    response = dlg.run()
    dlg.destroy()
    return response == Gtk.ResponseType.OK
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/ui -q`
Expected: PASS (hoặc SKIP nếu không có display; khi đó chạy lại trong phiên đồ hoạ).

- [ ] **Step 6: Viết `cleanup_tab.py`**

`disk_cleaner/ui/cleanup_tab.py`:

```python
from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..core.cleaner import run_cleanup  # noqa: E402
from ..core.fsutil import free_bytes, human  # noqa: E402
from ..core.models import Risk  # noqa: E402
from ..core.registry import build_categories  # noqa: E402
from ..core.rootrunner import RootRunner  # noqa: E402
from ..core.scanner import scan_all  # noqa: E402
from .widgets import CategoryCard, confirm, icon  # noqa: E402


class CleanupTab(Gtk.Box):
    def __init__(self, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.categories = build_categories()
        self.on_changed = on_changed or (lambda: None)
        self.cards: list[CategoryCard] = []
        self.busy = False

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroller = Gtk.ScrolledWindow()
        scroller.add(self.list_box)
        self.pack_start(scroller, True, True, 0)

        log_exp = Gtk.Expander(label="Nhật ký")
        self.log = Gtk.TextView(editable=False, monospace=True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(90)
        log_scroll.add(self.log)
        log_exp.add(log_scroll)
        self.pack_start(log_exp, False, False, 0)

        footer = Gtk.Box(spacing=10)
        footer.get_style_context().add_class("footer")
        self.spinner = Gtk.Spinner()
        footer.pack_start(self.spinner, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        footer.pack_start(self.status, True, True, 0)
        self.selected_label = Gtk.Label()
        footer.pack_start(self.selected_label, False, False, 0)
        self.scan_btn = Gtk.Button()
        box = Gtk.Box(spacing=6)
        box.pack_start(icon("view-refresh-symbolic"), False, False, 0)
        box.pack_start(Gtk.Label(label="Quét lại"), False, False, 0)
        self.scan_btn.add(box)
        self.scan_btn.connect("clicked", lambda _b: self.rescan())
        footer.pack_start(self.scan_btn, False, False, 0)
        self.clean_btn = Gtk.Button(label="Dọn đã chọn")
        self.clean_btn.get_style_context().add_class("suggested-action")
        self.clean_btn.connect("clicked", self._on_clean)
        footer.pack_start(self.clean_btn, False, False, 0)
        self.pack_start(footer, False, False, 0)

        self.rescan()

    # ---- quét ----
    def rescan(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Đang quét…")
        for card in self.cards:
            self.list_box.remove(card)
        self.cards = []
        self._update_selected()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        for outcome in scan_all(self.categories):
            GLib.idle_add(self._add_outcome, outcome)
        GLib.idle_add(self._scan_done)

    def _add_outcome(self, outcome) -> bool:
        if not outcome.items and not outcome.error:
            return False
        card = CategoryCard(outcome.category, outcome.items, self._update_selected, outcome.error)
        self.cards.append(card)
        self.list_box.pack_start(card, False, False, 0)
        card.show_all()
        self._update_selected()
        return False

    def _scan_done(self) -> bool:
        total = sum(i.size_bytes for c in self.cards for i in c.items)
        self._set_busy(False, f"Quét xong: có thể dọn tối đa {human(total)}")
        self.on_changed()
        return False

    # ---- dọn ----
    def _selection(self):
        return [(c.cat, c.selected_items()) for c in self.cards if c.selected_items()]

    def _update_selected(self) -> None:
        total = sum(c.selected_size() for c in self.cards)
        self.selected_label.set_markup(f"Đã chọn: <b>{human(total)}</b>")
        self.clean_btn.set_sensitive(not self.busy and total > 0)

    def _on_clean(self, _btn) -> None:
        selection = self._selection()
        if not selection:
            return
        total = sum(i.size_bytes for _c, items in selection for i in items)
        lines = [f"• {cat.title}: {len(items)} mục, {human(sum(i.size_bytes for i in items))}"
                 for cat, items in selection]
        dangerous = any(cat.risk == Risk.DANGEROUS for cat, _ in selection)
        body = "\n".join(lines) + f"\n\nƯớc tính giải phóng: {human(total)}"
        if dangerous:
            body += "\n\nCó mục NGUY HIỂM (có thể mất dữ liệu vĩnh viễn)."
        if not confirm(self.get_toplevel(), "Dọn các mục đã chọn?", body, "XOA" if dangerous else None):
            return
        self._set_busy(True, "Đang dọn… (có thể hỏi mật khẩu)")
        threading.Thread(target=self._clean_worker, args=(selection, free_bytes("/")), daemon=True).start()

    def _clean_worker(self, selection, free_before: int) -> None:
        results = run_cleanup(selection, dry_run=False, root_runner=RootRunner())
        GLib.idle_add(self._clean_done, selection, results, free_before)

    def _clean_done(self, selection, results, free_before) -> bool:
        titles = {cat.id: cat.title for cat, _ in selection}
        buf = self.log.get_buffer()
        reported = 0
        for cid, res in results.items():
            reported += res.freed_bytes
            parts = [f"giải phóng {human(res.freed_bytes)}"]
            parts += [f"BỎ QUA: {s}" for s in res.skipped]
            parts += [f"LỖI: {e}" for e in res.errors]
            buf.insert(buf.get_end_iter(), f"{titles.get(cid, cid)}: " + "; ".join(parts) + "\n")
        gained = max(0, free_bytes("/") - free_before)
        errors = sum(len(r.errors) for r in results.values())
        self._set_busy(False, "")
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                message_type=Gtk.MessageType.INFO if not errors else Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.OK, text="Dọn dẹp hoàn tất")
        dlg.format_secondary_text(f"Ước tính giải phóng: {human(reported)}\nỔ trống thực tế tăng: {human(gained)}"
                                  + (f"\n{errors} lỗi, xem mục Nhật ký." if errors else ""))
        dlg.run()
        dlg.destroy()
        self.on_changed()
        self.rescan()
        return False

    def _set_busy(self, busy: bool, text: str) -> None:
        self.busy = busy
        self.status.set_text(text)
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.scan_btn.set_sensitive(not busy)
        self._update_selected()
```

- [ ] **Step 7: Viết `app.py` và `__main__.py`**

`disk_cleaner/ui/app.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .cleanup_tab import CleanupTab  # noqa: E402
from .widgets import UsageBar, icon  # noqa: E402


def load_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name("style.css")))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Disk Cleaner")
        self.set_default_size(980, 720)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)
        self.usage = UsageBar("/")
        root.pack_start(self.usage, False, False, 0)
        self.notebook = Gtk.Notebook()
        root.pack_start(self.notebook, True, True, 0)
        self.add_tab(CleanupTab(on_changed=self.usage.refresh), "Dọn dẹp", "edit-clear-all-symbolic")

    def add_tab(self, widget, title: str, icon_name: str) -> None:
        label = Gtk.Box(spacing=6)
        label.pack_start(icon(icon_name), False, False, 0)
        label.pack_start(Gtk.Label(label=title), False, False, 0)
        label.show_all()
        self.notebook.append_page(widget, label)


def run() -> int:
    load_css()
    app = Gtk.Application(application_id="vn.local.DiskCleaner")
    app.connect("activate", lambda a: MainWindow(a).show_all())
    return app.run(sys.argv)
```

`disk_cleaner/__main__.py`:

```python
import sys

from disk_cleaner.ui.app import run

if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 8: Chạy thử giao diện thật**

Run: `cd ~/disk-cleaner && python3 -m disk_cleaner` (dùng `python3` hệ thống để có sẵn `gi`).
Kiểm tra bằng mắt:
- Thanh dung lượng `/` ở trên cùng (xanh khi <80%).
- Các thẻ hiện dần khi quét; nhãn rủi ro có icon và màu; ổ khoá ở mục cần root.
- Mục "An toàn" tích sẵn; "Tải lại được" và "Nguy hiểm" không tích; kernel đang chạy bị khoá.
- Bấm **Dọn đã chọn** với một mục nhỏ (vd. Thùng rác): hiện hộp xác nhận → dọn → hộp kết quả → quét lại.
- Chọn một volume Docker: hộp xác nhận bắt gõ `XOA` (nút Dọn chỉ bật khi gõ đúng). **Không bấm xác nhận thật** nếu bạn chưa muốn xoá.
- Mục root: hộp mật khẩu `pkexec` hiện ra; bấm Huỷ → nhật ký ghi "BỎ QUA", không báo lỗi.

Expected: không có `Traceback` trong terminal.

- [ ] **Step 9: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat(ui): khung GTK, thanh dung lượng và tab Dọn dẹp"
git push
```

---

### Task 6: `sysinfo` và tab Hệ thống

**Files:**
- Create: `disk_cleaner/core/sysinfo.py`, `disk_cleaner/ui/system_tab.py`
- Modify: `disk_cleaner/ui/app.py` (thêm tab)
- Test: `tests/core/test_sysinfo.py`

**Interfaces:**
- Consumes: `fsutil.run`, `fsutil.dir_size`.
- Produces:
  - `sysinfo.parse_meminfo(text) -> dict[str, int]` (byte), `sysinfo.memory() -> dict` (`total, used, available, swap_total, swap_used`)
  - `sysinfo.cpu_model() -> str`, `sysinfo.CpuMeter().percent() -> float`
  - `sysinfo.temperature(root="/sys/class/hwmon") -> float | None`
  - `sysinfo.top_processes(n=10) -> list[tuple[int, str, int]]`
  - `sysinfo.autostart_apps(home=None) -> list[str]`, `sysinfo.partitions() -> list[dict]`
  - `system_tab.SystemTab()` (`Gtk.Box`)

- [ ] **Step 1: Viết test (sẽ fail)**

`tests/core/test_sysinfo.py`:

```python
from disk_cleaner.core import sysinfo

MEMINFO = """MemTotal:        8000000 kB
MemFree:         1000000 kB
MemAvailable:    5000000 kB
SwapTotal:       4000000 kB
SwapFree:        3000000 kB
"""


def test_parse_meminfo_converts_kb_to_bytes():
    m = sysinfo.parse_meminfo(MEMINFO)
    assert m["MemTotal"] == 8_000_000 * 1024
    assert m["SwapFree"] == 3_000_000 * 1024


def test_memory_derived_values(monkeypatch):
    monkeypatch.setattr(sysinfo, "_read", lambda p: MEMINFO)
    mem = sysinfo.memory()
    assert mem["total"] == 8_000_000 * 1024
    assert mem["used"] == 3_000_000 * 1024
    assert mem["swap_used"] == 1_000_000 * 1024


def test_temperature_takes_max_and_handles_missing(tmp_path):
    assert sysinfo.temperature(tmp_path) is None
    (tmp_path / "hwmon0").mkdir()
    (tmp_path / "hwmon0" / "temp1_input").write_text("48000\n")
    (tmp_path / "hwmon0" / "temp2_input").write_text("52500\n")
    assert sysinfo.temperature(tmp_path) == 52.5


def test_top_processes_parses_ps(monkeypatch):
    out = "  123  45678 chrome\n   77   1024 my app name\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=10: (0, out, ""))
    assert sysinfo.top_processes(5) == [(123, "chrome", 45678 * 1024), (77, "my app name", 1024 * 1024)]


def test_top_processes_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=10: (1, "", "x"))
    assert sysinfo.top_processes() == []


def test_autostart_reads_names(tmp_path):
    d = tmp_path / ".config/autostart"
    d.mkdir(parents=True)
    (d / "a.desktop").write_text("[Desktop Entry]\nName=CopyQ\nExec=copyq\n")
    (d / "b.desktop").write_text("[Desktop Entry]\nExec=noname\n")
    assert sysinfo.autostart_apps(tmp_path) == ["CopyQ", "b"]


def test_cpu_meter_bounds(monkeypatch):
    samples = iter([(100, 200), (150, 400)])
    monkeypatch.setattr(sysinfo, "_read_cpu", lambda: next(samples))
    meter = sysinfo.CpuMeter()
    assert meter.percent() == 75.0  # dt=200, di=50


def test_partitions_returns_list():
    parts = sysinfo.partitions()
    assert isinstance(parts, list) and all({"mount", "total", "used"} <= set(p) for p in parts)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_sysinfo.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Viết `sysinfo.py`**

`disk_cleaner/core/sysinfo.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from .fsutil import run


def _read(path: str) -> str:
    return Path(path).read_text()


def parse_meminfo(text: str) -> dict[str, int]:
    out = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            out[key.strip()] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
    return out


def memory() -> dict[str, int]:
    m = parse_meminfo(_read("/proc/meminfo"))
    total = m.get("MemTotal", 0)
    avail = m.get("MemAvailable", 0)
    return {"total": total, "available": avail, "used": total - avail,
            "swap_total": m.get("SwapTotal", 0),
            "swap_used": m.get("SwapTotal", 0) - m.get("SwapFree", 0)}


def cpu_model() -> str:
    try:
        for line in _read("/proc/cpuinfo").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return "Không rõ"


def _read_cpu() -> tuple[int, int]:
    fields = _read("/proc/stat").splitlines()[0].split()[1:]
    vals = [int(x) for x in fields]
    return vals[3] + vals[4], sum(vals)  # idle + iowait, tổng


class CpuMeter:
    """Phần trăm CPU đang dùng kể từ lần gọi trước."""

    def __init__(self):
        self._prev = _read_cpu()

    def percent(self) -> float:
        idle, total = _read_cpu()
        prev_idle, prev_total = self._prev
        self._prev = (idle, total)
        dt, di = total - prev_total, idle - prev_idle
        return 0.0 if dt <= 0 else max(0.0, min(100.0, 100.0 * (dt - di) / dt))


def temperature(root="/sys/class/hwmon") -> float | None:
    temps = []
    for f in Path(root).glob("hwmon*/temp*_input"):
        try:
            temps.append(int(f.read_text().strip()) / 1000)
        except (OSError, ValueError):
            pass
    return max(temps) if temps else None


def top_processes(n: int = 10) -> list[tuple[int, str, int]]:
    rc, out, _err = run(["ps", "-eo", "pid=,rss=,comm=", "--sort=-rss"], timeout=10)
    if rc != 0:
        return []
    procs = []
    for line in out.splitlines()[:n]:
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            procs.append((int(parts[0]), parts[2].strip(), int(parts[1]) * 1024))
    return procs


def autostart_apps(home=None) -> list[str]:
    d = Path(home or Path.home()) / ".config/autostart"
    names = []
    for f in sorted(d.glob("*.desktop")):
        name = f.stem
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Name="):
                    name = line.partition("=")[2].strip()
                    break
        except OSError:
            pass
        names.append(name)
    return names


def partitions() -> list[dict]:
    fstypes = {"ext4", "vfat", "ntfs", "ntfs3", "btrfs", "xfs", "fuseblk"}
    seen, out = set(), []
    try:
        lines = _read("/proc/mounts").splitlines()
    except OSError:
        return out
    for line in lines:
        dev, mount, fstype = line.split()[:3]
        if fstype not in fstypes or dev in seen:
            continue
        seen.add(dev)
        try:
            u = shutil.disk_usage(mount)
        except OSError:
            continue
        out.append({"device": dev, "mount": mount, "fstype": fstype, "total": u.total, "used": u.used})
    return out
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 5: Viết `system_tab.py`**

`disk_cleaner/ui/system_tab.py`:

```python
from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..core import sysinfo  # noqa: E402
from ..core.fsutil import dir_size, human  # noqa: E402


class SystemTab(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.cpu = sysinfo.CpuMeter()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(14)
        self.add(box)

        box.pack_start(Gtk.Label(label=f"CPU: {sysinfo.cpu_model()}", xalign=0), False, False, 0)
        self.cpu_bar, self.cpu_lbl = self._meter(box, "CPU")
        self.ram_bar, self.ram_lbl = self._meter(box, "RAM")
        self.swap_bar, self.swap_lbl = self._meter(box, "Swap")
        self.temp_lbl = Gtk.Label(xalign=0)
        box.pack_start(self.temp_lbl, False, False, 0)

        box.pack_start(self._heading("Phân vùng"), False, False, 0)
        self.parts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self.parts_box, False, False, 0)

        box.pack_start(self._heading("Top 10 tiến trình dùng RAM"), False, False, 0)
        self.proc_store = Gtk.ListStore(int, str, str)
        tree = Gtk.TreeView(model=self.proc_store)
        for i, title in enumerate(("PID", "Tên", "RAM")):
            tree.append_column(Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i))
        box.pack_start(tree, False, False, 0)

        box.pack_start(self._heading("Ứng dụng khởi động cùng máy"), False, False, 0)
        apps = sysinfo.autostart_apps()
        box.pack_start(Gtk.Label(label=", ".join(apps) if apps else "Không có", xalign=0, wrap=True),
                       False, False, 0)

        box.pack_start(self._heading("Dung lượng ứng dụng lớn (chỉ xem)"), False, False, 0)
        self.steam_lbl = Gtk.Label(label="Steam: đang tính…", xalign=0)
        box.pack_start(self.steam_lbl, False, False, 0)
        threading.Thread(target=self._steam_worker, daemon=True).start()

        self._tick()
        GLib.timeout_add_seconds(2, self._tick)

    @staticmethod
    def _heading(text: str) -> Gtk.Label:
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
        return lbl

    @staticmethod
    def _meter(box, title):
        row = Gtk.Box(spacing=10)
        row.pack_start(Gtk.Label(label=title, xalign=0, width_chars=6), False, False, 0)
        bar = Gtk.ProgressBar()
        row.pack_start(bar, True, True, 0)
        lbl = Gtk.Label(xalign=1, width_chars=26)
        row.pack_start(lbl, False, False, 0)
        box.pack_start(row, False, False, 0)
        return bar, lbl

    def _steam_worker(self) -> None:
        size = dir_size(Path.home() / ".steam")
        GLib.idle_add(self.steam_lbl.set_text, f"Steam (~/.steam): {human(size)}  ·  gỡ game trong Steam để giải phóng")

    def _tick(self) -> bool:
        if not self.get_mapped():
            return True
        pct = self.cpu.percent()
        self.cpu_bar.set_fraction(pct / 100)
        self.cpu_lbl.set_text(f"{pct:.0f}%")
        mem = sysinfo.memory()
        self.ram_bar.set_fraction(mem["used"] / max(1, mem["total"]))
        self.ram_lbl.set_text(f"{human(mem['used'])} / {human(mem['total'])}")
        self.swap_bar.set_fraction(mem["swap_used"] / max(1, mem["swap_total"]))
        self.swap_lbl.set_text(f"{human(mem['swap_used'])} / {human(mem['swap_total'])}")
        t = sysinfo.temperature()
        self.temp_lbl.set_text(f"Nhiệt độ: {t:.0f}°C" if t is not None else "Nhiệt độ: không đọc được")
        self.proc_store.clear()
        for pid, name, rss in sysinfo.top_processes(10):
            self.proc_store.append([pid, name, human(rss)])
        for child in self.parts_box.get_children():
            self.parts_box.remove(child)
        for p in sysinfo.partitions():
            row = Gtk.Box(spacing=10)
            bar = Gtk.ProgressBar()
            bar.set_fraction(p["used"] / max(1, p["total"]))
            row.pack_start(Gtk.Label(label=f"{p['mount']} ({p['fstype']})", xalign=0, width_chars=22),
                           False, False, 0)
            row.pack_start(bar, True, True, 0)
            row.pack_start(Gtk.Label(label=f"{human(p['used'])} / {human(p['total'])}", xalign=1, width_chars=22),
                           False, False, 0)
            self.parts_box.pack_start(row, False, False, 0)
        self.parts_box.show_all()
        return True
```

- [ ] **Step 6: Thêm tab vào `app.py`**

Trong `disk_cleaner/ui/app.py`, thêm import và dòng thêm tab:

```python
from .system_tab import SystemTab  # noqa: E402
```

Trong `MainWindow.__init__`, sau dòng thêm tab "Dọn dẹp":

```python
        self.add_tab(SystemTab(), "Hệ thống", "computer-symbolic")
```

- [ ] **Step 7: Chạy thử giao diện**

Run: `cd ~/disk-cleaner && python3 -m disk_cleaner` rồi mở tab **Hệ thống**.
Expected: CPU/RAM/Swap thay đổi mỗi 2 giây khi tab đang mở, có nhiệt độ, danh sách phân vùng (`/`, `/boot/efi`, ổ NTFS nếu đã mount), top 10 tiến trình, danh sách khởi động, dòng Steam hiện dung lượng sau vài giây. Chuyển sang tab khác thì ngừng cập nhật.

- [ ] **Step 8: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat: tab Hệ thống (RAM, CPU, nhiệt độ, tiến trình, phân vùng)"
git push
```

---

### Task 7: `bigfiles`, nhóm venv/node_modules và tab File lớn

**Files:**
- Create: `disk_cleaner/core/bigfiles.py`, `disk_cleaner/ui/bigfiles_tab.py`
- Modify: `disk_cleaner/core/registry.py` (thêm `BigDirsCategory`), `disk_cleaner/ui/app.py` (thêm tab)
- Test: `tests/core/test_bigfiles.py`; cập nhật `tests/core/test_registry.py`

**Interfaces:**
- Consumes: `safety.*`, `fsutil.*`, `models.*`.
- Produces:
  - `bigfiles.Entry(path, size, kind, atime, deletable)` (dataclass; `kind` là `"file"` hoặc `"dir"`)
  - `bigfiles.find_big_files(root, min_bytes=200*1024*1024, home=None) -> list[Entry]` (sắp giảm dần theo size)
  - `bigfiles.find_big_dirs(root, home=None, skip_hidden=True, min_bytes=0) -> list[Entry]`
  - `bigfiles.BigDirsCategory(home)` (`Category`, id `big-dirs`)
  - `bigfiles_tab.BigFilesTab()`

- [ ] **Step 1: Viết test (sẽ fail)**

`tests/core/test_bigfiles.py`:

```python
from pathlib import Path

from disk_cleaner.core import bigfiles


def _tree(tmp_path):
    home = tmp_path / "home"
    nm = home / "Màn hình nền" / "dự án 1" / "node_modules"
    nm.mkdir(parents=True)
    (nm / "pkg").mkdir()
    (nm / "pkg" / "big.bin").write_bytes(b"x" * 20000)
    (nm / "pkg" / "node_modules").mkdir()          # lồng nhau: không đi sâu thêm
    (home / "dự án 1" / "venv").mkdir(parents=True)
    (home / "dự án 1" / "venv" / "lib.so").write_bytes(b"x" * 20000)
    (home / "dự án 1" / "requirements.txt").write_text("numpy")
    (home / ".config" / "app" / "node_modules").mkdir(parents=True)
    (home / ".config" / "app" / "node_modules" / "x").write_bytes(b"x" * 20000)
    (home / "video lớn.mkv").write_bytes(b"x" * 30000)
    (home / "nhỏ.txt").write_text("hi")
    return home


def test_find_big_dirs_unicode_names_and_no_nested_descend(tmp_path):
    home = _tree(tmp_path)
    found = bigfiles.find_big_dirs(home, home=home)
    paths = {str(e.path.relative_to(home)) for e in found}
    assert paths == {"Màn hình nền/dự án 1/node_modules", "dự án 1/venv"}
    assert all(e.kind == "dir" and e.deletable for e in found)


def test_find_big_dirs_skips_hidden_by_default_but_can_include(tmp_path):
    home = _tree(tmp_path)
    with_hidden = bigfiles.find_big_dirs(home, home=home, skip_hidden=False)
    hidden = [e for e in with_hidden if ".config" in e.path.parts]
    assert hidden and not hidden[0].deletable


def test_find_big_dirs_min_bytes(tmp_path):
    home = _tree(tmp_path)
    assert bigfiles.find_big_dirs(home, home=home, min_bytes=10**9) == []


def test_find_big_files_threshold_and_order(tmp_path):
    home = _tree(tmp_path)
    found = bigfiles.find_big_files(home, min_bytes=10000, home=home)
    names = [e.path.name for e in found]
    assert "nhỏ.txt" not in names
    assert names[0] == "video lớn.mkv" or found[0].size >= found[-1].size
    cfg = [e for e in found if ".config" in e.path.parts]
    assert cfg and not cfg[0].deletable
    video = [e for e in found if e.path.name == "video lớn.mkv"][0]
    assert video.deletable and video.kind == "file"


def test_big_dirs_category_scan_and_clean(tmp_path):
    home = _tree(tmp_path)
    cat = bigfiles.BigDirsCategory(home)
    items = cat.scan()
    assert {Path(i.path).name for i in items} == {"node_modules", "venv"}
    assert cat.expandable
    venv = [i for i in items if Path(i.path).name == "venv"]
    res = cat.clean(venv, dry_run=False)
    assert res.errors == [] and not (home / "dự án 1" / "venv").exists()
    assert (home / "dự án 1" / "requirements.txt").exists()


def test_big_dirs_category_never_deletes_project_root(tmp_path):
    home = _tree(tmp_path)
    cat = bigfiles.BigDirsCategory(home)
    from disk_cleaner.core.models import Item
    bad = Item("x", "x", 1, path=str(home / "dự án 1"))
    res = cat.clean([bad], dry_run=False)
    assert res.errors and (home / "dự án 1").exists()
```

Thêm vào `tests/core/test_registry.py` (cuối hàm assert):

```python
    assert "big-dirs" in set(ids)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_bigfiles.py tests/core/test_registry.py -q`
Expected: `ImportError` / assert fail.

- [ ] **Step 3: Viết `bigfiles.py`**

`disk_cleaner/core/bigfiles.py`:

```python
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
            if d in safety.BUILD_NAMES and not p.is_symlink():
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
```

- [ ] **Step 4: Cập nhật `registry.py`**

Thêm import và đưa `BigDirsCategory` vào cuối danh sách:

```python
from .bigfiles import BigDirsCategory
```

```python
        DockerVolumes(),
        BigDirsCategory(home),
    ]
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 6: Viết `bigfiles_tab.py`**

`disk_cleaner/ui/bigfiles_tab.py`:

```python
from __future__ import annotations

import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from ..core import bigfiles  # noqa: E402
from ..core.fsutil import human, remove_path  # noqa: E402
from ..core.logging_ import record  # noqa: E402
from ..core.models import CleanResult  # noqa: E402
from .widgets import confirm, icon  # noqa: E402


class BigFilesTab(Gtk.Box):
    def __init__(self, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.home = Path.home()
        self.on_changed = on_changed or (lambda: None)
        self.busy = False

        info = Gtk.Label(label="File lớn (≥ 200 MB) và thư mục venv/node_modules/build trong thư mục của bạn. "
                               "Mục xám là dữ liệu ứng dụng, chỉ xem.", xalign=0, wrap=True)
        info.get_style_context().add_class("dim")
        info.set_margin_start(12)
        info.set_margin_top(8)
        self.pack_start(info, False, False, 0)

        # selected, path, size_text, kind, last_used, deletable, size_bytes
        self.store = Gtk.ListStore(bool, str, str, str, str, bool, int)
        tree = Gtk.TreeView(model=self.store)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_toggled)
        tree.append_column(Gtk.TreeViewColumn("", toggle, active=0, sensitive=5, activatable=5))
        for idx, title in ((1, "Đường dẫn"), (2, "Dung lượng"), (3, "Loại"), (4, "Dùng gần nhất")):
            renderer = Gtk.CellRendererText()
            if idx == 1:
                renderer.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
            col = Gtk.TreeViewColumn(title, renderer, text=idx, sensitive=5)
            col.set_resizable(True)
            col.set_expand(idx == 1)
            col.set_sort_column_id(6 if idx == 2 else idx)
            tree.append_column(col)
        scroller = Gtk.ScrolledWindow()
        scroller.add(tree)
        self.pack_start(scroller, True, True, 0)

        footer = Gtk.Box(spacing=10)
        footer.get_style_context().add_class("footer")
        self.spinner = Gtk.Spinner()
        footer.pack_start(self.spinner, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        footer.pack_start(self.status, True, True, 0)
        self.scan_btn = Gtk.Button(label="Quét")
        self.scan_btn.connect("clicked", lambda _b: self.rescan())
        footer.pack_start(self.scan_btn, False, False, 0)
        self.del_btn = Gtk.Button()
        box = Gtk.Box(spacing=6)
        box.pack_start(icon("edit-delete-symbolic"), False, False, 0)
        box.pack_start(Gtk.Label(label="Xoá đã chọn"), False, False, 0)
        self.del_btn.add(box)
        self.del_btn.get_style_context().add_class("destructive-action")
        self.del_btn.connect("clicked", self._on_delete)
        footer.pack_start(self.del_btn, False, False, 0)
        self.pack_start(footer, False, False, 0)

        self.rescan()

    def rescan(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Đang quét thư mục của bạn…")
        self.store.clear()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        entries = bigfiles.find_big_files(self.home, home=self.home)
        entries += bigfiles.find_big_dirs(self.home, home=self.home)
        entries.sort(key=lambda e: -e.size)
        GLib.idle_add(self._fill, entries)

    def _fill(self, entries) -> bool:
        for e in entries:
            used = time.strftime("%Y-%m-%d", time.localtime(e.atime)) if e.atime else "?"
            self.store.append([False, str(e.path), human(e.size), "Thư mục" if e.kind == "dir" else "File",
                               used, e.deletable, e.size])
        self._set_busy(False, f"{len(entries)} mục, tổng {human(sum(e.size for e in entries))}")
        return False

    def _on_toggled(self, _renderer, path) -> None:
        self.store[path][0] = not self.store[path][0]

    def _on_delete(self, _btn) -> None:
        rows = [(r[1], r[6]) for r in self.store if r[0] and r[5]]
        if not rows:
            return
        total = sum(s for _p, s in rows)
        shown = "\n".join(f"• {p}  ({human(s)})" for p, s in rows[:12])
        more = f"\n…và {len(rows) - 12} mục khác" if len(rows) > 12 else ""
        if not confirm(self.get_toplevel(), f"Xoá {len(rows)} mục đã chọn?",
                       f"{shown}{more}\n\nGiải phóng ~{human(total)}. Việc này không thể hoàn tác."):
            return
        self._set_busy(True, "Đang xoá…")
        threading.Thread(target=self._delete_worker, args=(rows,), daemon=True).start()

    def _delete_worker(self, rows) -> None:
        result = CleanResult()
        for path, _size in rows:
            try:
                result.freed_bytes += remove_path(path, [self.home], self.home)
            except Exception as exc:
                result.errors.append(f"{path}: {exc}")
        record("bigfiles-tab", result, dry_run=False)
        GLib.idle_add(self._delete_done, result)

    def _delete_done(self, result) -> bool:
        self._set_busy(False, f"Đã giải phóng {human(result.freed_bytes)}"
                              + (f", {len(result.errors)} lỗi" if result.errors else ""))
        self.on_changed()
        self.busy = False
        self.rescan()
        return False

    def _set_busy(self, busy: bool, text: str) -> None:
        self.busy = busy
        self.status.set_text(text)
        (self.spinner.start if busy else self.spinner.stop)()
        self.scan_btn.set_sensitive(not busy)
        self.del_btn.set_sensitive(not busy)
```

- [ ] **Step 7: Thêm tab vào `app.py`**

Thêm import:

```python
from .bigfiles_tab import BigFilesTab  # noqa: E402
```

Trong `MainWindow.__init__`, sau tab Dọn dẹp (trước tab Hệ thống):

```python
        self.add_tab(BigFilesTab(on_changed=self.usage.refresh), "File lớn", "system-search-symbolic")
```

- [ ] **Step 8: Chạy thử giao diện**

Run: `cd ~/disk-cleaner && python3 -m disk_cleaner` rồi mở tab **File lớn**.
Expected: sau vài giây hiện danh sách file ≥200 MB và các thư mục `venv`/`node_modules`; dòng thuộc thư mục ẩn (`~/.config`, `~/.steam`, `~/.vscode`…) bị xám, không tích được; sắp xếp được theo dung lượng. Tích một thư mục thử (vd. `venv` của project cũ nếu có) → **Xoá đã chọn** → hộp xác nhận liệt kê đúng đường dẫn. **Không xác nhận nếu chưa muốn xoá thật.**

- [ ] **Step 9: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat: tìm file lớn, nhóm venv/node_modules và tab File lớn"
git push
```

---

### Task 8: `diskmap` (treemap) và tab Khám phá đĩa

**Files:**
- Create: `disk_cleaner/core/diskmap.py`, `disk_cleaner/ui/diskmap_tab.py`
- Modify: `disk_cleaner/ui/app.py` (thêm tab)
- Test: `tests/core/test_diskmap.py`

**Interfaces:**
- Consumes: `fsutil.dir_size`, `fsutil.human`.
- Produces:
  - `diskmap.DirEntry(name, path, size, is_dir)`
  - `diskmap.list_children(path) -> list[DirEntry]` (giảm dần theo size, bỏ symlink, bỏ qua thư mục không đọc được)
  - `diskmap.squarify(sizes, x, y, w, h) -> list[tuple[float, float, float, float]]` (cùng thứ tự `sizes`)
  - `diskmap_tab.DiskMapTab()`

- [ ] **Step 1: Viết test (sẽ fail)**

`tests/core/test_diskmap.py`:

```python
import math

from disk_cleaner.core import diskmap


def test_squarify_fills_area_without_overlap_or_overflow():
    sizes = [60, 30, 20, 10, 5, 5]
    rects = diskmap.squarify(sizes, 0, 0, 400, 300)
    assert len(rects) == len(sizes)
    assert math.isclose(sum(w * h for _x, _y, w, h in rects), 400 * 300, rel_tol=1e-6)
    for x, y, w, h in rects:
        assert x >= -1e-6 and y >= -1e-6 and x + w <= 400 + 1e-6 and y + h <= 300 + 1e-6
    for i, (x1, y1, w1, h1) in enumerate(rects):
        for x2, y2, w2, h2 in rects[i + 1:]:
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert not (ox > 1e-6 and oy > 1e-6)


def test_squarify_area_proportional_to_size():
    rects = diskmap.squarify([75, 25], 0, 0, 100, 100)
    areas = [w * h for _x, _y, w, h in rects]
    assert math.isclose(areas[0] / areas[1], 3.0, rel_tol=1e-6)


def test_squarify_edge_cases():
    assert diskmap.squarify([], 0, 0, 10, 10) == []
    assert len(diskmap.squarify([0, 0], 0, 0, 10, 10)) == 2
    assert len(diskmap.squarify([5, 0, 3], 0, 0, 10, 10)) == 3
    assert diskmap.squarify([5], 0, 0, 0, 0) == [(0, 0, 0.0, 0.0)]


def test_list_children_sorted_skips_symlinks_and_unreadable(tmp_path):
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "f").write_bytes(b"x" * 20000)
    (tmp_path / "small.txt").write_bytes(b"x" * 100)
    (tmp_path / "Màn hình nền").mkdir()
    (tmp_path / "Màn hình nền" / "a").write_bytes(b"x" * 5000)
    (tmp_path / "link").symlink_to(tmp_path / "big")
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "f").write_bytes(b"x" * 9000)
    locked.chmod(0)
    try:
        entries = diskmap.list_children(tmp_path)
    finally:
        locked.chmod(0o755)
    names = [e.name for e in entries]
    assert "link" not in names
    assert names[0] == "big" and entries[0].is_dir
    assert "Màn hình nền" in names and "small.txt" in names
    assert [e.size for e in entries] == sorted((e.size for e in entries), reverse=True)


def test_list_children_missing_path_returns_empty(tmp_path):
    assert diskmap.list_children(tmp_path / "nope") == []
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/core/test_diskmap.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Viết `diskmap.py`**

`disk_cleaner/core/diskmap.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .fsutil import dir_size


@dataclass
class DirEntry:
    name: str
    path: Path
    size: int
    is_dir: bool


def list_children(path) -> list[DirEntry]:
    """Các mục con trực tiếp của path kèm dung lượng, giảm dần. Bỏ symlink."""
    out: list[DirEntry] = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    is_dir = e.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                out.append(DirEntry(e.name, Path(e.path), dir_size(e.path), is_dir))
    except OSError:
        return []
    return sorted(out, key=lambda d: -d.size)


def _worst(row: list[float], side: float) -> float:
    s = sum(row)
    return max(max(side * side * r / (s * s), s * s / (side * side * r)) for r in row)


def squarify(sizes: list[float], x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Treemap 'squarified': trả về (x, y, w, h) cho mỗi size, giữ nguyên thứ tự.
    `sizes` nên được sắp giảm dần."""
    n = len(sizes)
    if n == 0:
        return []
    total = float(sum(sizes))
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, 0.0, 0.0)] * n
    areas = [max(s * w * h / total, 1e-12) for s in sizes]
    rects: list[tuple[float, float, float, float]] = []
    i = 0
    while i < n:
        side = min(w, h)
        row = [areas[i]]
        j = i + 1
        while j < n and _worst(row + [areas[j]], side) <= _worst(row, side):
            row.append(areas[j])
            j += 1
        s = sum(row)
        if w >= h:                       # cột bên trái, rộng s/h
            cw = s / h
            cy = y
            for a in row:
                ch = a / cw
                rects.append((x, cy, cw, ch))
                cy += ch
            x += cw
            w -= cw
        else:                            # hàng phía trên, cao s/w
            rh = s / w
            cx = x
            for a in row:
                cw2 = a / rh
                rects.append((cx, y, cw2, rh))
                cx += cw2
            y += rh
            h -= rh
        i = j
    return rects
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/core -q`
Expected: tất cả PASS.

- [ ] **Step 5: Viết `diskmap_tab.py`**

`disk_cleaner/ui/diskmap_tab.py`:

```python
from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from ..core.diskmap import DirEntry, list_children, squarify  # noqa: E402
from ..core.fsutil import human  # noqa: E402
from .widgets import icon  # noqa: E402

PALETTE = [(0.35, 0.55, 0.85), (0.45, 0.70, 0.55), (0.85, 0.60, 0.35), (0.65, 0.50, 0.80),
           (0.80, 0.45, 0.50), (0.40, 0.65, 0.75), (0.75, 0.70, 0.35)]
MIN_SHARE = 0.004   # mục nhỏ hơn 0.4% tổng được gộp vào ô "(nhỏ khác)"


class DiskMapTab(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.current = Path.home()
        self.entries: list[DirEntry] = []
        self.rects: list[tuple[float, float, float, float, DirEntry | None]] = []
        self.loading = False

        bar = Gtk.Box(spacing=6)
        bar.set_margin_start(12)
        bar.set_margin_top(8)
        self.up_btn = Gtk.Button()
        self.up_btn.add(icon("go-up-symbolic"))
        self.up_btn.set_tooltip_text("Lên thư mục cha")
        self.up_btn.connect("clicked", lambda _b: self.navigate(self.current.parent))
        bar.pack_start(self.up_btn, False, False, 0)
        home_btn = Gtk.Button(label="Home")
        home_btn.connect("clicked", lambda _b: self.navigate(Path.home()))
        bar.pack_start(home_btn, False, False, 0)
        root_btn = Gtk.Button(label="/")
        root_btn.connect("clicked", lambda _b: self.navigate(Path("/")))
        bar.pack_start(root_btn, False, False, 0)
        self.path_lbl = Gtk.Label(xalign=0)
        bar.pack_start(self.path_lbl, True, True, 6)
        self.spinner = Gtk.Spinner()
        bar.pack_end(self.spinner, False, False, 12)
        self.pack_start(bar, False, False, 0)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(400, 300)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.area.connect("draw", self._on_draw)
        self.area.connect("button-press-event", self._on_click)
        self.area.connect("motion-notify-event", self._on_motion)
        self.pack_start(self.area, True, True, 0)

        hint = Gtk.Label(label="Nhấp vào thư mục để đi sâu · chuột phải để mở trong trình quản lý file · "
                               "tab này chỉ xem, không xoá", xalign=0)
        hint.get_style_context().add_class("dim")
        hint.set_margin_start(12)
        hint.set_margin_bottom(8)
        self.pack_start(hint, False, False, 0)

        self.navigate(self.current)

    def navigate(self, path: Path) -> None:
        if self.loading:
            return
        self.current = Path(path)
        self.loading = True
        self.spinner.start()
        self.path_lbl.set_text(f"{self.current}  — đang quét…")
        threading.Thread(target=self._worker, args=(self.current,), daemon=True).start()

    def _worker(self, path: Path) -> None:
        entries = list_children(path)
        GLib.idle_add(self._loaded, path, entries)

    def _loaded(self, path, entries) -> bool:
        self.loading = False
        self.spinner.stop()
        self.entries = entries
        self.path_lbl.set_text(f"{path}   ·   {human(sum(e.size for e in entries))}")
        self.up_btn.set_sensitive(path != path.parent)
        self.area.queue_draw()
        return False

    def _layout(self, w: float, h: float):
        total = sum(e.size for e in self.entries)
        big = [e for e in self.entries if total and e.size / total >= MIN_SHARE]
        rest = total - sum(e.size for e in big)
        sizes = [e.size for e in big] + ([rest] if rest > 0 else [])
        rects = squarify(sizes, 4, 4, w - 8, h - 8)
        items: list[DirEntry | None] = list(big) + ([None] if rest > 0 else [])
        self.rects = [(x, y, rw, rh, e) for (x, y, rw, rh), e in zip(rects, items)]

    def _on_draw(self, widget, cr) -> bool:
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        self._layout(w, h)
        for idx, (x, y, rw, rh, entry) in enumerate(self.rects):
            r, g, b = PALETTE[idx % len(PALETTE)] if entry else (0.6, 0.6, 0.6)
            cr.rectangle(x, y, max(0, rw - 2), max(0, rh - 2))
            cr.set_source_rgb(r, g, b)
            cr.fill()
            if rw > 70 and rh > 34:
                name = entry.name if entry else "(nhỏ khác)"
                size = human(entry.size) if entry else ""
                layout = widget.create_pango_layout(f"{name}\n{size}")
                layout.set_width(int((rw - 10) * Pango.SCALE))
                layout.set_ellipsize(Pango.EllipsizeMode.END)
                layout.set_height(int((rh - 8) * Pango.SCALE))
                cr.set_source_rgb(1, 1, 1)
                cr.move_to(x + 5, y + 4)
                PangoCairo.show_layout(cr, layout)
        return False

    def _entry_at(self, px: float, py: float) -> DirEntry | None:
        for x, y, rw, rh, entry in self.rects:
            if x <= px <= x + rw and y <= py <= y + rh:
                return entry
        return None

    def _on_motion(self, widget, ev) -> bool:
        e = self._entry_at(ev.x, ev.y)
        widget.set_tooltip_text(f"{e.path}\n{human(e.size)}" if e else None)
        return False

    def _on_click(self, _widget, ev) -> bool:
        e = self._entry_at(ev.x, ev.y)
        if e is None:
            return False
        if ev.button == 1 and e.is_dir:
            self.navigate(e.path)
        elif ev.button == 3:
            opener = shutil.which("thunar") or shutil.which("xdg-open")
            if opener:
                target = e.path if e.is_dir else e.path.parent
                subprocess.Popen([opener, str(target)])
        return True
```

- [ ] **Step 6: Thêm tab vào `app.py`**

Thêm import:

```python
from .diskmap_tab import DiskMapTab  # noqa: E402
```

Trong `MainWindow.__init__`, chèn **ngay sau** tab Dọn dẹp (thứ tự cuối cùng: Dọn dẹp, Khám phá đĩa, File lớn, Hệ thống):

```python
        self.add_tab(DiskMapTab(), "Khám phá đĩa", "drive-harddisk-symbolic")
```

- [ ] **Step 7: Chạy thử giao diện**

Run: `cd ~/disk-cleaner && python3 -m disk_cleaner` rồi mở tab **Khám phá đĩa**.
Expected: treemap của thư mục Home hiện sau vài giây; ô lớn là thư mục nặng (vd. `.steam`, `.config`); nhấp ô thư mục để đi sâu; nút mũi tên lên, `Home`, `/` hoạt động; rê chuột hiện tooltip đường dẫn + dung lượng; chuột phải mở Thunar. Đổi kích thước cửa sổ thì treemap vẽ lại đúng.

- [ ] **Step 8: Commit và push**

```bash
git add disk_cleaner tests
git commit -m "feat: tab Khám phá đĩa (treemap Cairo)"
git push
```

---

### Task 9: Menu ứng dụng, README và kiểm tra cuối

**Files:**
- Create: `disk-cleaner.desktop.in`, `README.md`
- Modify: `docs/superpowers/specs/2026-10-26-disk-cleaner-design.md` (cập nhật cấu trúc cho khớp thực tế)

**Interfaces:**
- Consumes: toàn bộ ứng dụng.

- [ ] **Step 1: Tạo `disk-cleaner.desktop.in`**

```ini
[Desktop Entry]
Type=Application
Name=Disk Cleaner
Comment=Dọn dẹp và tối ưu dung lượng ổ đĩa
Exec=python3 -m disk_cleaner
Path=@DIR@
Icon=drive-harddisk
Terminal=false
Categories=System;Utility;
```

- [ ] **Step 2: Tạo `README.md`**

````markdown
# Disk Cleaner

Ứng dụng GTK3 để xem và dọn dung lượng ổ đĩa trên Ubuntu/XFCE: dọn theo nhóm có mức rủi ro,
khám phá đĩa (treemap), tìm file lớn / venv / node_modules bỏ quên, xem tổng quan hệ thống.

## Chạy

```bash
python3 -m disk_cleaner
```

Yêu cầu: Python 3.12 và PyGObject (GTK 3) — Ubuntu desktop có sẵn.
Thao tác cần root (APT, journal, kernel cũ, snap) sẽ hiện hộp mật khẩu của `pkexec` khi bấm **Dọn**.

## Cài vào menu ứng dụng

```bash
sed "s|@DIR@|$PWD|" disk-cleaner.desktop.in > ~/.local/share/applications/disk-cleaner.desktop
```

## An toàn

- Mọi thao tác xoá đi qua `disk_cleaner/core/safety.py` (danh sách cấm, kiểm tra symlink, chặn xoá nguyên thư mục dự án).
- Mục **Nguy hiểm** (Docker volume) mặc định không tích và phải gõ `XOA` để xác nhận.
- Thao tác root chỉ nhận danh sách cố định trong `disk_cleaner/root_helper.py`.
- Log: `~/.local/state/disk-cleaner/cleanup.log`.

## Kiểm thử

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
````

- [ ] **Step 3: Chạy toàn bộ test**

Run: `.venv/bin/python -m pytest -q`
Expected: tất cả PASS (test giao diện SKIP nếu không có display).

- [ ] **Step 4: Đối chiếu số liệu quét với công cụ thật (chỉ đọc)**

Run:
```bash
.venv/bin/python -I - <<'EOF'
import sys; sys.path.insert(0, ".")
from disk_cleaner.core.registry import build_categories
from disk_cleaner.core.scanner import scan_all
from disk_cleaner.core.fsutil import human
total = 0
for o in scan_all(build_categories()):
    s = sum(i.size_bytes for i in o.items); total += s
    print(f"{o.category.risk.value:11} {o.category.title:36} {human(s):>10} {o.error or ''}")
print("TỔNG có thể dọn:", human(total))
EOF
du -sh ~/.npm ~/.cache/pip ~/.local/share/Trash 2>/dev/null; docker system df
```
Expected: số của `Cache npm`, `Cache pip`, `Thùng rác` xấp xỉ `du`; Docker volume/image xấp xỉ `docker system df`; không có dòng lỗi.

- [ ] **Step 5: Dọn thử một mục nhỏ, an toàn (có chủ ý)**

Mở app, tích **chỉ** mục "Thùng rác" (nếu còn dữ liệu) hoặc "Cache pip", bấm **Dọn đã chọn**.
Expected: hộp xác nhận → hộp kết quả; `~/.local/state/disk-cleaner/cleanup.log` có thêm dòng `RUN`; quét lại thì mục đó biến mất hoặc giảm mạnh; thư mục `~/Documents`, `~/vscode` còn nguyên.

Kiểm tra: `tail -3 ~/.local/state/disk-cleaner/cleanup.log && ls ~/vscode`.

- [ ] **Step 6: Cập nhật spec cho khớp thực tế**

Trong `docs/superpowers/specs/2026-10-26-disk-cleaner-design.md`, mục **3. Cấu trúc**: thay `categories.py` bằng `categories.py`, `tools.py`, `syscats.py`, `registry.py`, `models.py`, `fsutil.py`, `rootrunner.py`; bỏ thư mục `ui/icons/` và dòng "kèm SVG dự phòng" (thay bằng "chuỗi icon dự phòng trong `widgets.icon()`"); mục **7** ghi rõ `root_helper.py` nhận một chuỗi JSON danh sách thao tác.

- [ ] **Step 7: Commit và push**

```bash
git add README.md disk-cleaner.desktop.in docs
git commit -m "docs: README, mục menu ứng dụng và cập nhật spec theo triển khai"
git push
```

---

## Self-Review

**Spec coverage**
- §1 mục tiêu/thành công → Task 5 (hộp kết quả đối chiếu ổ trống thực), Task 9 Step 4–5.
- §3 cấu trúc → File Structure + Task 1–9 (tinh chỉnh nêu ở đầu plan, spec được cập nhật ở Task 9 Step 6).
- §4 mô hình dữ liệu → Task 1 (`models.py`).
- §5 các nhóm dọn: npm/pip/puppeteer/trash/thumbnails/Chrome/VS Code/Claude cũ → Task 2–3; APT/journal/kernel/snap → Task 4; Docker image dangling/không dùng/volume → Task 3; venv/node_modules → Task 7; Steam chỉ xem → Task 6.
- §6 an toàn → Task 1 (`safety.py`), Task 2 (cleaner bắt `SafetyError`), Task 5 (`confirm` với `XOA`), kernel `locked` → Task 4.
- §7 root → Task 4 (`root_helper.py`, `RootRunner`: regex chặt, từ chối kernel đang chạy, không `shell=True`, kiểm tra quyền file helper).
- §8 giao diện → Task 5 (thanh dung lượng, thẻ, badge, icon, xác nhận), Task 6–8 (3 tab còn lại).
- §9 lỗi/log → Task 2 (`logging_.py`, cô lập lỗi từng nhóm), Task 4 (huỷ pkexec).
- §10 kiểm thử → test ở từng task; kiểm tra thật ở Task 4 Step 10, Task 9 Step 4–5.
- §11 thứ tự triển khai → khớp thứ tự task (Hệ thống trước File lớn rồi Khám phá đĩa).

**Placeholder scan:** không còn "TBD/TODO"; mọi bước code đều có nội dung đầy đủ.

**Type consistency:** `Item.data`, `Category.root_ops`, `RootRunner.run -> list[dict]` (khoá `ok/error/cancelled`), `run_cleanup(selection, dry_run, root_runner, log_path)`, `ScanOutcome(category, items, error)`, `remove_path/remove_contents(..., home, check_project)` được dùng nhất quán giữa các task; `CategoryCard.selected_items()` đúng kiểu `run_cleanup` nhận.

**Review Focus:** 5 mục đều có test ở task sở hữu code (Task 1: symlink + thư mục không đọc được; Task 2: pkexec huỷ; Task 3: Docker daemon tắt; Task 4: chỉ một kernel).
