"""Stage 2: LLM 智能过滤 - 基于项目类型判断文件重要性."""
import json

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.langfuse_prompt import get_compiled_messages


def llm_filter_files(ctx: PipelineContext) -> None:
    # 构建文件 JSON 列表，只包含可能重要的文件
    files_json = json.dumps([
        {"path": f.path, "type": f.file_type, "size": f.size}
        for f in ctx.all_files
        if f.is_important  # 初始标记为重要的才送入 LLM 进一步过滤
    ], ensure_ascii=False, indent=2)

    adaptor = LLMAdaptor(ctx.lite_config)
    messages = get_compiled_messages("file-filter", project_name=ctx.project_name, files_json=files_json)
    response = adaptor.call_for_json(messages, response_format={"type": "json_object"})

    try:
        result = json.loads(response)
        unimportant_paths = set(result.get("unimportant_paths", []))
    except (json.JSONDecodeError, KeyError, TypeError):
        unimportant_paths = set()

    # 修正 is_important 标记
    for f in ctx.all_files:
        if f.path in unimportant_paths:
            f.is_important = False
