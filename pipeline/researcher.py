import os

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from log.printer import print_event


def research_modules(ctx: PipelineContext, report_dir: str) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    total = len(ctx.selected_modules)
    for i, module in enumerate(ctx.selected_modules):
        print(f"\n{'='*60}")
        print(f"正在研究模块 [{i+1}/{total}]: {module.name}")
        print(f"  文件: {', '.join(module.files)}")
        print(f"{'='*60}")

        messages = _build_sub_agent_messages(ctx, module)

        events = react_stream(
            messages=messages,
            tools=tools,
            provider=ctx.provider,
            max_steps=ctx.max_sub_agent_steps,
        )

        _collect_sub_agent_output(events, module)

        # 每个模块完成后立即写入报告
        report_path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(module.research_report)
        print(f"\n  -> 报告已写入 ({len(module.research_report)} 字符): {report_path}")


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
    step_num = 0

    for event in events:
        # print_event(event)
        if event.type == EventType.STEP_START:
            had_tool_calls_on_last_step = False
            step_num = event.step
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
            print(f"  [步骤 {step_num} 完成，输出 {len(event.content)} 字符]")
        if event.type == EventType.TOOL_CALL:
            had_tool_calls_on_last_step = True
            print(f"  [调用工具: {event.tool_name}]")
        if event.type == EventType.TOOL_CALL_SUCCESS:
            result_preview = (event.tool_result or "")[:100]
            print(f"  [工具结果: {result_preview}...]")
        if event.type == EventType.TOOL_CALL_FAILED:
            print(f"  [工具失败: {event.tool_error}]")

    if not step_contents:
        module.research_report = f"# 模块 {module.name} 分析报告\n\n未能生成报告。"
        return

    if not had_tool_calls_on_last_step:
        module.research_report = list(step_contents.values())[-1]
    else:
        # 超时结束 — 取最长的 content
        module.research_report = max(step_contents.values(), key=len)
