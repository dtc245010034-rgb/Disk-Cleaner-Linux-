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
