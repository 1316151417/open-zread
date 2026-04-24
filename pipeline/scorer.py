"""Stage 4: 模块打分排序 - 按重要性评分并倒序."""
import json

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.langfuse_prompt import get_compiled_messages


def score_and_rank_modules(ctx: PipelineContext) -> None:
    modules_json = json.dumps([
        {"name": m.name, "description": m.description, "files": m.files}
        for m in ctx.modules
    ], ensure_ascii=False, indent=2)

    adaptor = LLMAdaptor(ctx.lite_config)
    messages = get_compiled_messages("scorer", project_name=ctx.project_name, modules_json=modules_json)
    response = adaptor.call_for_json(messages, response_format={"type": "json_object"})

    result = json.loads(response)
    scores = result.get("scores", {})

    for m in ctx.modules:
        m.score = float(scores.get(m.name, 0))

    ctx.modules.sort(key=lambda m: m.score, reverse=True)
