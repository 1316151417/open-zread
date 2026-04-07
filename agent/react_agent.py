"""
ReAct Agent - implements the Observe -> Think -> Act loop with streaming events.
"""
import json
import re
import threading
from queue import Queue, Empty

from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

TOOL_CALL_RE = re.compile(r'^tool_use\([^)]*\).*$', re.MULTILINE)
MAX_STEP_CNT = 30
STREAM_TIMEOUT_PER_STEP = 120


def _format_messages_for_monitor(messages):
    """Format conversation messages for monitoring display."""
    parts = []
    for msg in messages:
        name = type(msg).__name__
        if name == 'SystemMessage':
            parts.append(f"[System]\n{msg.content}")
        elif name == 'UserMessage':
            parts.append(f"[User]\n{msg.content}")
        elif name == 'AssistantMessage':
            text = msg.content or ""
            if getattr(msg, 'tool_calls', None):
                tc_names = [tc.get("name", "?") for tc in msg.tool_calls]
                text += f"\n[调用工具: {', '.join(tc_names)}]"
            parts.append(f"[Assistant]\n{text}")
        elif name == 'ToolMessage':
            result = str(getattr(msg, 'tool_result', ''))[:500] if getattr(msg, 'tool_result', None) else "(空)"
            error = getattr(msg, 'tool_error', None)
            if error:
                result = f"错误: {error}"
            parts.append(f"[工具结果: {getattr(msg, 'tool_name', '?')}]\n{result}")
    return "\n\n".join(parts)


def _stream_with_timeout(adaptor, messages, tools, model, timeout):
    """对 adaptor.stream() 的迭代包装超时保护。"""
    result_queue = Queue()

    def worker():
        try:
            kwargs = {}
            if model:
                kwargs["model"] = model
            for event in adaptor.stream(messages, tools=tools, **kwargs):
                result_queue.put(("event", event))
            result_queue.put(("done", None))
        except Exception as e:
            import traceback
            result_queue.put(("exception", f"{e}\n{traceback.format_exc()}"))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    remaining = timeout
    while True:
        try:
            tag, data = result_queue.get(timeout=remaining)
            if tag == "done":
                return
            if tag == "exception":
                raise RuntimeError(f"Stream exception: {data}")
            yield data
        except Empty:
            raise TimeoutError(f"LLM stream timeout after {timeout}s (no events received)")


def _parse_tool_arguments(arguments_str: str) -> dict:
    """安全解析 tool arguments JSON字符串。"""
    if not arguments_str:
        return {}
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tool arguments: {arguments_str[:100]}... ({e})")


def _execute_tool(tool, tool_arguments: str):
    """执行工具，返回 (result, error)。"""
    try:
        args = _parse_tool_arguments(tool_arguments)
        result = tool(**args)
        return result, None
    except Exception as e:
        import traceback
        print(f"  !!! 工具执行失败 {tool.name}: {e}\n{traceback.format_exc()}", flush=True)
        return None, str(e)


def stream(messages, tools, provider="anthropic", model=None, max_steps=MAX_STEP_CNT, event_handler=None):
    """
    ReAct stream generator: yields events for each step.

    Args:
        event_handler: Optional callback(event) called for every event.
                       Allows forwarding events to an external monitor.
    """
    def _emit(event):
        if event_handler:
            event_handler(event)

    adaptor = LLMAdaptor(provider=provider)
    react_finished = False
    step = 1

    while (not react_finished) and step <= max_steps:
        cur_step = step
        # Capture messages summary for monitoring (input to this LLM call)
        msg_summary = _format_messages_for_monitor(messages)
        _emit(Event(type=EventType.STEP_START, step=cur_step, raw={"messages": msg_summary}))
        yield Event(type=EventType.STEP_START, step=cur_step, raw={"messages": msg_summary})
        step = step + 1

        content = ""
        thinking = ""
        raw_tool_calls = []
        tool_results = {}

        try:
            stream_iter = _stream_with_timeout(adaptor, messages, tools, model, STREAM_TIMEOUT_PER_STEP)
        except TimeoutError as e:
            print(f"  [TIMEOUT] 步骤 {cur_step} LLM 调用超时: {e}", flush=True)
            _emit(Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step))
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        try:
            for event in stream_iter:
                if event.type == EventType.THINKING_DELTA:
                    thinking += event.content or ""
                elif event.type == EventType.CONTENT_DELTA:
                    content += event.content or ""
                elif event.type == EventType.TOOL_CALL:
                    raw_tool_calls.append(event.raw)
                    # Emit original TOOL_CALL so monitor sees LLM decision before execution
                    _emit(event)
                    tool = next((t for t in tools if t.name == event.tool_name), None)
                    if tool is None:
                        tool_results[event.tool_id] = {"result": None, "error": f"Tool '{event.tool_name}' not found"}
                        e2 = Event(type=EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_error=f"Tool '{event.tool_name}' not found")
                        _emit(e2); yield e2
                    else:
                        result, error = _execute_tool(tool, event.tool_arguments)
                        tool_results[event.tool_id] = {"result": result, "error": error}
                        e2 = Event(type=EventType.TOOL_CALL_SUCCESS if not error else EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_result=result, tool_error=error)
                        _emit(e2); yield e2
                    continue
                else:
                    _emit(event)
                    yield event
        except TimeoutError as e:
            print(f"  [TIMEOUT] 步骤 {cur_step} LLM 调用超时: {e}", flush=True)
            _emit(Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step))
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        filtered_content = TOOL_CALL_RE.sub('', content).strip()
        e_end = Event(type=EventType.STEP_END, content=filtered_content, step=cur_step,
                      raw={"full_content": content, "messages": msg_summary})
        _emit(e_end); yield e_end

        if not raw_tool_calls:
            react_finished = True
            break

        messages.append(AssistantMessage(content=content, tool_calls=raw_tool_calls, thinking=thinking))
        for raw_tc in raw_tool_calls:
            tid = raw_tc["id"]
            tr = tool_results[tid]
            messages.append(ToolMessage(tool_id=tid, tool_name=raw_tc["name"], tool_result=tr["result"], tool_error=tr["error"]))
