# Open Zread 文档构建

文档内容在 `docs/`，静态站点生成到 `docs/site/`（已忽略，不进入 Git）。

## 构建

需要 Python 3.12；使用 `uv` 临时安装 Markdown 和 Pygments，不修改项目的 `pyproject.toml`：

```bash
uv run --no-project --with markdown --with pygments python docs/tools/build.py
```

生成结果在 `docs/site/`，部署时把整个目录放到站点的 `/open-zread/` 下。

## 本地预览

```bash
python docs/tools/serve.py
```

访问 <http://127.0.0.1:8081/open-zread/>。

## 目录

- `docs/tools/intro/`：介绍页 HTML / CSS / favicon；
- `docs/tools/assets/`：文档站 CSS、JS、主题初始化；
- `docs/tools/build.py`：Markdown → HTML、侧栏、目录、搜索索引；
- `docs/tools/serve.py`：把 `docs/site` 挂到 `/open-zread/` 的本地静态服务器。
