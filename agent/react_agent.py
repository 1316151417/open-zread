import json
from provider.adaptor import LLMAdaptor
from base.types import EventType

MAX_LLM_CALL_CNT = 30


def react(messages, tools):
    adaptor = LLMAdaptor()
    react_finished = False
    llm_call_cnt = 0

    while (not react_finished) and llm_call_cnt < MAX_LLM_CALL_CNT:
        llm_call_cnt = llm_call_cnt + 1

        content = ""
        thinking = ""
        tool_call_dict = {}

        for event in adaptor.stream(
            messages,
            tools=tools,
        ):
            if event.type == EventType.CONTENT_DELTA:
                content += event.content
                print(event.content, end="", flush=True)

            elif event.type == EventType.THINKING_DELTA:
                thinking += event.content
                print(event.content, end="", flush=True)

            elif event.type == EventType.TOOL_CALL:
                # 工具调用
                tool_id = event.tool_id
                tool_name = event.tool_name
                tool_arguments = event.tool_arguments
                tool_status = "running"
                # 定义结构
                tool_call = {
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "tool_arguments": tool_arguments,
                    "tool_status": tool_status,
                    "tool_result": None,
                    "tool_error": None,
                }
                # 存入字典
                tool_call_dict[event.tool_id] = tool_call
                # 开始执行
                print(f"\n[Tool Call] {tool_name}({tool_arguments})")
                try:
                    # 匹配工具
                    exec_tool = next((t for t in tools if t.name == tool_name), None)
                    if exec_tool is None:
                        raise ValueError(f"Tool '{tool_name}' not found")
                    # 参数解析
                    exec_tool_arguments = json.loads(tool_arguments) if tool_arguments else {}
                    # 执行工具
                    result = exec_tool(**exec_tool_arguments)
                    print(f"[Tool Result] {result}")
                    # 更新工具调用结果
                    tool_call["tool_status"] = "success"
                    tool_call["tool_result"] = result
                except Exception as e:
                    # 更新工具调用错误
                    tool_call["tool_status"] = "failed"
                    tool_call["tool_error"] = str(e)
        if not tool_call_dict:
            # 没有工具调用，结束
            react_finished = True
        for tool_call in tool_call_dict.values():
            # TODO openai是 tool, anthropic是 user
            messages.append({
                "role": "user",
                "content": str(tool_call),
            })
    return content or "finished"
