"""LLM设置对话框"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from config import LLM_CONFIG
from config import BASE_DIR
from logger import get_logger
from settings_store import (
    apply_saved_settings as _apply_saved_settings,
    decode_key,
    encode_key,
    load_settings as _load_settings,
    save_settings as _save_settings,
)

SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
log = get_logger("ui.settings_dialog")


CLOUD_VENDOR_PRESETS = {
    "openai": {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model_placeholder": "gpt-4o-mini",
        "api_key_placeholder": "sk-...",
    },
    "deepseek": {
        "id": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model_placeholder": "deepseek-chat",
        "api_key_placeholder": "sk-...",
    },
    "moonshot": {
        "id": "moonshot",
        "label": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model_placeholder": "moonshot-v1-8k",
        "api_key_placeholder": "sk-...",
    },
    "qwen": {
        "id": "qwen",
        "label": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_placeholder": "qwen-plus",
        "api_key_placeholder": "sk-...",
    },
    "zhipu": {
        "id": "zhipu",
        "label": "智谱",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model_placeholder": "glm-4-plus",
        "api_key_placeholder": "sk-...",
    },
    "claude_compatible": {
        "id": "claude_compatible",
        "label": "Claude（兼容接口）",
        "base_url": "",
        "model_placeholder": "claude-3-5-sonnet",
        "api_key_placeholder": "兼容接口提供的 API Key",
    },
    "custom": {
        "id": "custom",
        "label": "自定义兼容接口",
        "base_url": "",
        "model_placeholder": "your-model-name",
        "api_key_placeholder": "your-api-key",
    },
}


def get_cloud_vendor_preset(vendor: str) -> dict:
    return CLOUD_VENDOR_PRESETS.get(vendor, CLOUD_VENDOR_PRESETS["custom"])


def _normalize_models_url(base_url: str) -> str:
    url = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if not url:
        url = "https://api.openai.com/v1"
    if url.endswith("/models"):
        return url
    return f"{url}/models"


def _extract_model_names(payload) -> list[str]:
    if payload is None or isinstance(payload, str):
        return []

    items = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        elif isinstance(payload.get("models"), list):
            items = payload.get("models", [])
        else:
            return []
    elif isinstance(payload, list):
        items = payload
    else:
        data = getattr(payload, "data", None)
        if isinstance(data, list):
            items = data
        elif data is not None:
            items = [data]
        else:
            return []

    names = []
    for item in items:
        if isinstance(item, str):
            if item:
                names.append(item)
            continue
        if isinstance(item, dict):
            name = item.get("id") or item.get("name") or item.get("model")
            if name:
                names.append(str(name))
            continue
        name = getattr(item, "id", None) or getattr(item, "name", None) or getattr(item, "model", None)
        if name:
            names.append(str(name))
    return names


def _probe_openai_compatible(api_key: str, base_url: str) -> tuple[list[str], str]:
    import httpx

    url = _normalize_models_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}"}
    response = httpx.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        return [], "???????????? JSON ????"

    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"].get("message") or str(payload["error"])
        raise RuntimeError(error)

    return _extract_model_names(payload), ""


def _encode_key(key: str) -> str:
    """对 API Key 进行 base64 编码，避免明文存储"""
    return encode_key(key)


def _decode_key(encoded: str) -> str:
    """解码 API Key"""
    return decode_key(encoded)


def load_settings() -> dict:
    """从文件加载设置"""
    return _load_settings(SETTINGS_FILE)


def save_settings(settings: dict):
    """保存设置到文件"""
    _save_settings(settings, SETTINGS_FILE)


def apply_saved_settings():
    """启动时应用已保存的设置到 LLM_CONFIG"""
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

        # Ollama 设置
        ollama_group = QGroupBox("Ollama (本地模型)")
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

        # OpenAI 设置
        openai_group = QGroupBox("OpenAI / 兼容API (云端)")
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

        # 按钮
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
                QMessageBox.information(self, "连接成功",
                                        f"Ollama 连接正常\n可用模型: {', '.join(models[:10])}")
            else:
                QMessageBox.warning(self, "连接成功", "Ollama 已连接，但未找到已下载的模型")
        except Exception as e:
            QMessageBox.critical(self, "连接失败",
                                 f"无法连接到 Ollama\n地址: {url}\n错误: {e}")

    def _test_openai(self):
        api_key = self.openai_key.text().strip()
        base_url = self.openai_url.text().strip() or "https://api.openai.com/v1"
        vendor_label = self.openai_vendor.currentText()
        if not api_key:
            QMessageBox.warning(self, "配置不完整", "请先填写 API Key")
            return

        try:
            names, note = _probe_openai_compatible(api_key, base_url)
            if names:
                QMessageBox.information(
                    self,
                    "连接成功",
                    f"{vendor_label} 连接正常\n可用模型: {', '.join(names[:10])}",
                )
            else:
                extra = note or "兼容接口已响应，但未返回标准模型列表"
                QMessageBox.information(self, "连接成功", f"{vendor_label} 连接正常\n{extra}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "连接失败",
                f"无法连接到 {vendor_label}\n地址: {_normalize_models_url(base_url)}\n错误: {e}",
            )

    def _save(self):
        # 更新运行时配置
        LLM_CONFIG["ollama"]["base_url"] = self.ollama_url.text().strip() or "http://localhost:11434"
        LLM_CONFIG["ollama"]["model"] = self.ollama_model.text().strip() or "qwen2.5:7b"
        LLM_CONFIG["openai"]["vendor"] = self.openai_vendor.currentData() or "openai"
        LLM_CONFIG["openai"]["api_key"] = self.openai_key.text().strip()
        LLM_CONFIG["openai"]["base_url"] = self.openai_url.text().strip() or "https://api.openai.com/v1"
        LLM_CONFIG["openai"]["model"] = self.openai_model.text().strip() or "gpt-4o-mini"

        # 持久化（API Key 编码存储）
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
