# -*- coding: utf-8 -*-
"""回迁日志（journal）：记录每个种子的处理状态，支持回滚与断点续跑。"""
import json
import os
import threading

JOURNAL_VERSION = 1
MAX_RUNS = 50


class Journal:
    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self._data = None
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.load()

    # ---- 基础读写 ----
    def load(self):
        with self._lock:
            data = None
            try:
                if os.path.exists(self.path):
                    with open(self.path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
            except (OSError, ValueError):
                data = None
            if not isinstance(data, dict):
                data = {}
            data.setdefault("version", JOURNAL_VERSION)
            data.setdefault("entries", {})
            data.setdefault("runs", [])
            data.setdefault("no_source", {})
            data.setdefault("last_run", {})
            self._data = data
            return data

    def save(self):
        with self._lock:
            data = self._data or {}
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def data(self):
        with self._lock:
            return json.loads(json.dumps(self._data or {}, ensure_ascii=False))

    # ---- 条目 ----
    def entries(self):
        with self._lock:
            return dict((self._data or {}).get("entries") or {})

    def entry(self, tid):
        return self.entries().get(str(tid)) or {}

    def update_entry(self, tid, fields):
        with self._lock:
            entries = self._data.setdefault("entries", {})
            key = str(tid)
            item = entries.get(key) or {}
            item.update(fields or {})
            item["id"] = int(tid) if str(tid).isdigit() else tid
            entries[key] = item
            self.save()
            return item

    def set_no_source(self, tid, info):
        with self._lock:
            bucket = self._data.setdefault("no_source", {})
            bucket[str(tid)] = info or {}
            self.save()

    def drop_no_source(self, tid):
        with self._lock:
            bucket = self._data.setdefault("no_source", {})
            if str(tid) in bucket:
                bucket.pop(str(tid), None)
                self.save()

    # ---- 每轮运行 ----
    def add_run(self, run):
        with self._lock:
            runs = self._data.setdefault("runs", [])
            runs.insert(0, run)
            del runs[MAX_RUNS:]
            self._data["last_run"] = run
            self.save()

    def last_run(self):
        return self.data().get("last_run") or {}
