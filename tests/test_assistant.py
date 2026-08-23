from langchain_core.messages import AIMessage, ToolMessage

from travel_assistant.assistant import TravelAssistant
from travel_assistant.config import Settings


class FakeToolCallingModel:
    def __init__(self):
        self.calls = []
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "plan_trip_dates",
                        "args": {
                            "start_date": "2026-09-01",
                            "end_date": "2026-09-03",
                            "travelers": 2,
                        },
                        "id": "call_dates_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="行程共 3 天、住宿 2 晚。"),
        ]

    def bind_tools(self, _tools, **_kwargs):
        return self

    def invoke(self, messages):
        self.calls.append(list(messages))
        return self.responses.pop(0)


def make_settings(max_tool_rounds: int = 4) -> Settings:
    return Settings(
        provider="ollama",
        model_name="fake",
        api_key=None,
        base_url="http://localhost:11434",
        max_tool_rounds=max_tool_rounds,
        show_tool_trace=True,
    )


def test_assistant_runs_manual_tool_loop():
    model = FakeToolCallingModel()
    assistant = TravelAssistant(make_settings(), model=model)

    result = assistant.ask("9月1日到3日去旅行，2个人，一共几天？")

    assert result.answer == "行程共 3 天、住宿 2 晚。"
    assert len(result.tool_events) == 1
    assert result.tool_events[0].name == "plan_trip_dates"
    assert result.tool_events[0].success is True
    assert any(isinstance(message, ToolMessage) for message in model.calls[1])


def test_clear_removes_conversation_history():
    assistant = TravelAssistant(make_settings(), model=FakeToolCallingModel())
    assistant.ask("测试")
    assistant.clear()

    assert len(assistant.messages) == 1
