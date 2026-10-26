from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..core.fsutil import human  # noqa: E402
from ..core.models import Category, Item, Risk  # noqa: E402

RISK_INFO = {
    Risk.SAFE: ("An toàn", "emblem-ok-symbolic", "risk-safe"),
    Risk.RELOADABLE: ("Tải lại được", "dialog-warning-symbolic", "risk-reloadable"),
    Risk.DANGEROUS: ("Nguy hiểm", "dialog-error-symbolic", "risk-dangerous"),
}


def icon(name: str, size=Gtk.IconSize.MENU) -> Gtk.Image:
    """Icon theo theme; dự phòng tên không symbolic rồi image-missing."""
    theme = Gtk.IconTheme.get_default()
    for candidate in (name, name.removesuffix("-symbolic"), "image-missing"):
        if theme.has_icon(candidate):
            return Gtk.Image.new_from_icon_name(candidate, size)
    return Gtk.Image.new_from_icon_name("image-missing", size)


class RiskBadge(Gtk.Box):
    def __init__(self, risk: Risk):
        super().__init__(spacing=4)
        text, icon_name, css = RISK_INFO[risk]
        ctx = self.get_style_context()
        ctx.add_class("risk-badge")
        ctx.add_class(css)
        self.pack_start(icon(icon_name), False, False, 0)
        self.pack_start(Gtk.Label(label=text), False, False, 0)
        self.set_valign(Gtk.Align.CENTER)


class UsageBar(Gtk.Box):
    def __init__(self, path: str = "/"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.path = path
        self.get_style_context().add_class("usage-box")
        top = Gtk.Box(spacing=8)
        top.pack_start(icon("drive-harddisk-symbolic", Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
        self.label = Gtk.Label(xalign=0)
        top.pack_start(self.label, True, True, 0)
        self.pack_start(top, False, False, 0)
        self.bar = Gtk.ProgressBar()
        self.bar.get_style_context().add_class("usage-bar")
        self.pack_start(self.bar, False, False, 0)
        self.refresh()

    def refresh(self) -> None:
        st = os.statvfs(self.path)
        free = st.f_bavail * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        frac = used / max(1, used + free)
        ctx = self.bar.get_style_context()
        for c in ("usage-ok", "usage-warn", "usage-crit"):
            ctx.remove_class(c)
        ctx.add_class("usage-crit" if frac > 0.9 else "usage-warn" if frac > 0.8 else "usage-ok")
        self.bar.set_fraction(frac)
        self.label.set_markup(
            f"<b>{GLib.markup_escape_text(self.path)}</b>   {human(used)} / {human(used + free)} "
            f"({frac:.0%})   ·   Trống <b>{human(free)}</b>")


class CategoryCard(Gtk.Box):
    """Một thẻ nhóm dọn: checkbox chính + (nếu expandable) danh sách mục con."""

    def __init__(self, cat: Category, items: list[Item], on_changed, error: str | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.cat, self.items, self.on_changed = cat, items, on_changed
        self.child_checks: list[tuple[Item, Gtk.CheckButton]] = []
        self._syncing = False
        self.get_style_context().add_class("card")

        selectable = error is None and any(not i.locked for i in items)
        default_on = selectable and cat.risk == Risk.SAFE

        head = Gtk.Box(spacing=10)
        self.master = Gtk.CheckButton()
        self.master.set_sensitive(selectable)
        self.master.set_active(default_on)
        self.master.connect("toggled", self._on_master)
        head.pack_start(self.master, False, False, 0)
        head.pack_start(icon(cat.icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=cat.title, xalign=0)
        title.get_style_context().add_class("card-title")
        desc = Gtk.Label(label=error or cat.description, xalign=0, wrap=True)
        desc.get_style_context().add_class("error-text" if error else "dim")
        text.pack_start(title, False, False, 0)
        text.pack_start(desc, False, False, 0)
        head.pack_start(text, True, True, 0)

        head.pack_start(RiskBadge(cat.risk), False, False, 0)
        if cat.needs_root:
            lock = icon("security-high-symbolic")
            lock.set_tooltip_text("Cần quyền root (hỏi mật khẩu khi dọn)")
            head.pack_start(lock, False, False, 0)
        size = Gtk.Label(label=human(sum(i.size_bytes for i in items)) if not error else "",
                         width_chars=9, xalign=1)
        size.get_style_context().add_class("size-label")
        head.pack_start(size, False, False, 6)

        self.revealer = None
        if cat.expandable and items:
            toggle = Gtk.ToggleButton()
            toggle.set_relief(Gtk.ReliefStyle.NONE)
            toggle.add(icon("pan-down-symbolic"))
            toggle.connect("toggled", lambda b: self.revealer.set_reveal_child(b.get_active()))
            head.pack_end(toggle, False, False, 0)
        self.pack_start(head, False, False, 0)

        if cat.expandable and items:
            self.revealer = Gtk.Revealer()
            rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for item in items:
                rows.pack_start(self._item_row(item, default_on), False, False, 0)
            self.revealer.add(rows)
            self.pack_start(self.revealer, False, False, 0)

    def _item_row(self, item: Item, default_on: bool) -> Gtk.Box:
        row = Gtk.Box(spacing=8)
        row.get_style_context().add_class("item-row")
        chk = Gtk.CheckButton(label=item.label)
        chk.set_sensitive(not item.locked)
        chk.set_active(default_on and not item.locked)
        chk.connect("toggled", self._on_child)
        self.child_checks.append((item, chk))
        row.pack_start(chk, False, False, 0)
        if item.detail:
            d = Gtk.Label(label=item.detail, xalign=0)
            d.get_style_context().add_class("dim")
            row.pack_start(d, True, True, 0)
        if item.locked:
            row.pack_start(icon("changes-prevent-symbolic"), False, False, 0)
        sz = Gtk.Label(label=human(item.size_bytes))
        sz.get_style_context().add_class("dim")
        row.pack_end(sz, False, False, 0)
        return row

    def _on_master(self, _btn) -> None:
        if self._syncing:
            return
        if self.revealer is not None:
            self._syncing = True
            self.master.set_inconsistent(False)
            for item, chk in self.child_checks:
                if not item.locked:
                    chk.set_active(self.master.get_active())
            self._syncing = False
        self.on_changed()

    def _on_child(self, _btn) -> None:
        if self._syncing:
            return
        unlocked = [chk.get_active() for item, chk in self.child_checks if not item.locked]
        self._syncing = True
        if unlocked and all(unlocked):
            self.master.set_inconsistent(False)
            self.master.set_active(True)
        elif not any(unlocked):
            self.master.set_inconsistent(False)
            self.master.set_active(False)
        else:
            self.master.set_active(False)
            self.master.set_inconsistent(True)
        self._syncing = False
        self.on_changed()

    def selected_items(self) -> list[Item]:
        if self.revealer is not None:
            return [item for item, chk in self.child_checks if chk.get_active() and not item.locked]
        return list(self.items) if self.master.get_active() else []

    def selected_size(self) -> int:
        return sum(i.size_bytes for i in self.selected_items())


def confirm(parent, title: str, body: str, require_text: str | None = None) -> bool:
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.WARNING,
                            buttons=Gtk.ButtonsType.NONE, text=title)
    dlg.format_secondary_text(body)
    dlg.add_button("Huỷ", Gtk.ResponseType.CANCEL)
    ok = dlg.add_button("Dọn", Gtk.ResponseType.OK)
    ok.get_style_context().add_class("destructive-action")
    if require_text:
        entry = Gtk.Entry()
        entry.set_placeholder_text(f"Gõ {require_text} để xác nhận")
        dlg.get_message_area().pack_start(entry, False, False, 6)
        ok.set_sensitive(False)
        entry.connect("changed", lambda e: ok.set_sensitive(e.get_text().strip() == require_text))
    dlg.show_all()
    response = dlg.run()
    dlg.destroy()
    return response == Gtk.ResponseType.OK
