# Open Zread

> 用 AI 把本地代码变成文档，一条命令搞定。

Open Zread 是 [Zread CLI](https://github.com/ZreadAI/zread_cli) 的开源版本，通过 AI 大模型自动分析代码仓库，生成结构化的 Wiki 文档。所有数据完全本地存储，不会上传到任何服务器。

> **定位**：本项目主要用于 **学习 Agent 开发**，代码架构清晰，涵盖 ReAct 循环、工具调用、上下文压缩、Prompt 管理等核心模式，适合作为 Agent 开发的入门参考。

与闭源版相比，Open Zread 使用纯 Python 实现，架构清晰，方便二次开发和定制。默认集成 [Langfuse](https://github.com/langfuse/langfuse) 进行调用链追踪和 Prompt 管理，方便观察 Agent 的每一步决策过程。

## 功能特性

- **自动分析** — AI Agent 自动探索代码库，识别架构和关键模块
- **结构化文档** — 两阶段流水线：先生成目录（TOC），再并行生成详细文档
- **多模型支持** — 兼容 OpenAI 和 Anthropic 协议，支持 DeepSeek、OpenAI 等任意兼容模型
- **本地运行** — 所有分析在本地完成，代码不会离开你的机器
- **可观测性** — 默认集成 [Langfuse](https://github.com/langfuse/langfuse)，支持 Prompt 管理和调用链追踪，可观察 Agent 每一步的决策过程
- **上下文压缩** — 超长对话自动压缩，避免超出模型上下文窗口

## 快速开始

### 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
git clone https://github.com/your-username/open-zread.git
cd open-zread
uv sync
```

### 配置

1. 复制环境变量文件并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY="your-api-key"
LANGFUSE_SECRET_KEY=""
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_BASE_URL=""
```

2. 启动 Langfuse（用于监控 Agent 调用链和 Prompt 管理）：

```bash
# 克隆 Langfuse 仓库
git clone https://github.com/langfuse/langfuse.git

# 启动 Langfuse 服务（需要 Docker）
cd langfuse
docker compose up
```

Langfuse 默认运行在 `http://localhost:3000`，首次访问时创建账号后即可获得 `SECRET_KEY` 和 `PUBLIC_KEY`，填入 `.env` 即可。

3. 根据需要修改 `settings.json`（可选，已有默认配置）：

```bash
cp settings.json.example settings.json
```

`settings.json` 支持配置三个模型层级：

| 层级 | 用途 | 默认模型 |
|------|------|----------|
| `lite` | 轻量任务 | deepseek-v4-flash |
| `pro` | TOC 生成 | deepseek-v4-flash (thinking) |
| `max` | 内容生成 | deepseek-v4-flash (thinking) |

### 运行

在目标项目目录下执行：

```bash
cd /path/to/your/project
uv run python /path/to/open-zread/main.py
```

生成的文档保存在当前目录的 `.zread/wiki/` 下：

```
.zread/
└── wiki/
    ├── current          # 指向最新版本的指针
    └── versions/
        └── 2026-04-26-120000/
            ├── wiki.json   # 文档目录索引
            ├── 1-xiang-mu-gai-shu.md
            ├── 2-kuai-su-qi-dong.md
            └── ...
```

## 自定义模型

`settings.json` 中的每个模型层级支持以下字段：

```json
{
  "provider": "openai",
  "base_url": "https://api.deepseek.com",
  "api_key": "${DEEPSEEK_API_KEY}",
  "model": "deepseek-v4-flash",
  "max_tokens": 8192,
  "thinking": true,
  "reasoning_effort": "high"
}
```

- `provider`：`openai` 或 `anthropic`（决定使用哪种 API 协议）
- `base_url`：API 地址，支持任何兼容 OpenAI/Anthropic 接口的服务
- `api_key`：API 密钥，支持 `${ENV_VAR}` 环境变量引用
- `thinking`：是否启用模型的思考模式
- `reasoning_effort`：推理深度（`low` / `medium` / `high` / `max`）

其他配置项：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `max_sub_agent_steps` | 单个主题的最大 ReAct 步数 | 30 |
| `research_parallel` | 是否并行生成内容 | true |
| `research_threads` | 并行线程数 | 10 |
| `doc_language` | 文档语言 | 中文 |
| `target_audience` | 目标受众 | 初级开发者 |

## 架构

```
main.py → pipeline/run.py (run_pipeline)
  ├─ Phase 1: explorer.py → ReAct Agent (pro 模型) → XML TOC → Topic[]
  └─ Phase 2: researcher.py → ReAct Agent (max 模型) → Markdown 文档
```

```
├── agent/            # ReAct Agent 循环实现（含上下文压缩）
├── base/             # 核心类型：Event、Tool、Message、@tool 装饰器
├── pipeline/         # 两阶段流水线：章节拆分 + 内容生成
├── prompt/           # Prompt 模板与 Langfuse Prompt 管理
├── provider/         # LLM 提供商抽象层（OpenAI / Anthropic 协议）
├── setting/          # 配置加载与合并
├── tool/             # Agent 可用工具：目录结构、文件读取、Shell 命令
└── util/             # 工具函数：TOC 解析、内容提取、slug 生成
```

### 与闭源版的区别

| 特性 | Open Zread | Zread CLI |
|------|-----------|-----------|
| 语言 | Python | Rust |
| 安装方式 | `uv sync` | Homebrew / npm / winget |
| 模型 | 自备 API Key | 内置提供商 + 自定义 |
| 内置阅读器 | 无 | `zread browse` |
| 命令行交互 | 无 | 完整 CLI（login / config / generate） |
| Prompt 管理 | Langfuse | 内置 |
| 可扩展性 | 源码完全开放 | 闭源 |

## 开发

```bash
# 安装依赖
uv sync

# 同步 Prompt 到 Langfuse（需要配置 Langfuse 环境变量）
uv run python -m prompt.langfuse_prompt_init
```

## License

MIT
