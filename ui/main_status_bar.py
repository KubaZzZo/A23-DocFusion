"""Main window top status bar."""
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from config import LLM_CONFIG
from llm.provider_presets import get_cloud_vendor_preset


TEXT_UNCONFIGURED_MODEL = "\u672a\u914d\u7f6e\u6a21\u578b"
TEXT_UNCONFIGURED_URL = "\u672a\u914d\u7f6e\u5730\u5740"


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
        label = preset.get("label", cloud.get("vendor", "OpenAI\u517c\u5bb9"))
        model = cloud.get("model") or preset.get("model_placeholder") or TEXT_UNCONFIGURED_MODEL
        url = cloud.get("base_url") or preset.get("base_url") or TEXT_UNCONFIGURED_URL

    return {
        "provider": provider,
        "label": label,
        "model": model,
        "url": url,
        "summary": f"{label} - {model}",
        "tooltip": f"\u5f53\u524d LLM: {label}\n\u6a21\u578b: {model}\n\u670d\u52a1\u5730\u5740: {url}",
    }


class MainStatusBar(QWidget):
    def __init__(self, on_settings_clicked=None, on_provider_changed=None, parent=None):
        super().__init__(parent)
        self.on_settings_clicked = on_settings_clicked
        self.on_provider_changed = on_provider_changed
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

        llm_label = QLabel("LLM\u5f15\u64ce")
        llm_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        top_layout.addWidget(llm_label)

        self.llm_combo = QComboBox()
        self.llm_combo.addItems(["ollama (\u672c\u5730)", "openai (\u4e91\u7aef)"])
        self.llm_combo.setCurrentIndex(0 if LLM_CONFIG["provider"] == "ollama" else 1)
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        self.llm_combo.setFixedWidth(160)
        top_layout.addWidget(self.llm_combo)

        self.lbl_llm_status = QLabel("\u25cf \u5c31\u7eea")
        self.lbl_llm_status.setStyleSheet("font-size: 11px; color: #52C41A; background: transparent;")
        top_layout.addWidget(self.lbl_llm_status)

        self.lbl_llm_model = QLabel("")
        self.lbl_llm_model.setStyleSheet("font-size: 12px; color: #333; background: transparent; font-weight: 600;")
        top_layout.addWidget(self.lbl_llm_model)

        self.lbl_llm_endpoint = QLabel("")
        self.lbl_llm_endpoint.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        top_layout.addWidget(self.lbl_llm_endpoint)

        top_layout.addStretch()

        self.btn_settings = QPushButton("\u8bbe\u7f6e")
        self.btn_settings.setFixedWidth(90)
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)

    def _open_settings(self):
        if self.on_settings_clicked:
            self.on_settings_clicked()

    def _on_llm_changed(self, index):
        LLM_CONFIG["provider"] = "ollama" if index == 0 else "openai"
        self.lbl_llm_status.setText("\u25cf \u5207\u6362\u4e2d")
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
