# 配置与本地存储

`setting/settings.py` 负责把 JSON 配置、环境变量和默认值合并成运行配置；`pipeline/run.py` 负责把结果写入 `.zread/wiki/`。

## 配置加载

`load_settings(path=None)`：

1. 如果传入 `path`，使用它；
2. 否则依次查找：
   - `<当前目录>/settings.json`
   - `<open-zread>/setting/settings.json`
3. 找到就读取，否则使用 `_DEFAULTS`；
4. 与默认值做顶层合并；
5. 对 `lite` / `pro` / `max` 再做一次层级内合并；
6. 递归展开所有 `${VAR}`；
7. 对 Anthropic 配置补 `/anthropic`；
8. 缓存到模块级 `_settings`。

这意味着：

- 仓库根目录的 `settings.json` 不是“包内默认配置”，从目标项目运行时不会读取；
- 配置在第一次调用时缓存，运行中修改不会生效；
- 部分字段缺失时用默认值补齐，不会报错；
- `api_key` 支持环境变量展开，但不支持嵌套表达式。

`reset_settings()` 只用于测试/特殊场景，会清空缓存。

## 默认配置

来自 `_DEFAULTS`：

| 项 | 默认值 |
| --- | --- |
| `lite.provider` | `openai` |
| `lite.model` | `deepseek-v4-flash` |
| `pro.model` | `deepseek-v4-flash`，thinking=true，effort=high |
| `max.model` | `deepseek-v4-flash`，thinking=true，effort=max |
| `max_sub_agent_steps` | `30` |
| `research_parallel` | `true` |
| `research_threads` | `10` |
| `doc_language` | `中文` |
| `target_audience` | `初级开发者` |
| `base_url` | `https://api.deepseek.com` |
| `api_key` | `${DEEPSEEK_API_KEY}` |

README 的示例配置使用 `provider=anthropic`，代码默认使用 `openai`。两者都指向 DeepSeek 时，协议路径不同，需按服务端实际接口选择。

## 环境变量加载顺序

`main.py`：

```python
import dotenv
dotenv.load_dotenv()

from pipeline import run_pipeline
```

`load_dotenv()` 在导入流水线之前执行，因此：

- `.env` 中的 `LANGFUSE_ENABLE` 能在 `util/langfuse.py` 导入时被读到；
- `.env` 中的 `DEEPSEEK_API_KEY` 能被 `${DEEPSEEK_API_KEY}` 展开。

但 `load_dotenv()` 默认从**当前工作目录**查找 `.env`。从目标项目运行时，Open Zread 根目录的 `.env` 不会被自动加载；需要在 Shell 中导出变量，或在目标项目放 `.env`。

## 配置文件缓存与线程

`_settings` 是模块级单例。多个主题线程共享同一份配置字典；配置在运行期间只读，因此通常安全。不要在运行中修改返回的 dict，否则会影响其他线程。

`LLMAdaptor` 每个阶段/主题创建自己的实例，但使用同一份配置字段。

## Wiki 存储

```text
.zread/wiki/
├── current
└── versions/
    └── <timestamp>/
        ├── wiki.json
        └── <slug>.md
```

- 时间戳是本地时间 `%Y-%m-%d-%H%M%S`；
- `current` 是文本文件，内容不带换行（代码直接 `f.write`）；
- `wiki.json` 的 `generated_at` 是 UTC ISO 字符串，带 `Z`；
- `language` 只区分中文/其他；
- 每次运行创建新目录，没有自动清理；
- `.zread/` 在项目 `.gitignore` 中。

## 写入时序与一致性

```text
创建版本目录 → 写 current → 阶段 1 → 写 wiki.json → 阶段 2 写 Markdown
```

- 不是原子事务；
- 阶段 2 失败会留下不完整目录；
- `wiki.json` 可能列出不存在的内容文件；
- 没有锁文件或恢复标记；
- 多进程同时运行会各自创建版本，`current` 以后写入者为准。

## 数据边界

- 本地保存：版本目录、`wiki.json`、Markdown、`current`；
- 发送到模型：Prompt、目录结构、工具读取的代码片段、工具输出；
- 发送到 Langfuse（可选）：Prompt、调用链、工具输入输出、元数据；
- `.env` 被 `.gitignore` 忽略，但 `.env.example` 可能被提交；模板中不应包含真实密钥。

Open Zread 不提供加密、访问控制或数据保留策略；这些由操作系统和外部服务决定。
