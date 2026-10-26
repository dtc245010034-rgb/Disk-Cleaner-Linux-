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
        seen: set[str] = set()
        unique = []
        for g in groups:  # ~/snap/code/current là symlink tới revision: chỉ giữ một đường dẫn thật
            real = os.path.realpath(g)
            if g.is_dir() and real not in seen:
                seen.add(real)
                unique.append(g)
        return unique

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
