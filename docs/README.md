# Open Zread 文档索引

> 用 AI 把本地代码变成结构化 Wiki。

本页是 **Open Zread 项目自身的使用与实现文档**，不是 Open Zread 为其他仓库生成的 Wiki 预览。生成结果仍然使用 Zread CLI 的 `zread browse` 查看。

## 阅读路线

| 目的 | 建议路线 |
| --- | --- |
| 第一次运行 | [快速开始](features/01-getting-started.md) → [模型与配置](features/02-models-and-config.md) → [输出与预览](features/06-output-and-preview.md) |
| 理解整体设计 | [总览与模块地图](overview.md) → [两阶段流水线](features/03-two-phase-pipeline.md) → [流水线实现](internals/02-pipeline.md) |
| 学习 Agent 写法 | [ReAct Agent 循环](internals/01-react-agent.md) → [工具与安全边界](internals/05-tools-safety.md) → [Prompt 管理](internals/04-prompts.md) |
| 排查模型问题 | [模型协议适配](internals/03-providers.md) → [模型与配置](features/02-models-and-config.md) |
| 查看数据与配置 | [配置与本地存储](internals/06-settings-storage.md) |

## 概览

- [总览与模块地图](overview.md)：项目目标、两阶段架构、模块职责和数据流。

## 功能

| 页面 | 内容 |
| --- | --- |
| [快速开始](features/01-getting-started.md) | 安装、环境变量、配置、运行与常见问题 |
| [模型与配置](features/02-models-and-config.md) | 三档模型、OpenAI / Anthropic 协议、`settings.json` |
| [两阶段流水线](features/03-two-phase-pipeline.md) | 先生成目录，再并行生成正文 |
| [文件系统工具](features/04-tools.md) | 目录、文件读取和只读 Shell 命令 |
| [Langfuse 可观测性](features/05-observability.md) | 调用链追踪和远程 Prompt 管理 |
| [输出与预览](features/06-output-and-preview.md) | `.zread/wiki` 结构、版本和预览方式 |

## 原理

| 页面 | 内容 |
| --- | --- |
| [ReAct Agent 循环](internals/01-react-agent.md) | 流式事件、工具执行、步骤上限和上下文压缩 |
| [流水线编排](internals/02-pipeline.md) | 阶段编排、XML 目录解析、并行生成与失败处理 |
| [模型协议适配](internals/03-providers.md) | LLMAdaptor、双协议消息转换和流式事件 |
| [Prompt 管理](internals/04-prompts.md) | 本地模板、Langfuse Prompt、变量和输出格式 |
| [工具与安全边界](internals/05-tools-safety.md) | 白名单、输出限制和只读承诺的真实边界 |
| [配置与本地存储](internals/06-settings-storage.md) | 配置合并、环境变量加载、Wiki 版本格式 |

## 边界说明

- **本地编排不等于代码不出本机**：流水线在本机运行，但模型请求会把 Prompt、目录结构和工具读取到的代码片段发送给你配置的模型服务。
- **只读工具不是安全沙箱**：白名单能降低误操作风险，但不能把不可信仓库变成安全的执行环境。
- **没有内置阅读器**：生成的是 Markdown 和 `wiki.json`，预览请使用 Zread CLI 的 `zread browse`。
- **项目定位是学习 Agent**：CLI 交互、Web 预览等外围功能不在本仓库范围内。
