import os
from pathlib import Path

from pipeline.types import PipelineContext, FileInfo

EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode", ".claude",
    "target", "bin", "obj", "out",
    "vendor", "Pods", ".gradle", ".dart_tool",
}

EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite",
    ".class", ".jar", ".war",
    ".npy", ".npz", ".parquet", ".pkl", ".pickle",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}

EXCLUDE_NAMES = {
    ".DS_Store", "Thumbs.db",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Gemfile.lock",
    "Cargo.lock", "go.sum", "poetry.lock", "uv.lock",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".kts",
    ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".swift", ".m", ".mm",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".proto", ".graphql", ".gql",
    ".md", ".rst", ".txt", ".csv",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    ".dockerfile", ".makefile",
    ".sql", ".prisma",
    ".gitignore", ".env", ".editorconfig",
}


def scan_project(ctx: PipelineContext) -> None:
    root = Path(ctx.project_path)

    all_files = []
    tree_entries = []

    for dirpath, dirnames, filenames in os.walk(root):
        # 过滤排除的目录（原地修改 dirnames 影响 os.walk 后续遍历）
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]

        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            full_path = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower()

            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            is_text = ext in TEXT_EXTENSIONS

            fi = FileInfo(path=rel_path, size=size, extension=ext, is_text=is_text)
            all_files.append(fi)
            tree_entries.append(fi)

    ctx.all_files = all_files
    ctx.tree_text = _build_tree_text(ctx.project_name, all_files)
    ctx.filtered_files = [f for f in all_files if _is_important_file(f)]


def _build_tree_text(project_name: str, files: list[FileInfo]) -> str:
    if not files:
        return f"{project_name}/\n  (empty)"

    tree = {}
    for fi in files:
        parts = Path(fi.path).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = fi.size

    lines = [f"{project_name}/"]
    _render_tree(tree, lines, "")
    return "\n".join(lines)


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
            size_str = _format_size(value)
            lines.append(f"{prefix}{connector}{name}  ({size_str})")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"


def _is_important_file(f: FileInfo) -> bool:
    name = os.path.basename(f.path)
    if name in EXCLUDE_NAMES:
        return False
    if f.extension in EXCLUDE_EXTENSIONS:
        return False
    if not f.is_text:
        return False
    # 跳过空文件
    if f.size == 0:
        return False
    return True


if __name__ == "__main__":
    ctx = PipelineContext(
        project_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        project_name="CodeDeepResearch",
    )
    scan_project(ctx)
    print(f"Total files: {len(ctx.all_files)}")
    print(f"Filtered files: {len(ctx.filtered_files)}")
    print()
    print(ctx.tree_text)
    print()
    print("Filtered files:")
    for f in ctx.filtered_files:
        print(f"  {f.path} ({f.size}B)")
