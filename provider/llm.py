"""
Shared LLM utilities for pipeline modules.
"""
import threading
from queue import Queue, Empty

from base.types import EventType, SystemMessage, UserMessage

DEFAULT_TIMEOUT = 60


def extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON（可能被 markdown 代码块包裹）。"""
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


def call_llm_sync(adaptor, messages, timeout=DEFAULT_TIMEOUT, response_format=None):
    """同步 LLM 调用，返回完整文本内容。"""
    result_queue = Queue()

    def worker():
        try:
            kwargs = {}
            if response_format is not None:
                kwargs["response_format"] = response_format
            for event in adaptor.stream(messages, **kwargs):
                result_queue.put(("event", event))
            result_queue.put(("done", None))
        except Exception as e:
            result_queue.put(("exception", str(e)))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    content = ""
    while True:
        try:
            tag, data = result_queue.get(timeout=timeout)
            if tag == "done":
                return content
            if tag == "exception":
                raise RuntimeError(f"LLM stream exception: {data}")
            if data.type == EventType.CONTENT_DELTA:
                content += data.content
        except Empty:
            raise TimeoutError(f"LLM call timeout after {timeout}s")
    return content


def call_llm(provider: str, system: str, user: str, model: str | None = None, timeout: int = DEFAULT_TIMEOUT, response_format=None) -> str:
    """简单的同步 LLM 调用封装。"""
    from provider.adaptor import LLMAdaptor
    adaptor = LLMAdaptor(provider=provider)
    messages = [SystemMessage(system), UserMessage(user)]
    try:
        return call_llm_sync(adaptor, messages, timeout=timeout, response_format=response_format)
    except TimeoutError as e:
        print(f"  [LLM 调用超时] {e}", flush=True)
        return ""
