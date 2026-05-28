import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_utils import FileTransaction, sanitize_upload_filename


def test_write_bytes_unique_does_not_overwrite_existing_file(tmp_path):
    target = tmp_path / "same-name.txt"
    target.write_text("original", encoding="utf-8")

    with FileTransaction() as tx:
        saved = tx.write_bytes_unique(target, b"new content")
        tx.commit()

    assert target.read_text(encoding="utf-8") == "original"
    assert saved != target
    assert saved.name.startswith("same-name_")
    assert saved.read_bytes() == b"new content"


def test_uncommitted_unique_write_rolls_back_only_created_file(tmp_path):
    target = tmp_path / "same-name.txt"
    target.write_text("original", encoding="utf-8")

    try:
        with FileTransaction() as tx:
            saved = tx.write_bytes_unique(target, b"new content")
            raise RuntimeError("abort")
    except RuntimeError:
        pass

    assert target.read_text(encoding="utf-8") == "original"
    assert not saved.exists()


def test_sanitize_upload_filename_removes_path_and_special_characters():
    assert sanitize_upload_filename(r"..\..\CON?.docx") == "CON_file.docx"
    assert sanitize_upload_filename(" report;\r\nbad?.xlsx ") == "report;__bad.xlsx"
    assert sanitize_upload_filename("...txt", default_stem="upload") == "txt"
