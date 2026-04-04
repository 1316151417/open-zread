import json

DEBUG = True


class Logger:
    @staticmethod
    def debug(msg: str, **kwargs):
        if not DEBUG:
            return

        print(f"[DEBUG] {msg}")
        for key, value in kwargs.items():
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
