"""Main window top status bar."""
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from config import LLM_CONFIG
from llm.provider_presets import get_cloud_vendor_preset
from ui.task_runner import TaskWorker, is_worker_running
from logger import get_logger

log = get_logger("ui.status_bar")

TEXT_UNCONFIGURED_MODEL = "未配置模型"
TEXT_UNCONFIGURED_URL = "未配置地址"

_STATUS_READY = ("● 就绪", "#52C41A")
_STATUS_UNKNOWN = ("● 未知", "#8C8C8C")
_STATUS_UNREACHABLE = ("● 未连接", "#FF4D4F")


def llm_status_snapshot(config: dict | None = None) -> dict:
    cfg = config or LLM_CONFIG
    provider = cfg.get("provider", "ollama")
    if provider == "ollama":
        ollama = cfg.get("ollama", {})
        label = "Ollama"
        model = ollama.get("model") or TEXT_UNCONFIGURED_MODEL
        url = ollama.get("base_url") or "http://localhost:11434"
    else:
        cloud = cfg.get("openai", {})
        preset = get_cloud_vendor_preset(cloud.get("vendor", "openai"))
        label = preset.get("label", cloud.get("vendor", "OpenAI兼容"))
        model = cloud.get("model") or preset.get("model_placeholder") or TEXT_UNCONFIGURED_MODEL
        url = cloud.get("base_url") or preset.get("base_url") or TEXT_UNCONFIGURED_URL
        proxy_url = cloud.get("proxy_url", "")
    if provider == "ollama":
        proxy_url = ""

    return {
        "provider": provider,
        "label": label,
        "model": model,
        "url": url,
        "proxy_url": proxy_url,
        "summary": f"{label} - {model}",
        "tooltip": (
            f"当前 LLM: {label}\n模型: {model}\n服务地址: {url}"
            + (f"\n代理地址: {proxy_url}" if proxy_url else "")
        ),
    }


class MainStatusBar(QWidget):
    def __init__(self, on_settings_clicked=None, on_provider_changed=None, parent=None):
        super().__init__(parent)
        self.on_settings_clicked = on_settings_clicked
        self.on_provider_changed = on_provider_changed
        self._health_worker = None
        self._build_ui()
        self.refresh_llm_status()

    def _build_ui(self):
        top_layout = QHBoxLayout(self)
        top_layout.setContentsMargins(16, 8, 16, 8)

        brand = QLabel("DocFusion")
        brand.setStyleSheet("font-size: 16px; font-weight: bold; color: #5B8DEF; background: transparent;")
        top_layout.addWidget(brand)

        ver = QLabel("v1.0")
        ver.setStyleSheet("font-size: 10px; color: #CCC; background: transparent; margin-top: 4px;")
        top_layout.addWidget(ver)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #E0E0E0; background: transparent;")
        sep.setFixedHeight(24)
        top_layout.addWidget(sep)

        llm_label = QLabel("LLM引擎")
        llm_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        top_layout.addWidget(llm_label)

        self.llm_combo = QComboBox()
        self.llm_combo.addItems(["ollama (本地)", "openai (云端)"])
        self.llm_combo.setCurrentIndex(0 if LLM_CONFIG["provider"] == "ollama" else 1)
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        self.llm_combo.setFixedWidth(160)
        top_layout.addWidget(self.llm_combo)

        self.lbl_llm_status = QLabel(_STATUS_UNKNOWN[0])
        self.lbl_llm_status.setStyleSheet(
            f"font-size: 11px; color: {_STATUS_UNKNOWN[1]}; background: transparent;"
        )
        top_layout.addWidget(self.lbl_llm_status)

        self.lbl_llm_model = QLabel("")
        self.lbl_llm_model.setStyleSheet("font-size: 12px; color: #333; background: transparent; font-weight: 600;")
        top_layout.addWidget(self.lbl_llm_model)

        self.lbl_llm_endpoint = QLabel("")
        self.lbl_llm_endpoint.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        top_layout.addWidget(self.lbl_llm_endpoint)

        top_layout.addStretch()

        self.btn_settings = QPushButton("设置")
        self.btn_settings.setFixedWidth(90)
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)

    def _open_settings(self):
        if self.on_settings_clicked:
            self.on_settings_clicked()

    def _on_llm_changed(self, index):
        LLM_CONFIG["provider"] = "ollama" if index == 0 else "openai"
        self.lbl_llm_status.setText("● 切换中")
        self.lbl_llm_status.setStyleSheet("font-size: 11px; color: #FAAD14; background: transparent;")
        self.refresh_llm_status()
        if self.on_provider_changed:
            self.on_provider_changed(LLM_CONFIG["provider"])

    def refresh_llm_status(self):
        snapshot = llm_status_snapshot()
        self.lbl_llm_model.setText(snapshot["summary"])
        self.lbl_llm_endpoint.setText(snapshot["url"])
        tooltip = snapshot["tooltip"]
        self.lbl_llm_status.setToolTip(tooltip)
        self.lbl_llm_model.setToolTip(tooltip)
        self.lbl_llm_endpoint.setToolTip(tooltip)

        self._set_status(*_STATUS_UNKNOWN)
        self._launch_health_check(snapshot)

    def _set_status(self, text: str, color: str):
        self.lbl_llm_status.setText(text)
        self.lbl_llm_status.setStyleSheet(f"font-size: 11px; color: {color}; background: transparent;")

    def _launch_health_check(self, snapshot: dict):
        if is_worker_running(self._health_worker):
            return
        self._health_worker = TaskWorker(
            lambda: _probe_llm_health(snapshot),
            error_prefix="llm health check",
        )
        self._health_worker.succeeded.connect(lambda ok: self._on_health_result(ok))
        self._health_worker.failed.connect(lambda _msg: self._set_status(*_STATUS_UNREACHABLE))
        self._health_worker.start()

    def _on_health_result(self, ok: bool):
        self._set_status(*_STATUS_READY if ok else _STATUS_UNREACHABLE)


def _probe_llm_health(snapshot: dict) -> bool:
    import httpx

    try:
        with httpx.Client(timeout=3, proxy=snapshot.get("proxy_url") or None, trust_env=True) as client:
            if snapshot["provider"] == "ollama":
                resp = client.get(f"{snapshot['url']}/api/tags")
                return resp.status_code == 200
            else:
                resp = client.get(
                    f"{snapshot['url']}/models",
                    headers={"Authorization": f"Bearer {_get_cloud_api_key()}"},
                )
                return resp.status_code in (200, 401)
    except Exception:
        return False


def _get_cloud_api_key() -> str:
    from config import LLM_CONFIG as cfg

    from settings_store import decode_key

    api_key_ref = cfg["openai"].get("api_key_ref", "")
    if api_key_ref:
        return decode_key(api_key_ref)
    return cfg["openai"].get("api_key", "")
