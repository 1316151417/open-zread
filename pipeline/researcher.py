"""Stage 5: 子模块深度研究 - 并行 ReAct agent × N 模块 + 评估迭代."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER, EVAL_AGENT_SYSTEM, EVAL_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from provider.llm import call_llm, extract_json
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType


def research_modules(ctx: PipelineContext, report_dir: str) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1, **kwargs):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(
                run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step, **kwargs,
            ))

    pub(PipelineEventType.STAGE_START, "researcher", {"stage_index": 5})

    settings = ctx.settings
    parallel = settings.get("parallel_research", True)
    max_eval_rounds = settings.get("max_eval_rounds", 3)

    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]
    total = len(ctx.selected_modules)

    # Attach pub to ctx so sub-functions can use it
    ctx._event_bus = bus
    ctx._pub = pub

    if parallel and total > 1:
        max_workers = settings.get("max_parallel_workers", 8)
        print(f"  并行研究 {total} 个模块（最多 {max_eval_rounds} 轮评估，{max_workers} 并发）", flush=True)
        with ThreadPoolExecutor(max_workers=min(total, max_workers)) as executor:
            futures = {}
            for module in ctx.selected_modules:
                future = executor.submit(_research_single_module, ctx, module, tools, max_eval_rounds, report_dir, verbose=False)
                futures[future] = module
            for future in as_completed(futures):
                module = futures[future]
                try:
                    future.result(timeout=600)
                    print(f"  ✓ [{module.name}] 完成 ({len(module.research_report)} 字符)", flush=True)
                except FuturesTimeoutError:
                    print(f"  ✗ [{module.name}] 研究超时（>600秒），强制跳过", flush=True)
                    module.research_report = f"# 模块 {module.name} 分析报告\n\n研究超时，未能完成。"
                    _write_module_report(report_dir, module)
                except Exception as e:
                    import traceback
                    print(f"  ✗ [{module.name}] 失败: {e}", flush=True)
                    print(f"  ✗ 堆栈: {traceback.format_exc()}", flush=True)
                    module.research_report = f"# 模块 {module.name} 分析报告\n\n研究过程出错: {e}"
                    _write_module_report(report_dir, module)
    else:
        print(f"  串行研究 {total} 个模块", flush=True)
        for module in ctx.selected_modules:
            _research_single_module(ctx, module, tools, max_eval_rounds, report_dir, verbose=True)

    pub(PipelineEventType.STAGE_END, "researcher", {
        "output_summary": f"researched {total} modules"
    })


def _research_single_module(ctx: PipelineContext, module: Module, tools: list, max_eval_rounds: int, report_dir: str, verbose: bool = True) -> None:
    pub = getattr(ctx, '_pub', None)
    run_id = ctx.run_id
    sub_id = f"module_{module.name}"

    # Set project root for this thread — ContextVar does NOT propagate via ThreadPoolExecutor
    set_project_root(ctx.project_path)

    def do_pub(et, stage, data, step=1, **kwargs):
        if pub and run_id:
            pub(et, stage, data, step, sub_node_id=sub_id, sub_node_name=module.name, **kwargs)

    def make_react_handler(module_name: str, round_num: int = 0, phase: str = "generate"):
        from base.types import Event as ReactEvent
        _sub_id = f"module_{module_name}"
        def react_handler(event: ReactEvent):
            if event.type == EventType.STEP_START:
                # Publish LLM_CALL FIRST — before any tool calls
                raw = getattr(event, 'raw', None) or {}
                do_pub(PipelineEventType.LLM_CALL, "researcher", {
                    "module_name": module_name,
                    "model": ctx.pro_model,
                    "prompt": raw.get("messages", ""),
                    "step": event.step,
                    "round": round_num,
                    "phase": phase,
                }, step=event.step, operation_type="llm_call")
                do_pub(PipelineEventType.LLM_STEP_START, "researcher", {
                    "module_name": module_name, "step": event.step, "round": round_num, "phase": phase,
                }, step=event.step, operation_type=phase)
            elif event.type == EventType.STEP_END:
                content = getattr(event, 'content', '') or ''
                raw = getattr(event, 'raw', None) or {}
                do_pub(PipelineEventType.LLM_STEP_END, "researcher", {
                    "module_name": module_name,
                    "step": event.step,
                    "content": content,
                    "response": raw.get("full_content", content),
                    "round": round_num,
                    "phase": phase,
                }, step=event.step, operation_type=phase)
            elif event.type == EventType.TOOL_CALL:
                do_pub(PipelineEventType.LLM_TOOL_CALL, "researcher", {
                    "module_name": module_name,
                    "tool_name": event.tool_name,
                    "tool_arguments": getattr(event, 'tool_arguments', ''),
                    "tool_id": getattr(event, 'tool_id', ''),
                    "step": getattr(event, 'step', 1),
                    "round": round_num,
                    "phase": phase,
                }, operation_type="tool_call")
            elif event.type == EventType.TOOL_CALL_SUCCESS:
                result = getattr(event, 'tool_result', None)
                do_pub(PipelineEventType.LLM_TOOL_RESULT, "researcher", {
                    "module_name": module_name,
                    "tool_name": event.tool_name,
                    "tool_result": str(result) if result else None,
                    "tool_arguments": getattr(event, 'tool_arguments', ''),
                    "step": getattr(event, 'step', 1),
                    "round": round_num,
                    "phase": phase,
                }, operation_type="tool_result")
            elif event.type == EventType.TOOL_CALL_FAILED:
                do_pub(PipelineEventType.LLM_TOOL_ERROR, "researcher", {
                    "module_name": module_name,
                    "tool_name": event.tool_name,
                    "tool_error": getattr(event, 'tool_error', ''),
                    "step": getattr(event, 'step', 1),
                    "round": round_num,
                    "phase": phase,
                }, operation_type="tool_result")
            elif event.type == EventType.CONTENT_DELTA:
                do_pub(PipelineEventType.LLM_CONTENT, "researcher", {
                    "module_name": module_name,
                    "content": event.content or '',
                    "step": getattr(event, 'step', 1),
                    "round": round_num,
                    "phase": phase,
                }, operation_type="content")
        return react_handler

    tag = f"[{module.name}]"

    # Publish SUB_NODE_START for this module
    pub(PipelineEventType.SUB_NODE_START, "researcher", {
        "module_name": module.name,
        "module_files": module.files,
        "module_description": module.description,
    }, sub_node_id=sub_id, sub_node_name=module.name)

    _print(verbose, f"  {tag} 开始研究 ({len(module.files)} 个文件)")

    # === 阶段 1：多轮生成 + 评估反馈 ===
    for round_num in range(1, max_eval_rounds + 1):
        _print(verbose, f"  {tag} === 第 {round_num}/{max_eval_rounds} 轮 ===")
        messages = _build_generate_messages(ctx, module, round_num)

        _print(verbose or round_num == 1, f"  {tag} 调用 ReAct agent 生成报告...")
        events = react_stream(messages=messages, tools=tools, provider=ctx.provider, model=ctx.pro_model, max_steps=ctx.max_sub_agent_steps, event_handler=make_react_handler(module.name, round_num, "generate"))
        report = _collect_agent_output(events, tag, verbose)
        module.research_report = report

        if round_num >= max_eval_rounds:
            print(f"  {tag} 达到最大轮次，进入最终生成", flush=True)
            break

        print(f"  {tag} 正在评估报告质量...", flush=True)
        eval_result = _evaluate_report(ctx, module, report, round_num)
        score = eval_result.get("total_score", "?")

        if eval_result.get("pass", False):
            print(f"  {tag} 评估通过 (分数: {score})，进入最终生成", flush=True)
            break
        else:
            suggestions = eval_result.get("suggestions", [])
            print(f"  {tag} 评估未通过 (分数: {score})，改进后重试", flush=True)
            if verbose:
                for s in suggestions:
                    print(f"    → {s}", flush=True)

    # === 阶段 2：最终无工具生成报告 ===
    _print(verbose, f"  {tag} 构建最终报告（无工具模式）...")
    final_messages = _build_final_messages(ctx, module)
    final_messages.append(UserMessage("已收集足够上下文，请立即生成完整的中文分析报告。不再调用任何工具，直接输出报告。"))

    _print(verbose, f"  {tag} 最终生成，无工具模式...")
    events = react_stream(messages=final_messages, tools=[], provider=ctx.provider, model=ctx.pro_model, max_steps=ctx.max_sub_agent_steps, event_handler=make_react_handler(module.name, 0, "final"))
    report = _collect_agent_output(events, tag, verbose)
    module.research_report = report

    _write_module_report(report_dir, module)
    print(f"  {tag} 报告已保存", flush=True)

    pub(PipelineEventType.SUB_NODE_END, "researcher", {
        "module_name": module.name,
        "report_len": len(module.research_report) if module.research_report else 0,
    }, sub_node_id=sub_id, sub_node_name=module.name)

    pub(PipelineEventType.STAGE_RESEARCH_COMPLETE, "researcher", {
        "module_name": module.name,
        "report_len": len(module.research_report) if module.research_report else 0,
    })


def _build_generate_messages(ctx: PipelineContext, module: Module, round_num: int) -> list:
    system_prompt = SUB_AGENT_SYSTEM.format(module_name=module.name, project_name=ctx.project_name, module_description=module.description, module_files="\n".join(f"  - {f}" for f in module.files))
    messages = [SystemMessage(system_prompt), UserMessage(SUB_AGENT_USER.format(module_name=module.name))]

    if round_num > 1 and module.research_report:
        improvement_hints = getattr(module, '_eval_suggestions', [])
        hints_text = "\n".join(f"  - {s}" for s in improvement_hints) if improvement_hints else "无具体建议"
        messages.append(UserMessage(f"上一轮评估发现以下不足，请针对性改进：\n{hints_text}\n\n请重新读取相关文件，补充缺失的分析，输出改进后的完整报告。"))

    return messages


def _build_final_messages(ctx: PipelineContext, module: Module) -> list:
    system_prompt = SUB_AGENT_SYSTEM.format(module_name=module.name, project_name=ctx.project_name, module_description=module.description, module_files="\n".join(f"  - {f}" for f in module.files))
    messages = [SystemMessage(system_prompt), UserMessage(SUB_AGENT_USER.format(module_name=module.name))]

    if module.research_report:
        suggestions = getattr(module, '_eval_suggestions', [])
        hints_text = "\n".join(f"  - {s}" for s in suggestions) if suggestions else "无具体建议"
        messages.append(UserMessage(f"以下是之前的研究结论，可作为参考：\n{module.research_report[:3000]}\n\n评估建议：\n{hints_text}\n\n请综合以上信息，生成最终的完整分析报告。"))

    return messages


def _evaluate_report(ctx: PipelineContext, module: Module, report: str, round_num: int = 0) -> dict:
    pub = getattr(ctx, '_pub', None)
    run_id = ctx.run_id
    sub_id = f"module_{module.name}"

    def do_pub(et, stage, data, step=1, **kwargs):
        if pub and run_id:
            pub(et, stage, data, step, sub_node_id=sub_id, sub_node_name=module.name, **kwargs)

    system_prompt = EVAL_AGENT_SYSTEM.format(project_name=ctx.project_name, module_name=module.name, module_description=module.description, module_files="\n".join(f"  - {f}" for f in module.files))
    user_prompt = EVAL_AGENT_USER.format(module_name=module.name, report=report)

    print(f"  [{module.name}] 调用评估 LLM...", flush=True)
    start = time.time()
    response = call_llm(ctx.provider, system_prompt, user_prompt, model=ctx.pro_model)
    duration_ms = int((time.time() - start) * 1000)
    print(f"  [{module.name}] 评估响应 {len(response)} 字符", flush=True)

    # Publish eval LLM call with full data
    do_pub(PipelineEventType.LLM_CALL, "researcher", {
        "model": ctx.pro_model,
        "prompt": user_prompt,
        "response": response,
        "duration_ms": duration_ms,
        "call_type": "eval",
        "round": round_num,
    }, operation_type="eval")

    try:
        result = json.loads(extract_json(response))
        print(f"  [{module.name}] 评估解析成功: {result}", flush=True)
    except json.JSONDecodeError as e:
        print(f"  [{module.name}] 评估 JSON 解析失败: {e}", flush=True)
        result = {"pass": True, "total_score": 30, "suggestions": []}

    # Publish structured eval result
    do_pub(PipelineEventType.EVAL_RESULT, "researcher", {
        "module_name": module.name,
        "eval_pass": result.get("pass", False),
        "total_score": result.get("total_score", 0),
        "suggestions": result.get("suggestions", []),
        "round": round_num,
    }, operation_type="eval")

    module._eval_suggestions = result.get("suggestions", [])
    return result


def _collect_agent_output(events, tag: str, verbose: bool) -> str:
    step_contents = {}
    had_tool_calls = False
    step_count = 0

    for event in events:
        if event.type == EventType.STEP_START:
            had_tool_calls = False
            step_count += 1
            if not verbose:
                print(f"  {tag} 步骤 {step_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
        if event.type == EventType.TOOL_CALL:
            had_tool_calls = True
            if not verbose:
                print(f"  {tag}   工具: {event.tool_name}", flush=True)

    if not step_contents:
        return "（未能生成报告）"

    if not had_tool_calls:
        return list(step_contents.values())[-1]
    return max(step_contents.values(), key=len)


def _write_module_report(report_dir: str, module: Module) -> None:
    path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(module.research_report)


def _print(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, flush=True)
