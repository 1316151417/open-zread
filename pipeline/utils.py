"""Pipeline 共用工具函数."""
from pathlib import Path

from base.types import EventType


def build_file_tree(files) -> str:
    """构建文本形式的文件树。"""
    tree = {}
    for f in files:
        parts = Path(f.path).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None

    lines = ["project/"]
    _render_tree(tree, lines, "")
    return "".join(lines)


def _render_tree(node: dict, lines: list, prefix: str) -> None:
    items = sorted(node.items(), key=lambda x: (not isinstance(x[1], dict), x[0]))
    for i, (name, value) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        if isinstance(value, dict):
            lines.append(f"{prefix}{connector}{name}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            _render_tree(value, lines, child_prefix)
        else:
            lines.append(f"{prefix}{connector}{name}")


def collect_report(events) -> str:
    """从 ReAct agent 事件流中提取最终报告内容。"""
    contents = [e.content for e in events if e.type == EventType.STEP_END and e.content]
    return contents[-1] if contents else "（未能生成报告）"
