from pathlib import Path

import pytest

from travel_assistant.config import ConfigurationError, Settings


MODEL_ENV_KEYS = [
    "MODEL_PROVIDER",
    "MODEL_NAME",
    "MODEL_API_KEY",
    "MODEL_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "MAX_TOOL_ROUNDS",
    "SHOW_TOOL_TRACE",
]


def clear_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_deepseek_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clear_model_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_PROVIDER=deepseek\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="API_KEY"):
        Settings.from_env(env_file)


def test_ollama_gets_default_base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clear_model_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MODEL_PROVIDER=ollama\nMODEL_NAME=qwen3:4b\nSHOW_TOOL_TRACE=false\n",
        encoding="utf-8",
    )

    settings = Settings.from_env(env_file)

    assert settings.provider == "ollama"
    assert settings.model_name == "qwen3:4b"
    assert settings.base_url == "http://localhost:11434"
    assert settings.api_key is None
    assert settings.show_tool_trace is False


def test_max_tool_rounds_is_validated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clear_model_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MODEL_PROVIDER=ollama\nMODEL_NAME=qwen3:4b\nMAX_TOOL_ROUNDS=0\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="1 到 20"):
        Settings.from_env(env_file)
