from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


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
    """从 ReAct agent 事件流中提取最终内容作为报告"""
    # 收集最后一步的 content（即 agent 不再调用工具时的最终输出）
    step_contents = {}
    for event in events:
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content

    # 取最后一步的内容作为报告
    if step_contents:
        module.research_report = list(step_contents.values())[-1]
    else:
        module.research_report = f"(No report generated for module: {module.name})"
