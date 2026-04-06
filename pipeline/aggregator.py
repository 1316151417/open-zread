from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def aggregate_reports(ctx: PipelineContext) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    module_reports = "\n\n---\n\n".join(
        f"### 模块：{m.name}\n\n{m.research_report}"
        for m in ctx.selected_modules
    )

    system_prompt = AGGREGATOR_SYSTEM.format(
        project_name=ctx.project_name,
        tree_text=ctx.tree_text,
    )
    user_msg = AGGREGATOR_USER.format(module_reports=module_reports)

    messages = [SystemMessage(system_prompt), UserMessage(user_msg)]

    events = react_stream(
        messages=messages,
        tools=tools,
        provider=ctx.provider,
        max_steps=ctx.max_sub_agent_steps,
    )

    # 收集最终输出
    step_contents = {}
    had_tool_calls_on_last_step = False

    for event in events:
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
        if event.type == EventType.TOOL_CALL:
            had_tool_calls_on_last_step = True
        elif event.type == EventType.STEP_START:
            had_tool_calls_on_last_step = False

    if not step_contents:
        ctx.final_report = "# 错误：未能生成报告"
        return

    if not had_tool_calls_on_last_step:
        ctx.final_report = list(step_contents.values())[-1]
    else:
        ctx.final_report = max(step_contents.values(), key=len)
