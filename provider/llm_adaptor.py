from dataclasses import dataclass
from enum import Enum
from deepseek_llm import call_stream


class EventType(Enum):
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    MESSAGE_END = "message_end"


@dataclass
class Event:
    type: EventType
    data: str | None = None
    tool_index: int | None = None


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
                yield Event(EventType.CONTENT_DELTA, delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tools:
                        tools[idx] = {"started": False, "arguments": ""}
                        yield Event(EventType.TOOL_START, tool_index=idx)
                        tools[idx]["started"] = True

                    if tc.function.arguments:
                        tools[idx]["arguments"] += tc.function.arguments

            if choice.finish_reason is not None:
                yield Event(EventType.MESSAGE_END, choice.finish_reason)

                if choice.finish_reason == "tool_calls":
                    for idx, tool_data in tools.items():
                        yield Event(
                            EventType.TOOL_END,
                            data=tool_data["arguments"],
                            tool_index=idx,
                        )

                return
