from disk_cleaner.core import fsutil


def _home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_dir_size_counts_files_and_ignores_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_bytes(b"x" * 50000)
    d = tmp_path / "d"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 10000)
    (d / "link").symlink_to(outside)
    size = fsutil.dir_size(d)
    assert 10000 <= size < 50000


def test_dir_size_skips_unreadable_directory(tmp_path):  # Review Focus 2
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "f").write_bytes(b"x" * 5000)
    (tmp_path / "ok").write_bytes(b"x" * 5000)
    locked.chmod(0)
    try:
        assert fsutil.dir_size(tmp_path) >= 5000
    finally:
        locked.chmod(0o755)


def test_human():
    assert fsutil.human(512) == "512 B"
    assert fsutil.human(1536) == "1.5 KB"
    assert fsutil.human(5 * 1024**3) == "5.0 GB"


def test_free_bytes_positive():
    assert fsutil.free_bytes("/") > 0


def test_run_missing_command_returns_127():
    rc, out, err = fsutil.run(["definitely-not-a-command-xyz"])
    assert rc == 127 and out == ""


def test_remove_contents_keeps_root(tmp_path):
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "f").write_bytes(b"x" * 4000)
    (root / "top").write_bytes(b"x" * 4000)
    freed, errors = fsutil.remove_contents(root, [root], home)
    assert root.is_dir() and list(root.iterdir()) == []
    assert errors == [] and freed >= 8000


def test_remove_path_symlink_removes_only_link(tmp_path):  # Review Focus 1
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    root.mkdir(parents=True)
    target = home / "Documents"
    target.mkdir()
    (target / "keep").write_text("1")
    link = root / "l"
    link.symlink_to(target)
    fsutil.remove_path(link, [root], home)
    assert not link.is_symlink()
    assert (target / "keep").exists()


def test_remove_contents_reports_safety_errors_and_continues(tmp_path):
    home = _home(tmp_path)
    root = home / ".cache" / "x"
    proj = root / "proj"
    (proj / ".git").mkdir(parents=True)
    (root / "junk").write_bytes(b"x" * 100)
    freed, errors = fsutil.remove_contents(root, [root], home)
    assert proj.exists() and not (root / "junk").exists()
    assert len(errors) == 1
