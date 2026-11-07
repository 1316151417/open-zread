# 输出与预览

Open Zread 的输出是完全本地的文件：`wiki.json` 描述目录，Markdown 保存正文，`current` 指向最新版本。它不内置阅读器，预览交给 Zread CLI。

## 目录结构

在目标项目根目录下：

```text
.zread/wiki/
├── current
└── versions/
    └── 2026-04-26-120000/
        ├── wiki.json
        ├── 1-xiang-mu-gai-shu.md
        ├── 2-kuai-su-qi-dong.md
        └── ...
```

- `current`：纯文本，内容形如 `versions/2026-04-26-120000`；
- `versions/<timestamp>`：每次运行新建，不覆盖旧版本；
- `wiki.json`：阶段 1 结束后写入；
- `<slug>.md`：阶段 2 每个主题完成时立即写入。

## wiki.json

结构大致如下：

```json
{
  "id": "2026-04-26-120000",
  "generated_at": "2026-04-26T04:00:00.000000Z",
  "language": "zh",
  "pages": [
    {
      "slug": "1-xiang-mu-gai-shu",
      "title": "项目概述",
      "file": "1-xiang-mu-gai-shu.md",
      "section": "快速入门",
      "level": "Beginner"
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `id` | 版本时间戳 |
| `generated_at` | UTC 生成时间 |
| `language` | `doc_language` 为“中文”时写 `zh`，否则写 `en` |
| `pages[].slug` | `{序号}-{拼音}` |
| `pages[].file` | 对应 Markdown 文件名 |
| `pages[].section` | 章节名 |
| `pages[].level` | `Beginner` / `Intermediate` / `Advanced` |
| `pages[].group` | 有分组时出现 |

`wiki.json` 在正文生成之前生成，所以生成中断时它可能列出尚未写完的文件。重新运行会创建新版本，旧版本保留。

## slug 规则

`util/utils.py:slugify` 使用 `pypinyin.lazy_pinyin`：

- 中文转拼音；
- 英文保留；
- 只保留字母、数字和连字符；
- 加上主题序号，例如 `1-xiang-mu-gai-shu`。

同一主题在 `wiki.json`、Markdown 文件名和目录链接中使用同一个 slug。

## 预览

使用 [Zread CLI](https://github.com/ZreadAI/zread_cli)：

```bash
zread browse
```

CLI 会读取 `.zread/wiki/current` 指向的版本并启动预览。Open Zread 自己 **没有** `browse` 命令，也没有内置 Web 阅读器。

也可以：

- 用编辑器打开生成的 Markdown；
- 用任意 Markdown 工具渲染；
- 读取 `wiki.json` 做二次处理。

## 版本与清理

- 每次运行新增一个 `versions/<timestamp>`；
- `current` 在阶段 1 后更新，即使后续内容失败也指向新版本；
- 没有自动清理策略；
- `.zread/` 在项目 `.gitignore` 中，默认不会进入 Git；
- 需要保留或分享时，自行备份整个版本目录。

## 生成质量

Markdown 由模型生成，Open Zread 不做内容正确性校验。Prompt 要求来源标注和交叉引用，但：

- 来源链接可能不存在或不精确；
- Mermaid 图表由模型编写，语法可能错误；
- 主题范围可能越界；
- 同一仓库不同版本的结果可能不同。

提交或分享前应人工检查。
