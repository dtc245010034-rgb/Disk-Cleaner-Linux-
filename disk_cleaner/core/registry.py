from __future__ import annotations

from pathlib import Path

from .categories import ClaudeOldVersions, fs_categories
from .models import Category
from .syscats import AptCache, JournalLogs, OldKernels, OldSnaps
from .tools import DockerDangling, DockerUnusedImages, DockerVolumes, npm_cache, pip_cache


def build_categories(home=None) -> list[Category]:
    """Thứ tự hiển thị: từ an toàn tới rủi ro."""
    home = Path(home) if home else Path.home()
    return [
        *fs_categories(home),
        npm_cache(home),
        pip_cache(home),
        ClaudeOldVersions(home),
        AptCache(),
        JournalLogs(),
        DockerDangling(),
        OldKernels(),
        OldSnaps(),
        DockerUnusedImages(),
        DockerVolumes(),
    ]
