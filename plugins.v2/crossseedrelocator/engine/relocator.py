# -*- coding: utf-8 -*-
"""单个种子的回迁闭环：改保存路径 -> 等校验完成 -> 去标签 -> 清旧硬链。"""
import os
import posixpath
import time

from .infer import LABEL_CS
from .util import is_under, join_path, norm, now_text

POLL_SECONDS = 3


class Relocator:
    def __init__(self, client, cfg, journal, log=None):
        self.client = client
        self.cfg = cfg
        self.journal = journal
        self.log = log

    # ---- 基础设施 ----
    def _log(self, message, level="INFO"):
        if not self.log:
            return
        try:
            getattr(self.log, level.lower(), self.log.info)(message)
        except Exception:
            pass

    def _torrent(self, tid):
        rows = self.client.torrent_get(
            [
                "id",
                "name",
                "status",
                "percentDone",
                "error",
                "errorString",
                "labels",
                "downloadDir",
                "totalSize",
                "files",
            ],
            ids=[tid],
        )
        return rows[0] if rows else None

    def _wait_seed(self, tid, timeout_min, expect_dir=None):
        """等待「改路径 -> 校验完成 -> 做种」真正落地。

        注意：torrent-set-location 之后 TR 的状态可能短暂还是「做种」，
        必须确认 downloadDir 已变成目标路径，且观察到校验阶段（status 1/2）
        或至少过了 10 秒，才认账，避免把改路径前的旧状态误判为成功。
        """
        deadline = time.time() + max(1, timeout_min) * 60
        started = time.time()
        seed_hits = 0
        downloading_hits = 0
        saw_checking = False
        while time.time() < deadline:
            torrent = self._torrent(tid)
            if not torrent:
                return False, "种子在客户端中不存在"
            error = int(torrent.get("error") or 0)
            if error:
                return False, "客户端报错：%s" % (torrent.get("errorString") or error)
            status = int(torrent.get("status") or 0)
            pct = float(torrent.get("percentDone") or 0)
            if status in (1, 2):
                saw_checking = True
            dir_ok = True
            if expect_dir:
                dir_ok = norm(torrent.get("downloadDir") or "") == norm(expect_dir)
            if status in (5, 6) and pct >= 0.9999 and dir_ok and (saw_checking or time.time() - started > 10):
                seed_hits += 1
                downloading_hits = 0
                if seed_hits >= 2:
                    return True, ""
            elif status in (3, 4):
                seed_hits = 0
                downloading_hits += 1
                if pct < 0.99 and downloading_hits >= 2:
                    return False, "新路径下未找到完整文件，客户端开始重新下载"
            else:
                seed_hits = 0
            time.sleep(POLL_SECONDS)
        return False, "等待校验完成超时（%d 分钟）" % int(timeout_min)

    @staticmethod
    def _decrease(referenced, path):
        if referenced.get(path, 0) <= 1:
            referenced.pop(path, None)
        else:
            referenced[path] -= 1

    # ---- 旧硬链接清理 ----
    def _prune_dir(self, path):
        cs_root = norm(self.cfg.get("cs_root"))
        current = norm(path)
        while current and is_under(current, cs_root) and current != cs_root:
            try:
                os.rmdir(current)
            except OSError:
                break
            current = posixpath.dirname(current)

    def remove_old_links(self, old_dir, files, referenced):
        """删除链接目录里不再被任何种子引用的文件，并清理空目录。"""
        removed = 0
        for item in files or []:
            path = join_path(old_dir, item.get("name") or "")
            if referenced.get(path, 0) > 0:
                continue
            try:
                os.remove(path)
                removed += 1
            except OSError:
                continue
        dirs = set()
        for item in files or []:
            dirs.add(posixpath.dirname(join_path(old_dir, item.get("name") or "")))
        for path in sorted(dirs, key=len, reverse=True):
            self._prune_dir(path)
        return removed

    def _account(self, referenced, old_dir, new_dir, files):
        for item in files or []:
            self._decrease(referenced, join_path(old_dir, item.get("name") or ""))
            referenced[join_path(new_dir, item.get("name") or "")] += 1

    # ---- 加/去 cross-seed 标签 ----
    def ensure_label(self, item):
        labels = list(item.get("labels") or [])
        if LABEL_CS in labels:
            return False
        self.client.torrent_set([item["id"]], labels=labels + [LABEL_CS])
        return True

    def _remove_label(self, tid, labels_before):
        labels = [label for label in (labels_before or []) if label != LABEL_CS]
        if len(labels) != len(labels_before or []):
            self.client.torrent_set([tid], labels=labels)
        return labels

    # ---- 单个种子回迁 ----
    def relocate(self, item, referenced):
        tid = item["id"]
        old_dir = norm(item["current_dir"])
        new_dir = norm(item["target_dir"])
        timeout_min = int(self.cfg.get("single_timeout_min") or 30)
        torrent = self._torrent(tid)
        labels_before = list((torrent or {}).get("labels") or item.get("labels") or [])
        record = {
            "id": tid,
            "name": item["name"],
            "hash": item.get("hash"),
            "size": item.get("size"),
            "status": "relocating",
            "old_dir": old_dir,
            "new_dir": new_dir,
            "labels_before": labels_before,
            "source_id": item.get("source_id"),
            "updated_at": now_text(),
        }
        self.journal.update_entry(tid, record)
        self._log("开始回迁 id=%s name=%s -> %s" % (tid, item["name"], new_dir))
        try:
            self.client.stop([tid])
            self.client.set_location([tid], new_dir, move=False)
            self.client.start([tid])
            ok, detail = self._wait_seed(tid, timeout_min, expect_dir=new_dir)
        except Exception as err:  # noqa: BLE001
            ok, detail = False, "RPC 异常：%s" % err
        if not ok:
            rollback_detail = ""
            try:
                self.client.stop([tid])
                self.client.set_location([tid], old_dir, move=False)
                self.client.start([tid])
                self._wait_seed(tid, timeout_min, expect_dir=old_dir)
            except Exception as err:  # noqa: BLE001
                rollback_detail = str(err)
            self.journal.update_entry(
                tid,
                {
                    "status": "failed",
                    "reason": detail,
                    "rollback_error": rollback_detail,
                    "updated_at": now_text(),
                },
            )
            self._log("回迁失败 id=%s：%s（已退回原路径）" % (tid, detail), "WARN")
            return {"ok": False, "id": tid, "name": item["name"], "reason": detail}

        labels_after = self._remove_label(tid, labels_before)
        removed = 0
        try:
            removed = self.remove_old_links(old_dir, (torrent or {}).get("files"), referenced)
            self._account(referenced, old_dir, new_dir, (torrent or {}).get("files"))
        except Exception as err:  # noqa: BLE001
            self._log("清理旧链接失败 id=%s：%s" % (tid, err), "WARN")
        self.journal.update_entry(
            tid,
            {
                "status": "success",
                "reason": "",
                "labels_after": labels_after,
                "removed_files": removed,
                "finished_at": now_text(),
                "updated_at": now_text(),
            },
        )
        self._log("回迁成功 id=%s 新路径=%s 清理旧文件=%d" % (tid, new_dir, removed))
        return {"ok": True, "id": tid, "name": item["name"], "removed_files": removed}

    # ---- 回滚 ----
    def rollback_entry(self, tid, entry):
        old_dir = norm(entry.get("old_dir"))
        if not old_dir:
            return {"ok": False, "id": tid, "reason": "没有记录原路径，无法回滚"}
        timeout_min = int(self.cfg.get("single_timeout_min") or 30)
        torrent = self._torrent(tid)
        if not torrent:
            return {"ok": False, "id": tid, "reason": "种子在客户端中不存在"}
        current_dir = norm(torrent.get("downloadDir"))
        if current_dir == old_dir:
            return {"ok": True, "id": tid, "reason": "已经位于原路径"}
        try:
            self.client.stop([tid])
            self.client.set_location([tid], old_dir, move=False)
            self.client.start([tid])
            ok, detail = self._wait_seed(tid, timeout_min, expect_dir=old_dir)
        except Exception as err:  # noqa: BLE001
            return {"ok": False, "id": tid, "reason": "RPC 异常：%s" % err}
        if not ok:
            self.journal.update_entry(tid, {"status": "failed", "reason": "回滚失败：" + detail, "updated_at": now_text()})
            return {"ok": False, "id": tid, "reason": detail}
        labels = list(entry.get("labels_before") or [])
        try:
            self.client.torrent_set([tid], labels=labels)
        except Exception:  # noqa: BLE001
            pass
        self.journal.update_entry(tid, {"status": "rolled_back", "updated_at": now_text(), "rolled_back_at": now_text()})
        self._log("已回滚 id=%s -> %s" % (tid, old_dir), "WARN")
        return {"ok": True, "id": tid}
