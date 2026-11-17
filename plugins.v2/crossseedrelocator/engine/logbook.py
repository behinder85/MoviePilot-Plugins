# -*- coding: utf-8 -*-
"""插件自带日志文件（供 UI 查看，按大小滚动）。"""
import os
import threading
import time


class LogBook:
    def __init__(self, path, max_bytes=2 * 1024 * 1024):
        self.path = path
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def write(self, message, level="INFO"):
        line = "%s [%s] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            level,
            str(message).replace("\n", " "),
        )
        with self._lock:
            try:
                if os.path.exists(self.path) and os.path.getsize(self.path) > self.max_bytes:
                    backup = self.path + ".1"
                    try:
                        if os.path.exists(backup):
                            os.remove(backup)
                        os.replace(self.path, backup)
                    except OSError:
                        pass
                with open(self.path, "a", encoding="utf-8") as fp:
                    fp.write(line)
            except OSError:
                pass

    def info(self, message):
        self.write(message, "INFO")

    def warn(self, message):
        self.write(message, "WARN")

    def error(self, message):
        self.write(message, "ERROR")

    def tail(self, lines=200):
        try:
            if not os.path.exists(self.path):
                return []
            with open(self.path, "r", encoding="utf-8", errors="replace") as fp:
                content = fp.readlines()
            return [line.rstrip("\n") for line in content[-max(1, min(int(lines), 2000)):]]
        except OSError:
            return []
