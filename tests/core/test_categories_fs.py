from pathlib import Path

from disk_cleaner.core import categories as cats
from disk_cleaner.core.models import Risk


def test_dirs_category_hides_when_empty(tmp_path):
    d = tmp_path / ".cache" / "x"
    d.mkdir(parents=True)
    assert cats.DirsCategory("x", "X", "d", [d], tmp_path).scan() == []


def test_dirs_category_scan_and_dry_run(tmp_path):
    d = tmp_path / ".cache" / "x"
    d.mkdir(parents=True)
    (d / "f").write_bytes(b"x" * 8000)
    c = cats.DirsCategory("x", "X", "d", [d], tmp_path)
    items = c.scan()
    assert len(items) == 1 and items[0].size_bytes >= 8000 and c.risk == Risk.SAFE
    res = c.clean(items, dry_run=True)
    assert res.freed_bytes >= 8000 and (d / "f").exists()


def test_dirs_category_clean_removes_contents_keeps_dir(tmp_path):
    d = tmp_path / ".cache" / "x"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f").write_bytes(b"x" * 8000)
    c = cats.DirsCategory("x", "X", "d", [d], tmp_path)
    res = c.clean(c.scan(), dry_run=False)
    assert d.is_dir() and list(d.iterdir()) == [] and res.freed_bytes >= 8000


def test_dirs_category_cleans_dir_containing_package_json(tmp_path):
    d = tmp_path / ".cache" / "ts"
    (d / "6.0").mkdir(parents=True)
    (d / "6.0" / "package.json").write_text("{}")
    (d / "6.0" / "big").write_bytes(b"x" * 5000)
    c = cats.DirsCategory("ts", "TS", "d", [d], tmp_path)
    res = c.clean(c.scan(), dry_run=False)
    assert res.errors == [] and not (d / "6.0").exists()


def test_chrome_clean_keeps_cookies_indexeddb_and_scriptcache(tmp_path):
    home = tmp_path
    prof = home / ".config/google-chrome/Default"
    cs = prof / "Service Worker/CacheStorage/a"
    cs.mkdir(parents=True)
    (cs / "f").write_bytes(b"x" * 5000)
    (prof / "Service Worker/ScriptCache").mkdir(parents=True)
    (prof / "Service Worker/ScriptCache/s").write_bytes(b"x" * 100)
    (prof / "Cookies").write_bytes(b"c")
    (prof / "IndexedDB").mkdir()
    (prof / "IndexedDB/db").write_bytes(b"d")
    (home / ".cache/google-chrome").mkdir(parents=True)
    (home / ".cache/google-chrome/c").write_bytes(b"x" * 5000)
    cat = cats.DirsCategory("chrome-cache", "Cache Chrome", "", cats.chrome_dirs(home), home)
    cat.clean(cat.scan(), dry_run=False)
    assert (prof / "Cookies").exists()
    assert (prof / "IndexedDB/db").exists()
    assert (prof / "Service Worker/ScriptCache/s").exists()
    assert not cs.exists()
    assert not (home / ".cache/google-chrome/c").exists()


def test_fs_categories_ids(tmp_path):
    ids = {c.id for c in cats.fs_categories(tmp_path)}
    assert {"trash", "chrome-cache", "vscode-cache", "puppeteer-cache", "misc-cache"} <= ids


def test_claude_old_versions_keeps_newest_and_running(tmp_path):
    home = tmp_path
    g = home / ".local/share/claude/versions"
    g.mkdir(parents=True)
    for v in ("2.1.2", "2.1.9", "2.1.10"):
        (g / v).write_bytes(b"x" * 5000)
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/agy.123.old").write_bytes(b"x" * 5000)
    running = {str((g / "2.1.9").resolve())}
    c = cats.ClaudeOldVersions(home, running_exes=lambda: running)
    names = sorted(Path(i.path).name for i in c.scan())
    assert names == ["2.1.2", "agy.123.old"]
    res = c.clean(c.scan(), dry_run=False)
    assert res.errors == []
    assert not (g / "2.1.2").exists()
    assert (g / "2.1.9").exists() and (g / "2.1.10").exists()


def test_claude_old_versions_not_duplicated_via_snap_current_symlink(tmp_path):
    rev = tmp_path / "snap/code/267/.local/share/claude/versions"
    rev.mkdir(parents=True)
    for v in ("2.1.1", "2.1.2"):
        (rev / v).write_bytes(b"x" * 5000)
    (tmp_path / "snap/code/current").symlink_to("267")
    c = cats.ClaudeOldVersions(tmp_path, running_exes=lambda: set())
    items = c.scan()
    assert len(items) == 1 and Path(items[0].path).name == "2.1.1"


def test_claude_old_versions_rechecks_running_at_clean_time(tmp_path):
    g = tmp_path / ".local/share/claude/versions"
    g.mkdir(parents=True)
    for v in ("2.1.2", "2.1.10"):
        (g / v).write_bytes(b"x" * 5000)
    state = {"running": set()}
    c = cats.ClaudeOldVersions(tmp_path, running_exes=lambda: state["running"])
    items = c.scan()
    state["running"] = {str((g / "2.1.2").resolve())}
    res = c.clean(items, dry_run=False)
    assert (g / "2.1.2").exists() and len(res.skipped) == 1
