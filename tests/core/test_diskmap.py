import math

from disk_cleaner.core import diskmap


def test_squarify_fills_area_without_overlap_or_overflow():
    sizes = [60, 30, 20, 10, 5, 5]
    rects = diskmap.squarify(sizes, 0, 0, 400, 300)
    assert len(rects) == len(sizes)
    assert math.isclose(sum(w * h for _x, _y, w, h in rects), 400 * 300, rel_tol=1e-6)
    for x, y, w, h in rects:
        assert x >= -1e-6 and y >= -1e-6 and x + w <= 400 + 1e-6 and y + h <= 300 + 1e-6
    for i, (x1, y1, w1, h1) in enumerate(rects):
        for x2, y2, w2, h2 in rects[i + 1:]:
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert not (ox > 1e-6 and oy > 1e-6)


def test_squarify_area_proportional_to_size():
    rects = diskmap.squarify([75, 25], 0, 0, 100, 100)
    areas = [w * h for _x, _y, w, h in rects]
    assert math.isclose(areas[0] / areas[1], 3.0, rel_tol=1e-6)


def test_squarify_edge_cases():
    assert diskmap.squarify([], 0, 0, 10, 10) == []
    assert len(diskmap.squarify([0, 0], 0, 0, 10, 10)) == 2
    assert len(diskmap.squarify([5, 0, 3], 0, 0, 10, 10)) == 3
    assert diskmap.squarify([5], 0, 0, 0, 0) == [(0, 0, 0.0, 0.0)]


def test_list_children_sorted_skips_symlinks_and_unreadable(tmp_path):
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "f").write_bytes(b"x" * 20000)
    (tmp_path / "small.txt").write_bytes(b"x" * 100)
    (tmp_path / "Màn hình nền").mkdir()
    (tmp_path / "Màn hình nền" / "a").write_bytes(b"x" * 5000)
    (tmp_path / "link").symlink_to(tmp_path / "big")
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "f").write_bytes(b"x" * 9000)
    locked.chmod(0)
    try:
        entries = diskmap.list_children(tmp_path)
    finally:
        locked.chmod(0o755)
    names = [e.name for e in entries]
    assert "link" not in names
    assert names[0] == "big" and entries[0].is_dir
    assert "Màn hình nền" in names and "small.txt" in names
    assert [e.size for e in entries] == sorted((e.size for e in entries), reverse=True)


def test_list_children_missing_path_returns_empty(tmp_path):
    assert diskmap.list_children(tmp_path / "nope") == []
