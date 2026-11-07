#!/usr/bin/env python3
"""Build the static Open Zread documentation site.

Usage:
    uv run --with markdown --with pygments python docs/tools/build.py
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

try:
    import markdown
    from markdown.extensions.codehilite import CodeHiliteExtension
    from markdown.extensions.toc import TocExtension
except ImportError:
    print("缺少 markdown。请运行：")
    print("  uv run --with markdown --with pygments python docs/tools/build.py")
    raise SystemExit(1)

try:
    from pygments.formatters import HtmlFormatter
except ImportError:
    HtmlFormatter = None

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
TOOLS = DOCS / "tools"
SITE = DOCS / "site"
REPO_URL = "https://github.com/1316151417/open-zread"

GROUP_LABELS = {
    "home": "索引",
    "overview": "概览",
    "features": "功能",
    "internals": "原理",
}

ICONS = {
    "menu": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>',
    "search": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
    "sun": '<svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    "moon": '<svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a7 7 0 1 0 10.5 10.5Z"/></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.2-3.4-1.2-.4-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.4-1.1.7-1.3-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7 1 .7 2v3c0 .3.2.6.7.5A10 10 0 0 0 12 2Z"/></svg>',
    "prev": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>',
    "next": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>',
}


@dataclass
class Doc:
    source: Path
    title: str
    group: str
    output: str
    url: str
    markdown: str


class SearchParser(HTMLParser):
    def __init__(self, doc: Doc):
        super().__init__(convert_charrefs=True)
        self.doc = doc
        self.entries: list[dict] = []
        self.heading_id = ""
        self.heading_text = ""
        self.in_heading = False
        self.heading_buffer: list[str] = []
        self.body_buffer: list[str] = []
        self.in_body = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"pre", "code", "style", "script"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"h2", "h3"}:
            self.flush_body()
            self.heading_id = attrs.get("id", "")
            self.heading_text = ""
            self.heading_buffer = []
            self.in_heading = True
        elif tag in {"p", "li", "td"}:
            self.in_body = True
            self.body_buffer = []

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in {"pre", "code", "style", "script"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in {"h2", "h3"}:
            self.heading_text = clean_text("".join(self.heading_buffer))
            self.in_heading = False
            if self.heading_text:
                self.entries.append(
                    {
                        "url": self.entry_url(),
                        "title": self.doc.title,
                        "id": self.heading_id,
                        "heading": self.heading_text,
                        "text": "",
                    }
                )
        elif tag in {"p", "li", "td"}:
            self.flush_body()

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_heading:
            self.heading_buffer.append(data)
        elif self.in_body:
            self.body_buffer.append(data)

    def flush_body(self):
        if not self.in_body:
            return
        text = clean_text("".join(self.body_buffer))
        self.in_body = False
        self.body_buffer = []
        if not text:
            return
        self.entries.append(
            {
                "url": self.entry_url(),
                "title": self.doc.title,
                "id": self.heading_id,
                "heading": self.heading_text,
                "text": text[:260],
            }
        )

    def entry_url(self):
        return self.doc.url


def clean_text(value: str) -> str:
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def slugify_heading(value: str, separator: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff\-\s]", separator, value, flags=re.UNICODE)
    value = re.sub(r"\s+", separator, value)
    value = re.sub(f"{re.escape(separator)}+", separator, value)
    value = value.strip(separator).lower()
    return value or "section"


def markdown_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if not match:
        return fallback
    title = match.group(1)
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    title = re.sub(r"[*_`]", "", title)
    return clean_text(title) or fallback


def output_name(source: Path, group: str) -> str:
    if group == "home":
        return "index.html"
    stem = re.sub(r"^\d+-", "", source.stem)
    if group == "overview":
        return f"{stem}.html"
    return f"{group}/{stem}.html"


def discover_docs(base: str) -> tuple[list[Doc], str]:
    version_match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    version = version_match.group(1) if version_match else "0.0.0"
    docs_base = f"{base}/docs"
    specs = [
        (DOCS / "README.md", "home"),
        (DOCS / "overview.md", "overview"),
    ]
    specs += [(path, "features") for path in sorted((DOCS / "features").glob("*.md"))]
    specs += [(path, "internals") for path in sorted((DOCS / "internals").glob("*.md"))]

    docs: list[Doc] = []
    for source, group in specs:
        text = source.read_text(encoding="utf-8")
        output = output_name(source, group)
        url = f"{docs_base}/" if output == "index.html" else f"{docs_base}/{output}"
        docs.append(
            Doc(
                source=source,
                title=markdown_title(text, source.stem),
                group=group,
                output=output,
                url=url,
                markdown=text,
            )
        )
    return docs, version


def rewrite_links(html_text: str, doc: Doc, docs_by_source: dict[Path, Doc], base: str) -> str:
    def rewrite(match: re.Match) -> str:
        href = match.group(1)
        if not href or href.startswith(("#", "mailto:", "tel:", "http://", "https://", "//")):
            return f'href="{href}"'
        path_part, _, fragment = href.partition("#")
        path_part, _, query = path_part.partition("?")
        if path_part.endswith(".md"):
            resolved = (doc.source.parent / path_part).resolve()
            target = docs_by_source.get(resolved)
            if target:
                suffix = f"?{query}" if query else ""
                suffix += f"#{fragment}" if fragment else ""
                return f'href="{target.url}{suffix}"'
            if resolved.exists() and resolved.is_relative_to(ROOT):
                rel = resolved.relative_to(ROOT).as_posix()
                suffix = f"#{fragment}" if fragment else ""
                return f'href="{REPO_URL}/blob/main/{rel}{suffix}"'
        if path_part.startswith("../"):
            resolved = (doc.source.parent / path_part).resolve()
            if resolved.exists() and resolved.is_file() and resolved.is_relative_to(ROOT):
                rel = resolved.relative_to(ROOT).as_posix()
                suffix = f"#{fragment}" if fragment else ""
                return f'href="{REPO_URL}/blob/main/{rel}{suffix}"'
        if path_part.startswith("/"):
            return f'href="{base}{href}"'
        return f'href="{href}"'

    html_text = re.sub(r'href="([^"]*)"', rewrite, html_text)
    return re.sub(
        r'(<a href="https?://[^"]+")',
        r'\1 target="_blank" rel="noopener"',
        html_text,
    )


def flatten_toc(tokens: list[dict], depth: int = 0) -> list[dict]:
    result = []
    for token in tokens:
        if token.get("level") in {2, 3}:
            result.append(
                {
                    "id": token.get("id", ""),
                    "text": clean_text(re.sub(r"<[^>]+>", "", token.get("name", ""))),
                    "depth": token.get("level"),
                }
            )
        result.extend(flatten_toc(token.get("children", []), depth + 1))
    return result


def render_markdown(doc: Doc, docs_by_source: dict[Path, Doc], base: str) -> tuple[str, list[dict], list[dict]]:
    md = markdown.Markdown(
        extensions=[
            "extra",
            TocExtension(slugify=slugify_heading, separator="-"),
            CodeHiliteExtension(guess_lang=False, css_class="highlight"),
        ]
    )
    html_text = md.convert(doc.markdown)
    toc = flatten_toc(md.toc_tokens)
    html_text = rewrite_links(html_text, doc, docs_by_source, base)
    parser = SearchParser(doc)
    parser.feed(html_text)
    parser.close()
    parser.flush_body()
    html_text = re.sub(
        r'<h([2-6]) id="([^"]+)">(.*?)</h\1>',
        lambda match: (
            f'<h{match.group(1)} id="{match.group(2)}">'
            f'<a class="heading-anchor" href="#{match.group(2)}" aria-hidden="true">#</a>'
            f"{match.group(3)}</h{match.group(1)}>"
        ),
        html_text,
        flags=re.DOTALL,
    )
    html_text = html_text.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    return html_text, toc, parser.entries


def sidebar_html(docs: list[Doc], current: Doc) -> str:
    groups = []
    for group in ("home", "overview", "features", "internals"):
        items = [doc for doc in docs if doc.group == group]
        if not items:
            continue
        links = []
        for doc in items:
            active = doc.url == current.url
            current_attr = ' aria-current="page"' if active else ""
            links.append(
                f'<a class="nav-item{" active" if active else ""}" href="{doc.url}"'
                f'{current_attr}>{html.escape(doc.title)}</a>'
            )
        groups.append(
            f'<div class="nav-group"><div class="nav-label">{GROUP_LABELS[group]}</div>'
            + "".join(links)
            + "</div>"
        )
    return "".join(groups)


def toc_html(toc: list[dict]) -> str:
    if not toc:
        return ""
    links = "".join(
        f'<a class="toc-link depth-{entry["depth"]}" href="#{entry["id"]}">{html.escape(entry["text"])}</a>'
        for entry in toc
    )
    return f'<aside class="toc" aria-label="本页目录"><div class="toc-inner"><div class="toc-label">本页目录</div>{links}</div></aside>'


def pager_html(docs: list[Doc], current: Doc) -> str:
    index = next((i for i, doc in enumerate(docs) if doc.url == current.url), -1)
    prev_doc = docs[index - 1] if index > 0 else None
    next_doc = docs[index + 1] if 0 <= index < len(docs) - 1 else None
    prev = (
        f'<a class="pager-link pager-prev" href="{prev_doc.url}">{ICONS["prev"]}'
        f'<span><small>上一篇</small><strong>{html.escape(prev_doc.title)}</strong></span></a>'
        if prev_doc
        else "<span></span>"
    )
    nxt = (
        f'<a class="pager-link pager-next" href="{next_doc.url}"><span><small>下一篇</small>'
        f'<strong>{html.escape(next_doc.title)}</strong></span>{ICONS["next"]}</a>'
        if next_doc
        else "<span></span>"
    )
    return f'<nav class="pager" aria-label="翻页">{prev}{nxt}</nav>'


def page_html(
    doc: Doc,
    docs: list[Doc],
    content: str,
    toc: list[dict],
    version: str,
    base: str,
) -> str:
    docs_base = f"{base}/docs"
    assets = f"{base}/assets"
    toc_markup = toc_html(toc)
    layout_class = "layout" if toc else "layout no-toc"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(doc.title)} · Open Zread 文档">
  <meta name="open-zread-docs-base" content="{docs_base}">
  <meta name="open-zread-assets" content="{assets}">
  <title>{html.escape(doc.title)} · Open Zread 文档</title>
  <link rel="icon" href="{base}/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{assets}/docs.css">
  <link rel="stylesheet" href="{assets}/pygments.css">
  <script src="{assets}/theme.js"></script>
</head>
<body>
  <header class="topbar">
    <button id="sidebar-toggle" class="icon-button menu-button" type="button" aria-label="打开导航">{ICONS["menu"]}</button>
    <a class="brand" href="{docs_base}/">
      <span class="brand-mark">Z</span>
      <span class="brand-name">Open Zread 文档</span>
      <span class="brand-version">v{html.escape(version)}</span>
    </a>
    <div class="topbar-spacer"></div>
    <button id="search-open" class="search-trigger" type="button" aria-label="搜索文档">
      {ICONS["search"]}<span>搜索文档</span><kbd>⌘K</kbd>
    </button>
    <a class="topbar-link" href="{base}/">介绍页</a>
    <button id="theme-toggle" class="icon-button" type="button" aria-label="切换深浅色">{ICONS["sun"]}{ICONS["moon"]}</button>
    <a class="icon-button" href="{REPO_URL}" target="_blank" rel="noopener" aria-label="GitHub 仓库">{ICONS["github"]}</a>
  </header>
  <div class="{layout_class}">
    <aside id="sidebar" class="sidebar">
      <nav aria-label="文档导航">{sidebar_html(docs, doc)}</nav>
      <div class="sidebar-foot">v{html.escape(version)} · <a href="{base}/">项目介绍</a></div>
    </aside>
    <div class="sidebar-scrim" data-sidebar-close></div>
    <main class="content">
      <article class="markdown">{content}</article>
      {pager_html(docs, doc)}
      <footer class="site-foot">
        <span>Open Zread 文档</span>
        <a href="{base}/">项目介绍</a>
        <a href="{REPO_URL}" target="_blank" rel="noopener">GitHub</a>
      </footer>
    </main>
    {toc_markup}
  </div>
  <div id="search-modal" class="search-modal" hidden>
    <div class="search-backdrop" data-search-close></div>
    <div class="search-panel" role="dialog" aria-modal="true" aria-label="搜索文档">
      <div class="search-input-row">
        {ICONS["search"]}
        <input id="search-input" type="search" placeholder="搜索标题、正文…" autocomplete="off" spellcheck="false">
        <kbd>Esc</kbd>
      </div>
      <div id="search-results" class="search-results">
        <p class="search-empty">输入关键词开始搜索</p>
      </div>
      <div class="search-footer">
        <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
        <span><kbd>Enter</kbd> 打开</span>
        <span><kbd>⌘K</kbd> 关闭</span>
      </div>
    </div>
  </div>
  <script type="module" src="{assets}/docs.js"></script>
</body>
</html>
"""


def pygments_css() -> str:
    if HtmlFormatter is None:
        return ""
    try:
        light = HtmlFormatter(style="friendly").get_style_defs(".highlight")
        dark = HtmlFormatter(style="github-dark").get_style_defs(".highlight")
    except Exception:
        return ""
    light = light.replace(".highlight", 'html[data-theme="light"] .highlight')
    dark = dark.replace(".highlight", 'html[data-theme="dark"] .highlight')
    return (
        f"{light}\n\n{dark}\n\n"
        "html[data-theme=\"light\"] .markdown .highlight,\n"
        "html[data-theme=\"dark\"] .markdown .highlight {\n"
        "  background: transparent;\n"
        "}\n"
    )


def build(base: str) -> None:
    base = "/" + base.strip("/") if base.strip("/") else ""
    docs, version = discover_docs(base)
    docs_by_source = {doc.source.resolve(): doc for doc in docs}

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "docs" / "features").mkdir(parents=True)
    (SITE / "docs" / "internals").mkdir(parents=True)
    (SITE / "assets").mkdir(parents=True)

    for name in ("index.html", "styles.css", "favicon.svg"):
        shutil.copy2(TOOLS / "intro" / name, SITE / name)
    for name in ("docs.css", "docs.js", "theme.js"):
        shutil.copy2(TOOLS / "assets" / name, SITE / "assets" / name)
    (SITE / "assets" / "pygments.css").write_text(pygments_css(), encoding="utf-8")

    search_entries: list[dict] = []
    for doc in docs:
        content, toc, entries = render_markdown(doc, docs_by_source, base)
        search_entries.extend(entries)
        target = SITE / "docs" / doc.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html(doc, docs, content, toc, version, base), encoding="utf-8")

    (SITE / "assets" / "search.json").write_text(
        json.dumps({"version": version, "entries": search_entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Built {len(docs)} docs for {base or '/'} (v{version})")
    print(f"  site: {SITE}")
    print(f"  search entries: {len(search_entries)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="/open-zread", help="部署站点根路径（默认 /open-zread）")
    args = parser.parse_args()
    build(args.base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
