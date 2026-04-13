# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM 驱动的自动化代码深度分析引擎。输入任意代码仓库路径，输出结构化的中文项目分析报告（架构总览、模块详解、跨模块洞察、总结建议）。

底层使用 DeepSeek API 端点，支持 OpenAI/Anthropic 两种协议格式的流式调用 + 工具调用（ReAct 模式）。

## Commands

```bash
# 分析本地项目
uv run python main.py /path/to/project

# 指定配置文件
uv run python main.py /path/to/project --settings /path/to/settings.json

# 输出到指定文件
uv run python main.py /path/to/project -o output.md

# 运行测试
python test/llm_test.py

# 使用 uv 管理依赖（项目用 uv，不用 pip）
uv sync
uv add <package>
```

## Environment Variables

```bash
export DEEPSEEK_API_KEY="your-api-key"
export DEBUG=1  # 启用调试日志输出
```

## Architecture

### 6-Stage Pipeline

```
输入 → 扫描项目 → LLM过滤 → 模块拆分 → 模块打分 → 深度研究 → 汇总报告 → 输出
```

1. **scanner** — 遍历文件，收集大小/扩展名/路径，硬编码过滤 node_modules/.git/test/docs
2. **llm_filter** — 基于项目类型判断文件重要性，LLM 智能过滤
3. **decomposer** — 按目录结构 + import 关系划分模块
4. **scorer** — 核心度/依赖度/入口/领域独特性评分
5. **researcher** — 并行 ReAct agent 深度研究，每模块生成→评估→重试→最终
6. **aggregator** — ReAct agent 整合所有模块报告，生成→评估→重试→最终

### 事件流（核心数据流）

所有交互通过 `Event` 统一抽象，流式顺序：

```
MESSAGE_START → THINKING_START → THINKING_DELTA* → THINKING_END
              → CONTENT_START  → CONTENT_DELTA*  → CONTENT_END
              → TOOL_CALL*
              → MESSAGE_END

ReAct agent 额外事件：
STEP_START/STEP_END（每轮迭代）
TOOL_CALL_SUCCESS/TOOL_CALL_FAILED（工具执行结果）
```

### 关键模块

| 文件 | 职责 |
|------|------|
| `base/types.py` | 核心类型：EventType/Event/Tool/Message 体系/@tool 装饰器 |
| `provider/adaptor.py` | LLMAdaptor 统一流式接口，OpenAI/Anthropic 协议互转，上下文压缩 |
| `provider/api/anthropic_api.py` | Anthropic 协议客户端实现 |
| `provider/api/openai_api.py` | OpenAI 协议客户端实现 |
| `agent/react_agent.py` | ReAct 循环：消费事件、执行工具、维护多轮对话 |
| `pipeline/run.py` | `run_pipeline()` 入口，6 阶段调度 |
| `pipeline/types.py` | PipelineContext/Module/FileInfo 数据结构 |
| `prompt/pipeline_prompts.py` | 所有提示词定义：FILE_FILTER/SCORER/SUB_AGENT/EVAL/AGGREGATOR 等 |
| `prompt/react_prompts.py` | ReAct agent 专用提示词 |
| `tool/fs_tool.py` | 文件系统工具：read_file/list_directory/glob_pattern/grep_content（线程安全） |
| `log/printer.py` | 事件格式化打印，流式输出追踪 |
| `log/logger.py` | 调试日志，DEBUG=1 启用 |

### 关键设计

1. **TOOL_CALL 事件的 `raw` 字段**：携带 `{"id", "name", "arguments"}`，直接构建 `AssistantMessage`
2. **`@tool` 装饰器**：从函数签名/docstring 自动提取参数，生成 `Tool` 对象
3. **消息格式转换在 adaptor 层**：agent 层使用统一中间格式
4. **三级模型分层**：lite=过滤/pro=研究/max=汇总，平衡速度与质量
5. **tool_use 文本过滤**：`STEP_END` 过滤 LLM 误输出的 `tool_use(...)` 文本
6. **流式超时保护**：daemon thread + Queue + 120s per step + 60s LLM call
7. **上下文压缩**：`MAX_CONTEXT_CHARS=200000` 阈值，自动压缩超长对话保留关键引用

### Settings Configuration (`settings.json`)

三级模型独立配置，每级包含 provider/base_url/api_key/model/max_tokens：

```json
{
  "lite": { "provider": "anthropic", "base_url": "https://api.deepseek.com/anthropic", "model": "deepseek-chat" },
  "pro":  { "provider": "anthropic", "base_url": "https://api.deepseek.com/anthropic", "model": "deepseek-chat" },
  "max":  { "provider": "anthropic", "base_url": "https://api.deepseek.com/anthropic", "model": "deepseek-reasoner" },
  "max_sub_agent_steps": 30,
  "research_parallel": true,
  "research_threads": 10,
  "debug": false
}
```

| 配置项 | 说明 |
|--------|------|
| `lite` | 分类/过滤/打分用（速度快） |
| `pro` | 子模块深度分析 + 评估用（推理能力强） |
| `max` | 最终汇总用（最强推理） |
| `max_sub_agent_steps` | 每个 agent 的最大步数 |
| `research_parallel` | 是否并行研究模块 |
| `research_threads` | 并行研究线程数 |

## Dependencies

Python 3.12, `anthropic>=0.89.0`, `openai>=2.30.0`。包管理用 `uv`.
