import json
import os

_DEFAULTS = {
    "provider": "anthropic",
    "lite_model": "deepseek-chat",
    "pro_model": "deepseek-chat",
    "max_model": "deepseek-reasoner",
    "max_tokens": 16384,
    "max_sub_agents": 5,
    "max_sub_agent_steps": 15,
    "max_eval_rounds": 3,
    "parallel_research": True,
}

_settings = None


def load_settings(path: str | None = None) -> dict:
    global _settings
    if _settings is not None:
        return _settings

    if path is None:
        # 按优先级查找 settings.json
        candidates = [
            os.path.join(os.getcwd(), "settings.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                path = candidate
                break

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
        _settings = {**_DEFAULTS, **user_settings}
    else:
        _settings = dict(_DEFAULTS)

    return _settings


def get_settings() -> dict:
    return load_settings()


def get_provider() -> str:
    return get_settings()["provider"]


def get_model() -> str:
    return get_settings().get("model", _DEFAULTS.get("lite_model", "deepseek-chat"))


def get_lite_model() -> str:
    return get_settings().get("lite_model", _DEFAULTS.get("lite_model", "deepseek-chat"))


def get_pro_model() -> str:
    return get_settings().get("pro_model", _DEFAULTS.get("pro_model", "deepseek-chat"))


def get_max_model() -> str:
    return get_settings().get("max_model", _DEFAULTS.get("max_model", "deepseek-reasoner"))


def get_max_tokens() -> int:
    return get_settings()["max_tokens"]
