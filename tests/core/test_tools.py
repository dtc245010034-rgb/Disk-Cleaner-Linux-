import json

import pytest

from disk_cleaner.core import tools
from disk_cleaner.core.models import Risk

DF = {
    "Images": [
        {"ID": "sha256:aaa", "Repository": "<none>", "Tag": "<none>", "Containers": "0", "UniqueSize": "10MB"},
        {"ID": "sha256:bbb", "Repository": "grafana/grafana", "Tag": "13", "Containers": "0", "UniqueSize": "483MB"},
        {"ID": "sha256:ccc", "Repository": "mysql", "Tag": "8.4", "Containers": "1", "UniqueSize": "254MB"},
    ],
    "Volumes": [
        {"Name": "proj_db", "Links": "0", "Size": "206.7MB",
         "Labels": "com.docker.compose.project=proj,com.docker.compose.volume=db"},
        {"Name": "abc123", "Links": "0", "Size": "46.4MB", "Labels": ""},
        {"Name": "inuse", "Links": "1", "Size": "1MB", "Labels": "com.docker.compose.project=p"},
    ],
}


@pytest.fixture
def docker(monkeypatch):
    calls = []

    def _run(cmd, timeout=60):
        calls.append(cmd)
        if cmd[:3] == ["docker", "system", "df"]:
            return 0, json.dumps(DF), ""
        return 0, "", ""

    monkeypatch.setattr(tools, "run", _run)
    return calls


def test_parse_size():
    assert tools.parse_size("46.4MB") == 46_400_000
    assert tools.parse_size("127kB") == 127_000
    assert tools.parse_size("0B") == 0
    assert tools.parse_size("N/A") == 0
    assert tools.parse_size("") == 0


def test_docker_dangling_only_untagged_unused(docker):
    items = tools.DockerDangling().scan()
    assert len(items) == 1 and items[0].size_bytes == 10_000_000
    tools.DockerDangling().clean(items, dry_run=False)
    assert ["docker", "image", "prune", "-f"] in docker


def test_docker_unused_images_excludes_used_and_untagged(docker):
    cat = tools.DockerUnusedImages()
    items = cat.scan()
    assert [i.label for i in items] == ["grafana/grafana:13"]
    assert cat.risk == Risk.RELOADABLE and cat.expandable
    res = cat.clean(items, dry_run=False)
    assert ["docker", "rmi", "grafana/grafana:13"] in docker
    assert res.freed_bytes == 483_000_000


def test_docker_volumes_project_label_and_locked(docker):
    cat = tools.DockerVolumes()
    items = {i.id: i for i in cat.scan()}
    assert items["docker-volume:proj_db"].detail == "Project: proj"
    assert items["docker-volume:abc123"].detail == "Không rõ project"
    assert items["docker-volume:inuse"].locked is True
    assert cat.risk == Risk.DANGEROUS
    cat.clean([items["docker-volume:abc123"]], dry_run=False)
    assert ["docker", "volume", "rm", "abc123"] in docker


def test_docker_dry_run_does_not_run_destructive_commands(docker):
    cat = tools.DockerVolumes()
    cat.clean(cat.scan(), dry_run=True)
    assert not any(c[:2] in (["docker", "volume"], ["docker", "rmi"]) for c in docker)


def test_docker_daemon_down_hides_all_docker_categories(monkeypatch):  # Review Focus 3
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (1, "", "Cannot connect to the Docker daemon"))
    assert tools.DockerDangling().scan() == []
    assert tools.DockerUnusedImages().scan() == []
    assert tools.DockerVolumes().scan() == []


def test_docker_bad_json_is_handled(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (0, "not json", ""))
    assert tools.docker_df() is None


def test_command_cache_dry_run_and_clean(tmp_path, monkeypatch):
    d = tmp_path / ".npm"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 9000)
    calls = []

    def _run(cmd, timeout=60):
        calls.append(cmd)
        (d / "f").unlink()
        return 0, "", ""

    monkeypatch.setattr(tools, "run", _run)
    cat = tools.CommandCache("npm-cache", "Cache npm", "d", d, ["npm", "cache", "clean", "--force"], "npm")
    items = cat.scan()
    assert items[0].size_bytes >= 9000
    assert cat.clean(items, dry_run=True).freed_bytes >= 9000 and calls == []
    res = cat.clean(items, dry_run=False)
    assert calls == [["npm", "cache", "clean", "--force"]] and res.freed_bytes >= 9000


def test_command_cache_failure_reports_error(tmp_path, monkeypatch):
    d = tmp_path / ".npm"
    d.mkdir()
    (d / "f").write_bytes(b"x" * 9000)
    monkeypatch.setattr(tools, "run", lambda cmd, timeout=60: (1, "", "npm lỗi"))
    cat = tools.CommandCache("npm-cache", "Cache npm", "d", d, ["npm"], "npm")
    res = cat.clean(cat.scan(), dry_run=False)
    assert res.errors == ["npm lỗi"] and res.freed_bytes == 0
