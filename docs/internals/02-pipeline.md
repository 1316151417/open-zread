# 流水线编排

`pipeline/run.py` 负责把配置、目录、版本、阶段 1 和阶段 2 串起来。它不包含 Prompt 或协议细节，主要是流程和状态管理。

## run_pipeline 的顺序

```text
run_pipeline(settings_path=None)
  ├─ session_id = pipeline-<uuid8>
  ├─ load_settings()
  ├─ project_path = os.getcwd()
  ├─ 创建 .zread/wiki/versions/<timestamp>/
  ├─ 写 current 指针
  ├─ 构造 PipelineContext
  │    ├─ lite / pro / max 配置
  │    ├─ 步数、并发、语言、受众
  │    └─ settings
  ├─ 阶段 1：generate_toc(ctx)
  ├─ 写 wiki.json
  └─ 阶段 2：逐主题 generate_topic_content
```

`settings_path` 参数存在，但 `main.py` 调用时传 `None`，因此配置来自当前目录或内置默认值。

## 版本与 current 的时序

```python
version_dir = .zread/wiki/versions/<timestamp>
current      = .zread/wiki/current
```

- 版本目录在阶段 1 **之前**创建；
- `current` 在阶段 1 **之前**写入；
- `wiki.json` 在阶段 1 **之后**、阶段 2 **之前**写入。

如果阶段 1 失败，版本目录和 `current` 可能已经存在，但没有 `wiki.json`。如果阶段 2 中途失败，`wiki.json` 会列出所有主题，但部分 Markdown 文件缺失。这是“尽早可见”和“原子性”之间的取舍。

## PipelineContext

`pipeline/types.py` 中的 `PipelineContext` 保存：

| 字段 | 用途 |
| --- | --- |
| `project_path` / `project_name` | 目标目录 |
| `lite_config` / `pro_config` / `max_config` | 三档模型配置 |
| `max_sub_agent_steps` | 单主题 ReAct 步数 |
| `research_parallel` / `research_threads` | 并行策略 |
| `settings` | 语言、受众等 |
| `repo_structure` | 预生成的目录结构 |
| `toc_xml` | 阶段 1 原始输出 |
| `topics` | 解析后的 `Topic` 列表 |

`Topic` 包含 `name`、`slug`、`level`、`section_name`、可选的 `group_name` 和生成后的 `content`。

## 阶段包装与 Langfuse

`_observed(name, fn, ...)` 在 `propagate_attributes(session_id=..., metadata=...)` 中调用 `observe`：

- `generate_toc`：整个阶段 1；
- `generate_content`：单个主题，metadata 带 `topic_name`；
- 会话 ID 在本次运行内固定，便于在 Langfuse 中串起来。

关闭 Langfuse 时，`propagate_attributes` 是 `nullcontext`，`observe` 是恒等装饰器。

## 阶段 2 的并发

```python
if research_parallel:
    with ThreadPoolExecutor(max_workers=research_threads) as executor:
        futures = {executor.submit(_process_topic, t): t for t in ctx.topics}
        for future in as_completed(futures):
            future.result()
else:
    for topic in ctx.topics:
        _process_topic(topic)
```

- `research_threads` 默认 10；
- 每个主题独立调用 `generate_topic_content`；
- 每个主题完成立即写自己的 `<slug>.md`；
- 单个主题异常被 `_process_topic` 捕获并打印，不影响其他主题；
- 并行时 stdout 会交错，日志顺序不等于主题顺序。

## 工具根目录与线程

`tool/fs_tool.py` 用 `ContextVar` 保存项目根目录。每个主题在自己的线程里调用 `set_project_root(ctx.project_path)`，因此不会与其他线程串目录。`ContextVar` 的值在线程内独立，这是并行安全的关键。

## TOC 解析

`util/utils.py:parse_toc_xml`：

- 用正则提取 `<section>`、`<group>`、`<topic>`;
- `<section>` 后的第一行非标签文本作为章节名；
- 主题按出现顺序编号；
- slug 使用 `pypinyin` 生成 `{index}-{pinyin}`；
- 支持 group；group 内主题带 `group_name`；
- 解析失败返回空列表，阶段 1 抛错。

正则解析对模型输出格式敏感。Prompt 要求只输出 XML/HTML 片段，但模型仍可能加解释文字；只要 `<section>` 等标签存在，通常能提取。

## 内容提取

`researcher.py` 用 `extract_blog_content` 从模型输出中取 `<blog>...</blog>`。没有 `<blog>` 标签时直接返回原文。这意味着模型可能把“分析过程”也写入最终 Markdown。

## 已知限制

- 没有断点续跑：中断后重新运行会创建新版本；
- 没有主题级重试；
- 没有并发写入锁：不同主题写不同文件，通常安全；`wiki.json` 和 `current` 在阶段 2 前写入；
- `lite` 配置当前不参与执行；
- 没有 TOC 人工编辑入口；
- 失败主题不会从 `wiki.json` 删除。
