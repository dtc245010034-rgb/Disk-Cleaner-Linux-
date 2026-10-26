from disk_cleaner.core import sysinfo

MEMINFO = """MemTotal:        8000000 kB
MemFree:         1000000 kB
MemAvailable:    5000000 kB
SwapTotal:       4000000 kB
SwapFree:        3000000 kB
"""


def test_parse_meminfo_converts_kb_to_bytes():
    m = sysinfo.parse_meminfo(MEMINFO)
    assert m["MemTotal"] == 8_000_000 * 1024
    assert m["SwapFree"] == 3_000_000 * 1024


def test_memory_derived_values(monkeypatch):
    monkeypatch.setattr(sysinfo, "_read", lambda p: MEMINFO)
    mem = sysinfo.memory()
    assert mem["total"] == 8_000_000 * 1024
    assert mem["used"] == 3_000_000 * 1024
    assert mem["swap_used"] == 1_000_000 * 1024


def test_temperature_takes_max_and_handles_missing(tmp_path):
    assert sysinfo.temperature(tmp_path) is None
    (tmp_path / "hwmon0").mkdir()
    (tmp_path / "hwmon0" / "temp1_input").write_text("48000\n")
    (tmp_path / "hwmon0" / "temp2_input").write_text("52500\n")
    assert sysinfo.temperature(tmp_path) == 52.5


def test_top_processes_parses_ps(monkeypatch):
    out = "  123  45678 chrome\n   77   1024 my app name\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=10: (0, out, ""))
    assert sysinfo.top_processes(5) == [(123, "chrome", 45678 * 1024), (77, "my app name", 1024 * 1024)]


def test_top_processes_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=10: (1, "", "x"))
    assert sysinfo.top_processes() == []


def test_autostart_reads_names(tmp_path):
    d = tmp_path / ".config/autostart"
    d.mkdir(parents=True)
    (d / "a.desktop").write_text("[Desktop Entry]\nName=CopyQ\nExec=copyq\n")
    (d / "b.desktop").write_text("[Desktop Entry]\nExec=noname\n")
    assert sysinfo.autostart_apps(tmp_path) == ["CopyQ", "b"]


def test_cpu_meter_bounds(monkeypatch):
    samples = iter([(100, 200), (150, 400)])
    monkeypatch.setattr(sysinfo, "_read_cpu", lambda: next(samples))
    meter = sysinfo.CpuMeter()
    assert meter.percent() == 75.0  # dt=200, di=50


def test_partitions_returns_list():
    parts = sysinfo.partitions()
    assert isinstance(parts, list) and all({"mount", "total", "used"} <= set(p) for p in parts)
