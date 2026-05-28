from pathlib import Path


def test_vps_docker_example_uses_bridge_network_and_loopback_port_mapping():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "--network host" not in readme
    assert "-p 127.0.0.1:8010:8010" in readme


def test_deployment_examples_run_service_as_docfusion_user():
    root = Path(__file__).resolve().parents[2]
    deploy_dir = root / "deploy"

    assert (deploy_dir / "docfusion-api.service").read_text(encoding="utf-8").count("User=docfusion") == 1
    assert (deploy_dir / "docfusion-toolkit-api.service").read_text(encoding="utf-8").count("User=docfusion") == 1


def test_nginx_example_reverse_proxies_main_api_and_toolkit_api():
    config = (Path(__file__).resolve().parents[2] / "deploy" / "nginx-docfusion.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://127.0.0.1:8000" in config
    assert "proxy_pass http://127.0.0.1:8010" in config
