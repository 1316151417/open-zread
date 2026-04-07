"""
Logger - formatted debug output for development.
"""
import json
import logging
import os

# Configure logger based on DEBUG environment variable
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.WARNING,
    format="%(message)s",
)
_logger = logging.getLogger("codedeepresearch")


class Logger:
    """Simple debug logger that prints formatted output when DEBUG is enabled."""

    def debug(self, msg: str, start: str = "", end: str = "\n", flush: bool = False, **kwargs):
        if not DEBUG:
            return
        print(f"{start}{msg}", end=end, flush=flush)
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "messages":
                print(f"  {key}:")
                for i, m in enumerate(value):
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    content_preview = content[:60] + "..." if len(content) > 60 else content
                    print(f"    [{i}] {role}: {content_preview}")
            elif key == "tools":
                print(f"  {key}:")
                for i, t in enumerate(value):
                    if hasattr(t, "name"):
                        print(f"    [{i}] {t.name}")
                        desc_line = t.description.split('\n')[0] if t.description else ""
                        print(f"        description: {desc_line}")
                        if t.parameters:
                            print(f"        parameters:")
                            for param_name, param in t.parameters.items():
                                print(f"          {param_name}: {param.description}")
                    else:
                        print(f"    [{i}] {t}")
            elif isinstance(value, str):
                preview = value[:100] + "..." if len(value) > 100 else value
                print(f"  {key}: {preview}")
            elif isinstance(value, (dict, list)):
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
                preview = formatted[:200] + "..." if len(formatted) > 200 else formatted
                print(f"  {key}: {preview}")
            else:
                print(f"  {key}: {value}")


logger = Logger()
