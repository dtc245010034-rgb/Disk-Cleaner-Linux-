from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .fsutil import dir_size


@dataclass
class DirEntry:
    name: str
    path: Path
    size: int
    is_dir: bool


def list_children(path) -> list[DirEntry]:
    """Các mục con trực tiếp của path kèm dung lượng, giảm dần. Bỏ symlink."""
    out: list[DirEntry] = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    is_dir = e.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                out.append(DirEntry(e.name, Path(e.path), dir_size(e.path), is_dir))
    except OSError:
        return []
    return sorted(out, key=lambda d: -d.size)


def _worst(row: list[float], side: float) -> float:
    s = sum(row)
    return max(max(side * side * r / (s * s), s * s / (side * side * r)) for r in row)


def squarify(sizes: list[float], x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Treemap 'squarified': trả về (x, y, w, h) cho mỗi size, giữ nguyên thứ tự.
    `sizes` nên được sắp giảm dần."""
    n = len(sizes)
    if n == 0:
        return []
    total = float(sum(sizes))
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, 0.0, 0.0)] * n
    areas = [max(s * w * h / total, 1e-12) for s in sizes]
    rects: list[tuple[float, float, float, float]] = []
    i = 0
    while i < n:
        side = min(w, h)
        row = [areas[i]]
        j = i + 1
        while j < n and _worst(row + [areas[j]], side) <= _worst(row, side):
            row.append(areas[j])
            j += 1
        s = sum(row)
        if w >= h:                       # cột bên trái, rộng s/h
            cw = s / h
            cy = y
            for a in row:
                ch = a / cw
                rects.append((x, cy, cw, ch))
                cy += ch
            x += cw
            w -= cw
        else:                            # hàng phía trên, cao s/w
            rh = s / w
            cx = x
            for a in row:
                cw2 = a / rh
                rects.append((cx, y, cw2, rh))
                cx += cw2
            y += rh
            h -= rh
        i = j
    return rects
