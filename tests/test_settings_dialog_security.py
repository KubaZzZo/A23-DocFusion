"""Settings dialog API-key residency tests."""
from pathlib import Path


def test_settings_dialog_does_not_load_plaintext_key_from_runtime_config():
    source = Path(__file__).parents[1] / "ui" / "settings_dialog.py"
    text = source.read_text(encoding="utf-8")

    assert 'self.openai_key.setText(LLM_CONFIG["openai"]["api_key"])' not in text
    assert 'LLM_CONFIG["openai"]["api_key"] = self.openai_key.text().strip()' not in text
