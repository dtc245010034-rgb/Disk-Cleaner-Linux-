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
