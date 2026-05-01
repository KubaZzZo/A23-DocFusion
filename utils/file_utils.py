"""文件工具函数"""
import shutil
from pathlib import Path
from datetime import datetime


def safe_copy(src: str, dest_dir: Path) -> Path:
    """安全复制文件到目标目录，同名文件自动加时间戳避免覆盖"""
    src_path = Path(src)
    dest = dest_dir / src_path.name

    if dest.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"{src_path.stem}_{timestamp}{src_path.suffix}"

    shutil.copyfile(src, dest)
    dest.chmod(0o666)
    return dest


class FileTransaction:
    """Track newly created files and remove them unless the caller commits."""

    def __init__(self):
        self._paths: list[Path] = []
        self._committed = False

    def track(self, path: str | Path) -> Path:
        tracked = Path(path)
        self._paths.append(tracked)
        return tracked

    def write_bytes(self, path: str | Path, content: bytes) -> Path:
        tracked = self.track(path)
        tracked.write_bytes(content)
        return tracked

    def commit(self):
        self._committed = True

    def rollback(self):
        for path in reversed(self._paths):
            path.unlink(missing_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None or not self._committed:
            self.rollback()
        return False
