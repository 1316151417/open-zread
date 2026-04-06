# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM 编排框架，支持多 provider（OpenAI/Anthropic 协议）的流式调用 + 工具调用（ReAct 模式）。底层使用 DeepSeek API 端点，兼容两种协议格式。

## Commands

```bash
# 运行测试
python test/llm_test.py

# 使用 uv 管理依赖（项目用 uv，不用 pip）
uv sync
uv add <package>
```

## Architecture

### 事件流（核心数据流）

所有交互通过 `Event` 统一抽象，按流式顺序：

```
MESSAGE_START → THINKING_START → THINKING_DELTA* → THINKING_END
              → CONTENT_START  → CONTENT_DELTA*  → CONTENT_END
              → TOOL_CALL*
              → MESSAGE_END
```

ReAct agent 在此基础上增加：`STEP_START/STEP_END`（每轮迭代）、`TOOL_CALL_SUCCESS/TOOL_CALL_FAILED`（工具执行结果）。

### 模块职责

- **`base/types.py`** — 所有核心类型：`EventType`、`Event`、`Tool`、`Message` 体系（System/User/Assistant/ToolMessage）、`@tool` 装饰器、`normalize_messages()`。这是整个系统的基础契约。
- **`provider/adaptor.py`** — `LLMAdaptor`：统一流式接口。内部根据 provider 分派到 OpenAI/Anthropic 的 SDK 调用，并将原生流式事件转换为统一的 `Event`。包含 `_convert_messages_openai/anthropic` 做 provider 间的消息格式转换。
- **`agent/react_agent.py`** — `stream()` 生成器：ReAct 循环。消费 `LLMAdaptor.stream()` 的事件，执行工具，维护多轮对话历史，向外转发事件。
- **`log/logger.py`** — `Logger.debug()`：带格式化的调试输出，`DEBUG=True` 时输出到控制台。
- **`log/printer.py`** — `print_event()`：将 Event 转为人类可读的终端输出。

### 关键设计决策

1. **TOOL_CALL 事件的 `raw` 字段**：携带 `{"id", "name", "arguments"}` 的 dict，可直接用于构建 `AssistantMessage(tool_calls=...)`，避免在 agent 层重复拆装数据。

2. **Anthropic vs OpenAI 流式差异**：
   - Anthropic：每个 tool_use 有独立的 `content_block_start/stop`，工具逐个触发执行
   - OpenAI：所有 tool_calls 在 `finish_reason` 时批量输出

3. **消息格式转换在 adaptor 层完成**：agent 层使用统一的中间格式（`AssistantMessage` 带 `tool_calls`、`ToolMessage` 带 `tool_id`/`tool_result`/`tool_error`），adaptor 负责转为各 provider 的原生格式。

4. **`@tool` 装饰器**：从函数签名和 docstring 自动提取参数类型、描述，生成 `Tool` 对象，同时保留原始函数可调用。

## Dependencies

Python 3.12, `anthropic>=0.89.0`, `openai>=2.30.0`。包管理用 `uv`。
