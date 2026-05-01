"""LLM 设置对话框"""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config import BASE_DIR, LLM_CONFIG
from logger import get_logger
from llm.provider_health import ProviderHealthChecker, ProviderHealthResult
from llm.provider_presets import (
    CLOUD_VENDOR_PRESETS,
    build_provider_profile,
    extract_model_names,
    get_cloud_vendor_preset,
    normalize_models_url,
    probe_openai_compatible,
)
from settings_store import (
    apply_saved_settings as _apply_saved_settings,
    decode_key,
    encode_key,
    load_settings as _load_settings,
    save_settings as _save_settings,
)

SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
log = get_logger("ui.settings_dialog")

_normalize_models_url = normalize_models_url
_extract_model_names = extract_model_names
_probe_openai_compatible = probe_openai_compatible


def _format_provider_health_message(vendor_label: str, result: ProviderHealthResult) -> str:
    if result.models:
        return f"{vendor_label} 连接正常\n可用模型: {', '.join(result.models[:10])}"
    return f"{vendor_label} 连接正常\n{result.message}"


def _encode_key(key: str) -> str:
    return encode_key(key)


def _decode_key(encoded: str) -> str:
    return decode_key(encoded)


def load_settings() -> dict:
    return _load_settings(SETTINGS_FILE)


def save_settings(settings: dict):
    _save_settings(settings, SETTINGS_FILE)


def apply_saved_settings():
    _apply_saved_settings(SETTINGS_FILE, LLM_CONFIG)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM 设置")
        self.setMinimumWidth(500)
        self._init_ui()
        self._load_current()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        ollama_group = QGroupBox("Ollama（本地模型）")
        ollama_form = QFormLayout(ollama_group)
        self.ollama_url = QLineEdit()
        self.ollama_url.setPlaceholderText("http://localhost:11434")
        ollama_form.addRow("服务地址:", self.ollama_url)
        self.ollama_model = QLineEdit()
        self.ollama_model.setPlaceholderText("qwen2.5:7b")
        ollama_form.addRow("模型名称:", self.ollama_model)
        self.btn_test_ollama = QPushButton("测试连接")
        self.btn_test_ollama.clicked.connect(self._test_ollama)
        ollama_form.addRow("", self.btn_test_ollama)
        layout.addWidget(ollama_group)

        openai_group = QGroupBox("OpenAI / 兼容 API（云端）")
        openai_form = QFormLayout(openai_group)
        self.openai_vendor = QComboBox()
        for vendor_id, preset in CLOUD_VENDOR_PRESETS.items():
            self.openai_vendor.addItem(preset["label"], vendor_id)
        self.openai_vendor.currentIndexChanged.connect(self._on_vendor_changed)
        openai_form.addRow("云端供应商:", self.openai_vendor)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("sk-...")
        openai_form.addRow("API Key:", self.openai_key)
        self.openai_url = QLineEdit()
        self.openai_url.setPlaceholderText("https://api.openai.com/v1")
        openai_form.addRow("Base URL:", self.openai_url)
        self.openai_model = QLineEdit()
        self.openai_model.setPlaceholderText("gpt-4o-mini")
        openai_form.addRow("模型名称:", self.openai_model)
        self.btn_test_openai = QPushButton("测试连接")
        self.btn_test_openai.clicked.connect(self._test_openai)
        openai_form.addRow("", self.btn_test_openai)
        layout.addWidget(openai_group)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setStyleSheet("background-color: #909399;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)
        btn_bar.addWidget(self.btn_save)
        layout.addLayout(btn_bar)

    def _load_current(self):
        self.ollama_url.setText(LLM_CONFIG["ollama"]["base_url"])
        self.ollama_model.setText(LLM_CONFIG["ollama"]["model"])
        vendor = LLM_CONFIG["openai"].get("vendor", "openai")
        index = self.openai_vendor.findData(vendor)
        self.openai_vendor.setCurrentIndex(index if index >= 0 else self.openai_vendor.findData("custom"))
        self.openai_key.setText(LLM_CONFIG["openai"]["api_key"])
        self.openai_url.setText(LLM_CONFIG["openai"]["base_url"])
        self.openai_model.setText(LLM_CONFIG["openai"]["model"])
        self._apply_vendor_preset(self.openai_vendor.currentData(), preserve_values=True)

    def _apply_vendor_preset(self, vendor: str, preserve_values: bool = False):
        preset = get_cloud_vendor_preset(vendor)
        self.openai_key.setPlaceholderText(preset["api_key_placeholder"])
        self.openai_url.setPlaceholderText(preset["base_url"] or "https://api.example.com/v1")
        self.openai_model.setPlaceholderText(preset["model_placeholder"])

        if not preserve_values:
            self.openai_url.setText(preset["base_url"])
            if not self.openai_model.text().strip():
                self.openai_model.setText(preset["model_placeholder"])

    def _on_vendor_changed(self, index: int):
        vendor = self.openai_vendor.itemData(index)
        self._apply_vendor_preset(vendor)

    def _test_ollama(self):
        import httpx

        url = self.ollama_url.text().strip() or "http://localhost:11434"
        try:
            resp = httpx.get(f"{url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if models:
                QMessageBox.information(self, "连接成功", f"Ollama 连接正常\n可用模型: {', '.join(models[:10])}")
            else:
                QMessageBox.warning(self, "连接成功", "Ollama 已连接，但未找到已下载的模型")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法连接到 Ollama\n地址: {url}\n错误: {e}")

    def _test_openai(self):
        api_key = self.openai_key.text().strip()
        base_url = self.openai_url.text().strip() or "https://api.openai.com/v1"
        vendor_label = self.openai_vendor.currentText()
        if not api_key:
            QMessageBox.warning(self, "配置不完整", "请先填写 API Key")
            return

        profile = build_provider_profile(
            {
                "vendor": self.openai_vendor.currentData() or "openai",
                "api_key": api_key,
                "base_url": base_url,
                "model": self.openai_model.text().strip(),
            }
        )
        result = ProviderHealthChecker().check_openai_compatible(profile)
        if result.ok:
            QMessageBox.information(self, "连接成功", _format_provider_health_message(vendor_label, result))
        else:
            QMessageBox.critical(
                self,
                "连接失败",
                f"无法连接到 {vendor_label}\n地址: {result.url}\n错误: {result.message}",
            )

    def _save(self):
        LLM_CONFIG["ollama"]["base_url"] = self.ollama_url.text().strip() or "http://localhost:11434"
        LLM_CONFIG["ollama"]["model"] = self.ollama_model.text().strip() or "qwen2.5:7b"
        LLM_CONFIG["openai"]["vendor"] = self.openai_vendor.currentData() or "openai"
        LLM_CONFIG["openai"]["api_key"] = self.openai_key.text().strip()
        LLM_CONFIG["openai"]["base_url"] = self.openai_url.text().strip() or "https://api.openai.com/v1"
        LLM_CONFIG["openai"]["model"] = self.openai_model.text().strip() or "gpt-4o-mini"

        settings = {
            "provider": LLM_CONFIG["provider"],
            "ollama_url": LLM_CONFIG["ollama"]["base_url"],
            "ollama_model": LLM_CONFIG["ollama"]["model"],
            "openai_vendor": LLM_CONFIG["openai"]["vendor"],
            "openai_key": _encode_key(LLM_CONFIG["openai"]["api_key"]),
            "openai_url": LLM_CONFIG["openai"]["base_url"],
            "openai_model": LLM_CONFIG["openai"]["model"],
        }
        save_settings(settings)
        QMessageBox.information(self, "保存成功", "设置已保存并生效")
        self.accept()
