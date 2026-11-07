# 两阶段流水线

一次运行分成两个阶段：先让模型决定“写哪些页面”，再为每个页面单独写正文。阶段之间通过 `Topic` 列表和 `wiki.json` 衔接。

## 阶段 1：生成目录

入口是 `pipeline/explorer.py:generate_toc`：

1. 设置目标项目根目录（`ContextVar`，线程安全）；
2. 预先获取两层目录结构；
3. 用 `pro` 配置编译 `step1` Prompt；
4. 启动 ReAct Agent，允许调用目录、文件读取和只读 Shell 工具；
5. 收集最终文本，按 `<section>` / `<group>` / `<topic>` 解析为 `Topic`。

Prompt 要求模型输出：

```html
<section>
快速入门
<topic level="Beginner">
项目概述
</topic>
<topic level="Beginner">
快速启动指南
</topic>
</section>
<section>
深度解析
<group>
核心机制
<topic level="Advanced">
ReAct Agent
</topic>
</group>
</section>
```

约束：

- 主题总数由 Prompt 限制为不超过 30 个；
- 每个主题必须带 `Beginner` / `Intermediate` / `Advanced`；
- 章节名和主题名使用配置的文档语言；
- slug 由 `util/utils.py:slugify` 生成：`{序号}-{拼音}`，例如 `1-xiang-mu-gai-shu`；
- 解析器本身不会截断超过 30 个的主题，限制主要靠 Prompt。

目录解析失败会抛出“未能解析出任何主题”，阶段 2 不会启动。

## 写入目录与版本

阶段 1 成功后，`pipeline/run.py` 会：

1. 创建 `.zread/wiki/versions/<YYYY-MM-DD-HHMMSS>/`；
2. 写入 `current` 指针；
3. 用 `Topic` 生成 `wiki.json`。

`wiki.json` 在正文生成之前就已保存，因此生成中断时目录仍然存在，部分 `file` 可能还没有对应内容。详情见[输出与预览](06-output-and-preview.md)。

## 阶段 2：逐主题生成

入口是 `pipeline/researcher.py:generate_topic_content`：

1. 每个主题重新设置项目根目录；
2. 使用 `max` 配置和 `step2` Prompt；
3. Prompt 带上完整目录和 `[你当前在此处]` 标记，限制只写当前主题；
4. ReAct Agent 再次使用三个文件系统工具；
5. 从输出中提取 `<blog>...</blog>`，作为该主题的 Markdown。

每个主题是独立 Agent，不共享对话历史。它们共享的只有：

- 目标项目目录；
- 预生成的目录结构；
- 全局配置（并发数、步数、语言、受众）。

## 并行与失败处理

`research_parallel=true` 时用 `ThreadPoolExecutor` 按 `research_threads` 并发执行。每个主题完成后立即写入自己的 `<slug>.md`。

失败处理规则：

- 单个主题抛异常时打印失败信息，不终止其他主题；
- 全部主题结束后仍然算流程完成；
- `wiki.json` 不会因为某个主题失败而删除对应条目；
- 重新运行会创建新版本，不会覆盖失败版本。

这适合“先拿到大部分页面”的用法，但意味着你需要自己检查哪些页面缺失。

## 目录如何影响正文

阶段 2 的 Prompt 包含：

- 当前主题名和章节；
- 完整目录及当前位置；
- 目标受众；
- 文档语言；
- 顶层目录结构。

Prompt 要求模型使用 Mermaid、表格和 `Sources: [文件名](相对路径#Lx-Ly)` 标注来源，并只用当前主题范围的内容。实际输出质量取决于模型是否遵守这些约束；Open Zread 没有后处理校验引用是否真实。

## 可以调整什么

| 目标 | 配置 |
| --- | --- |
| 减少单主题步数 | `max_sub_agent_steps` |
| 关闭并行 | `research_parallel=false` |
| 降低并发 | `research_threads` |
| 改文档语言 | `doc_language` |
| 改目标受众 | `target_audience` |
| 换阶段模型 | `pro` / `max` 配置 |

阶段内部实现见[流水线编排](../internals/02-pipeline.md)，Agent 循环见[ReAct Agent 循环](../internals/01-react-agent.md)。
