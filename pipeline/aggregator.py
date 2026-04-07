"""Stage 6: 最终报告汇总 - ReAct agent 整合所有模块报告."""
import json
import time

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER, AGGREGATOR_EVAL_SYSTEM, AGGREGATOR_EVAL_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from provider.llm import call_llm, extract_json
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType


def aggregate_reports(ctx: PipelineContext) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1, **kwargs):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(
                run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step, **kwargs,
            ))

    pub(PipelineEventType.STAGE_START, "aggregator", {"stage_index": 6})

    def make_react_handler(sub_node_id: str, sub_node_name: str, op_type: str, round_num: int = 0):
        from base.types import Event as ReactEvent
        def react_handler(event: ReactEvent):
            if event.type == EventType.STEP_START:
                # Publish LLM_CALL FIRST — before any tool calls
                raw = getattr(event, 'raw', None) or {}
                pub(PipelineEventType.LLM_CALL, "aggregator", {
                    "model": ctx.max_model,
                    "prompt": raw.get("messages", ""),
                    "step": event.step,
                    "round": round_num,
                }, sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                   operation_type="llm_call")
                pub(PipelineEventType.LLM_STEP_START, "aggregator",
                    {"step": event.step, "round": round_num},
                    step=event.step,
                    sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                    operation_type=op_type)
            elif event.type == EventType.STEP_END:
                content = getattr(event, 'content', '') or ''
                raw = getattr(event, 'raw', None) or {}
                pub(PipelineEventType.LLM_STEP_END, "aggregator",
                    {"step": event.step, "content": content, "response": raw.get("full_content", content), "round": round_num},
                    step=event.step,
                    sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                    operation_type=op_type)
            elif event.type == EventType.TOOL_CALL:
                pub(PipelineEventType.LLM_TOOL_CALL, "aggregator", {
                    "tool_name": event.tool_name,
                    "tool_arguments": getattr(event, 'tool_arguments', ''),
                    "step": getattr(event, 'step', 1),
                }, sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                   operation_type="tool_call")
            elif event.type == EventType.TOOL_CALL_SUCCESS:
                result = getattr(event, 'tool_result', None)
                pub(PipelineEventType.LLM_TOOL_RESULT, "aggregator", {
                    "tool_name": event.tool_name,
                    "tool_result": str(result) if result else None,
                    "tool_arguments": getattr(event, 'tool_arguments', ''),
                    "step": getattr(event, 'step', 1),
                }, sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                   operation_type="tool_result")
            elif event.type == EventType.TOOL_CALL_FAILED:
                pub(PipelineEventType.LLM_TOOL_ERROR, "aggregator", {
                    "tool_name": event.tool_name,
                    "tool_error": getattr(event, 'tool_error', ''),
                    "step": getattr(event, 'step', 1),
                }, sub_node_id=sub_node_id, sub_node_name=sub_node_name,
                   operation_type="tool_result")
        return react_handler

    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    module_reports = "\n\n---\n\n".join(f"### 模块：{m.name}\n\n{m.research_report}" for m in ctx.selected_modules)
    max_eval_rounds = ctx.settings.get("max_eval_rounds", 1)
    final_report = ""
    eval_result = {"suggestions": []}

    # === 阶段 1：多轮生成 + 评估反馈 ===
    for round_num in range(1, max_eval_rounds + 1):
        # Publish sub-node start for generate phase
        pub(PipelineEventType.SUB_NODE_START, "aggregator", {
            "phase": "generate", "round": round_num,
        }, sub_node_id="aggregate_generate", sub_node_name="生成Agent", operation_type="generate")

        system_prompt = AGGREGATOR_SYSTEM.format(project_name=ctx.project_name, tree_text=ctx.tree_text)
        user_msg = AGGREGATOR_USER.format(project_name=ctx.project_name, module_reports=module_reports)
        messages = [SystemMessage(system_prompt), UserMessage(user_msg)]

        print(f"  汇总 agent 第 {round_num}/{max_eval_rounds} 轮：研究阶段...", flush=True)
        events = react_stream(messages=messages, tools=tools, provider=ctx.provider, model=ctx.max_model, max_steps=ctx.max_sub_agent_steps, event_handler=make_react_handler("aggregate_generate", "生成Agent", "generate", round_num))

        step_contents = _collect_step_contents(events)
        if not step_contents:
            final_report = "# 错误：未能生成报告"
            pub(PipelineEventType.SUB_NODE_END, "aggregator", {
                "phase": "generate", "round": round_num, "status": "error",
            }, sub_node_id="aggregate_generate", sub_node_name="生成Agent")
            break

        best_research = max(step_contents.values(), key=len)
        print(f"  研究阶段完成，最佳内容 {len(best_research)} 字符", flush=True)

        pub(PipelineEventType.SUB_NODE_END, "aggregator", {
            "phase": "generate", "round": round_num, "content_len": len(best_research),
        }, sub_node_id="aggregate_generate", sub_node_name="生成Agent")

        if round_num >= max_eval_rounds:
            final_report = best_research
            break

        # 评估报告
        print(f"  汇总 agent 正在评估报告质量...", flush=True)
        eval_result = _evaluate_aggregator_report(ctx, best_research, round_num)

        if eval_result.get("pass", False):
            print(f"  汇总 agent 评估通过 (分数: {eval_result.get('total_score')})，进入最终生成", flush=True)
            final_report = best_research
            break
        else:
            suggestions = eval_result.get("suggestions", [])
            print(f"  汇总 agent 评估未通过 (分数: {eval_result.get('total_score')})，改进后重试", flush=True)
            for s in suggestions[:3]:
                print(f"    → {s}", flush=True)
            module_reports = best_research

    # === 阶段 2：最终无工具生成 ===
    pub(PipelineEventType.SUB_NODE_START, "aggregator", {
        "phase": "final",
    }, sub_node_id="aggregate_final", sub_node_name="最终生成", operation_type="generate")

    system_prompt = AGGREGATOR_SYSTEM.format(project_name=ctx.project_name, tree_text=ctx.tree_text)
    final_messages = [
        SystemMessage(system_prompt),
        UserMessage(AGGREGATOR_USER.format(project_name=ctx.project_name, module_reports=module_reports)),
        UserMessage(f"以下是之前的研究结论，可作为参考：\n{final_report[:3000]}\n\n评估建议：\n{_get_suggestions_text(eval_result)}\n\n请综合以上信息，生成最终的完整中文项目分析报告。不再调用任何工具，直接输出报告。"),
    ]

    print(f"  汇总 agent 最终生成（无工具模式）...", flush=True)
    events2 = react_stream(messages=final_messages, tools=[], provider=ctx.provider, model=ctx.max_model, max_steps=ctx.max_sub_agent_steps, event_handler=make_react_handler("aggregate_final", "最终生成", "generate"))

    step_contents2 = _collect_step_contents(events2)
    if step_contents2:
        ctx.final_report = max(step_contents2.values(), key=len)
    elif final_report:
        ctx.final_report = final_report
    else:
        ctx.final_report = "# 错误：未能生成报告"

    pub(PipelineEventType.SUB_NODE_END, "aggregator", {
        "phase": "final", "content_len": len(ctx.final_report) if ctx.final_report else 0,
    }, sub_node_id="aggregate_final", sub_node_name="最终生成")

    pub(PipelineEventType.STAGE_AGGREGATE_COMPLETE, "aggregator", {
        "report_len": len(ctx.final_report) if ctx.final_report else 0,
    })
    pub(PipelineEventType.STAGE_END, "aggregator", {
        "output_summary": f"aggregator complete, final report {len(ctx.final_report) if ctx.final_report else 0} chars"
    })


def _collect_step_contents(events) -> dict:
    step_contents = {}
    step_count = 0
    for event in events:
        if event.type == EventType.STEP_START:
            step_count += 1
            print(f"  汇总 agent 步骤 {step_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
            print(f"  汇总 agent 步骤 {step_count} 完成，内容 {len(event.content)} 字符", flush=True)
        if event.type == EventType.TOOL_CALL:
            print(f"  汇总 agent 调用工具: {event.tool_name}", flush=True)
    return step_contents


def _evaluate_aggregator_report(ctx: PipelineContext, report: str, round_num: int = 0) -> dict:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1, **kwargs):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(
                run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step, **kwargs,
            ))

    # Publish eval sub-node start
    pub(PipelineEventType.SUB_NODE_START, "aggregator", {
        "phase": "eval", "round": round_num,
    }, sub_node_id="aggregate_eval", sub_node_name="评估Agent", operation_type="eval")

    system_prompt = AGGREGATOR_EVAL_SYSTEM.format(project_name=ctx.project_name)
    user_prompt = AGGREGATOR_EVAL_USER.format(project_name=ctx.project_name, report=report)

    print(f"  [汇总评估] 调用评估 LLM...", flush=True)
    start = time.time()
    response = call_llm(ctx.provider, system_prompt, user_prompt, model=ctx.max_model)
    duration_ms = int((time.time() - start) * 1000)
    print(f"  [汇总评估] 评估响应 {len(response)} 字符", flush=True)

    # Publish eval LLM call with full data
    pub(PipelineEventType.LLM_CALL, "aggregator", {
        "model": ctx.max_model,
        "prompt": user_prompt,
        "response": response,
        "duration_ms": duration_ms,
        "call_type": "eval",
        "round": round_num,
    }, sub_node_id="aggregate_eval", sub_node_name="评估Agent", operation_type="eval")

    try:
        result = json.loads(extract_json(response))
        print(f"  [汇总评估] 评估结果: pass={result.get('pass')}, score={result.get('total_score')}", flush=True)
    except json.JSONDecodeError as e:
        print(f"  [汇总评估] JSON 解析失败: {e}", flush=True)
        result = {"pass": True, "total_score": 30, "suggestions": []}

    # Publish structured eval result
    pub(PipelineEventType.EVAL_RESULT, "aggregator", {
        "eval_pass": result.get("pass", False),
        "total_score": result.get("total_score", 0),
        "suggestions": result.get("suggestions", []),
        "round": round_num,
    }, sub_node_id="aggregate_eval", sub_node_name="评估Agent", operation_type="eval")

    # Publish eval sub-node end
    pub(PipelineEventType.SUB_NODE_END, "aggregator", {
        "phase": "eval", "round": round_num,
        "eval_pass": result.get("pass", False),
        "total_score": result.get("total_score", 0),
    }, sub_node_id="aggregate_eval", sub_node_name="评估Agent")

    return result


def _get_suggestions_text(eval_result: dict) -> str:
    suggestions = eval_result.get("suggestions", [])
    if not suggestions:
        return "无具体建议"
    return "\n".join(f"  - {s}" for s in suggestions)
