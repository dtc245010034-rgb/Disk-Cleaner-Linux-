from disk_cleaner.core.registry import build_categories


def test_registry_ids_unique_and_complete(tmp_path):
    cats = build_categories(tmp_path)
    ids = [c.id for c in cats]
    assert len(ids) == len(set(ids))
    for c in cats:
        assert c.title and c.icon and c.risk
    assert {"trash", "chrome-cache", "npm-cache", "apt-cache", "journal", "kernels",
            "snaps", "docker-volumes"} <= set(ids)
