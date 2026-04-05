from provider.adaptor import LLMAdaptor
from base.types import EventType

# 最多调用30次LLM，避免死循环
MAX_LLM_CALL_CNT = 5

def react(messages, tools):    
    adaptor = LLMAdaptor()
    react_finished = False
    llm_call_cnt = 0
    
    while((not react_finished) and llm_call_cnt < MAX_LLM_CALL_CNT):
        # LLM调用次数+1
        llm_call_cnt = llm_call_cnt + 1
        # 参数准备
        content = ""
        thinking = ""
        tool_calls = []
        # 调用LLM
        for event in adaptor.stream(
            messages, 
            tools=tools,
        ):
            # 消息处理
            if event.type == EventType.CONTENT_DELTA:
                content += event.content
            # 思考处理
            elif event.type == EventType.THINKING_DELTA:
                thinking += event.content
            # 工具调用
            elif event.type == EventType.TOOL_CALL:
                tool_calls.append({
                    "tool_id": event.tool_id,
                    "tool_name": event.tool_name,
                    "tool_arguments": event.tool_arguments,
                    "tool_status": "running",
                })
                # TODO 调用工具
        react_finished = tool_calls == []
    return content or "finished"