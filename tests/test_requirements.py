from pathlib import Path


def test_requirements_include_pytest_for_test_suite():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()

    assert any(line.strip().startswith("pytest>=8.0.0") for line in requirements)
