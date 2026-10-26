from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..core.cleaner import run_cleanup  # noqa: E402
from ..core.fsutil import free_bytes, human  # noqa: E402
from ..core.models import Risk  # noqa: E402
from ..core.registry import build_categories  # noqa: E402
from ..core.rootrunner import RootRunner  # noqa: E402
from ..core.scanner import scan_all  # noqa: E402
from .widgets import CategoryCard, confirm, icon  # noqa: E402


class CleanupTab(Gtk.Box):
    def __init__(self, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.categories = build_categories()
        self.on_changed = on_changed or (lambda: None)
        self.cards: list[CategoryCard] = []
        self.busy = False

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroller = Gtk.ScrolledWindow()
        scroller.add(self.list_box)
        self.pack_start(scroller, True, True, 0)

        log_exp = Gtk.Expander(label="Nhật ký")
        self.log = Gtk.TextView(editable=False, monospace=True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(90)
        log_scroll.add(self.log)
        log_exp.add(log_scroll)
        self.pack_start(log_exp, False, False, 0)

        footer = Gtk.Box(spacing=10)
        footer.get_style_context().add_class("footer")
        self.spinner = Gtk.Spinner()
        footer.pack_start(self.spinner, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        footer.pack_start(self.status, True, True, 0)
        self.selected_label = Gtk.Label()
        footer.pack_start(self.selected_label, False, False, 0)
        self.scan_btn = Gtk.Button()
        box = Gtk.Box(spacing=6)
        box.pack_start(icon("view-refresh-symbolic"), False, False, 0)
        box.pack_start(Gtk.Label(label="Quét lại"), False, False, 0)
        self.scan_btn.add(box)
        self.scan_btn.connect("clicked", lambda _b: self.rescan())
        footer.pack_start(self.scan_btn, False, False, 0)
        self.clean_btn = Gtk.Button(label="Dọn đã chọn")
        self.clean_btn.get_style_context().add_class("suggested-action")
        self.clean_btn.connect("clicked", self._on_clean)
        footer.pack_start(self.clean_btn, False, False, 0)
        self.pack_start(footer, False, False, 0)

        self.rescan()

    # ---- quét ----
    def rescan(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Đang quét…")
        for card in self.cards:
            self.list_box.remove(card)
        self.cards = []
        self._update_selected()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        for outcome in scan_all(self.categories):
            GLib.idle_add(self._add_outcome, outcome)
        GLib.idle_add(self._scan_done)

    def _add_outcome(self, outcome) -> bool:
        if not outcome.items and not outcome.error:
            return False
        card = CategoryCard(outcome.category, outcome.items, self._update_selected, outcome.error)
        self.cards.append(card)
        self.list_box.pack_start(card, False, False, 0)
        card.show_all()
        self._update_selected()
        return False

    def _scan_done(self) -> bool:
        total = sum(i.size_bytes for c in self.cards for i in c.items)
        self._set_busy(False, f"Quét xong: có thể dọn tối đa {human(total)}")
        self.on_changed()
        return False

    # ---- dọn ----
    def _selection(self):
        return [(c.cat, c.selected_items()) for c in self.cards if c.selected_items()]

    def _update_selected(self) -> None:
        total = sum(c.selected_size() for c in self.cards)
        self.selected_label.set_markup(f"Đã chọn: <b>{human(total)}</b>")
        self.clean_btn.set_sensitive(not self.busy and total > 0)

    def _on_clean(self, _btn) -> None:
        selection = self._selection()
        if not selection:
            return
        total = sum(i.size_bytes for _c, items in selection for i in items)
        lines = [f"• {cat.title}: {len(items)} mục, {human(sum(i.size_bytes for i in items))}"
                 for cat, items in selection]
        dangerous = any(cat.risk == Risk.DANGEROUS for cat, _ in selection)
        body = "\n".join(lines) + f"\n\nƯớc tính giải phóng: {human(total)}"
        if dangerous:
            body += "\n\nCó mục NGUY HIỂM (có thể mất dữ liệu vĩnh viễn)."
        if not confirm(self.get_toplevel(), "Dọn các mục đã chọn?", body, "XOA" if dangerous else None):
            return
        self._set_busy(True, "Đang dọn… (có thể hỏi mật khẩu)")
        threading.Thread(target=self._clean_worker, args=(selection, free_bytes("/")), daemon=True).start()

    def _clean_worker(self, selection, free_before: int) -> None:
        results = run_cleanup(selection, dry_run=False, root_runner=RootRunner())
        GLib.idle_add(self._clean_done, selection, results, free_before)

    def _clean_done(self, selection, results, free_before) -> bool:
        titles = {cat.id: cat.title for cat, _ in selection}
        buf = self.log.get_buffer()
        reported = 0
        for cid, res in results.items():
            reported += res.freed_bytes
            parts = [f"giải phóng {human(res.freed_bytes)}"]
            parts += [f"BỎ QUA: {s}" for s in res.skipped]
            parts += [f"LỖI: {e}" for e in res.errors]
            buf.insert(buf.get_end_iter(), f"{titles.get(cid, cid)}: " + "; ".join(parts) + "\n")
        gained = max(0, free_bytes("/") - free_before)
        errors = sum(len(r.errors) for r in results.values())
        self._set_busy(False, "")
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                message_type=Gtk.MessageType.INFO if not errors else Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.OK, text="Dọn dẹp hoàn tất")
        dlg.format_secondary_text(f"Ước tính giải phóng: {human(reported)}\nỔ trống thực tế tăng: {human(gained)}"
                                  + (f"\n{errors} lỗi, xem mục Nhật ký." if errors else ""))
        dlg.run()
        dlg.destroy()
        self.on_changed()
        self.rescan()
        return False

    def _set_busy(self, busy: bool, text: str) -> None:
        self.busy = busy
        self.status.set_text(text)
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.scan_btn.set_sensitive(not busy)
        self._update_selected()
