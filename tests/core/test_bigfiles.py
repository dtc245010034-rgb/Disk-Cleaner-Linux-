from pathlib import Path

from disk_cleaner.core import bigfiles
from disk_cleaner.core.models import Item


def _tree(tmp_path):
    home = tmp_path / "home"
    nm = home / "Màn hình nền" / "dự án 1" / "node_modules"
    nm.mkdir(parents=True)
    (nm / "pkg").mkdir()
    (nm / "pkg" / "big.bin").write_bytes(b"x" * 20000)
    (nm / "pkg" / "node_modules").mkdir()          # lồng nhau: không đi sâu thêm
    (home / "dự án 1" / "venv").mkdir(parents=True)
    (home / "dự án 1" / "venv" / "lib.so").write_bytes(b"x" * 20000)
    (home / "dự án 1" / "requirements.txt").write_text("numpy")
    (home / ".config" / "app" / "node_modules").mkdir(parents=True)
    (home / ".config" / "app" / "node_modules" / "x").write_bytes(b"x" * 20000)
    (home / "video lớn.mkv").write_bytes(b"x" * 30000)
    (home / "nhỏ.txt").write_text("hi")
    return home


def test_find_big_dirs_unicode_names_and_no_nested_descend(tmp_path):
    home = _tree(tmp_path)
    found = bigfiles.find_big_dirs(home, home=home)
    paths = {str(e.path.relative_to(home)) for e in found}
    assert paths == {"Màn hình nền/dự án 1/node_modules", "dự án 1/venv"}
    assert all(e.kind == "dir" and e.deletable for e in found)


def test_build_and_dist_only_counted_next_to_a_project_marker(tmp_path):
    home = tmp_path / "home"
    # mã nguồn WordPress: dist/build KHÔNG phải sản phẩm build bỏ quên
    (home / "site/wp-includes/js/dist").mkdir(parents=True)
    (home / "site/wp-includes/js/dist/a.js").write_bytes(b"x" * 9000)
    (home / "site/wp-includes/build").mkdir(parents=True)
    (home / "site/wp-includes/build/b.php").write_bytes(b"x" * 9000)
    # dự án thật: dist cạnh package.json, build cạnh pyproject.toml
    (home / "web/dist").mkdir(parents=True)
    (home / "web/dist/bundle.js").write_bytes(b"x" * 9000)
    (home / "web/package.json").write_text("{}")
    (home / "lib/build").mkdir(parents=True)
    (home / "lib/build/o.bin").write_bytes(b"x" * 9000)
    (home / "lib/pyproject.toml").write_text("[project]")
    found = {str(e.path.relative_to(home)) for e in bigfiles.find_big_dirs(home, home=home)}
    assert found == {"web/dist", "lib/build"}


def test_find_big_dirs_skips_hidden_by_default_but_can_include(tmp_path):
    home = _tree(tmp_path)
    with_hidden = bigfiles.find_big_dirs(home, home=home, skip_hidden=False)
    hidden = [e for e in with_hidden if ".config" in e.path.parts]
    assert hidden and not hidden[0].deletable


def test_find_big_dirs_min_bytes(tmp_path):
    home = _tree(tmp_path)
    assert bigfiles.find_big_dirs(home, home=home, min_bytes=10**9) == []


def test_find_big_files_threshold_and_order(tmp_path):
    home = _tree(tmp_path)
    found = bigfiles.find_big_files(home, min_bytes=10000, home=home)
    names = [e.path.name for e in found]
    assert "nhỏ.txt" not in names
    assert names[0] == "video lớn.mkv" or found[0].size >= found[-1].size
    cfg = [e for e in found if ".config" in e.path.parts]
    assert cfg and not cfg[0].deletable
    video = [e for e in found if e.path.name == "video lớn.mkv"][0]
    assert video.deletable and video.kind == "file"


def test_big_dirs_category_scan_and_clean(tmp_path):
    home = _tree(tmp_path)
    cat = bigfiles.BigDirsCategory(home)
    items = cat.scan()
    assert {Path(i.path).name for i in items} == {"node_modules", "venv"}
    assert cat.expandable
    venv = [i for i in items if Path(i.path).name == "venv"]
    res = cat.clean(venv, dry_run=False)
    assert res.errors == [] and not (home / "dự án 1" / "venv").exists()
    assert (home / "dự án 1" / "requirements.txt").exists()


def test_big_dirs_category_never_deletes_project_root(tmp_path):
    home = _tree(tmp_path)
    cat = bigfiles.BigDirsCategory(home)
    bad = Item("x", "x", 1, path=str(home / "dự án 1"))
    res = cat.clean([bad], dry_run=False)
    assert res.errors and (home / "dự án 1").exists()
