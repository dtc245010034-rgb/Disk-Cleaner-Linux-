from __future__ import annotations

import grp
import json
import os
import pwd
from pathlib import Path

from .fsutil import run

HELPER = Path(__file__).resolve().parent.parent / "root_helper.py"
DEFAULT_PREFIX = ("pkexec", "/usr/bin/python3")


def _group_is_private(gid: int) -> bool:
    """True nếu gid là nhóm riêng của chính người dùng (nhóm chính, không có thành viên khác),
    như `dog:dog` trên Ubuntu. Quyền ghi của nhóm đó tương đương quyền ghi của chủ file."""
    if gid != os.getgid():
        return False
    try:
        members = grp.getgrgid(gid).gr_mem
    except KeyError:
        return False
    me = pwd.getpwuid(os.getuid()).pw_name
    return all(m == me for m in members)


class RootRunner:
    """Chạy root_helper bằng pkexec: một lần xác thực cho cả danh sách thao tác."""

    def __init__(self, helper=HELPER, prefix=DEFAULT_PREFIX):
        self.helper = Path(helper)
        self.prefix = tuple(prefix)

    def _check_helper(self) -> None:
        st = self.helper.stat()
        if st.st_mode & 0o002:
            raise RuntimeError("root_helper.py có quyền ghi cho người khác, từ chối chạy")
        if st.st_mode & 0o020 and not _group_is_private(st.st_gid):
            raise RuntimeError("root_helper.py có quyền ghi cho một nhóm dùng chung, từ chối chạy")
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
