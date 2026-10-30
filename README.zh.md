# AI 旅行决策助手

[English](README.md) | 简体中文

中文命令行旅行助手，将日期、天气、交通、住宿、餐饮、景点和预算工具组合成可解释的旅行建议。项目手写模型 → `tool_calls` → Python 工具 → `ToolMessage` 循环，让每一步决策与执行都可见，不依赖高级 Agent API。

当前 `0.1.0` 版本是 LangChain 学习项目，结合 Open-Meteo 在线天气、本地教学数据和费用公式；不查询真实预订库存，也不购买车票。

## 功能与数据边界

项目注册了八个工具：

- `plan_trip_dates`：校验起止日期，计算旅行天数和住宿晚数。
- `search_transport`：估算高铁、长途客运和自驾方案。
- `calculate_driving_cost`：计算油费、过路费、停车费、整车和人均成本。
- `estimate_hotel_cost`、`estimate_food_cost`：依据城市数据和消费标准估算住宿与餐饮。
- `search_attractions`：按兴趣筛选景点，估算门票。
- `get_travel_weather`：通过城市地理编码查询 Open-Meteo 预报。
- `calculate_total_budget`：汇总各项费用、预备金和人均成本，判断是否超过预算上限。

本地数据覆盖 **杭州、上海、北京、南京、苏州、成都、西安、广州**。交通、酒店、餐饮和景点费用均为教学估算，不是实时报价；实际出行前请向相关服务方核实价格与可用情况。天气地理编码可查询本地费用数据以外的城市。

## 环境与安装

- Python **3.11 或更高版本**。
- DeepSeek API 账号，或已启动且安装了工具调用模型的 Ollama 服务。
- 使用远程模型和 Open-Meteo 时需要联网。

依赖文件固定了 LangChain `1.2.12`、核心及模型适配包和配套库。以下命令在 PowerShell 中运行：

```powershell
git clone https://github.com/Daredevil3210/ai-travel-decision-assistant.git
cd ai-travel-decision-assistant
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

复制模板只用于首次配置，更新时保留已有 `.env`。也可激活已有 Conda 环境，进入仓库目录后安装 `requirements.txt`。

## 模型配置

编辑本地 `.env`：

```dotenv
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-v4-flash
MODEL_API_KEY=replace_with_your_private_key
MODEL_BASE_URL=https://api.deepseek.com
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

`deepseek-v4-flash` 是仓库模板中配置的标识，不代表服务可用性保证；请使用账号可访问且支持工具调用的模型。程序兼容 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 作为后备变量名。根目录 `.env` 会覆盖已有环境变量。

使用 Ollama 时，替换模型配置为：

```dotenv
MODEL_PROVIDER=ollama
MODEL_NAME=replace_with_your_installed_tool_capable_model
MODEL_BASE_URL=http://localhost:11434
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

仅设置 provider 不能保证具体本地模型会产生合法 `tool_calls`。如果模型只用文字描述“我要调用工具”，请改用真正支持工具调用的模型。`MAX_TOOL_ROUNDS` 必须在 1 到 20 之间。

可选的 LangSmith 变量见 `.env.example`，开启追踪可能上传模型消息和工具数据。密钥只写入已忽略的 `.env`，不要放入公开示例。

## 运行与追问

```powershell
python main.py
python main.py -q "我准备未来两天从杭州去上海，2个人，比较高铁和自驾并估算舒适型旅行总预算。"
python main.py --no-tool-trace
```

界面与系统提示词使用中文。交互命令为 `/help`、`/tools`、`/examples`、`/clear`、`/exit`。当前进程保留对话上下文，`/clear` 开始新的规划对话。

建议提供出发地、目的地、明确日期、人数、房间数、酒店档次、交通偏好、兴趣和预算上限。例如：

```text
我和朋友从杭州去上海，未来两天出行，2个人住1间舒适型酒店，
喜欢历史和摄影。请比较高铁和自驾，给出景点建议和总预算，上限3000元。
```

然后继续问 `把酒店改成经济型，其他条件不变，重新算预算。` 或 `如果改成自驾，两个人平摊后每人多少钱？`，比较备选方案。

开启轨迹后，终端会先显示工具名、参数和成功/失败状态，再展示最终回答。完整费用方案应调用 `calculate_total_budget`；如果轨迹未出现该工具，可明确要求调用总预算工具，避免依赖模型心算。

## 天气限制与排查

天气工具接受今天到 **未来第 15 天** 的日期，每次 **最多连续七天**。更远的行程可先做费用规划，临近出发再查天气。网络超时与网络错误会重试，失败返回错误信息，不编造天气。

启动提示缺少密钥时，检查当前仓库根目录的 `.env`，修改后重新启动。城市没有费用或景点数据时，可按现有结构扩充 `data/destinations.json`。Ollama 响应速度取决于模型大小及硬件。

## 项目结构

```text
ai-travel-decision-assistant/
├── main.py                    # CLI 和交互命令
├── travel_assistant/
│   ├── assistant.py           # 模型初始化及手写工具循环
│   ├── config.py              # 配置读取与校验
│   ├── data.py                # 本地城市数据读取
│   ├── prompts.py             # 中文规划提示词
│   └── tools.py               # 八个工具实现
├── data/destinations.json     # 坐标、费用基准和景点
├── tests/                    # 配置、工具和助手测试
├── docs/PROJECT_GUIDE.md      # 详细原理及源码导读
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

## 提供的检查

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

测试覆盖配置、日期/费用/景点/天气工具及手写工具循环，使用模拟模型响应和天气请求，并关闭测试追踪。它们验证本地行为，不代表真实模型质量或在线服务可用性。本次 README 更新未运行测试，也未调用模型或天气 API。

## 学习背景与许可

项目基于尚硅谷 LangChain 1.2 课程 Models、Messages、提示词与 Tools 阶段的知识进行综合练习。持久化会话、Agent API、真实地图/预订接口、结构化方案和 Web 界面仍为扩展方向，当前未实现。详细流程和代码阅读顺序见 [项目指南](docs/PROJECT_GUIDE.md)。

采用 [MIT License](LICENSE)，保留仓库中的 `AI Travel Decision Assistant contributors` 版权声明。
