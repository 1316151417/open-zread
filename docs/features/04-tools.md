# 文件系统工具

Open Zread 的 Agent 只有三个内置工具，全部位于 `tool/fs_tool.py`。它们的目标是“读取和调查”，不是修改仓库。

## 工具一览

| 工具 | 作用 | 关键限制 |
| --- | --- | --- |
| `get_dir_structure` | 输出树形目录结构 | 默认深度 3；跳过常见依赖目录和点文件 |
| `view_file_in_detail` | 读取文件片段 | 默认前 200 行；超过 100KB 拒绝读取 |
| `run_bash` | 执行只读查询命令 | 命令前缀白名单；危险模式过滤；30 秒超时；50K 输出上限 |

### get_dir_structure

参数：`dir_path="."`、`max_depth=3`。

- 路径相对于当前项目根目录；
- 目录优先排序；
- 跳过 `.git`、`node_modules`、`.venv`、`dist`、`build`、缓存目录等；
- 跳过点文件，但保留 `.env` 和 `.env.example` 名称（不读取内容）；
- 无权限目录会输出“（无权限）”。

实现里维护的是**硬编码跳过列表**。工具 docstring 和 Prompt 提到“过滤 `.gitignore` 条目”，但当前实现并没有解析 `.gitignore`；`pathspec` 虽然在依赖中，尚未接入。这一点见[工具与安全边界](../internals/05-tools-safety.md)。

### view_file_in_detail

参数：

```python
view_file_in_detail(
    file_path: str,
    start_line: int = 1,
    end_line: int = 200,
    show_line_numbers: bool = True,
)
```

- 路径相对于项目根目录；
- 读取整文件后截取行范围，返回文件名、行号和总行数；
- 大于 `MAX_READ_SIZE * 5`（约 100KB）时返回警告，不读取内容；
- 读取失败、文件不存在会返回文字错误，不抛异常给 Agent。

大文件需要模型自己分段调用；第一页不代表完整文件。

### run_bash

参数：`command: str`。

- 在工作目录（项目根目录）执行；
- `subprocess.run(..., shell=True)`；
- 超时 30 秒；
- 标准输出和标准错误合并返回；
- 输出超过 50,000 字符会截断。

允许的命令前缀包括：

```
ls find cat grep head tail wc file du stat which type echo pwd
git diff sort uniq awk sed tr cut xargs tee date uname whoami
```

危险模式（例如 `rm `、`mv `、`cp `、`chmod `、`sudo `、`curl `、`wget `、`>`、`>>`、`&&`、`;`、反引号、`$(`、常见解释器和包管理器）会被拒绝。`grep`、`find`、`git` 开头的管道 `|` 是例外。

## 为什么只有三个工具

- 目录和文件读取覆盖了“理解代码”的主要动作；
- 搜索、Git 历史、文本处理都可以通过 `run_bash` 完成；
- 没有 `write` / `edit` / 删除工具，降低误修改概率；
- 工具越少，Prompt 和模型选择越稳定。

## 使用建议

- 在 Prompt 或项目指令中要求模型“先看目录，再读关键文件”；
- 对大型仓库，从入口文件和 README 开始，而不是全量遍历；
- 需要生成内容时，确保工具返回的是可验证的代码，而不是模型猜测；
- 不要把白名单当成安全隔离。`git`、`sed`、`tee`、`xargs` 等命令的子命令或参数仍可能产生副作用。

## 安全边界

`run_bash` 的“只读”是**基于字符串的白名单和模式过滤**，不是操作系统级沙箱：

- `shell=True` 意味着允许的命令仍由 Shell 解析；
- 白名单按第一个词判断，给 `git`、`sed`、`tee`、`xargs` 留下了较大的参数空间；
- `git` 可以访问远端或执行某些有副作用的子命令；
- 模型可能被仓库中的文本提示注入，从而尝试绕过约束。

因此，Open Zread 适合在**你信任的本地仓库**上运行。详细分析见[工具与安全边界](../internals/05-tools-safety.md)。
