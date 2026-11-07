# 模型协议适配

`provider/` 把两类模型 API 统一成 `stream_events`、`call` 和消息格式。上层只认 `LLMAdaptor`，不直接依赖 OpenAI 或 Anthropic SDK。

## LLMAdaptor

```python
adaptor = LLMAdaptor(config)
adaptor.stream(messages, tools)
adaptor.stream_react(messages, tools, max_steps)
adaptor.react_for_text(messages, tools, max_steps)
adaptor.react_for_json(messages, tools, max_steps)
```

构造时按 `config["provider"]` 选择：

- `openai` → `provider/api/openai_api.py`
- `anthropic` → `provider/api/anthropic_api.py`
- 其他值 → `ValueError`

`_build_params` 把 `Tool` 对象转换成对应协议的 Schema：

- OpenAI：`{"type": "function", "function": {...}}`
- Anthropic：`{"name", "description", "input_schema"}`

`response_format` 只对 OpenAI 生效。

## 共用消息格式

`base/types.py` 定义统一消息：

- `SystemMessage`
- `UserMessage`
- `AssistantMessage`：`content`、`tool_calls`、`thinking`
- `ToolMessage`：`tool_id`、`tool_name`、`tool_result`、`tool_error`

`normalize_messages` 把对象转成 dict。两个 provider 再把这些 dict 转成各自协议。

## OpenAI 协议

入口：`provider/api/openai_api.py`。

### 客户端

- 启用 Langfuse 时使用 `langfuse.openai.OpenAI`，自动上报调用；
- 否则使用标准 `openai.OpenAI`；
- 默认 `base_url=https://api.deepseek.com`，默认 Key 读 `DEEPSEEK_API_KEY`；
- 超时 60 秒。

### 重试

`_with_retry` 只对以下错误重试一次（共两次尝试）：

- `APITimeoutError`
- `APIConnectionError`
- `TimeoutError`

重试间隔 1 秒。其他错误直接抛出。

### 消息转换

- `role=tool` → `tool_call_id` + 文本结果；
- assistant 的工具调用 → `tool_calls` 数组；
- `reasoning_content` 保留思考内容；
- 普通消息原样保留。

### 参数注入

```python
params["reasoning_effort"] = config["reasoning_effort"]
params["extra_body"]["thinking"] = {"type": "enabled" / "disabled"}
```

### 流式解析

- 识别 `reasoning_content` 和 `content`，分别发出 thinking / content 事件；
- 工具调用按 `delta.tool_calls[].index` 聚合 ID、名称和参数；
- `finish_reason` 到达时补发结束事件、工具调用事件和 `MESSAGE_END`；
- `usage` 从最后一个 chunk 读取。

工具调用的 `arguments` 是流式拼接的 JSON 字符串，由 ReAct 层解析。

## Anthropic 协议

入口：`provider/api/anthropic_api.py`。

### 客户端

- 使用标准 `anthropic.Anthropic`；
- 默认 `base_url=https://api.deepseek.com/anthropic`；
- Key 默认读 `DEEPSEEK_API_KEY`；
- 超时 60 秒。

`setting/settings.py` 会为 `provider=anthropic` 自动补 `/anthropic` 后缀，避免用户漏写。

### 消息转换

- system 消息被提取到 `params["system"]`；
- 多个 tool result 合并进一条 user 消息的 `tool_result` block；
- assistant 的 thinking / text / tool_use 转成 content blocks；
- tool_use 的 `input` 由 JSON 字符串解析成对象。

### 参数注入

```python
params["extra_body"]["thinking"] = {"type": "enabled" / "disabled"}
params["extra_body"]["output_config"] = {"effort": config["reasoning_effort"]}
```

### 流式解析

映射 Anthropic 事件：

| Anthropic 事件 | 统一事件 |
| --- | --- |
| `message_start` | `MESSAGE_START` |
| `content_block_start` (thinking) | `THINKING_START` |
| `content_block_start` (text) | `CONTENT_START` |
| `content_block_delta` (text_delta) | `CONTENT_DELTA` |
| `content_block_delta` (thinking_delta) | `THINKING_DELTA` |
| `content_block_delta` (input_json_delta) | 追加工具参数 |
| `content_block_stop` (tool_use) | `TOOL_CALL` |
| `message_delta` | 记录 stop_reason / usage |
| `message_stop` | `MESSAGE_END` |

Anthropic 的工具参数通过 `input_json_delta` 分片拼接，最后在 `content_block_stop` 发出。

## 同步调用

`adaptor.call(messages)` 用于上下文压缩摘要等非流式场景：

- OpenAI：`chat.completions.create`，返回第一条 message 的 content；
- Anthropic：`messages.create`，返回第一个 text block。

同步调用同样会注入思考参数，并走一次超时/连接重试。

## 两协议差异

| 维度 | OpenAI | Anthropic |
| --- | --- | --- |
| 工具 Schema 字段 | `parameters` | `input_schema` |
| system 消息 | 消息列表中的 system | 顶层 `system` 参数 |
| 思考参数 | `reasoning_effort` + `extra_body.thinking` | `extra_body.thinking` + `output_config.effort` |
| 工具结果 | tool role | user 消息中的 `tool_result` block |
| 自动 Langfuse 调用追踪 | 有（`langfuse.openai`） | 无（标准客户端） |
| `response_format` | 支持 | 不支持 |

## 已知边界

- 重试只覆盖超时/连接错误，不重放已经产生输出的流；
- 没有统一的 token 计数或成本统计；
- 协议兼容性取决于服务端，不保证任意“OpenAI 兼容”实现都支持工具调用和思考参数；
- 模型返回畸形 JSON 时，错误会在 ReAct 工具解析或上层 TOC/blog 解析处暴露。
