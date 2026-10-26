#!/usr/bin/env bash
# Cài Disk Cleaner vào menu ứng dụng của người dùng (không cần root).
#   ./install.sh              cài / cập nhật mục menu
#   ./install.sh --uninstall  gỡ mục menu (không xoá thư mục dự án)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
TARGET="$APPS/disk-cleaner.desktop"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$TARGET"
    command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
    echo "Đã gỡ mục menu: $TARGET"
    exit 0
fi

if ! command -v python3 >/dev/null; then
    echo "Thiếu python3. Cài bằng: sudo apt install python3" >&2
    exit 1
fi
if ! python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null; then
    echo "Thiếu PyGObject/GTK3. Cài bằng: sudo apt install python3-gi gir1.2-gtk-3.0" >&2
    exit 1
fi

mkdir -p "$APPS"
sed "s|@DIR@|$DIR|" "$DIR/disk-cleaner.desktop.in" > "$TARGET"
chmod 644 "$TARGET"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true

echo "Đã cài: $TARGET"
echo "Mở menu ứng dụng > System > Disk Cleaner, hoặc chạy: python3 -m disk_cleaner"
echo "Lưu ý: giữ nguyên thư mục này ($DIR); di chuyển nó thì chạy lại ./install.sh."
