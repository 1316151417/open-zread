from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from prompt.test_system_prompt import SYSTEM_PROMPT
from tool.test_tool import get_weather, get_temperature
from agent import react_agent
from log import logger

tools = [get_weather]

def print_event(event):
    if event.type == EventType.MESSAGE_START:
        logger.debug("[MESSAGE_START]")
    elif event.type == EventType.CONTENT_START:
        logger.debug("[Content Start]")
    elif event.type == EventType.CONTENT_DELTA:
        logger.debug(event.content, end="", flush=True)
    elif event.type == EventType.CONTENT_END:
        logger.debug("\n[Content End]")
    elif event.type == EventType.THINKING_START:
        logger.debug("[Thinking Start]")
    elif event.type == EventType.THINKING_DELTA:
        logger.debug(event.content, end="", flush=True)
    elif event.type == EventType.THINKING_END:
        logger.debug("\n[Thinking End]")
    elif event.type == EventType.TOOL_CALL:
        logger.debug("[Tool Call]", tool_name=event.tool_name, tool_arguments=event.tool_arguments)
    elif event.type == EventType.TOOL_CALL_SUCCESS:
        logger.debug("[Tool Result]", tool_result=str(event.tool_result))
    elif event.type == EventType.TOOL_CALL_FAILED:
        logger.debug("[Tool Error]", tool_error=str(event.tool_error))
    elif event.type == EventType.MESSAGE_END:
        logger.debug("[MESSAGE_END]", stop_reason=event.stop_reason, usage=event.usage)

def openai_test():
    adaptor = LLMAdaptor(provider="openai")

    for event in adaptor.stream(
        messages=[
            SystemMessage(SYSTEM_PROMPT),
            UserMessage("今天北京和上海的天气怎么样？"),
        ],
        tools=tools,
    ):
        print_event(event)

def anthropic_test():
    adaptor = LLMAdaptor(provider="anthropic")

    for event in adaptor.stream(
        messages=[
            SystemMessage(SYSTEM_PROMPT),
            UserMessage("今天北京和上海的天气怎么样？"),
        ],
        tools=tools,
    ):
        print_event(event)

def react_test():
    messages = [
        SystemMessage(SYSTEM_PROMPT),
        UserMessage("今天北京和上海的天气怎么样？"),
    ]
    # for event in react_agent.stream(messages, tools, provider="openai"):
    #     pass
    for event in react_agent.stream(messages, tools, provider="anthropic"):
        print_event(event)

if __name__ == "__main__":
    # print("=== OpenAI Test ===")
    # openai_test()
    # print("=== Anthropic Test ===")
    # anthropic_test()
    print("=== React Agent Test ===")
    react_test()
