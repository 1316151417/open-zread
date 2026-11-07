# Langfuse 可观测性

Open Zread 默认不依赖 Langfuse。设置 `LANGFUSE_ENABLE=true` 后，可以在 Langfuse 中查看流水线调用链、阶段耗时和 Prompt 版本。

## 两个开关层面

Langfuse 集成由 `util/langfuse.py` 集中处理，在 **模块导入时** 读取 `LANGFUSE_ENABLE`：

- `false`（默认）：`observe` 和 `propagate_attributes` 是 no-op；OpenAI 使用标准 `openai.OpenAI`；Prompt 从本地模板编译。
- `true`：从 `langfuse` 导入 `observe` / `propagate_attributes`；OpenAI 使用 `langfuse.openai.OpenAI`，自动上报调用；Prompt 从 Langfuse Prompt Management 获取。

因为开关在导入时求值，修改环境变量后需要重新启动进程。`main.py` 在导入流水线之前调用 `dotenv.load_dotenv()`，所以 `.env` 中的开关能生效。

## 环境变量

```env
LANGFUSE_ENABLE=true
LANGFUSE_SECRET_KEY="..."
LANGFUSE_PUBLIC_KEY="..."
LANGFUSE_BASE_URL="http://localhost:3000"
```

`.env.example` 只应包含占位符，不要把真实 Key 提交到仓库。仓库现有的 `.env.example` 若包含真实凭据，应立即删除并轮换。

## 本地 Langfuse

Langfuse 官方推荐用 Docker 启动。默认地址是 `http://localhost:3000`，首次访问创建账号后可以获得 Secret Key 和 Public Key。

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up
```

启动后把两个 Key 填入 `.env`，再设置 `LANGFUSE_ENABLE=true`。

## 同步 Prompt

启用 Langfuse 后，先把本地 Prompt 同步到 Langfuse：

```bash
uv run python -m prompt.langfuse_prompt_init
```

它会把三组 system / user 模板写成 chat prompt：

| 名称 | 用途 |
| --- | --- |
| `step1` | 阶段 1：生成文档目录 |
| `step2` | 阶段 2：生成单页正文 |
| `compress` | 上下文压缩 |

同步时会把 Python `str.format` 的 `{var}` 转成 Langfuse 的 `{{var}}`，并设置 `production` 标签。之后运行时 `get_compiled_messages(name, **variables)` 会从 Langfuse 拉取对应 Prompt 并编译变量。

## 能看到什么

- 流水线会话：`pipeline-<8位随机串>`；
- 阶段 span：`generate_toc`、`generate_content`；
- 每个主题的 metadata：`topic_name`；
- Agent stream 的 span：`react_agent_stream`；
- OpenAI 协议调用：由 `langfuse.openai.OpenAI` 自动记录；
- Prompt 获取：`get_compiled_messages` 标记为 generation，并关联使用的 Prompt。

Anthropic 协议使用标准 `anthropic` 客户端，没有对应的自动包装；阶段 span 仍然会记录，但底层调用的细节取决于客户端本身。

## 数据边界

启用 Langfuse 后，以下内容可能离开本机：

- Prompt 模板和变量；
- 目录结构、工具读取的文件片段；
- 模型调用的输入输出和元数据。

请使用可信的 Langfuse 实例，并遵守模型服务与 Langfuse 的数据处理条款。禁用 Langfuse 不会阻止代码片段随模型请求发送给模型服务。
