"""提示词编译：支持 Langfuse 远程和本地模板两种模式。"""
from util.langfuse import LANGFUSE_ENABLED

if LANGFUSE_ENABLED:
    from langfuse import get_client, observe

    _client = get_client()

    @observe(as_type="generation")
    def get_compiled_messages(name: str, **variables) -> list[dict]:
        """从 Langfuse 获取 chat prompt 并编译模板变量。"""
        prompt = _client.get_prompt(name, type="chat")
        _client.update_current_generation(prompt=prompt)
        return prompt.compile(**variables)

else:
    from prompt.pipeline_prompts import STEP1_SYSTEM, STEP1_USER, STEP2_SYSTEM, STEP2_USER
    from prompt.react_prompts import COMPRESS_SYSTEM, COMPRESS_USER

    _LOCAL_PROMPTS = {
        "step1": (STEP1_SYSTEM, STEP1_USER),
        "step2": (STEP2_SYSTEM, STEP2_USER),
        "compress": (COMPRESS_SYSTEM, COMPRESS_USER),
    }

    def get_compiled_messages(name: str, **variables) -> list[dict]:
        """从本地模板编译提示词。"""
        system_tmpl, user_tmpl = _LOCAL_PROMPTS[name]
        return [
            {"role": "system", "content": system_tmpl.format(**variables)},
            {"role": "user", "content": user_tmpl.format(**variables)},
        ]
