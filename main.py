from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from travel_assistant.assistant import TravelAssistant
from travel_assistant.config import ConfigurationError, Settings
from travel_assistant.tools import TOOLS


# Windows 的传统 GBK 终端无法显示部分 Emoji。保留中文输出，并用占位符替换
# 极少数无法编码的字符，避免模型偶尔返回 Emoji 时导致整个程序退出。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

console = Console()


EXAMPLES = [
    "我准备未来两天从杭州去上海，2个人，比较高铁和自驾并估算舒适型旅行总预算。",
    "帮我规划北京三日历史文化游，1个人，住经济型酒店，预算3000元。",
    "查询上海未来三天天气，并推荐适合摄影和室内活动的景点。",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 旅行决策助手")
    parser.add_argument("-q", "--question", help="只提问一次，回答后退出")
    parser.add_argument("--no-tool-trace", action="store_true", help="隐藏工具轨迹")
    return parser


def print_tools() -> None:
    console.print("\n[bold]当前旅行工具[/bold]")
    for item in TOOLS:
        console.print(f"  - [cyan]{item.name}[/cyan]：{item.description}")
    console.print()


def print_examples() -> None:
    console.print("\n[bold]示例问题[/bold]")
    for item in EXAMPLES:
        console.print(f"  - {item}")
    console.print()


def print_help() -> None:
    console.print(
        "\n[bold]命令[/bold]\n"
        "  /help      查看帮助\n"
        "  /tools     查看工具\n"
        "  /examples  查看示例问题\n"
        "  /clear     清空本次会话上下文\n"
        "  /exit      退出程序\n"
    )


def print_result(result, show_trace: bool) -> None:
    if show_trace and result.tool_events:
        console.print("[dim]本次工具调用：[/dim]")
        for event in result.tool_events:
            state = "成功" if event.success else "失败"
            console.print(f"  [dim]- {event.name}({event.arguments}) -> {state}[/dim]")
    console.print(Panel(Markdown(result.answer), title="旅行助手", border_style="green"))


def ask_once(assistant: TravelAssistant, question: str, show_trace: bool) -> None:
    with console.status("[bold cyan]正在查询并组合旅行工具...[/bold cyan]"):
        result = assistant.ask(question)
    print_result(result, show_trace)


def interactive_loop(assistant: TravelAssistant, show_trace: bool) -> None:
    console.print(
        Panel(
            "我可以组合日期、天气、交通、住宿、餐饮、景点和预算工具。\n"
            "交通与消费数据是教学估算，出行前请通过官方渠道复核。\n"
            "输入 [bold]/examples[/bold] 查看示例，输入 [bold]/exit[/bold] 退出。",
            title="AI 旅行决策助手",
            border_style="cyan",
        )
    )
    while True:
        try:
            question = console.input("[bold blue]你：[/bold blue]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见，祝旅途愉快！")
            return
        if not question:
            continue
        command = question.lower()
        if command in {"/exit", "/quit", "exit", "quit"}:
            console.print("再见，祝旅途愉快！")
            return
        if command == "/help":
            print_help()
            continue
        if command == "/tools":
            print_tools()
            continue
        if command == "/examples":
            print_examples()
            continue
        if command == "/clear":
            assistant.clear()
            console.print("[green]本次会话上下文已清空。[/green]")
            continue
        try:
            ask_once(assistant, question, show_trace)
        except Exception as exc:
            console.print(f"[bold red]请求失败：[/bold red]{exc}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        settings = Settings.from_env()
        assistant = TravelAssistant(settings)
    except ConfigurationError as exc:
        console.print(f"[bold red]配置错误：[/bold red]{exc}")
        console.print("请复制 .env.example 为 .env，并填写模型配置。")
        return 2
    except ImportError as exc:
        console.print(f"[bold red]缺少依赖：[/bold red]{exc}")
        console.print("请执行：pip install -r requirements.txt")
        return 3

    show_trace = settings.show_tool_trace and not args.no_tool_trace
    if args.question:
        ask_once(assistant, args.question, show_trace)
        return 0
    interactive_loop(assistant, show_trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
