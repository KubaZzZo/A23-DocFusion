from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_dependencies_script_exists_and_installs_requirements():
    script = ROOT / "install_dependencies.bat"
    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "requirements.txt" in content
    assert "-m pip install" in content
    assert "Tesseract-OCR" in content
    assert "winget install --id=UB-Mannheim.TesseractOCR" in content
    assert "Start-Process -FilePath '%~f0'" in content
    assert "--install-tesseract-only" in content


def test_start_script_exists_and_launches_main():
    script = ROOT / "start_docfusion.bat"
    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "main.py" in content
    assert "install_dependencies.bat" in content
    assert "http://127.0.0.1:8000/docs" in content


def test_old_conflicting_scripts_removed():
    assert not (ROOT / "run.bat").exists()
    assert not (ROOT / "setup.bat").exists()
