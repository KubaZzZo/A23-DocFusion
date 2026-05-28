from pathlib import Path


def test_gitignore_excludes_database_files():
    root = Path(__file__).resolve().parents[2]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "*.db" in gitignore
    assert "*.sqlite" in gitignore
    assert "*.sqlite3" in gitignore
