# 模型与配置

Open Zread 用 `settings.json` 描述模型、并发和文档风格。每个模型层级都独立选择协议、地址、Key、模型 ID 和思考参数。

## 三档模型

代码里定义了三档配置：

| 层级 | 当前用途 | 默认模型 |
| --- | --- | --- |
| `lite` | 预留给轻量任务；当前流水线只加载并打印，没有单独调用 | `deepseek-v4-flash` |
| `pro` | 阶段 1：探索仓库、生成文档目录 | `deepseek-v4-flash`（思考开启） |
| `max` | 阶段 2：逐主题生成 Markdown 正文 | `deepseek-v4-flash`（思考开启） |

压缩上下文时使用当前阶段自己的 `LLMAdaptor`，不会切换到 `lite`。如果你的配置只改 `lite`，当前版本不会影响主要流程。

默认值来自 `setting/settings.py`；README 里的示例把 `provider` 写成 `anthropic`，代码默认值是 `openai`。以你实际使用的服务端协议为准。

## 单个层级的字段

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

| 字段 | 说明 |
| --- | --- |
| `provider` | `openai` 或 `anthropic`，决定使用哪套消息和工具协议 |
| `base_url` | 模型服务地址；Anthropic 协议会自动补 `/anthropic` |
| `api_key` | 支持 `${ENV_VAR}` 展开；也可以直接写 Key，但不建议 |
| `model` | 服务端实际提供的模型 ID |
| `max_tokens` | 单次输出上限 |
| `thinking` | 是否启用思考模式 |
| `reasoning_effort` | 推理深度，示例使用 `low` / `medium` / `high` / `max` |

`thinking` 和 `reasoning_effort` 会按协议注入不同的请求参数：OpenAI 使用 `reasoning_effort` 和 `extra_body.thinking`，Anthropic 使用 `extra_body.thinking` 与 `extra_body.output_config.effort`。具体转换见[模型协议适配](../internals/03-providers.md)。

## 流水线配置

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `max_sub_agent_steps` | 单次 ReAct 的最大步数 | `30` |
| `research_parallel` | 是否并行生成主题内容 | `true` |
| `research_threads` | 并行线程数 | `10` |
| `doc_language` | 文档语言 | `中文` |
| `target_audience` | 目标读者，阶段 2 会写入 Prompt | `初级开发者` |

`doc_language` 只用于 Prompt 和 `wiki.json` 的语言标记；不是“任意语言都完整支持”的承诺。当前 `wiki.json` 会在值为“中文”时写 `zh`，其他值写 `en`。

## 配置文件从哪里读

`load_settings()` 的查找顺序：

1. 当前工作目录的 `settings.json`；
2. Open Zread 包内 `setting/settings.json`（仓库默认没有这个文件）；
3. 内置默认值。

读取后会与默认值做合并，再递归展开 `${VAR}`，最后为 Anthropic 地址补 `/anthropic`。配置在进程内缓存，运行中修改文件不会热更新。

从目标项目运行时，当前目录是目标项目，因此 **仓库根目录的 `settings.json` 不会被自动读取**。需要自定义时，在目标项目放一份 `settings.json`，或从 Open Zread 根目录启动（但那样分析的是 Open Zread 自己）。

## 环境变量

- `DEEPSEEK_API_KEY`：示例配置的默认 Key 变量。
- `LANGFUSE_ENABLE`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_BASE_URL`：Langfuse 开关与凭据。
- `.env` 由 `main.py` 在当前工作目录加载，且发生在导入流水线之前；这保证 `LANGFUSE_ENABLE` 在模块导入时能被读取。

环境变量和 `settings.json` 都会把代码片段发送给模型服务。不要把包含生产密钥的仓库直接交给不可信的模型端点。
