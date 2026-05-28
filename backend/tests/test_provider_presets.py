import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.provider_presets import get_cloud_vendor_preset


def test_maolaoapi_is_available_as_openai_compatible_provider():
    preset = get_cloud_vendor_preset("maolaoapi")

    assert preset["label"] == "Maolao API"
    assert preset["base_url"] == "https://maolaoapi.com/v1"
    assert preset["api_format"] == "openai_compatible"
