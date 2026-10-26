from disk_cleaner.core import cleaner, safety, scanner
from disk_cleaner.core.models import Category, CleanResult, Item, Risk


class Fake(Category):
    def __init__(self, id, items=None, needs_root=False, scan_error=None,
                 clean_error=None, available=True, risk=Risk.SAFE):
        self.id, self.title = id, id
        self._items = items if items is not None else [Item(id, id, 1000)]
        self.needs_root = needs_root
        self._scan_error, self._clean_error, self._available = scan_error, clean_error, available
        self.risk = risk
        self.clean_calls = []

    def available(self):
        return self._available

    def scan(self):
        if self._scan_error:
            raise self._scan_error
        return self._items

    def clean(self, items, dry_run):
        self.clean_calls.append(dry_run)
        if self._clean_error:
            raise self._clean_error
        return CleanResult(freed_bytes=sum(i.size_bytes for i in items))

    def root_ops(self, items):
        return [["apt-clean"]]


class FakeRunner:
    def __init__(self, ok=True, cancelled=False):
        self.ok, self.cancelled, self.calls = ok, cancelled, []

    def run(self, ops):
        self.calls.append(ops)
        if self.cancelled:
            return [{"ok": False, "cancelled": True, "error": "huỷ"} for _ in ops]
        if self.ok:
            return [{"ok": True} for _ in ops]
        return [{"ok": False, "error": "apt lỗi"} for _ in ops]


def test_scan_all_isolates_errors_and_skips_unavailable():
    cats = [Fake("a"), Fake("b", scan_error=RuntimeError("boom")),
            Fake("c", available=False), Fake("d")]
    out = list(scanner.scan_all(cats))
    assert [o.category.id for o in out] == ["a", "b", "d"]
    assert out[1].error and "boom" in out[1].error and out[1].items == []
    assert out[0].error is None


def test_run_cleanup_non_root(tmp_path):
    cat = Fake("a")
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=tmp_path / "log")
    assert res["a"].freed_bytes == 1000 and cat.clean_calls == [False]


def test_dry_run_never_calls_root_runner(tmp_path):
    cat, runner = Fake("r", needs_root=True), FakeRunner()
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=True, root_runner=runner,
                              log_path=tmp_path / "log")
    assert runner.calls == [] and res["r"].freed_bytes == 1000


def test_root_ops_are_batched_into_single_runner_call(tmp_path):
    a, b = Fake("a", needs_root=True), Fake("b", needs_root=True)
    runner = FakeRunner()
    res = cleaner.run_cleanup([(a, a._items), (b, b._items)], dry_run=False,
                              root_runner=runner, log_path=tmp_path / "log")
    assert len(runner.calls) == 1 and len(runner.calls[0]) == 2
    assert res["a"].freed_bytes == 1000 and res["b"].errors == []


def test_pkexec_cancel_is_skipped_not_error(tmp_path):  # Review Focus 5
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False,
                              root_runner=FakeRunner(cancelled=True), log_path=tmp_path / "log")
    assert res["r"].errors == [] and res["r"].freed_bytes == 0 and res["r"].skipped


def test_root_failure_reports_error_and_no_freed(tmp_path):
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False,
                              root_runner=FakeRunner(ok=False), log_path=tmp_path / "log")
    assert res["r"].errors == ["apt lỗi"] and res["r"].freed_bytes == 0


def test_root_without_runner_is_skipped(tmp_path):
    cat = Fake("r", needs_root=True)
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=tmp_path / "log")
    assert res["r"].skipped


def test_safety_error_is_captured_and_logged(tmp_path):
    log = tmp_path / "state" / "cleanup.log"
    cat = Fake("bad", clean_error=safety.SafetyError("cấm"))
    res = cleaner.run_cleanup([(cat, cat._items)], dry_run=False, log_path=log)
    assert "cấm" in res["bad"].errors[0]
    text = log.read_text(encoding="utf-8")
    assert "bad" in text and "RUN" in text


def test_empty_selection_is_ignored(tmp_path):
    cat = Fake("a")
    assert cleaner.run_cleanup([(cat, [])], dry_run=False, log_path=tmp_path / "log") == {}
