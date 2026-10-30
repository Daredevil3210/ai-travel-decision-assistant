# AI Travel Decision Assistant

English | [简体中文](README.zh.md)

A Chinese-language command-line assistant that combines dates, weather, transport, accommodation, food, attractions, and budget tools into an explainable travel proposal. The project implements the model → `tool_calls` → Python tool → `ToolMessage` loop explicitly, making each decision step visible without a high-level Agent API.

Version `0.1.0` is a LangChain learning project. It uses live Open-Meteo weather alongside local teaching data and cost formulas; it does not search booking inventory or purchase tickets.

## Capabilities and data boundaries

Eight registered tools cover:

- `plan_trip_dates`: validate dates and calculate trip days and hotel nights.
- `search_transport`: estimate high-speed rail, coach, and driving options.
- `calculate_driving_cost`: calculate fuel, toll, parking, vehicle, and per-person costs.
- `estimate_hotel_cost` and `estimate_food_cost`: estimate accommodation and meals from city data and selected standards.
- `search_attractions`: filter attractions by interests and estimate admission costs.
- `get_travel_weather`: retrieve Open-Meteo forecasts using city geocoding.
- `calculate_total_budget`: combine expenses, contingency, per-person cost, and a budget-limit comparison.

The local dataset covers **Hangzhou, Shanghai, Beijing, Nanjing, Suzhou, Chengdu, Xi'an, and Guangzhou**. Transport, accommodation, meal, and attraction figures are estimates for teaching, not current quotes. Verify actual availability and prices with the relevant providers before travel. Weather geocoding can cover cities beyond this local cost dataset.

## Requirements and installation

- Python **3.11 or later**.
- A DeepSeek API account, or a running Ollama service with a model that supports tool calls.
- Internet access for the selected remote model and Open-Meteo weather requests.

The dependency file pins LangChain `1.2.12`, its core/provider packages, and supporting libraries. Run the following from PowerShell:

```powershell
git clone https://github.com/Daredevil3210/ai-travel-decision-assistant.git
cd ai-travel-decision-assistant
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Copy the template only for initial setup; keep an existing `.env` when updating. An existing Conda environment can also be used: activate it, enter the repository directory, and install `requirements.txt`.

## Model configuration

Edit the local `.env`:

```dotenv
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-v4-flash
MODEL_API_KEY=replace_with_your_private_key
MODEL_BASE_URL=https://api.deepseek.com
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

`deepseek-v4-flash` is the identifier in the checked-in template, not an availability guarantee. Choose a model available to your account that supports tool calling. `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL` are accepted as fallback variable names. The project-root `.env` overrides existing environment values.

For Ollama, replace the provider settings with:

```dotenv
MODEL_PROVIDER=ollama
MODEL_NAME=replace_with_your_installed_tool_capable_model
MODEL_BASE_URL=http://localhost:11434
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

The provider name alone does not ensure that a particular local model produces valid `tool_calls`. If it only describes an intended call in prose, select a model that actually supports tools. `MAX_TOOL_ROUNDS` must be between 1 and 20.

The optional LangSmith variables are documented in `.env.example`; enabling tracing can upload model messages and tool data. Keep keys in the ignored `.env`, never in committed examples.

## Run and ask follow-up questions

```powershell
python main.py
python main.py -q "我准备未来两天从杭州去上海，2个人，比较高铁和自驾并估算舒适型旅行总预算。"
python main.py --no-tool-trace
```

The interface and system prompt are Chinese. Interactive commands are `/help`, `/tools`, `/examples`, `/clear`, and `/exit`. Conversation context is retained in the current process; `/clear` starts a new planning conversation.

For useful comparisons, provide departure/destination cities, exact dates, travelers, rooms, hotel standard, preferred transport, interests, and a budget ceiling. For example:

```text
我和朋友从杭州去上海，未来两天出行，2个人住1间舒适型酒店，
喜欢历史和摄影。请比较高铁和自驾，给出景点建议和总预算，上限3000元。
```

Then ask `把酒店改成经济型，其他条件不变，重新算预算。` or `如果改成自驾，两个人平摊后每人多少钱？` to compare alternatives.

When tracing is enabled, the terminal displays tool names, arguments, and success/failure before the final answer. A complete cost proposal should call `calculate_total_budget`; if the trace omits it, ask the assistant to use that tool instead of relying on model arithmetic.

## Weather limits and troubleshooting

The weather tool accepts dates from today through **15 days ahead**, with **at most seven consecutive days per request**. For a later trip, plan costs first and request the forecast closer to departure. Network timeouts and network errors are retried; failures return an error rather than fabricated weather.

If startup reports a missing key, check the `.env` in this repository's root and restart after editing. If cost or attraction data is missing for a city, extend `data/destinations.json` following its existing schema. Ollama latency depends on model size and available hardware.

## Project structure

```text
ai-travel-decision-assistant/
├── main.py                    # CLI and command handling
├── travel_assistant/
│   ├── assistant.py           # Model setup and manual tool loop
│   ├── config.py              # Environment loading and validation
│   ├── data.py                # Local city-data access
│   ├── prompts.py             # Chinese planning instructions
│   └── tools.py               # Eight tool implementations
├── data/destinations.json     # Coordinates, price baselines, attractions
├── tests/                    # Configuration, tools, and assistant tests
├── docs/PROJECT_GUIDE.md      # Detailed Chinese design/source guide
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

## Provided checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The tests cover configuration, date/cost/attraction/weather tools, and the manual tool loop. Model responses and weather requests are mocked, and test tracing is disabled. These checks exercise local behavior without demonstrating real-model quality or live-service availability. This README update did not run the tests or contact model/weather APIs.

## Learning context and license

The project builds on the Models, Messages, Prompts, and Tools concepts studied in the 尚硅谷 LangChain 1.2 course. Persistent conversations, an Agent API, live map/booking integrations, structured proposals, and a web interface remain extension ideas rather than implemented features. See the [project guide](docs/PROJECT_GUIDE.md) for the detailed flow and suggested reading order.

Licensed under [MIT](LICENSE), with the repository's `AI Travel Decision Assistant contributors` copyright notice.
