from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER


def aggregate_reports(ctx: PipelineContext) -> None:
    module_reports = "\n\n---\n\n".join(
        f"### Module: {m.name}\n\n{m.research_report}"
        for m in ctx.selected_modules
    )

    user_msg = AGGREGATOR_USER.format(
        project_name=ctx.project_name,
        tree_text=ctx.tree_text,
        module_reports=module_reports,
    )

    adaptor = LLMAdaptor(provider=ctx.provider)
    content = ""
    for event in adaptor.stream([SystemMessage(AGGREGATOR_SYSTEM), UserMessage(user_msg)]):
        if event.type == EventType.CONTENT_DELTA:
            content += event.content

    ctx.final_report = content if content else "# Error: Failed to generate report"
