from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from log.printer import print_event


def research_modules(ctx: PipelineContext) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    for i, module in enumerate(ctx.selected_modules):
        print(f"\n{'='*60}")
        print(f"Researching module {i+1}/{len(ctx.selected_modules)}: {module.name}")
        print(f"  Files: {', '.join(module.files)}")
        print(f"{'='*60}")

        messages = _build_sub_agent_messages(ctx, module)

        events = react_stream(
            messages=messages,
            tools=tools,
            provider=ctx.provider,
            max_steps=ctx.max_sub_agent_steps,
        )

        _collect_sub_agent_output(events, module)
        print(f"\n  -> Report collected ({len(module.research_report)} chars)")


def _build_sub_agent_messages(ctx: PipelineContext, module: Module) -> list:
    system_prompt = SUB_AGENT_SYSTEM.format(
        module_name=module.name,
        project_name=ctx.project_name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = SUB_AGENT_USER.format(module_name=module.name)
    return [SystemMessage(system_prompt), UserMessage(user_prompt)]


def _collect_sub_agent_output(events, module: Module) -> None:
    """从 ReAct agent 事件流中提取最终报告。

    策略：
    1. 如果 agent 自然结束（最后一步无 tool call），取最后一步 content
    2. 如果 agent 超时（达到 max_steps），取最长的一步 content（可能是中间的研究总结）
    """
    step_contents = {}
    had_tool_calls_on_last_step = False

    for event in events:
        print_event(event)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
        if event.type == EventType.TOOL_CALL:
            had_tool_calls_on_last_step = True
        elif event.type == EventType.STEP_START:
            had_tool_calls_on_last_step = False

    if not step_contents:
        module.research_report = f"(No report generated for module: {module.name})"
        return

    if not had_tool_calls_on_last_step:
        # 自然结束 — 取最后一步
        module.research_report = list(step_contents.values())[-1]
    else:
        # 超时结束 — 取最长的 content（最有可能是报告主体）
        module.research_report = max(step_contents.values(), key=len)
