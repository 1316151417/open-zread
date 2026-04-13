"""
Anthropic-compatible API client - configurable via settings.
"""
import os
import time

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 1


def call_anthropic(messages, base_url=None, api_key=None, model=None, max_tokens=None, **kwargs):
    """Anthropic-compatible synchronous call with configurable endpoint."""
    import anthropic

    client = anthropic.Anthropic(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com/anthropic",
        timeout=DEFAULT_TIMEOUT,
    )

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


def call_stream_anthropic(messages, base_url=None, api_key=None, model=None, max_tokens=None, **kwargs):
    """Anthropic-compatible streaming call with configurable endpoint."""
    import anthropic

    client = anthropic.Anthropic(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com/anthropic",
        timeout=DEFAULT_TIMEOUT,
    )

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
