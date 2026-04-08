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
