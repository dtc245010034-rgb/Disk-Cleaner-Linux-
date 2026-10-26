# Disk Cleaner

Ứng dụng GTK3 để xem và dọn dung lượng ổ đĩa trên Ubuntu/XFCE: dọn theo nhóm có mức rủi ro,
khám phá đĩa (treemap), tìm file lớn / venv / node_modules bỏ quên, xem tổng quan hệ thống.

## Cài đặt

Yêu cầu: Ubuntu (hoặc Debian) có Python 3.12+ và GTK 3. Ubuntu Desktop đã có sẵn; nếu thiếu:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0
```

Tải về và cài vào menu ứng dụng (không cần root):

```bash
git clone https://github.com/dtc245010034-rgb/Disk-Cleaner-Linux-.git
cd Disk-Cleaner-Linux-
./install.sh
```

Sau đó mở **Menu ứng dụng → System → Disk Cleaner**. Hoặc chạy thẳng, không cần cài:

```bash
python3 -m disk_cleaner
```

Giữ nguyên thư mục đã tải về (mục menu trỏ vào đó). Gỡ mục menu: `./install.sh --uninstall`.

Thao tác cần root (APT, journal, kernel cũ, snap) sẽ hiện hộp mật khẩu của `pkexec` khi bấm **Dọn**.

> Đã thử trên Ubuntu 24.04 + XFCE. Các nhóm dọn không có trên máy (Docker, snap, Chrome...) sẽ tự ẩn.

## An toàn

- Mọi thao tác xoá đi qua `disk_cleaner/core/safety.py` (danh sách cấm, kiểm tra symlink, chặn xoá nguyên thư mục dự án).
- Mục **Nguy hiểm** (Docker volume) mặc định không tích và phải gõ `XOA` để xác nhận.
- Thao tác root chỉ nhận danh sách cố định trong `disk_cleaner/root_helper.py`.
- Log: `~/.local/state/disk-cleaner/cleanup.log`.
- Hãy tự xem lại danh sách trước khi bấm **Dọn**; phần mềm được cung cấp "nguyên trạng", không bảo hành.

## Kiểm thử

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Giấy phép

[MIT](LICENSE)
