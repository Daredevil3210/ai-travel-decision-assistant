import os

import pytest


@pytest.fixture(autouse=True)
def disable_langsmith(monkeypatch: pytest.MonkeyPatch):
    """Keep unit tests local and deterministic."""
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    os.environ.pop("LANGCHAIN_API_KEY", None)
