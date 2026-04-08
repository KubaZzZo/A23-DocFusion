"""文件工具函数测试"""
import pytest
from pathlib import Path
from utils.file_utils import safe_copy

TEST_DIR = Path(__file__).parent / "test_data"
TEST_DIR.mkdir(exist_ok=True)


class TestSafeCopy:
    def test_copy_new_file(self):
        src = TEST_DIR / "source.txt"
        src.write_text("hello", encoding="utf-8")
        dest_dir = TEST_DIR / "dest_new"
        dest_dir.mkdir(exist_ok=True)

        result = safe_copy(str(src), dest_dir)
        assert result.exists()
        assert result.name == "source.txt"
        assert result.read_text(encoding="utf-8") == "hello"

        # cleanup
        result.unlink()
        dest_dir.rmdir()

    def test_copy_duplicate_gets_timestamp(self):
        src = TEST_DIR / "dup.txt"
        src.write_text("content", encoding="utf-8")
        dest_dir = TEST_DIR / "dest_dup"
        dest_dir.mkdir(exist_ok=True)

        # 第一次复制
        r1 = safe_copy(str(src), dest_dir)
        assert r1.name == "dup.txt"

        # 第二次复制同名文件，应加时间戳
        r2 = safe_copy(str(src), dest_dir)
        assert r2.name != "dup.txt"
        assert "dup_" in r2.name
        assert r2.exists()

        # cleanup
        r1.unlink()
        r2.unlink()
        dest_dir.rmdir()
