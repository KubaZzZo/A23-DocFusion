"""Persistent settings helpers independent of UI widgets."""
import base64
import ctypes
import json
import os
from pathlib import Path
from ctypes import wintypes

from config import BASE_DIR, LLM_CONFIG
from logger import get_logger

DEFAULT_SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
log = get_logger("settings_store")
KEY_PREFIX = "dpapi:"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]


def _dpapi_available() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def _protect_with_dpapi(value: str) -> str:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    data = value.encode("utf-8")
    buffer = ctypes.create_string_buffer(data)
    in_blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    out_blob = _DataBlob()

    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise ctypes.WinError()

    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return KEY_PREFIX + base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _unprotect_with_dpapi(value: str) -> str:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    protected = base64.b64decode(value[len(KEY_PREFIX):].encode("ascii"))
    buffer = ctypes.create_string_buffer(protected)
    in_blob = _DataBlob(
        len(protected),
        ctypes.cast(buffer, ctypes.c_void_p),
    )
    out_blob = _DataBlob()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise ctypes.WinError()

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def encode_key(key: str) -> str:
    """Encrypt API keys before writing settings to disk."""
    if not key:
        return ""
    if _dpapi_available():
        return _protect_with_dpapi(key)
    raise RuntimeError("Secure API key storage requires Windows DPAPI")


def decode_key(encoded: str) -> str:
    """Decrypt stored API keys, preserving legacy Base64 values."""
    if not encoded:
        return ""
    if encoded.startswith(KEY_PREFIX):
        return _unprotect_with_dpapi(encoded)
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        log.warning("Ignoring unsupported plaintext API key value in settings")
        return ""


def load_settings(settings_file: Path | str = DEFAULT_SETTINGS_FILE) -> dict:
    """Load persisted settings from JSON."""
    path = Path(settings_file)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("加载设置文件失败，使用默认设置: %s", e)
    return {}


def save_settings(settings: dict, settings_file: Path | str = DEFAULT_SETTINGS_FILE):
    """Save persisted settings to JSON."""
    path = Path(settings_file)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def apply_settings(settings: dict, runtime_config: dict | None = None):
    """Apply persisted settings to the runtime LLM config dictionary."""
    if runtime_config is None:
        runtime_config = LLM_CONFIG
    if not settings:
        return
    if "provider" in settings:
        runtime_config["provider"] = settings["provider"]
    if "ollama_url" in settings:
        runtime_config["ollama"]["base_url"] = settings["ollama_url"]
    if "ollama_model" in settings:
        runtime_config["ollama"]["model"] = settings["ollama_model"]
    if "openai_key" in settings:
        runtime_config["openai"]["api_key"] = ""
        runtime_config["openai"]["api_key_ref"] = settings["openai_key"]
    if "openai_vendor" in settings:
        runtime_config["openai"]["vendor"] = settings["openai_vendor"]
    if "openai_url" in settings:
        runtime_config["openai"]["base_url"] = settings["openai_url"]
    if "openai_model" in settings:
        runtime_config["openai"]["model"] = settings["openai_model"]
    if "openai_proxy" in settings:
        runtime_config["openai"]["proxy_url"] = settings["openai_proxy"]


def apply_saved_settings(settings_file: Path | str = DEFAULT_SETTINGS_FILE, runtime_config: dict = LLM_CONFIG):
    """Load settings from disk and apply them to runtime config."""
    apply_settings(load_settings(settings_file), runtime_config)
