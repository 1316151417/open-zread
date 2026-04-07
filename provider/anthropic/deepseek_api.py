"""
Anthropic-compatible DeepSeek API - delegates to provider/deepseek_base.py
"""
from provider.deepseek_base import call_anthropic as call, call_stream_anthropic as call_stream
