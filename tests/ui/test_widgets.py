import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

_init = Gtk.init_check()
_ok = _init[0] if isinstance(_init, tuple) else _init
pytestmark = pytest.mark.skipif(not _ok, reason="không có display")

from disk_cleaner.core.models import Category, Item, Risk  # noqa: E402
from disk_cleaner.ui.widgets import CategoryCard  # noqa: E402


class Cat(Category):
    id, title, icon, description = "c", "C", "folder-symbolic", "mô tả"
    expandable = True

    def __init__(self, risk):
        self.risk = risk


def _items():
    return [Item("a", "a", 100), Item("b", "b", 200), Item("k", "k", 300, locked=True)]


def test_safe_default_selects_unlocked_children():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    assert [i.id for i in card.selected_items()] == ["a", "b"]
    assert card.selected_size() == 300


def test_reloadable_default_selects_nothing_and_master_selects_all_unlocked():
    card = CategoryCard(Cat(Risk.RELOADABLE), _items(), lambda: None)
    assert card.selected_items() == []
    card.master.set_active(True)
    assert [i.id for i in card.selected_items()] == ["a", "b"]
    card.master.set_active(False)
    assert card.selected_items() == []


def test_dangerous_default_selects_nothing():
    card = CategoryCard(Cat(Risk.DANGEROUS), _items(), lambda: None)
    assert card.selected_items() == []


def test_locked_item_checkbox_is_insensitive():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    locked = [chk for it, chk in card.child_checks if it.locked][0]
    assert not locked.get_sensitive() and not locked.get_active()


def test_partial_child_selection_sets_master_inconsistent():
    card = CategoryCard(Cat(Risk.SAFE), _items(), lambda: None)
    card.child_checks[0][1].set_active(False)
    assert card.master.get_inconsistent()
    assert [i.id for i in card.selected_items()] == ["b"]


def test_on_changed_called_when_toggled():
    calls = []
    card = CategoryCard(Cat(Risk.RELOADABLE), _items(), lambda: calls.append(1))
    card.master.set_active(True)
    assert calls


def test_error_card_is_not_selectable():
    card = CategoryCard(Cat(Risk.SAFE), [], lambda: None, error="Lỗi: boom")
    assert card.selected_items() == [] and not card.master.get_sensitive()
