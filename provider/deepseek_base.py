"""
DeepSeek API client - consolidated implementation for both OpenAI and Anthropic protocols.
"""
import os
import time

from settings import get_model, get_max_tokens

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 1


def get_client_openai():
    """Get or create OpenAI-compatible client."""
    from openai import OpenAI, APITimeoutError, APIConnectionError
    return OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=DEFAULT_TIMEOUT,
    )


def get_client_anthropic():
    """Get or create Anthropic-compatible client."""
    import anthropic
    return anthropic.Anthropic(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/anthropic",
        timeout=DEFAULT_TIMEOUT,
    )


def call_openai(messages, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible synchronous call to DeepSeek."""
    from openai import APITimeoutError, APIConnectionError

    client = get_client_openai()
    model = model or get_model()
    max_tokens = max_tokens or get_max_tokens()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format or {"type": "json_object"},
                **kwargs,
            )
            return response.choices[0].message
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_stream_openai(messages, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible streaming call to DeepSeek."""
    from openai import APITimeoutError, APIConnectionError

    client = get_client_openai()
    model = model or get_model()
    max_tokens = max_tokens or get_max_tokens()

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format or {"type": "json_object"},
                **kwargs,
            )
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 流式调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_anthropic(messages, model=None, max_tokens=None, **kwargs):
    """Anthropic-compatible synchronous call to DeepSeek."""
    import anthropic

    client = get_client_anthropic()
    model = model or get_model()
    max_tokens = max_tokens or get_max_tokens()

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            )
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_stream_anthropic(messages, model=None, max_tokens=None, **kwargs):
    """Anthropic-compatible streaming call to DeepSeek."""
    import anthropic

    client = get_client_anthropic()
    model = model or get_model()
    max_tokens = max_tokens or get_max_tokens()

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            )
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 流式调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise
