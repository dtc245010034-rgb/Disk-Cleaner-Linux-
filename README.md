# Disk Cleaner

Ứng dụng GTK3 để xem và dọn dung lượng ổ đĩa trên Ubuntu/XFCE: dọn theo nhóm có mức rủi ro,
khám phá đĩa (treemap), tìm file lớn / venv / node_modules bỏ quên, xem tổng quan hệ thống.

## Chạy

```bash
python3 -m disk_cleaner
```

Yêu cầu: Python 3.12 và PyGObject (GTK 3) — Ubuntu desktop có sẵn.
Thao tác cần root (APT, journal, kernel cũ, snap) sẽ hiện hộp mật khẩu của `pkexec` khi bấm **Dọn**.

## Cài vào menu ứng dụng

```bash
sed "s|@DIR@|$PWD|" disk-cleaner.desktop.in > ~/.local/share/applications/disk-cleaner.desktop
```

## An toàn

- Mọi thao tác xoá đi qua `disk_cleaner/core/safety.py` (danh sách cấm, kiểm tra symlink, chặn xoá nguyên thư mục dự án).
- Mục **Nguy hiểm** (Docker volume) mặc định không tích và phải gõ `XOA` để xác nhận.
- Thao tác root chỉ nhận danh sách cố định trong `disk_cleaner/root_helper.py`.
- Log: `~/.local/state/disk-cleaner/cleanup.log`.

## Kiểm thử

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
