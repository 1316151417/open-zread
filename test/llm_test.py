from base.types import SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from prompt.test_system_prompt import SYSTEM_PROMPT
from tool.test_tool import get_weather, get_temperature
from agent import react_agent
from log.printer import print_event
from settings import get_lite_config

messages = [
    SystemMessage(SYSTEM_PROMPT),
    UserMessage("今天北京和上海的天气怎么样？"),
]
tools = [get_weather]

def adaptor_test():
    config = get_lite_config()
    adaptor = LLMAdaptor(config)
    for event in adaptor.stream(messages=messages, tools=tools):
        print_event(event)

def react_test():
    config = get_lite_config()
    for event in react_agent.stream(messages=messages, tools=tools, config=config):
        print_event(event)

if __name__ == "__main__":
    # print("=== Adaptor Test ===")
    # adaptor_test()
    # print("=== React Agent Test ===")
    react_test()
