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
