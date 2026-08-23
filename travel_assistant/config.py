from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when model configuration is incomplete."""


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    provider: str
    model_name: str
    api_key: str | None
    base_url: str | None
    max_tool_rounds: int = 8
    show_tool_trace: bool = True

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "Settings":
        project_env = (
            Path(env_path)
            if env_path is not None
            else Path(__file__).resolve().parents[1] / ".env"
        )
        load_dotenv(dotenv_path=project_env, override=True)

        provider = os.getenv("MODEL_PROVIDER", "deepseek").strip().lower()
        model_name = os.getenv("MODEL_NAME", "deepseek-v4-flash").strip()
        if provider == "deepseek":
            api_key = os.getenv("MODEL_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
            base_url = os.getenv("MODEL_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        else:
            api_key = None
            base_url = os.getenv("MODEL_BASE_URL")

        try:
            max_tool_rounds = int(os.getenv("MAX_TOOL_ROUNDS", "8"))
        except ValueError as exc:
            raise ConfigurationError("MAX_TOOL_ROUNDS 必须是整数。") from exc

        if provider not in {"deepseek", "ollama"}:
            raise ConfigurationError("MODEL_PROVIDER 目前只支持 deepseek 或 ollama。")
        if not model_name:
            raise ConfigurationError("MODEL_NAME 不能为空。")
        if provider == "deepseek" and not api_key:
            raise ConfigurationError(
                "使用 DeepSeek 时必须设置 MODEL_API_KEY 或 DEEPSEEK_API_KEY。"
            )
        if provider == "ollama" and not base_url:
            base_url = "http://localhost:11434"
        if max_tool_rounds < 1 or max_tool_rounds > 20:
            raise ConfigurationError("MAX_TOOL_ROUNDS 必须在 1 到 20 之间。")

        return cls(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            max_tool_rounds=max_tool_rounds,
            show_tool_trace=_as_bool(os.getenv("SHOW_TOOL_TRACE"), True),
        )
