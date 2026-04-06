import os
import re
from pathlib import Path

from base.types import tool

_project_root: str = ""

MAX_READ_SIZE = 20 * 1024  # 20KB — 控制上下文膨胀
MAX_GREP_RESULTS = 100


def set_project_root(path: str) -> None:
    global _project_root
    _project_root = path


@tool
def read_file(file_path: str) -> str:
    """Read the full contents of a file.

    Args:
        file_path: Relative path from the project root
    """
    full_path = os.path.join(_project_root, file_path)
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_READ_SIZE)
        if os.path.getsize(full_path) > MAX_READ_SIZE:
            content += f"\n\n... [truncated, file exceeds {MAX_READ_SIZE // 1024}KB]"
        return content
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except IsADirectoryError:
        return f"Error: {file_path} is a directory, not a file"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def list_directory(dir_path: str) -> str:
    """List files and subdirectories in a directory.

    Args:
        dir_path: Relative path from the project root, use '.' for root
    """
    full_path = os.path.join(_project_root, dir_path)
    try:
        entries = sorted(os.listdir(full_path))
        lines = []
        for name in entries:
            child = os.path.join(full_path, name)
            if os.path.isdir(child):
                lines.append(f"DIR:  {name}/")
            else:
                size = os.path.getsize(child)
                lines.append(f"FILE: {name} ({size} bytes)")
        return "\n".join(lines) if lines else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {dir_path}"
    except NotADirectoryError:
        return f"Error: {dir_path} is not a directory"
    except Exception as e:
        return f"Error listing directory: {e}"


@tool
def glob_pattern(pattern: str) -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern like '**/*.py' or 'src/**/*.ts'
    """
    root = Path(_project_root)
    matches = sorted(root.glob(pattern))
    # 只返回相对路径，且排除隐藏目录
    results = []
    for m in matches:
        rel = os.path.relpath(m, _project_root)
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        results.append(rel)
    if not results:
        return "No files matched the pattern."
    return "\n".join(results)


@tool
def grep_content(pattern: str, file_pattern: str = "**/*") -> str:
    """Search for a regex pattern across files.

    Args:
        pattern: Regular expression pattern to search for
        file_pattern: Glob pattern to limit which files to search, default all files
    """
    root = Path(_project_root)
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    results = []
    for match_path in sorted(root.glob(file_pattern)):
        if not match_path.is_file():
            continue
        rel = os.path.relpath(match_path, _project_root)
        # 跳过隐藏目录和二进制文件
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        try:
            with open(match_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append(f"{rel}:{line_no}: {line.rstrip()}")
                        if len(results) >= MAX_GREP_RESULTS:
                            return "\n".join(results) + f"\n... [truncated at {MAX_GREP_RESULTS} results]"
        except Exception:
            continue

    if not results:
        return "No matches found."
    return "\n".join(results)
