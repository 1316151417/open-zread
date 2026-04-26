"""Step 2: 内容生成 — 为单个主题生成详细文档."""
import os
import platform

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext, Topic
from pipeline.utils import build_toc_navigation, extract_blog_content
from prompt.langfuse_prompt import get_compiled_messages
from tool.fs_tool import set_project_root, get_dir_structure, view_file_in_detail, run_bash


def generate_topic_content(ctx: PipelineContext, topic: Topic) -> str:
    """为单个主题生成内容，返回 markdown 文本。"""
    set_project_root(ctx.project_path)
    adaptor = LLMAdaptor(ctx.pro_config)
    tools = [get_dir_structure, view_file_in_detail, run_bash]
    os_name = platform.system().lower()

    full_toc = build_toc_navigation(ctx.topics, topic)

    messages = get_compiled_messages("step2",
        working_dir=ctx.project_path,
        os_name=os_name,
        current_section=topic.section_name,
        current_topic=topic.name,
        target_audience=ctx.settings.get("target_audience", "初级开发者"),
        doc_language=ctx.settings.get("doc_language", "中文"),
        repo_structure=ctx.repo_structure,
        full_toc=full_toc,
    )

    raw_output = adaptor.react_for_text(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps)
    return extract_blog_content(raw_output)
