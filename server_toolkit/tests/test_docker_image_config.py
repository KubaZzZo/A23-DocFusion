from pathlib import Path


def test_dockerfile_declares_healthcheck():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"

    text = dockerfile.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in text
    assert "curl -f http://127.0.0.1:8010/healthz" in text
    assert "http://127.0.0.1:8010/healthz" in text


def test_readme_vps_run_command_avoids_public_listener_and_env_token():
    readme = Path(__file__).resolve().parents[1] / "README.md"

    text = readme.read_text(encoding="utf-8")

    assert "-e DOCFUSION_API_TOKEN=" not in text
    assert "DOCFUSION_API_TOKEN_FILE" in text
    assert "-p 127.0.0.1:8010:8010" in text
