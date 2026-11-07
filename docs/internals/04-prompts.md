# Prompt 管理

Open Zread 有两套 Prompt 来源：仓库内的 Python 模板和 Langfuse Prompt Management。两者使用同一组名称和变量，切换由 `LANGFUSE_ENABLE` 决定。

## 名称与调用点

| 名称 | 调用点 | 作用 |
| --- | --- | --- |
| `step1` | `pipeline/explorer.py` | 探索仓库并输出 XML 目录 |
| `step2` | `pipeline/researcher.py` | 为单个主题输出 `<blog>` Markdown |
| `compress` | `agent/react_agent.py` | 压缩过长对话 |

`get_compiled_messages(name, **variables)` 返回 `[system, user]` 两条消息。

## 本地模式

关闭 Langfuse 时：

- `step1` ← `prompt/pipeline_prompts.py:STEP1_SYSTEM / STEP1_USER`
- `step2` ← `STEP2_SYSTEM / STEP2_USER`
- `compress` ← `prompt/react_prompts.py:COMPRESS_SYSTEM / COMPRESS_USER`

使用 Python `str.format(**variables)` 编译。变量中的花括号必须符合 Python 格式规则；新增变量时要同步模板和调用点。

## Langfuse 模式

启用 Langfuse 时：

1. `get_compiled_messages` 从 Langfuse `get_prompt(name, type="chat")` 获取 chat prompt；
2. 调用 `prompt.compile(**variables)` 填充变量；
3. 通过 `update_current_generation(prompt=prompt)` 关联当前 generation。

同步命令：

```bash
uv run python -m prompt.langfuse_prompt_init
```

同步脚本把每个名称的 system/user 模板写成 chat prompt，并把 `{var}` 转成 Langfuse 的 `{{var}}`，设置 `production` 标签。

## step1 变量与约束

`step1` 使用：

| 变量 | 来源 |
| --- | --- |
| `working_dir` | 目标项目绝对路径 |
| `os_name` | `platform.system().lower()` |
| `repo_structure` | 阶段 1 预生成的两层目录 |
| `doc_language` | `settings.json` |

Prompt 要求：

- 输出严格的 `<section>` / `<group>` / `<topic>` 结构；
- 主题不超过 30 个；
- 快速入门的前两个主题固定为“项目概述”和“快速启动指南”；
- 深度解析用于技术细节；
- 每个主题带 `Beginner` / `Intermediate` / `Advanced`；
- 只输出目录，不附带解释。

解析器依赖这些标签；模型不遵守时会得到空主题或错误的结构。

## step2 变量与约束

`step2` 使用：

| 变量 | 来源 |
| --- | --- |
| `working_dir` / `os_name` | 同上 |
| `current_section` | 当前主题的章节 |
| `current_topic` | 当前主题名 |
| `target_audience` | `settings.json` |
| `doc_language` | 同上 |
| `repo_structure` | 预生成目录 |
| `full_toc` | 带当前位置标记的完整目录 |

Prompt 要求：

- 只写当前主题，不越界；
- 使用 Mermaid、表格和来源标注；
- 来源格式 `Sources: [文件名](相对路径#Lx-Ly)`；
- 最终内容包在 `<blog></blog>` 中；
- 语言和目标受众与配置一致。

`extract_blog_content` 只提取 `<blog>` 内部；没有标签时直接返回全文。

## compress 变量

`compress` 只接收 `conversation`，内容是被压缩消息的格式化文本，最多 30,000 字符。要求保留工具关键结果、重要结论、文件路径和函数名，丢弃冗余推理。

## 修改 Prompt 的注意点

- **本地模式**：修改 Python 字符串后立即生效；变量名必须与调用方一致。
- **Langfuse 模式**：同步脚本只负责创建新版本；正在使用的 Prompt 版本由 Langfuse 标签/部署策略决定。
- **格式约定**：TOC 依赖 XML 标签，正文依赖 `<blog>`；改格式要同步修改 `parse_toc_xml` / `extract_blog_content`。
- **语言**：章节名、主题名和正文都应遵守 `doc_language`；`wiki.json` 的语言标记只区分“中文/其他”。
- **安全**：Prompt 会包含仓库结构和工具读取的代码片段；不要在其中拼接密钥。

## 没有的机制

- 没有 Prompt 单元测试；
- 没有输出 Schema 校验（TOC 用正则，正文只取标签）；
- 没有自动回退：Langfuse 不可用时不会切回本地模板；
- 没有版本对比界面。

需要稳定输出时，优先在本地模板上迭代，验证后再同步到 Langfuse。
