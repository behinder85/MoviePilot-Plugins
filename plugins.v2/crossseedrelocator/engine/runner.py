# -*- coding: utf-8 -*-
"""一轮完整运行的编排：快照 -> 推断 -> 回迁 -> 清理。"""
import time
from collections import Counter

from .cleanup import run_cleanup
from .infer import BRIEF_FIELDS, TARGET_FIELDS, build_plan_phased
from .journal import Journal
from .relocator import Relocator
from .tr import client_from_config
from .util import is_under, join_path, now_text


class Runner:
    def __init__(self, cfg, data_dir, log=None):
        self.cfg = cfg
        self.data_dir = data_dir
        self.log = log
        self.journal = Journal(_path(data_dir, "journal.json"))

    def _log(self, message, level="INFO"):
        if not self.log:
            return
        try:
            getattr(self.log, level.lower(), self.log.info)(message)
        except Exception:
            pass

    def run(self, mode="preview", do_cleanup=False):
        """mode=preview 只推断不写；mode=apply 真正回迁。"""
        started = time.time()
        result = {
            "mode": mode,
            "started_at": now_text(),
            "finished_at": "",
            "elapsed_sec": 0,
            "torrent_client": "",
            "stats": {},
            "items": [],
            "moved": [],
            "failed": [],
            "skipped": [],
            "labeled": [],
            "no_source": [],
            "cleanup": None,
            "error": "",
        }
        try:
            client_conf, client = client_from_config(self.cfg)
            result["torrent_client"] = client_conf.get("name")
            brief = client.torrent_get(BRIEF_FIELDS)
            plan = build_plan_phased(client, self.cfg, self.journal, brief=brief)
        except Exception as err:  # noqa: BLE001
            result["error"] = "连接下载器或读取种子失败：%s" % err
            result["finished_at"] = now_text()
            result["elapsed_sec"] = int(time.time() - started)
            self._log(result["error"], "ERROR")
            return result

        result["stats"] = dict(plan.get("stats") or {})
        result["items"] = plan.get("items") or []
        self._log(
            "快照完成：共 %d 个种子，链接目录内待回迁 %d 个（可回迁 %d、无源 %d、等待校验 %d），文件系统校验=%s"
            % (
                result["stats"].get("torrents", 0),
                result["stats"].get("targets", 0),
                result["stats"].get("ready", 0),
                result["stats"].get("no_source", 0),
                result["stats"].get("waiting", 0),
                "开" if plan.get("fs_checked") else "关",
            )
        )

        if mode != "apply":
            result["finished_at"] = now_text()
            result["elapsed_sec"] = int(time.time() - started)
            return result

        relocator = Relocator(client, self.cfg, self.journal, self.log)
        # 引用计数只需要「downloadDir 位于链接目录内」的种子：目录外的种子不可能引用链接目录里的文件。
        cs_root = self.cfg.get("cs_root") or ""
        cs_ids = [
            torrent.get("id")
            for torrent in brief
            if cs_root and is_under(torrent.get("downloadDir") or "", cs_root)
        ]
        references = Counter()
        for start in range(0, len(cs_ids), 200):
            rows = client.torrent_get(["id", "files"], ids=cs_ids[start:start + 200])
            for row in rows:
                dl = row.get("downloadDir") or ""
                # 逐条取文件时下载目录可能未返回，退回按 id 匹配简表
                if not dl:
                    for torrent in brief:
                        if torrent.get("id") == row.get("id"):
                            dl = torrent.get("downloadDir") or ""
                            break
                for item in row.get("files") or []:
                    references[join_path(dl, item.get("name") or "")] += 1

        ready = [item for item in result["items"] if item["status"] == "ready"]
        no_source_items = [item for item in result["items"] if item["status"] == "no_source"]

        cap_count = int(self.cfg.get("cap_count") or 0)
        cap_size = int(self.cfg.get("cap_size_gb") or 0) * 1024 ** 3
        cap_minutes = int(self.cfg.get("cap_minutes") or 0)
        deadline = started + cap_minutes * 60 if cap_minutes else None
        used_count = 0
        used_size = 0

        for item in ready:
            if cap_count and used_count >= cap_count:
                result["skipped"].append(_skip(item, "达到单轮数量上限"))
                continue
            if cap_size and used_size + int(item.get("size") or 0) > cap_size:
                result["skipped"].append(_skip(item, "达到单轮体积上限"))
                continue
            if deadline and time.time() > deadline:
                result["skipped"].append(_skip(item, "达到单轮时长上限"))
                continue
            outcome = relocator.relocate(item, references)
            if outcome.get("ok"):
                result["moved"].append(outcome)
                used_count += 1
                used_size += int(item.get("size") or 0)
            else:
                result["failed"].append(outcome)

        # 无源项：保留 cross-seed 标签作为「CS 专属数据」标记
        if self.cfg.get("keep_label_on_no_source"):
            for item in no_source_items:
                try:
                    if relocator.ensure_label(item):
                        result["labeled"].append({"id": item["id"], "name": item["name"]})
                except Exception as err:  # noqa: BLE001
                    result["failed"].append({"id": item["id"], "name": item["name"], "reason": "加标签失败：%s" % err})
        result["no_source"] = [
            {
                "id": item["id"],
                "name": item["name"],
                "size": item["size"],
                "dir": item["current_dir"],
                "reason": item["reason"],
            }
            for item in no_source_items
        ]

        if do_cleanup and self.cfg.get("cleanup_enabled"):
            try:
                latest = client.torrent_get(TARGET_FIELDS)
                result["cleanup"] = run_cleanup(
                    self.cfg,
                    latest,
                    dry_run=bool(self.cfg.get("cleanup_dry_run", True)),
                    log=self.log,
                )
            except Exception as err:  # noqa: BLE001
                result["cleanup"] = {"error": "清理失败：%s" % err}

        result["finished_at"] = now_text()
        result["elapsed_sec"] = int(time.time() - started)
        self.journal.add_run(self._compact(result))
        return result

    @staticmethod
    def _compact(result):
        """写入 journal 的精简运行记录（不含完整 items，避免文件膨胀）。"""
        cleanup = result.get("cleanup") or {}
        return {
            "mode": result.get("mode"),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "elapsed_sec": result.get("elapsed_sec"),
            "torrent_client": result.get("torrent_client"),
            "stats": result.get("stats"),
            "moved": result.get("moved"),
            "failed": result.get("failed"),
            "skipped_count": len(result.get("skipped") or []),
            "labeled": result.get("labeled"),
            "no_source": result.get("no_source"),
            "cleanup": {
                key: cleanup.get(key)
                for key in (
                    "dry_run",
                    "scanned_files",
                    "deletable_files",
                    "deletable_human",
                    "deleted_files",
                    "deleted_human",
                    "removed_dirs",
                    "errors",
                )
                if key in cleanup
            }
            if cleanup
            else None,
        }


def _skip(item, reason):
    return {"id": item.get("id"), "name": item.get("name"), "reason": reason}


def _path(data_dir, name):
    import os

    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, name)
