"""Stage 5: 子模块深度研究 - ReAct agent 研究模块并生成报告."""
import json
import os

from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.langfuse_prompt import get_compiled_messages
from pipeline.utils import build_file_tree, collect_report
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def prepare_research(ctx: PipelineContext) -> tuple:
    """初始化研究工具和文件树，供 research_one_module 使用。"""
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]
    file_tree = build_file_tree(ctx.all_files)
    return tools, file_tree


def research_one_module(ctx: PipelineContext, module: Module, tools: list, report_dir: str, file_tree: str) -> None:
    """研究单个模块并生成报告。"""
    set_project_root(ctx.project_path)

    module_files_json = json.dumps(module.files, ensure_ascii=False, indent=2)

    messages = get_compiled_messages("sub-agent",
        project_name=ctx.project_name,
        module_name=module.name,
        file_tree=file_tree,
        module_files_json=module_files_json,
    )

    events = react_stream(messages=messages, tools=tools, config=ctx.pro_config, max_steps=ctx.max_sub_agent_steps)

    module.research_report = collect_report(events)

    path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(module.research_report)
