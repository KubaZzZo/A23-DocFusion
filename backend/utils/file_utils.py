"""文件工具函数"""
import re
import shutil
from pathlib import Path
from datetime import datetime


_UNSAFE_FILENAME_CHARS = re.compile(r"[\x00-\x1f\x7f<>:\"/\\|?*]")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_upload_filename(filename: str, default_stem: str = "upload") -> str:
    """Return a safe basename for storing a client-provided upload filename."""
    raw_name = Path(str(filename or "")).name
    name = _UNSAFE_FILENAME_CHARS.sub("_", raw_name).strip(" ._")
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem.strip(" ._") or default_stem
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = f"{stem}_file"
    safe_name = f"{stem}{suffix}" if suffix else stem
    return safe_name[:180] or default_stem


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

    def write_bytes_exclusive(self, path: str | Path, content: bytes) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            tracked = self.track(target)
            handle.write(content)
        return tracked

    def write_bytes_unique(self, path: str | Path, content: bytes) -> Path:
        target = Path(path)
        for attempt in range(100):
            candidate = target if attempt == 0 else self._collision_path(target, attempt)
            try:
                return self.write_bytes_exclusive(candidate, content)
            except FileExistsError:
                continue
        raise FileExistsError(f"Could not reserve a unique file path for {target.name}")

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

    @staticmethod
    def _collision_path(path: Path, attempt: int) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return path.with_name(f"{path.stem}_{timestamp}_{attempt}{path.suffix}")
