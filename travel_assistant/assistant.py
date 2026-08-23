from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from travel_assistant.config import Settings
from travel_assistant.prompts import SYSTEM_PROMPT
from travel_assistant.tools import TOOLS, TOOL_MAP


@dataclass(frozen=True)
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    success: bool


@dataclass(frozen=True)
class AssistantResult:
    answer: str
    tool_events: list[ToolEvent] = field(default_factory=list)


def build_model(settings: Settings):
    kwargs: dict[str, Any] = {
        "model": settings.model_name,
        "model_provider": settings.provider,
        "temperature": 0,
    }
    if settings.api_key:
        kwargs["api_key"] = settings.api_key
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return init_chat_model(**kwargs)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    return str(content)


def _tool_succeeded(content: Any) -> bool:
    if not isinstance(content, str):
        return True
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return not content.startswith("工具执行失败")
    return not (isinstance(parsed, dict) and "error" in parsed)


def _system_message() -> SystemMessage:
    current_date = date.today().isoformat()
    return SystemMessage(
        content=(
            f"{SYSTEM_PROMPT}\n"
            f"8. 当前日期是 {current_date}，请据此解析‘今天’、‘明天’、"
            "‘未来几天’等相对日期。"
        )
    )


class TravelAssistant:
    """Manual multi-round tool loop, intentionally implemented without Agent."""

    def __init__(self, settings: Settings, model=None):
        self.settings = settings
        self.model = model or build_model(settings)
        self.model_with_tools = self.model.bind_tools(TOOLS, tool_choice="auto")
        self.messages = [_system_message()]

    def clear(self) -> None:
        self.messages = [_system_message()]

    def ask(self, question: str) -> AssistantResult:
        if not question.strip():
            raise ValueError("问题不能为空。")
        self.messages.append(HumanMessage(content=question.strip()))
        events: list[ToolEvent] = []

        for _round in range(self.settings.max_tool_rounds):
            response: AIMessage = self.model_with_tools.invoke(self.messages)
            self.messages.append(response)
            if not response.tool_calls:
                answer = _content_to_text(response.content)
                return AssistantResult(answer or "模型没有返回文本。", events)

            for tool_call in response.tool_calls:
                name = tool_call.get("name", "")
                arguments = tool_call.get("args", {})
                selected_tool = TOOL_MAP.get(name)
                if selected_tool is None:
                    tool_message = ToolMessage(
                        content=f"工具调用失败：不存在名为 {name} 的工具。",
                        tool_call_id=tool_call.get("id", "unknown-tool-call"),
                        name=name or "unknown_tool",
                    )
                    success = False
                else:
                    try:
                        tool_message = selected_tool.invoke(tool_call)
                        success = _tool_succeeded(tool_message.content)
                    except Exception as exc:
                        tool_message = ToolMessage(
                            content=f"工具执行失败：{type(exc).__name__}: {exc}",
                            tool_call_id=tool_call.get("id", "failed-tool-call"),
                            name=name,
                        )
                        success = False
                self.messages.append(tool_message)
                events.append(ToolEvent(name=name, arguments=arguments, success=success))

        message = (
            f"工具调用超过最大轮数 {self.settings.max_tool_rounds}，"
            "为避免无限循环，本次旅行规划已停止。"
        )
        self.messages.append(AIMessage(content=message))
        return AssistantResult(message, events)
