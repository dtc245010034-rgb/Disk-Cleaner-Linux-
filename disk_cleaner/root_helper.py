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
