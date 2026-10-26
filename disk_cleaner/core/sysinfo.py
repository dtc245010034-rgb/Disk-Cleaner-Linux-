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
