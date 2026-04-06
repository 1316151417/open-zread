import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER, EVAL_AGENT_SYSTEM, EVAL_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from log.printer import print_event


def research_modules(ctx: PipelineContext, report_dir: str) -> None:
    settings = ctx.settings
    parallel = settings.get("parallel_research", True)
    max_eval_rounds = settings.get("max_eval_rounds", 3)

    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]
    total = len(ctx.selected_modules)

    if parallel and total > 1:
        print(f"  并行模式：同时研究 {total} 个模块")
        with ThreadPoolExecutor(max_workers=min(total, 4)) as executor:
            futures = {}
            for i, module in enumerate(ctx.selected_modules):
                future = executor.submit(
                    _research_single_module,
                    ctx, module, tools, i, total,
                    max_eval_rounds, report_dir,
                )
                futures[future] = module

            for future in as_completed(futures):
                module = futures[future]
                try:
                    future.result()
                    print(f"  ✓ 模块 {module.name} 研究完成")
                except Exception as e:
                    print(f"  ✗ 模块 {module.name} 研究失败: {e}")
                    module.research_report = f"# 模块 {module.name} 分析报告\n\n研究过程出错: {e}"
                    _write_module_report(report_dir, module)
    else:
        print(f"  串行模式：逐个研究 {total} 个模块")
        for i, module in enumerate(ctx.selected_modules):
            _research_single_module(
                ctx, module, tools, i, total,
                max_eval_rounds, report_dir,
            )


def _research_single_module(
    ctx: PipelineContext,
    module: Module,
    tools: list,
    index: int,
    total: int,
    max_eval_rounds: int,
    report_dir: str,
) -> None:
    prefix = f"[{index+1}/{total}]"
    print(f"\n{'='*60}")
    print(f"{prefix} 开始研究模块: {module.name}")
    print(f"  文件: {', '.join(module.files)}")
    print(f"{'='*60}")

    # 生成-评估循环
    for round_num in range(1, max_eval_rounds + 1):
        print(f"\n  {prefix} 第 {round_num}/{max_eval_rounds} 轮生成")

        # 生成报告
        messages = _build_generate_messages(ctx, module, round_num)
        events = react_stream(
            messages=messages,
            tools=tools,
            provider=ctx.provider,
            max_steps=ctx.max_sub_agent_steps,
        )
        report = _collect_agent_output(events, f"{prefix} [生成]")
        module.research_report = report

        # 最后一轮或只有一轮时跳过评估
        if round_num >= max_eval_rounds:
            print(f"  {prefix} 达到最大轮次，采用当前报告")
            break

        # 评估报告
        eval_result = _evaluate_report(ctx, module, report)
        if eval_result.get("pass", False):
            print(f"  {prefix} 评估通过 (总分: {eval_result.get('total_score', '?')})")
            break
        else:
            suggestions = eval_result.get("suggestions", [])
            print(f"  {prefix} 评估未通过 (总分: {eval_result.get('total_score', '?')})")
            for s in suggestions:
                print(f"    → {s}")

    # 写入报告
    _write_module_report(report_dir, module)
    print(f"  {prefix} 报告已写入 ({len(module.research_report)} 字符)")


def _build_generate_messages(ctx: PipelineContext, module: Module, round_num: int) -> list:
    system_prompt = SUB_AGENT_SYSTEM.format(
        module_name=module.name,
        project_name=ctx.project_name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = SUB_AGENT_USER.format(module_name=module.name)

    messages = [SystemMessage(system_prompt), UserMessage(user_prompt)]

    # 如果是第 2+ 轮，在 user message 中附带上轮报告和改进方向
    if round_num > 1 and module.research_report:
        improvement_hints = getattr(module, '_eval_suggestions', [])
        hints_text = "\n".join(f"  - {s}" for s in improvement_hints) if improvement_hints else "无具体建议"
        messages.append(UserMessage(
            f"上一轮的评估发现以下不足，请针对这些问题改进报告：\n{hints_text}\n\n"
            f"请重新读取相关文件，补充缺失的分析，输出改进后的完整报告。"
        ))

    return messages


def _evaluate_report(ctx: PipelineContext, module: Module, report: str) -> dict:
    """用 LLM 评估报告质量，返回评估结果 dict"""
    from pipeline.llm_filter import _call_llm

    system_prompt = EVAL_AGENT_SYSTEM.format(
        project_name=ctx.project_name,
        module_name=module.name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = EVAL_AGENT_USER.format(
        module_name=module.name,
        report=report,
    )

    response = _call_llm(ctx.provider, system_prompt, user_prompt)

    try:
        result = json.loads(_extract_json(response))
    except json.JSONDecodeError:
        # 解析失败默认通过
        return {"pass": True, "total_score": 30, "suggestions": []}

    # 保存建议到 module 上供下一轮使用
    module._eval_suggestions = result.get("suggestions", [])

    return result


def _collect_agent_output(events, prefix: str = "") -> str:
    """从 ReAct agent 事件流中提取最终输出"""
    step_contents = {}
    had_tool_calls_on_last_step = False

    for event in events:
        if event.type == EventType.STEP_START:
            had_tool_calls_on_last_step = False
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
            print(f"  {prefix} 步骤 {event.step} 完成 ({len(event.content)} 字符)")
        if event.type == EventType.TOOL_CALL:
            had_tool_calls_on_last_step = True
            print(f"  {prefix} 调用工具: {event.tool_name}")
        if event.type == EventType.TOOL_CALL_SUCCESS:
            result_len = len(event.tool_result) if event.tool_result else 0
            print(f"  {prefix} 工具结果: {result_len} 字符")

    if not step_contents:
        return "（未能生成报告）"

    if not had_tool_calls_on_last_step:
        return list(step_contents.values())[-1]
    else:
        return max(step_contents.values(), key=len)


def _write_module_report(report_dir: str, module: Module) -> None:
    """将模块报告写入文件"""
    path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(module.research_report)


def _extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON"""
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text
