"""Stage 4: 模块打分排序 - 核心度/依赖度/入口/领域独特性评分."""
import json

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import SCORER_SYSTEM, SCORER_USER


def score_and_rank_modules(ctx: PipelineContext) -> None:
    module_list = "\n".join(f"  - {m.name}: {m.description} (files: {', '.join(m.files)})" for m in ctx.modules)
    user_msg = SCORER_USER.format(project_name=ctx.project_name, module_list=module_list)

    response = call_llm(ctx.provider, SCORER_SYSTEM, user_msg, model=ctx.lite_model)

    try:
        scores = json.loads(extract_json(response))
    except json.JSONDecodeError:
        scores = {m.name: 50 for m in ctx.modules}

    for m in ctx.modules:
        m.importance_score = float(scores.get(m.name, 50))

    ctx.ranked_modules = sorted(ctx.modules, key=lambda m: m.importance_score, reverse=True)
    ctx.selected_modules = ctx.ranked_modules[: ctx.max_sub_agents]
