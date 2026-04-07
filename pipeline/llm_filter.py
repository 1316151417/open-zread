"""Stage 2: LLM 智能过滤 - 基于项目类型判断文件重要性."""
import json

from base.types import SystemMessage, UserMessage
from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import FILE_FILTER_SYSTEM, FILE_FILTER_USER


def llm_filter_files(ctx: PipelineContext) -> None:
    file_list = "\n".join(f"  {f.path} ({f.size}B)" for f in ctx.filtered_files)
    user_msg = FILE_FILTER_USER.format(project_name=ctx.project_name, tree_text=ctx.tree_text, file_list=file_list)

    response = call_llm(ctx.provider, FILE_FILTER_SYSTEM, user_msg, model=ctx.lite_model, response_format={"type": "json_object"})

    try:
        important_paths = json.loads(extract_json(response))
    except json.JSONDecodeError:
        ctx.important_files = list(ctx.filtered_files)
        return

    path_set = set(important_paths)
    ctx.important_files = [f for f in ctx.filtered_files if f.path in path_set]

    if len(ctx.important_files) < 3:
        ctx.important_files = list(ctx.filtered_files)
