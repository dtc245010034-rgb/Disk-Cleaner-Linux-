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
