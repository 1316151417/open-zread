DEBUG = True


class Logger:
    @staticmethod
    def debug(msg: str, **kwargs):
        if DEBUG:
            if kwargs:
                parts = [f"{k}={v}" for k, v in kwargs.items()]
                print("[DEBUG]", msg, " ".join(parts))
            else:
                print("[DEBUG]", msg)


logger = Logger()
