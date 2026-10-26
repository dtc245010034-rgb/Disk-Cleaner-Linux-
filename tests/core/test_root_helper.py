import pytest

from disk_cleaner import root_helper as rh


def test_apt_clean():
    assert rh.validate("apt-clean", []) == ["apt-get", "clean"]


def test_journal_vacuum_valid_and_invalid():
    assert rh.validate("journal-vacuum", ["100M"]) == ["journalctl", "--vacuum-size=100M"]
    for bad in ("100", "5G;rm", "-1M", "0M", "100M --all", ""):
        with pytest.raises(ValueError):
            rh.validate("journal-vacuum", [bad])


def test_kernel_purge_valid():
    argv = rh.validate("kernel-purge",
                       ["linux-image-7.0.0-34-generic", "linux-headers-7.0.0-34-generic",
                        "linux-headers-7.0.0-34"], running_version="7.0.0-38")
    assert argv == ["apt-get", "purge", "-y", "linux-image-7.0.0-34-generic",
                    "linux-headers-7.0.0-34-generic", "linux-headers-7.0.0-34"]


def test_kernel_purge_rejects_running_kernel():
    with pytest.raises(ValueError):
        rh.validate("kernel-purge", ["linux-image-7.0.0-38-generic"], running_version="7.0.0-38")


def test_kernel_purge_rejects_injection_and_other_packages():
    for bad in ("linux-image-1.0; rm -rf /", "bash", "linux-image-generic-hwe-24.04",
                "linux-image-7.0.0-34-generic extra", "--force-yes", "../etc"):
        with pytest.raises(ValueError):
            rh.validate("kernel-purge", [bad], running_version="7.0.0-38")
    with pytest.raises(ValueError):
        rh.validate("kernel-purge", [], running_version="7.0.0-38")


def test_snap_remove():
    assert rh.validate("snap-remove", ["firefox", "1234"]) == ["snap", "remove", "firefox", "--revision=1234"]
    for args in (["Firefox", "1"], ["firefox", "1a"], ["firefox"], ["fire fox", "1"], ["-x", "1"]):
        with pytest.raises(ValueError):
            rh.validate("snap-remove", args)


def test_unknown_op_rejected():
    with pytest.raises(ValueError):
        rh.validate("rm", ["-rf", "/"])


def test_execute_reports_invalid_ops_without_running():
    out = rh.execute([["rm", "-rf", "/"], []], running_version="7.0.0-38")
    assert [o["ok"] for o in out] == [False, False]
    assert "không hợp lệ" in out[0]["error"].lower() or "không được phép" in out[0]["error"].lower()
