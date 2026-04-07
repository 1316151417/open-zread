"""
ConfigManager - loads and manages pipeline configuration from settings.json.
Single source of truth. Supports hot-reload without restarting the pipeline.
"""
import json as _json
import copy
import os
import threading
from pathlib import Path
from typing import Any


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
    "server_url": "http://localhost:7890",
}


class ConfigManager:
    """
    Manages ALL pipeline configuration from settings.json (the single source of truth).

    Hot-reload: check_reload() compares file mtime and reloads if changed.
    Falls back to built-in defaults for missing keys.
    """

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            candidates = [
                Path.cwd() / "settings.json",
                Path(__file__).parent.parent / "settings.json",
            ]
            for c in candidates:
                if c.exists():
                    config_path = str(c)
                    break
        self._config_path = Path(config_path) if config_path else None
        self._config: dict = {}
        self._mtime: float = 0
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load config from settings.json, applying defaults for missing keys."""
        with self._lock:
            self._config = dict(_DEFAULTS)
            if self._config_path and self._config_path.exists():
                mtime = os.path.getmtime(self._config_path)
                self._mtime = mtime
                with open(self._config_path, encoding="utf-8") as f:
                    user = _json.load(f) or {}
                deep_merge(self._config, user)
            # Prompts always come from settings.json (may be empty dict = use defaults)
            if "prompts" not in self._config:
                self._config["prompts"] = {}

    def check_reload(self) -> bool:
        """Check if file changed; reload if so. Returns True if reloaded."""
        if self._config_path and self._config_path.exists():
            mtime = os.path.getmtime(self._config_path)
            if mtime != self._mtime:
                self._load()
                return True
        return False

    def reload(self) -> None:
        """Force reload from disk."""
        self._load()

    def get(self, *keys, default=None) -> Any:
        """Get a nested config value, e.g. get("prompts", "file_filter_system")."""
        with self._lock:
            val = self._config
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    return default
                if val is None:
                    return default
            return val

    def get_prompt(self, name: str, **kwargs) -> str:
        """
        Get a prompt template with format kwargs applied.
        e.g. get_prompt("file_filter_system", project_name="foo")
        """
        with self._lock:
            prompt = self._config.get("prompts", {}).get(name, "")
            if prompt and kwargs:
                prompt = prompt.format(**kwargs)
            return prompt

    def get_all(self) -> dict:
        """Return a deep copy of the entire config."""
        with self._lock:
            return copy.deepcopy(self._config)

    def save_prompt(self, name: str, content: str) -> None:
        """Save a prompt template to settings.json."""
        with self._lock:
            if "prompts" not in self._config:
                self._config["prompts"] = {}
            self._config["prompts"][name] = content
        if self._config_path:
            with open(self._config_path, "w", encoding="utf-8") as f:
                _json.dump(self._config, f, ensure_ascii=False, indent=2)

    def save_setting(self, key: str, value: Any) -> None:
        """Save a top-level setting to settings.json."""
        with self._lock:
            self._config[key] = value
        if self._config_path:
            with open(self._config_path, "w", encoding="utf-8") as f:
                _json.dump(self._config, f, ensure_ascii=False, indent=2)

    @property
    def server_url(self) -> str:
        return self.get("server_url", default="http://localhost:7890")

    @property
    def model_lite(self) -> str:
        return self.get("lite_model", default="deepseek-chat")

    @property
    def model_pro(self) -> str:
        return self.get("pro_model", default="deepseek-chat")

    @property
    def model_max(self) -> str:
        return self.get("max_model", default="deepseek-reasoner")

    @property
    def provider(self) -> str:
        return self.get("provider", default="anthropic")


def deep_merge(base: dict, overlay: dict) -> None:
    """Recursively merge overlay into base (in-place)."""
    for k, v in overlay.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            deep_merge(base[k], v)
        else:
            base[k] = v


# Global singleton
_config_manager: ConfigManager | None = None
_config_lock = threading.Lock()


def get_config_manager() -> ConfigManager:
    global _config_manager
    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigManager()
        return _config_manager
