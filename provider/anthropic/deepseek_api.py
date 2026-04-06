import os
import anthropic

client = anthropic.Anthropic(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/anthropic",
)


def call(messages, model="deepseek-chat", max_tokens=16384, **kwargs):
    return client.messages.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        **kwargs,
    )


def call_stream(messages, model="deepseek-chat", max_tokens=16384, **kwargs):
    return client.messages.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
        **kwargs,
    )
