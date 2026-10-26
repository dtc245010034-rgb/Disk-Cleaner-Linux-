# Disk Cleaner — Thiết kế

Ngày: 2026-10-26 · Trạng thái: chờ người dùng duyệt spec

## 1. Mục tiêu

Một ứng dụng desktop trực quan để người dùng (máy Ubuntu 24.04, XFCE, ổ `/` 60 GB) thấy
máy đang tốn dung lượng ở đâu, chọn từng mục rồi dọn, không phải gõ lệnh hay nhờ trợ lý mỗi lần.
Dựa trên các thao tác đã thực hiện thủ công ở phiên kiểm tra máy ngày 2026-10-26.

**Tiêu chí thành công**
- Mở app, thấy ngay mục nào đáng dọn kèm dung lượng.
- Bấm dọn, ổ được giải phóng đúng gần với số ước tính (sai lệch có báo cáo thực tế sau dọn).
- Không xoá nhầm dữ liệu người dùng (tài liệu, mã nguồn dự án, cookie/mật khẩu trình duyệt, Docker volume ngoài ý muốn).

**Ngoài phạm vi (YAGNI)**: chạy nền/định kỳ, gỡ cài đặt ứng dụng, quản lý Steam (chỉ hiển thị dung lượng),
dọn trên máy khác, hỗ trợ distro khác ngoài Ubuntu/XFCE, đóng gói `.deb`.

## 2. Quyết định đã chốt

| Chủ đề | Quyết định |
|---|---|
| Dạng app | Desktop, Python 3.12 + GTK3 (PyGObject, đã có sẵn trên máy) |
| Quyền root | Chạy bằng quyền user; thao tác cần root đi qua `pkexec` khi bấm Dọn |
| Chức năng | 4 tab: Dọn dẹp, Khám phá đĩa, File lớn, Hệ thống |
| Kiến trúc | Tách `core/` (không GUI) và `ui/` (GTK3); script `root_helper.py` cho thao tác root |
| Icon | Adwaita symbolic icons + nhãn rủi ro bằng CSS; có icon SVG dự phòng |
| Ngôn ngữ giao diện | Tiếng Việt |
| Vị trí dự án | `~/disk-cleaner/` |

## 3. Cấu trúc

```
~/disk-cleaner/
├── disk_cleaner/
│   ├── __main__.py          # điểm vào: python3 -m disk_cleaner
│   ├── core/
│   │   ├── categories.py    # định nghĩa nhóm dọn (id, tên, icon, risk, needs_root, scan(), clean())
│   │   ├── scanner.py       # chạy scan() các nhóm, trả ScanResult (không xoá gì)
│   │   ├── cleaner.py       # chạy clean() có dry_run, trả CleanResult (MB thu hồi, lỗi)
│   │   ├── safety.py        # whitelist/blacklist đường dẫn, mọi thao tác xoá phải qua đây
│   │   ├── diskmap.py       # quét cây thư mục (du-like) cho treemap
│   │   ├── bigfiles.py      # file lớn, node_modules/venv/build bị bỏ quên
│   │   ├── sysinfo.py       # RAM, swap, CPU, nhiệt độ, phân vùng, top tiến trình, autostart
│   │   └── logging_.py      # ghi ~/.local/state/disk-cleaner/cleanup.log
│   ├── ui/
│   │   ├── app.py           # cửa sổ chính, thanh dung lượng ổ, Notebook 4 tab
│   │   ├── cleanup_tab.py
│   │   ├── diskmap_tab.py   # treemap vẽ bằng Cairo
│   │   ├── bigfiles_tab.py
│   │   ├── system_tab.py
│   │   ├── widgets.py       # CategoryRow, RiskBadge, UsageBar, ConfirmDialog
│   │   ├── style.css        # pill màu, thẻ, thanh dung lượng, theme sáng/tối
│   │   └── icons/           # SVG dự phòng
│   └── root_helper.py       # chạy bằng pkexec; chỉ nhận tên thao tác cố định
├── tests/
├── disk-cleaner.desktop
└── README.md
```

Quy tắc phụ thuộc: `core/` không import GTK. `ui/` chỉ gọi `core/`. `root_helper.py` độc lập,
chỉ dùng thư viện chuẩn.

## 4. Mô hình dữ liệu

```python
class Risk(Enum): SAFE, RELOADABLE, DANGEROUS   # An toàn / Tải lại được / Nguy hiểm

@dataclass
class Item:                  # một dòng chọn được trong UI
    id: str                  # ví dụ "npm-cache", "docker-volume:dtc245010034_db_data"
    label: str
    detail: str              # mô tả một dòng (vd tên project của volume)
    size_bytes: int
    locked: bool = False     # vd kernel đang chạy; không cho tích chọn

class Category(Protocol):
    id: str; title: str; icon: str; risk: Risk; needs_root: bool
    def available(self) -> bool            # công cụ có tồn tại không (docker, snap...)
    def scan(self) -> list[Item]           # chỉ đọc
    def clean(self, items, dry_run) -> CleanResult
```

`CleanResult`: `freed_bytes`, `errors: list[str]`, `skipped: list[str]`.

## 5. Các nhóm dọn

| Nhóm | Đo | Dọn | Risk | Root |
|---|---|---|---|---|
| Cache npm | `~/.npm` | `npm cache clean --force` | SAFE | không |
| Cache pip | `~/.cache/pip` | `pip cache purge` | SAFE | không |
| Cache puppeteer | `~/.cache/puppeteer` | xoá nội dung | SAFE | không |
| Thùng rác | `~/.local/share/Trash` | xoá nội dung | SAFE | không |
| Thumbnails/shader cache | `~/.cache/{thumbnails,mesa_shader_cache,...}` (tên cố định) | xoá nội dung | SAFE | không |
| Cache Chrome | `~/.cache/google-chrome`; `Service Worker/CacheStorage`, `GPUCache`, `Dawn*Cache`, `component_crx_cache`, `extensions_crx_cache` trong `~/.config/google-chrome` | xoá đúng các thư mục đó; **không** đụng cookie, mật khẩu, IndexedDB, extension, `ScriptCache` | SAFE | không |
| Cache VS Code | `~/.config/Code/{CachedExtensionVSIXs,Cache}` | xoá nội dung | SAFE | không |
| Bản Claude Code cũ | `~/.local/share/claude/versions`, `~/.config/Claude/claude-code`, `~/.local/bin/agy.*.old` | giữ bản mới nhất **và** bản đang được tiến trình nào chạy (kiểm tra `/proc/*/exe`), xoá phần còn lại | SAFE | không |
| APT cache | `/var/cache/apt` | `apt-get clean` | SAFE | có |
| Journal | `journalctl --disk-usage` | `journalctl --vacuum-size=100M` | SAFE | có |
| Kernel cũ | gói `linux-image-*`/`linux-headers-*` trừ kernel đang chạy và kernel mới nhất | `apt-get purge` đúng gói | RELOADABLE | có |
| Snap revision cũ | `snap list --all` (disabled) | `snap remove --revision` | RELOADABLE | có |
| Docker: image dangling | `docker system df` | `docker image prune -f` | SAFE | không |
| Docker: image không dùng | `docker images`, trừ image gắn với container | chọn từng image `docker rmi` | RELOADABLE | không |
| Docker: volume | `docker volume ls` + dung lượng, kèm label compose project | chọn từng volume `docker volume rm` | DANGEROUS | không |
| Venv/node_modules bỏ quên | `bigfiles.py` | xoá từng thư mục đã chọn | RELOADABLE | không |

Ghi chú: Steam chỉ hiển thị dung lượng ở tab Hệ thống/Khám phá đĩa, không có hành động xoá.
Khi một nhóm `available()` trả `False` (không có docker/snap) thì ẩn nhóm đó.

## 6. An toàn (`safety.py`)

- **Whitelist gốc xoá**: chỉ cho phép xoá bên trong các thư mục cache đã khai báo ở `categories.py`
  và các thư mục do `bigfiles` phát hiện (tên cuối thuộc `{node_modules, venv, .venv, __pycache__, build, dist}`).
- **Blacklist cứng**: `/`, `/home`, `$HOME`, `/etc`, `/usr`, `/var` (trừ đường dẫn con whitelist),
  `~/Documents`, `~/Pictures`, `~/Desktop`, `~/Downloads`, `~/.ssh`, `~/.gnupg`, và gốc của mọi
  thư mục có `.git`, `package.json`, `requirements.txt`, `docker-compose*.yml` (chặn xoá nguyên project;
  chỉ cho xoá thư mục con thuộc whitelist bên trong project).
- Giải quyết symlink trước khi kiểm tra (`os.path.realpath`); từ chối nếu thoát khỏi whitelist.
- Mọi hàm xoá của `cleaner` gọi `safety.assert_deletable(path)`; vi phạm → `SafetyError`, không xoá, ghi log.
- Mức DANGEROUS: mặc định không tích; hộp xác nhận bắt gõ `XOA`.
- Kernel đang chạy và kernel mới nhất có `locked=True`.

## 7. Thao tác root (`root_helper.py`)

- Chạy `pkexec python3 /đường/dẫn/root_helper.py <op> [args]`; một lần xác thực cho cả lượt dọn
  (UI gom các thao tác root thành một lần gọi nhiều op tuần tự).
- Chỉ nhận op trong danh sách cố định: `apt-clean`, `journal-vacuum <size>`,
  `kernel-purge <pkg>...`, `snap-remove <name> <rev>`.
- Mỗi tham số được kiểm tra bằng regex chặt (tên gói `^linux-(image|headers)-[0-9][\w.\-]*$`,
  kích thước `^\d+[MG]$`, ...) và gói kernel bị từ chối nếu là kernel đang chạy.
- Không dùng `shell=True`; không nhận lệnh tuỳ ý.
- Trả kết quả từng op dạng JSON trên stdout; UI đọc để hiển thị.
- Đường dẫn file helper phải thuộc cài đặt của app và không ghi được bởi nhóm/người khác
  (kiểm tra trước khi gọi `pkexec`).

## 8. Giao diện

- **Cửa sổ chính**: thanh dung lượng ổ `/` ở trên cùng (bo góc; xanh <80%, vàng 80–90%, đỏ >90%,
  kèm "Trống X GB"), `Gtk.Notebook` 4 tab có icon, theme sáng/tối theo hệ thống.
- **Tab Dọn dẹp**: các nhóm dạng thẻ: checkbox, icon, tiêu đề, mô tả, `RiskBadge`, dung lượng
  căn phải (đậm), ổ khoá nhỏ nếu cần root. Nhóm Docker image/volume và Venv mở rộng thành từng dòng.
  Mục SAFE tích sẵn; RELOADABLE/DANGEROUS không. Footer: "Đã chọn X", nút **Quét lại**,
  nút **Dọn đã chọn** (nổi bật). Xác nhận liệt kê đúng các mục. Tiến trình + log từng bước;
  cuối cùng quét lại và báo "Đã thu hồi X MB".
- **Tab Khám phá đĩa**: treemap Cairo cho `~` hoặc `/`, nhấp để đi sâu, breadcrumb để lên,
  chuột phải "Mở trong Thunar". Chỉ xem.
- **Tab File lớn**: bảng file >200 MB và `node_modules`/`venv`/`.venv`/`__pycache__`/`build`/`dist`;
  cột đường dẫn, dung lượng, lần dùng gần nhất; tích và xoá có xác nhận; mục bị `safety` chặn
  không có nút xoá.
- **Tab Hệ thống**: RAM, swap, CPU, nhiệt độ, phân vùng, top 10 tiến trình theo RAM,
  app khởi động cùng máy; tự làm mới mỗi 2 giây khi tab đang mở. Chỉ xem.
- Quét/dọn chạy luồng nền (GLib idle để cập nhật UI), kết quả hiện dần theo nhóm.

**Icon** (Adwaita symbolic, kèm SVG dự phòng trong `ui/icons/`)

| Vị trí | Icon |
|---|---|
| Tab Dọn dẹp / Khám phá đĩa / File lớn / Hệ thống | `edit-clear-all-symbolic` / `drive-harddisk-symbolic` / `system-search-symbolic` / `computer-symbolic` |
| Thùng rác; cache; gói (docker/snap/apt/kernel); journal | `user-trash-symbolic`; `folder-symbolic`; `package-x-generic-symbolic`; `view-list-symbolic` |
| Cần root; quét lại; xoá | `security-high-symbolic`; `view-refresh-symbolic`; `edit-delete-symbolic` |
| Nhãn An toàn / Tải lại được / Nguy hiểm | `emblem-ok-symbolic` (xanh) / `dialog-warning-symbolic` (hổ phách) / `dialog-error-symbolic` (đỏ) |

## 9. Xử lý lỗi và log

- Lỗi của một nhóm chỉ đánh dấu nhóm đó (kèm lý do); các nhóm khác chạy tiếp.
- Công cụ vắng mặt → nhóm ẩn, không báo lỗi.
- Huỷ hộp mật khẩu `pkexec` → bỏ qua mọi mục cần root, báo rõ.
- `SafetyError` → dừng mục đó, không xoá, ghi log.
- Mọi thao tác xoá ghi `~/.local/state/disk-cleaner/cleanup.log`: thời gian, mục, dry-run hay thật, số byte, lỗi.

## 10. Kiểm thử

- `pytest` cho `core/` dùng thư mục giả trong `tmp_path`: scanner đo đúng; cleaner xoá đúng và
  `dry_run` không xoá gì; `safety` chặn mọi mục blacklist, symlink thoát whitelist, thư mục project.
- Docker/snap/apt/journalctl: mock `subprocess` (không chạy lệnh thật); kiểm tra đúng tham số lệnh,
  trích xuất đúng dung lượng từ output mẫu.
- `root_helper`: test hàm kiểm tra tham số (hợp lệ/không hợp lệ, kernel đang chạy bị từ chối); không gọi `pkexec` trong test.
- Giao diện: chạy app thật, chụp màn hình từng tab để người dùng xem (không viết unit test GTK).
- Kiểm tra cuối: chạy quét thật trên máy (chỉ đọc) so với số `du`/`docker system df`; dọn thử một mục SAFE nhỏ.

## 11. Thứ tự triển khai

1. Khung dự án, `safety.py`, `categories`/`scanner`/`cleaner` + test.
2. `root_helper.py` + test; UI cửa sổ chính + tab Dọn dẹp.
3. Tab Hệ thống (đơn giản nhất).
4. Tab File lớn.
5. Tab Khám phá đĩa (treemap).
6. `.desktop`, README, kiểm tra cuối.
