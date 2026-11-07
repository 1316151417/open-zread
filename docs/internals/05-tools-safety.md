# 工具与安全边界

三个文件系统工具是 Agent 与仓库之间的唯一内置通道。它们的设计目标是“读得够用、尽量不写”，但实现层面并不是安全沙箱。

## 实现概览

`tool/fs_tool.py` 使用 `ContextVar` 保存项目根目录：

```python
_project_root_var: ContextVar[str] = ContextVar("_project_root_var", default="")
set_project_root(path)   # 每个 Agent 线程调用
get_project_root()
```

这样并行主题不会互相切换目录。每个工具都用 `@tool` 装饰器把函数签名和 docstring 转成模型可见的 Schema。

## get_dir_structure

- 归一化 `os.path.join(root, dir_path)`，用 `normpath`；
- 递归 `os.listdir`，按名称排序；
- 跳过 `_SKIP_DIRS`：`.git`、`node_modules`、`vendor`、`.venv`、`__pycache__`、`dist`、`build`、缓存目录等；
- 跳过以 `.` 开头的条目，但保留 `.env` 和 `.env.example`；
- 深度达到 `max_depth` 停止；
- 无权限目录输出“（无权限）”。

**注意**：docstring 和 Prompt 声称会自动过滤 `.gitignore`，但当前代码只使用硬编码列表。`pathspec` 出现在 `pyproject.toml` 中，尚未被调用。因此 `.gitignore` 中忽略但不在硬编码列表里的目录仍可能被展示。

## view_file_in_detail

- 路径必须位于项目根目录下（通过 `os.path.join` 拼接；没有额外 realpath 逃逸检查）；
- 文件大于约 100KB 时直接返回警告；
- 读取全部行后按 `start_line`/`end_line` 截取；
- 可关闭行号；
- 读取异常返回字符串，不抛出。

“相对路径”来自模型，模型可能尝试 `../` 等路径。当前实现没有显式拒绝越界路径；这是另一个不应把工具当沙箱的原因。

## run_bash

执行前做两层过滤：

1. **危险模式子串检查**：`rm `、`mv `、`cp `、`chmod `、`chown `、`kill `、`sudo `、`curl `、`wget `、`>`、`>>`、`&&`、`;`、反引号、`$(`、`python`、`node`、`bash`、`sh `、`npm`、`pip`、`uv`、`docker`、`make` 等；
2. **首个词白名单**：`ls find cat grep head tail wc file du stat which type echo pwd git diff sort uniq awk sed tr cut xargs tee date uname whoami`。

例外：`grep`、`find`、`git` 开头的命令允许 `|`。

然后：

```python
subprocess.run(command, shell=True, capture_output=True, text=True, cwd=root, timeout=30)
```

输出上限 50,000 字符。

### 这不是安全沙箱

白名单按首词判断，允许的参数空间很大：

- `sed -i` 可以写文件；
- `tee` 可以写文件；
- `xargs` 可以组合执行其他程序；
- `git` 有大量子命令，部分会写对象、改配置或访问远端；
- `awk`/`tr`/`cut` 等通常只读，但组合方式不受限制；
- `shell=True` 意味着命令仍由 Shell 解析；
- 危险模式是字符串子串匹配，可通过引号、变量、编码等方式绕过。

此外，模型可能被仓库中的内容提示注入，主动尝试绕过约束。因此：

- 只在可信仓库上运行；
- 不要把 Open Zread 部署成多租户服务；
- 需要强隔离时，使用容器、只读挂载、独立用户和网络策略；
- 不要把“工具描述说只读”当成安全保证。

## 路径与写入

- 没有内置 `write` / `edit` / delete 工具；
- `view_file_in_detail` 的路径拼接没有显式根目录 containment 校验；
- `run_bash` 的工作目录是项目根目录，但命令可以访问其他路径（取决于系统权限）；
- 工具运行在启动 Open Zread 的当前用户权限下，没有降权。

## 超时与输出

| 项 | 值 |
| --- | --- |
| Shell 超时 | 30 秒 |
| Shell 输出上限 | 50,000 字符 |
| 文件读取上限 | 约 100KB |
| 目录默认深度 | 3 |

超时或输出截断会以文字返回给模型；模型需要自己决定是否分段读取。

## 已知缺口

- `.gitignore` 过滤未实现（`pathspec` 未接入）；
- 缺少 `realpath` 根目录 containment；
- 白名单对 `git`、`sed`、`tee`、`xargs` 过于宽松；
- 没有命令级参数解析，只有子串和首词检查；
- 没有审计日志（除非启用 Langfuse，且只记录工具输入输出到追踪）；
- 没有沙箱、容器或只读文件系统隔离。

这些缺口不影响“在可信仓库上做代码分析”的主要用途，但决定了它不能被视为安全边界。
