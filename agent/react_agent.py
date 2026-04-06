import json
import re
import threading
from queue import Queue, Empty
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

# 过滤 content 中的 tool_use(...) 文本行（LLM 有时会将其输出为普通文字）
_TOOL_CALL_RE = re.compile(r'^tool_use\([^)]*\).*$', re.MULTILINE)

MAX_STEP_CNT = 30
STREAM_TIMEOUT_PER_STEP = 120  # 每个步骤的最大等待秒数（120秒足够完成一次生成）


def _stream_with_timeout(adaptor, messages, tools, model, timeout):
    """对 adaptor.stream() 的迭代包装超时保护"""
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


def stream(messages, tools, provider="anthropic", model=None, max_steps=MAX_STEP_CNT):
    adaptor = LLMAdaptor(provider=provider)
    react_finished = False
    step = 1

    while (not react_finished) and step <= max_steps:
        cur_step = step
        yield Event(type=EventType.STEP_START, step=cur_step)
        step = step + 1

        content = ""
        thinking = ""
        raw_tool_calls = []
        tool_results = {}

        try:
            stream_iter = _stream_with_timeout(adaptor, messages, tools, model, STREAM_TIMEOUT_PER_STEP)
        except TimeoutError as e:
            print(f"  [TIMEOUT] 步骤 {cur_step} LLM 调用超时: {e}", flush=True)
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        try:
            for event in stream_iter:
                yield event
                if event.type == EventType.THINKING_DELTA:
                    thinking += event.content
                elif event.type == EventType.CONTENT_DELTA:
                    content += event.content
                elif event.type == EventType.TOOL_CALL:
                    raw_tool_calls.append(event.raw)
                    tool_results[event.tool_id] = {"result": None, "error": None}
                    try:
                        exec_tool = next((t for t in tools if t.name == event.tool_name), None)
                        if exec_tool is None:
                            raise ValueError(f"Tool '{event.tool_name}' not found")
                        exec_tool_arguments = json.loads(event.tool_arguments) if event.tool_arguments else {}
                        result = exec_tool(**exec_tool_arguments)
                        tool_results[event.tool_id]["result"] = result
                        yield Event(type=EventType.TOOL_CALL_SUCCESS, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_result=result)
                    except Exception as e:
                        import traceback
                        err_msg = f"工具执行失败 {event.tool_name}: {e}, 参数: {event.tool_arguments}"
                        print(f"  !!! {err_msg}\n{traceback.format_exc()}", flush=True)
                        tool_results[event.tool_id]["error"] = str(e)
                        yield Event(type=EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_error=e)
        except TimeoutError as e:
            print(f"  [TIMEOUT] 步骤 {cur_step} LLM 调用超时: {e}", flush=True)
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        # 过滤 content 中的 tool_use(...) 文本（LLM 有时将其输出为普通文字）
        filtered_content = _TOOL_CALL_RE.sub('', content).strip()
        yield Event(type=EventType.STEP_END, content=filtered_content, step=cur_step)
        if not raw_tool_calls:
            react_finished = True
            break

        # thinking 存入消息的独立字段，不混入 content
        messages.append(AssistantMessage(content=content, tool_calls=raw_tool_calls, thinking=thinking))
        for raw_tc in raw_tool_calls:
            tid = raw_tc["id"]
            tr = tool_results[tid]
            messages.append(ToolMessage(
                tool_id=tid,
                tool_name=raw_tc["name"],
                tool_result=tr["result"],
                tool_error=tr["error"],
            ))
