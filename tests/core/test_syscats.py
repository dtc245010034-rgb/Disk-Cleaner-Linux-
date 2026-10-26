from disk_cleaner.core import syscats
from disk_cleaner.core.models import Risk

DPKG = (
    "linux-headers-7.0.0-28-generic||un \n"
    "linux-headers-7.0.0-34-generic|31260|ii \n"
    "linux-headers-7.0.0-34|8000|ii \n"
    "linux-headers-7.0.0-38-generic|31337|ii \n"
    "linux-image-7.0.0-31-generic||rc \n"
    "linux-image-7.0.0-34-generic|16629|ii \n"
    "linux-image-7.0.0-38-generic|16649|ii \n"
)


def _kernels(monkeypatch, out, running="7.0.0-38-generic"):
    monkeypatch.setattr(syscats, "run", lambda cmd, timeout=60: (0, out, ""))
    return syscats.OldKernels(running_release=running)


def test_kernels_group_by_version_and_lock_running_and_newest(monkeypatch):
    items = {i.id: i for i in _kernels(monkeypatch, DPKG).scan()}
    assert set(items) == {"kernel:7.0.0-31", "kernel:7.0.0-34", "kernel:7.0.0-38"}
    assert items["kernel:7.0.0-38"].locked and not items["kernel:7.0.0-34"].locked
    assert items["kernel:7.0.0-34"].size_bytes == (31260 + 8000 + 16629) * 1024
    assert sorted(items["kernel:7.0.0-34"].data["pkgs"]) == sorted([
        "linux-headers-7.0.0-34-generic", "linux-headers-7.0.0-34", "linux-image-7.0.0-34-generic"])


def test_kernels_root_ops_skip_locked(monkeypatch):
    cat = _kernels(monkeypatch, DPKG)
    items = cat.scan()
    ops = cat.root_ops(items)
    assert len(ops) == 1 and ops[0][0] == "kernel-purge"
    assert "linux-image-7.0.0-38-generic" not in ops[0]
    assert "linux-image-7.0.0-34-generic" in ops[0]
    assert "linux-image-7.0.0-31-generic" in ops[0]


def test_single_kernel_is_fully_locked(monkeypatch):  # Review Focus 4
    out = ("linux-image-7.0.0-38-generic|16649|ii \n"
           "linux-headers-7.0.0-38-generic|31337|ii \n")
    cat = _kernels(monkeypatch, out)
    items = cat.scan()
    assert len(items) == 1 and items[0].locked
    assert cat.root_ops(items) == []


def test_kernels_empty_output(monkeypatch):
    assert _kernels(monkeypatch, "").scan() == []


def test_journal_reclaim_over_target(monkeypatch):
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (
        0, "Archived and active journals take up 300.0M in the file system.\n", ""))
    cat = syscats.JournalLogs()
    items = cat.scan()
    assert items[0].size_bytes == 200 * 1024 * 1024
    assert cat.root_ops(items) == [["journal-vacuum", "100M"]]


def test_journal_hidden_when_under_target(monkeypatch):
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (
        0, "Archived and active journals take up 45.0M in the file system.\n", ""))
    assert syscats.JournalLogs().scan() == []


def test_apt_cache(tmp_path):
    (tmp_path / "a.deb").write_bytes(b"x" * 9000)
    cat = syscats.AptCache(path=tmp_path)
    items = cat.scan()
    assert items[0].size_bytes >= 9000 and cat.needs_root and cat.root_ops(items) == [["apt-clean"]]


def test_snaps_only_disabled(monkeypatch, tmp_path):
    out = ("Name  Version  Rev  Tracking  Publisher  Notes\n"
           "core20  1.0  2922  latest/stable  canonical**  base\n"
           "core20  1.0  2900  latest/stable  canonical**  base,disabled\n"
           "code    abc  267   latest/stable  vscode**     classic\n")
    (tmp_path / "core20_2900.snap").write_bytes(b"x" * 7000)
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (0, out, ""))
    cat = syscats.OldSnaps(snaps_dir=tmp_path)
    items = cat.scan()
    assert [i.id for i in items] == ["snap:core20:2900"]
    assert items[0].size_bytes == 7000
    assert cat.risk == Risk.RELOADABLE
    assert cat.root_ops(items) == [["snap-remove", "core20", "2900"]]


def test_snaps_none_disabled(monkeypatch):
    out = "Name  Version  Rev  Tracking  Publisher  Notes\ncode  abc  267  latest/stable  vscode**  classic\n"
    monkeypatch.setattr(syscats, "run", lambda c, timeout=60: (0, out, ""))
    assert syscats.OldSnaps().scan() == []
