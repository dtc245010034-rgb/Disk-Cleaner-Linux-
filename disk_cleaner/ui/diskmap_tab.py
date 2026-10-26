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
