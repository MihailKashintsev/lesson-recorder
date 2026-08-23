"""
Sanity checks for the PROVIDERS registry in core/summarizer.py.

Each entry describes a real LLM backend behind the shared OpenAI-compatible
client, so a missing key or a bad default_model would silently break that
provider at runtime instead of failing loudly. GigaChat gets its own
assertions since it's the Sber-specific provider (OAuth, not a plain bearer
API key) this app was built to showcase.
"""
from core.summarizer import PROVIDERS

REQUIRED_KEYS = {"name", "base_url", "models", "default_model", "key_hint", "auth_header"}


def test_every_provider_has_required_keys():
    for provider_id, cfg in PROVIDERS.items():
        missing = REQUIRED_KEYS - cfg.keys()
        assert not missing, f"provider '{provider_id}' is missing keys: {missing}"


def test_default_model_is_in_models_list():
    for provider_id, cfg in PROVIDERS.items():
        if provider_id == "custom":
            continue  # custom has no fixed model list, user supplies their own
        assert cfg["default_model"] in cfg["models"], (
            f"provider '{provider_id}' default_model "
            f"'{cfg['default_model']}' not found in its own models list"
        )


def test_gigachat_is_configured_as_sber_oauth_provider():
    giga = PROVIDERS["gigachat"]
    assert giga["auth_type"] == "gigachat_oauth"
    assert giga["base_url"] == "https://gigachat.devices.sberbank.ru/api/v1"
