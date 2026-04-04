from ..base import EventType, Event
from .deepseek_openai_api import call_stream


class LLMAdaptor:
    def stream(self, messages, **kwargs):
        state = "idle"
        tools = {}

        for chunk in call_stream(messages, **kwargs):
            choice = chunk.choices[0]
            delta = choice.delta

            if state == "idle":
                if delta.role == "assistant" or delta.content or delta.tool_calls:
                    state = "streaming"
                    yield Event(EventType.MESSAGE_START)

            if delta.content:
                yield Event(EventType.CONTENT_DELTA, content=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tools:
                        tools[idx] = {
                            "name": tc.function.name or "",
                            "arguments": "",
                            "started": False,
                        }

                    if tc.function.name and not tools[idx]["started"]:
                        tools[idx]["started"] = True
                        yield Event(
                            EventType.TOOL_START,
                            tool_index=idx,
                            tool_name=tools[idx]["name"],
                        )

                    if tc.function.arguments:
                        tools[idx]["arguments"] += tc.function.arguments

            if choice.finish_reason is not None:
                for idx, tool in tools.items():
                    yield Event(
                        EventType.TOOL_END,
                        tool_index=idx,
                        tool_name=tool["name"],
                        tool_arguments=tool["arguments"],
                    )

                yield Event(EventType.MESSAGE_END, finish_reason=choice.finish_reason)
                return
