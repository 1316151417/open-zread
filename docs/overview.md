# 总览与模块地图

Open Zread 是一个用 AI Agent 分析本地代码仓库、生成结构化 Wiki 的 Python 工具。它先让模型探索项目并产出文档目录，再为每个主题启动独立的 ReAct Agent 写正文，最终把结果写入目标项目目录的 `.zread/wiki/`。

项目定位是 **学习 Agent 开发**：代码量不大，但包含 ReAct 循环、工具调用、上下文压缩、Prompt 管理和双协议模型适配等核心模式。

## 它解决什么问题

面对一个不熟悉的仓库，人通常先看目录、入口和关键模块，再决定从哪里深入。Open Zread 把这条路径交给模型：

1. 读取仓库结构和关键文件；
2. 生成有层级的文档目录（TOC）；
3. 围绕每个主题继续调查并写出一页 Markdown；
4. 把目录、页面和版本信息保存到本地。

它不是聊天客户端，也不是通用 RAG 系统；输出是可供 Zread CLI 预览的 Wiki 文件。

## 两阶段流水线

```
main.py
  └─ pipeline/run.py
       ├─ 阶段 1：pipeline/explorer.py
       │    LLMAdaptor(pro) → ReAct Agent → 文件系统工具
       │    → XML 目录 → parse_toc_xml → Topic[]
       └─ 阶段 2：pipeline/researcher.py
            LLMAdaptor(max) → 每个主题独立 ReAct Agent
            → <blog> Markdown → .zread/wiki/versions/<timestamp>/
```

阶段 1 只负责“写什么”，阶段 2 负责“每页怎么写”。两阶段分开，使目录结构可以先被检查，也方便第二阶段的主题并行生成。

## 模块地图

| 模块 | 职责 | 入口 |
| --- | --- | --- |
| `agent` | ReAct 循环、流式事件、工具执行、上下文压缩 | [agent/react_agent.py](https://github.com/1316151417/open-zread/blob/main/agent/react_agent.py) |
| `base` | Event、Tool、Message 类型与 `@tool` 装饰器 | [base/types.py](https://github.com/1316151417/open-zread/blob/main/base/types.py) |
| `pipeline` | 两阶段编排、TOC 生成、逐主题内容生成 | [pipeline/run.py](https://github.com/1316151417/open-zread/blob/main/pipeline/run.py) |
| `prompt` | Prompt 模板、本地编译、Langfuse 远程管理 | [prompt/langfuse_prompt.py](https://github.com/1316151417/open-zread/blob/main/prompt/langfuse_prompt.py) |
| `provider` | OpenAI / Anthropic 协议适配与流式解析 | [provider/adaptor.py](https://github.com/1316151417/open-zread/blob/main/provider/adaptor.py) |
| `setting` | `settings.json` 加载、合并、环境变量展开 | [setting/settings.py](https://github.com/1316151417/open-zread/blob/main/setting/settings.py) |
| `tool` | 目录结构、文件读取、只读 Shell 工具 | [tool/fs_tool.py](https://github.com/1316151417/open-zread/blob/main/tool/fs_tool.py) |
| `util` | TOC 解析、内容提取、slug、Langfuse 开关 | [util/utils.py](https://github.com/1316151417/open-zread/blob/main/util/utils.py) |

所有模块都用普通 Python 编写，没有框架魔法。`LLMAdaptor` 是唯一的模型入口，工具通过 `@tool` 装饰器自动生成参数 Schema。

## 一次运行的产物

```text
<目标项目>/.zread/wiki/
├── current                      # 文本指针：versions/<timestamp>
└── versions/
    └── 2026-04-26-120000/
        ├── wiki.json            # 目录、页面、语言、生成时间
        ├── 1-xiang-mu-gai-shu.md
        ├── 2-kuai-su-qi-dong.md
        └── ...
```

`wiki.json` 在阶段 1 结束后、正文生成前写入；`current` 也会先更新。因此生成中断时，目录可能已经可见，但部分 Markdown 页面尚未写完。每次运行都会创建新版本，不覆盖旧版本。

## 设计取舍

- **目录先行**：先用较轻的 `pro` 配置生成结构，避免一上来就为错误结构写大量正文。
- **逐主题独立 Agent**：每个主题有自己的对话和工具调用，互不共享上下文，适合并行；代价是主题之间可能重复探索同一批文件。
- **本地编排，外部模型**：文件操作、目录遍历和结果存储在本机；Prompt 和代码片段会发送给配置的模型服务。
- **Prompt 双模式**：默认使用仓库内模板；启用 Langfuse 后可以从远程 Prompt Management 拉取，便于调优。
- **只读工具**：没有写入、删除或执行程序的内置工具；但白名单不是操作系统级沙箱，边界见[工具与安全边界](internals/05-tools-safety.md)。
- **字符数压缩**：上下文超过 200K 字符时压缩旧消息，而不是依赖模型 token 计数。

## 阅读路线

- 想运行：从[快速开始](features/01-getting-started.md)开始。
- 想理解整体：读[两阶段流水线](features/03-two-phase-pipeline.md)，再看[流水线编排](internals/02-pipeline.md)。
- 想学习 Agent：读[ReAct Agent 循环](internals/01-react-agent.md)和[工具与安全边界](internals/05-tools-safety.md)。
- 想接模型：读[模型协议适配](internals/03-providers.md)。

## 明确边界

Open Zread 不提供登录、账号、内置模型额度、CLI 交互或内置 Wiki 阅读器。它也不承诺“只读工具绝对安全”或“生成内容一定正确”。使用前请阅读目标仓库和模型服务的权限、隐私及费用条款。
