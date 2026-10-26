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
        self.rescan()
        return False

    def _set_busy(self, busy: bool, text: str) -> None:
        self.busy = busy
        self.status.set_text(text)
        (self.spinner.start if busy else self.spinner.stop)()
        self.scan_btn.set_sensitive(not busy)
        self.del_btn.set_sensitive(not busy)
