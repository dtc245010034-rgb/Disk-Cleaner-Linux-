import sys

from disk_cleaner.core.rootrunner import RootRunner


def _helper(tmp_path, body):
    h = tmp_path / "helper.py"
    h.write_text(body)
    h.chmod(0o644)
    return h


def test_parses_helper_json(tmp_path):
    h = _helper(tmp_path, "import json,sys\nprint(json.dumps([{'ok': True}]))\n")
    r = RootRunner(helper=h, prefix=(sys.executable,))
    assert r.run([["apt-clean"]]) == [{"ok": True}]


def test_passes_ops_as_single_json_argument(tmp_path):
    h = _helper(tmp_path, "import json,sys\nops=json.loads(sys.argv[1])\n"
                          "print(json.dumps([{'ok': True, 'n': len(ops)}]))\n")
    r = RootRunner(helper=h, prefix=(sys.executable,))
    assert r.run([["a"], ["b"]])[0]["n"] == 2


def test_pkexec_cancel_marks_all_ops_cancelled(tmp_path):
    h = _helper(tmp_path, "pass\n")
    r = RootRunner(helper=h, prefix=("sh", "-c", "exit 126", "--"))
    out = r.run([["apt-clean"], ["journal-vacuum", "100M"]])
    assert len(out) == 2 and all(o["cancelled"] for o in out)


def test_group_writable_helper_is_refused(tmp_path):
    h = _helper(tmp_path, "print('[]')\n")
    h.chmod(0o666)
    out = RootRunner(helper=h, prefix=(sys.executable,)).run([["apt-clean"]])
    assert out[0]["ok"] is False and "quyền ghi" in out[0]["error"]


def test_garbage_output_becomes_error(tmp_path):
    h = _helper(tmp_path, "print('oops')\n")
    out = RootRunner(helper=h, prefix=(sys.executable,)).run([["apt-clean"]])
    assert out[0]["ok"] is False


def test_empty_ops_returns_empty(tmp_path):
    assert RootRunner(helper=_helper(tmp_path, "pass\n"), prefix=(sys.executable,)).run([]) == []
