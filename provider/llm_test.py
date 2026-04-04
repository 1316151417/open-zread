from provider.anthropic_provider.anthropic_adaptor import LLMAdaptor, EventType

tools = [
    {
        "name": "get_weather",
        "description": "获取一个城市的天气",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称",
                },
            },
            "required": ["city"],
        },
    }
]

adaptor = LLMAdaptor()

for event in adaptor.stream(
    system="你是一个天气预报助手。注意：你可以在一次响应中调用多次工具",
    messages=[
        {"role": "user", "content": "今天北京和上海的天气怎么样？"},
    ],
    tools=tools,
):
    if event.type == EventType.MESSAGE_START:
        print("[MESSAGE_START]")
    elif event.type == EventType.CONTENT_DELTA:
        print(event.content, end="", flush=True)
    elif event.type == EventType.TOOL_START:
        print(f"\n[TOOL_START#{event.tool_index}] name={event.tool_name}")
    elif event.type == EventType.TOOL_END:
        print(f"\n[TOOL_END#{event.tool_index}] name={event.tool_name} args={event.tool_arguments}")
    elif event.type == EventType.MESSAGE_END:
        print(f"\n[MESSAGE_END: {event.finish_reason}]")
