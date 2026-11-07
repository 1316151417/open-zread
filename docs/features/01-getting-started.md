# 快速开始

本文从零运行一次 Open Zread，并说明配置文件的读取位置——这一点和很多 CLI 工具不同。

## 环境要求

- Python **3.12** 或更高版本
- [uv](https://docs.astral.sh/uv/) 包管理器
- 一个兼容 OpenAI 或 Anthropic 协议的模型 API Key（默认示例使用 DeepSeek）

## 安装

```bash
git clone https://github.com/1316151417/open-zread.git
cd open-zread
uv sync
```

`uv sync` 会按 `pyproject.toml` 创建 `.venv` 并安装依赖。项目没有发布到 PyPI，入口是仓库里的 `main.py`。

## 配置模型

复制环境变量模板并填入自己的 Key：

```bash
cp .env.example .env
```

`.env` 中至少需要：

```env
DEEPSEEK_API_KEY="your-api-key"
```

> `.env.example` 只是模板。不要把真实 Key 提交到仓库；`.env` 已被 `.gitignore` 忽略。

## 在目标项目中运行

Open Zread 分析的是 **当前工作目录**，不是 Open Zread 自己所在的目录。推荐用 `--project` 显式指定 Open Zread 的 Python 环境：

```bash
cd /path/to/your/project
uv run --project /path/to/open-zread python /path/to/open-zread/main.py
```

注意两个“当前目录”语义：

1. **分析目标**：`os.getcwd()`，即你执行命令时所在的目录。
2. **配置来源**：`dotenv.load_dotenv()` 和 `load_settings()` 也从当前目录读取。上面的命令不会自动加载 `/path/to/open-zread/.env` 和它的 `settings.json`。

因此，从目标项目运行时，建议先把 Key 导入当前 Shell：

```bash
set -a
source /path/to/open-zread/.env
set +a

cd /path/to/your/project
uv run --project /path/to/open-zread python /path/to/open-zread/main.py
```

也可以在目标项目放一份自己的 `.env` 和 `settings.json`，但不要提交；如果你只想使用默认配置，可以完全不提供 `settings.json`。

## 运行过程

终端会依次显示：

1. `lite` / `pro` / `max` 三档模型名；
2. 阶段 1 识别出的主题列表；
3. 阶段 2 每个主题的完成或失败状态；
4. `.zread/wiki/versions/<timestamp>/` 的输出路径。

运行时会在目标项目下创建：

```text
.zread/wiki/
├── current
└── versions/
    └── 2026-04-26-120000/
        ├── wiki.json
        └── <slug>.md
```

## 预览结果

Open Zread 不内置阅读器。使用 Zread CLI：

```bash
zread browse
```

也可以直接用编辑器打开 `.zread/wiki/versions/<timestamp>/` 下的 Markdown 文件。`wiki.json` 描述目录、页面 slug、章节和难度级别。

## 常见问题

| 现象 | 先检查 |
| --- | --- |
| 提示没有 API Key 或鉴权失败 | 当前目录是否加载到了环境变量；Key 是否有效 |
| 请求地址 404 / 协议不匹配 | `provider` 与 `base_url` 是否对应；Anthropic 地址会自动补 `/anthropic` |
| 模型不存在 | `model` 是否是服务端实际提供的 ID |
| 目录生成失败 | 模型是否按 XML 格式输出；可查看阶段 1 的原始输出 |
| 个别主题失败 | 其他主题仍会继续；重新运行会创建新版本 |
| 运行很慢或超出上下文 | 减少主题数、降低并发，或检查上下文压缩是否触发 |

## 安全提醒

- 代码片段、目录结构和工具输出会进入 Prompt 并发送给你配置的模型服务。
- Langfuse 开启后，追踪数据还会发送到 Langfuse 服务。
- 工具是只读白名单，但不是安全沙箱；不要在不可信仓库上运行并假定绝对隔离。
- 生成内容可能不准确，提交前应人工检查。
