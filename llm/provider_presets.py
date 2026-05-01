"""OpenAI-compatible provider presets and probing helpers."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    base_url: str
    model_placeholder: str
    api_key_placeholder: str
    api_format: str = "openai_compatible"
    models_path: str = "/models"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProviderProfile:
    vendor: str
    label: str
    api_format: str
    api_key: str
    base_url: str
    model: str


_PRESETS = [
    ProviderPreset("openai", "OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", "sk-..."),
    ProviderPreset("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", "sk-..."),
    ProviderPreset("moonshot", "Moonshot", "https://api.moonshot.cn/v1", "moonshot-v1-8k", "sk-..."),
    ProviderPreset("qwen", "通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", "sk-..."),
    ProviderPreset("zhipu", "智谱", "https://open.bigmodel.cn/api/paas/v4/", "glm-4-plus", "sk-..."),
    ProviderPreset("claude_compatible", "Claude（兼容接口）", "", "claude-3-5-sonnet", "兼容接口提供的 API Key"),
    ProviderPreset("custom", "自定义兼容接口", "", "your-model-name", "your-api-key"),
]

CLOUD_VENDOR_PRESETS = {preset.id: preset.to_dict() for preset in _PRESETS}


def get_cloud_vendor_preset(vendor: str) -> dict:
    return CLOUD_VENDOR_PRESETS.get(vendor, CLOUD_VENDOR_PRESETS["custom"])


def build_provider_profile(config: dict) -> ProviderProfile:
    vendor = config.get("vendor", "openai")
    preset = get_cloud_vendor_preset(vendor)
    return ProviderProfile(
        vendor=vendor if vendor in CLOUD_VENDOR_PRESETS else "custom",
        label=preset["label"],
        api_format=preset["api_format"],
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url") or preset["base_url"] or "https://api.openai.com/v1",
        model=config.get("model") or preset["model_placeholder"],
    )


def normalize_models_url(base_url: str) -> str:
    url = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if not url:
        url = "https://api.openai.com/v1"
    if url.endswith("/models"):
        return url
    return f"{url}/models"


def extract_model_names(payload) -> list[str]:
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


def probe_openai_compatible(api_key: str, base_url: str) -> tuple[list[str], str]:
    from llm.provider_health import ProviderHealthChecker

    profile = build_provider_profile({"vendor": "custom", "api_key": api_key, "base_url": base_url, "model": ""})
    result = ProviderHealthChecker().check_openai_compatible(profile)
    if not result.ok:
        raise RuntimeError(result.message)
    return result.models, "" if result.models else result.message


__all__ = [
    "CLOUD_VENDOR_PRESETS",
    "ProviderProfile",
    "ProviderPreset",
    "build_provider_profile",
    "extract_model_names",
    "get_cloud_vendor_preset",
    "normalize_models_url",
    "probe_openai_compatible",
]
