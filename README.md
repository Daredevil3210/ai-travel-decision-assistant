# AI 旅行决策助手

这是一个面向 LangChain 初学者的命令行项目。用户只需用中文描述出发地、目的地、日期、人数、兴趣和预算，模型会自行选择并组合日期、天气、交通、住宿、餐饮、景点和总预算工具，最后给出一份可比较、可解释的旅行建议。

项目刻意使用“手写工具调用循环”，没有直接使用高级 Agent。这样可以清楚看到尚硅谷课程学到 Tools 阶段之后，模型如何产生 `tool_calls`、程序如何执行工具、如何把 `ToolMessage` 交还给模型，以及模型如何基于结果继续决策。

## 能做什么

- 校验起止日期，计算旅行天数和住宿晚数。
- 比较高铁、长途客运、自驾的时间和费用估算。
- 根据里程、油耗、油价、过路费和停车费计算自驾成本。
- 按城市、酒店档次、房间数估算住宿费用。
- 按人数、天数和消费标准估算餐饮费用。
- 按兴趣筛选景点，并计算门票估算。
- 通过 Open-Meteo 查询未来 16 天内的天气预报。
- 汇总各项费用、预备金和人均成本，并判断是否超预算。
- 在同一次对话中继续追问、修改条件和比较备选方案。

目前内置教学数据的城市有：杭州、上海、北京、南京、苏州、成都、西安、广州。

> 天气来自 Open-Meteo 在线预报；交通、酒店、餐饮和景点价格均为教学估算，不是实时预订价格。实际出行前请到铁路、地图、酒店及景区官方渠道复核。

## 项目结构

```text
project2/
├─ data/
│  └─ destinations.json       # 城市坐标、消费基准和景点教学数据
├─ docs/
│  └─ PROJECT_GUIDE.md        # 原理、执行流程和扩展说明
├─ tests/
│  ├─ conftest.py
│  ├─ test_assistant.py       # 手写工具循环测试
│  ├─ test_config.py          # 模型配置测试
│  └─ test_tools.py           # 旅行工具测试
├─ travel_assistant/
│  ├─ assistant.py            # 模型初始化与多轮工具调用循环
│  ├─ config.py               # .env 配置读取与校验
│  ├─ data.py                 # 本地城市数据读取
│  ├─ prompts.py              # 旅行助手系统提示词
│  └─ tools.py                # 8 个 LangChain 工具
├─ .env.example               # 可公开的配置模板
├─ .gitignore                 # 明确忽略真实 .env
├─ main.py                    # CLI 入口
└─ requirements.txt
```

## 1. 安装环境

推荐复用课程的 Conda 环境：

```powershell
cd D:\Project\project2
conda activate langchain1.2
pip install -r requirements.txt
```

也可以创建独立虚拟环境：

```powershell
cd D:\Project\project2
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

要求 Python 3.11 或更高版本。

## 2. 配置模型

项目支持 DeepSeek 在线模型和 Ollama 本地模型。

### 使用 DeepSeek

复制模板：

```powershell
Copy-Item .env.example .env
```

在 `.env` 中填写：

```dotenv
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-v4-flash
MODEL_API_KEY=你的真实密钥
MODEL_BASE_URL=https://api.deepseek.com
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

课程中已经使用 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL` 的话也可继续使用，程序会兼容这两个变量名。

### 使用 Ollama

先确认 Ollama 服务已启动并且模型支持工具调用，再把 `.env` 改为：

```dotenv
MODEL_PROVIDER=ollama
MODEL_NAME=qwen3:4b
MODEL_BASE_URL=http://localhost:11434
MAX_TOOL_ROUNDS=8
SHOW_TOOL_TRACE=true
```

不同本地模型的工具调用能力差异很大。若模型只输出“我要调用某工具”却没有真正产生 `tool_calls`，请换用明确支持 Tools 的模型。

### 密钥安全

`.env` 已写入 `.gitignore`，不可提交到 GitHub。只能提交 `.env.example`，且其中只能放占位符。发布前可执行：

```powershell
git status --short
git check-ignore .env
```

第二条命令输出 `.env` 才表示忽略规则生效。

## 3. 启动项目

进入交互模式：

```powershell
cd D:\Project\project2
python main.py
```

单次提问后退出：

```powershell
python main.py -q "我和朋友从杭州去上海玩3天，2个人，住舒适型酒店，喜欢历史和摄影，总预算3000元，请比较高铁和自驾。"
```

隐藏工具调用轨迹：

```powershell
python main.py --no-tool-trace
```

交互命令：

- `/help`：查看帮助。
- `/tools`：查看全部工具。
- `/examples`：查看示例问题。
- `/clear`：清空对话上下文，开始新规划。
- `/exit`：退出程序。

## 4. 推荐提问方式

信息越完整，模型需要追问的次数越少。建议至少给出：

- 出发城市和目的地。
- 明确的起止日期。
- 人数、房间数和酒店档次。
- 偏好的交通方式。
- 兴趣关键词，如历史、自然、亲子、摄影、美食、夜景。
- 总预算上限。

示例：

```text
我和朋友从杭州去上海，2026-09-01出发，2026-09-03返回，
2个人住1间舒适型酒店，喜欢历史和摄影。
请比较高铁和自驾，给出景点建议和总预算，预算上限3000元。
```

天气工具只接受今天到未来第 15 天、连续最多 7 天的日期。若行程更远，助手仍可做预算和路线估算，但应在临近出发时再查询天气。

你也可以在首轮回答后继续说：

```text
把酒店改成经济型，其他条件不变，重新算预算。
```

或：

```text
如果改成自驾，两个人平摊后每人多少钱？
```

## 5. 输出怎么看

启用 `SHOW_TOOL_TRACE=true` 时，答案上方会显示工具轨迹。例如：

```text
• plan_trip_dates(...) -> 成功
• search_transport(...) -> 成功
• estimate_hotel_cost(...) -> 成功
• calculate_total_budget(...) -> 成功
```

这表示模型先决定调用哪些工具，Python 执行后再把结果交给模型。轨迹只显示工具名、参数和成功状态；最终答案会把原始 JSON 整理成人能读懂的中文方案。

完整旅行规划中应看到 `calculate_total_budget`。如果没有出现，说明模型没有遵守汇总要求，可以明确补充“请调用总预算工具汇总，不要心算”。

## 6. 运行测试

安装开发依赖：

```powershell
pip install -r requirements-dev.txt
```

执行：

```powershell
python -m pytest
```

单元测试不会调用真实大模型，也不会消耗 API 额度；天气测试使用模拟响应，因此不依赖网络。

## 7. 常见问题

### 提示缺少 API Key

检查 `.env` 是否位于 `D:\Project\project2\.env`，以及变量名是否为 `MODEL_API_KEY` 或 `DEEPSEEK_API_KEY`。修改后重启程序。

### 天气查询失败

检查网络，确认日期在未来 16 天内且一次不超过 7 天。天气接口失败时程序不会编造数据，而会返回失败原因。

### 某个城市没有数据

当前本地价格和景点工具只覆盖 8 个示例城市。可参照 `data/destinations.json` 的结构新增城市；天气工具本身可通过地理编码查询更多城市。

### 输出的价格与实际不一致

这是预期行为。项目重点是学习 Tools 和决策流程，价格公式及本地数据都是教学估算，不是票务或酒店聚合平台。

### Ollama 响应慢

首次运行需要加载模型；速度还取决于模型大小、CPU/GPU 和内存。可先选较小且支持工具调用的模型，同时减少上下文并避免一次提出过于复杂的规划。

## 继续学习

完成当前版本后，可以随着课程进度继续加入：

- 使用 Agent API 替换手写循环，并比较两种方式。
- 加入短期记忆和持久化会话。
- 接入真实地图、铁路、酒店或 POI API。
- 使用结构化输出固定旅行方案格式。
- 使用 LangSmith 查看每轮模型与工具调用。
- 增加 Streamlit 或 FastAPI 界面。

更详细的设计和代码阅读顺序见 [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)。
