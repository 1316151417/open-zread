# ReAct Agent 循环

`agent/react_agent.py` 是 Open Zread 的执行核心。它把模型流式输出、工具调用和消息追加组织成一个可迭代的事件流，并在上下文过长时压缩历史。

## 输入与输出

```python
stream(messages, tools, config: dict, max_steps=30)
```

- `messages`：统一消息列表（`SystemMessage` / `UserMessage` / `AssistantMessage` / `ToolMessage` 或 dict）；
- `tools`：`Tool` 对象列表，来自 `@tool` 装饰器；
- `config`：当前模型层级配置；
- 返回值：生成器，逐个 `yield Event`。

循环内部创建 `LLMAdaptor(config)`，因此 `pro` 和 `max` 阶段各自使用自己的协议和模型。

## 一步做什么

```text
STEP_START
  ↓
压缩上下文（必要时）
  ↓
adaptor.stream(messages, tools) → 流式事件
  ↓
遇到 TOOL_CALL → 执行工具 → TOOL_CALL_SUCCESS / FAILED
  ↓
STEP_END（累积的文本 + 工具调用）
  ↓
有工具调用？→ 追加 Assistant + Tool 消息，进入下一步
没有工具调用？→ 结束
```

关键实现：

- `_Step` 累积 `content`、`thinking`、`tool_calls` 和工具结果；
- 工具在流式事件到达时按顺序执行，不并发；
- 工具参数用 `json.loads` 解析，失败会抛出 `ValueError`；
- 找不到工具名会抛出 `RuntimeError`；
- 工具自身抛出的异常会被捕获，作为 `tool_error` 回传给模型；
- 工具结果和错误都会进入下一条 `ToolMessage`。

## 消息结构

一步结束后追加：

```python
AssistantMessage(
    content=step_state.content,
    tool_calls=step_state.tool_calls,
    thinking=step_state.thinking,
)
ToolMessage(
    tool_id=...,
    tool_name=...,
    tool_result=...,
    tool_error=...,
)
```

`AssistantMessage.to_dict()` 会把 `thinking` 写成 `reasoning_content`，保留工具调用；`ToolMessage` 在 OpenAI 和 Anthropic 协议中会各自转换。

## 步骤上限

`max_steps` 默认 30，来自 `settings.json` 的 `max_sub_agent_steps`。达到上限后循环结束，没有单独的“超步数”事件。调用方通过 `collect_report(events)` 取最后一个 `STEP_END` 的 `content` 作为最终文本。

这意味着：

- 如果最后一步仍在调用工具，最终文本可能是中间思考，而不是完整报告；
- 失败或截断不会抛出统一异常，调用方需要检查输出；
- 更大的步数会增加调用次数和费用。

## 上下文压缩

阈值与保留策略：

| 项 | 值 |
| --- | --- |
| 触发阈值 | 消息 JSON 字符数 `> 200,000` |
| 保留最近消息 | 6 条非 system 消息 |
| 摘要输入上限 | 30,000 字符 |
| 摘要 Prompt | `compress` |

流程：

1. 统计所有消息 `json.dumps(..., ensure_ascii=False)` 的字符数；
2. 超过阈值时，把 system 消息和最近 6 条非 system 消息分开；
3. 丢弃最近消息开头孤立的 `tool` 消息，避免工具结果没有对应的 tool call；
4. 用当前 `LLMAdaptor` 同步调用（`adaptor.call`）生成摘要；
5. 把摘要写成一条 user 消息，加一条 assistant 确认，再接上最近消息；
6. 打印压缩前后字符数。

失败处理：

- 摘要调用异常时打印错误，摘要为空；
- 仍然使用 system + 最近消息继续；
- 不保证保留每个细节。

注意这是**字符数**阈值，不是模型 token 计数；多语言、JSON 结构和工具输出的字符密度不同，实际 token 占用可能差异很大。

## Langfuse 观察

`stream` 被 `@observe(name="react_agent_stream")` 装饰；启用 Langfuse 时会产生 Agent span。关闭时装饰器是 no-op。

## 已知边界

- 工具调用串行执行，慢工具会阻塞当前步骤；
- 不支持模型一次返回多个并行工具后的并发执行；
- 压缩只保留最近 6 条，可能导致早期文件内容丢失；
- 没有自动重试整步；传输层只对超时/连接错误重试一次；
- 模型输出格式异常时，由上层解析（TOC XML / `<blog>`）暴露问题。
