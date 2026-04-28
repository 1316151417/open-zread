"""Langfuse 开关与条件导入。

在 import 时读取 LANGFUSE_ENABLE 环境变量。
关闭时提供 no-op 的 observe、propagate_attributes，以及标准 openai.OpenAI。
"""
import os
from contextlib import nullcontext

LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLE", "false").lower() == "true"

if LANGFUSE_ENABLED:
    from langfuse import observe, propagate_attributes
    from langfuse.openai import OpenAI
else:
    def observe(**kwargs):
        """Langfuse 禁用时的 no-op 装饰器。"""
        def decorator(fn):
            return fn
        return decorator

    def propagate_attributes(**kwargs):
        """Langfuse 禁用时的 no-op 上下文管理器。"""
        return nullcontext()

    from openai import OpenAI
