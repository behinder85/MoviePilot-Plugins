# -*- coding: utf-8 -*-
"""CrossSeed辅种路径回迁（CrossSeedRelocator）。

把 cross-seed 注入到链接目录的辅种，在 Transmission 中的保存路径回迁到原始下载路径，
去掉 cross-seed 标签并清理链接目录；同时支持定期清理链接目录中未做种的文件。
"""
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType

from .engine.config import DEFAULT_CONFIG, normalize_config
from .engine.journal import Journal
from .engine.logbook import LogBook
from .engine.runner import Runner
from .engine.tr import client_from_config
from .engine.util import human_size, now_text

PLUGIN_ID = "CrossSeedRelocator"


class CrossSeedRelocator(_PluginBase):
    # 插件元数据
    plugin_name = "CrossSeed辅种路径回迁"
    plugin_desc = "把 cross-seed 注入的辅种在 Transmission 中的保存路径回迁到原始下载路径，清理链接目录与未做种文件。"
    plugin_icon = "https://raw.githubusercontent.com/behinder85/MoviePilot-Plugins/main/icons/crossseed_relocator.svg"
    plugin_version = "1.1.1"
    plugin_author = "zjuzxj"
    author_url = ""
    plugin_config_prefix = "crossseedrelocator_"
    plugin_order = 26
    auth_level = 2

    def __init__(self):
        super().__init__()
        self._enabled = False
        self._conf = normalize_config({})
        self._lock = threading.RLock()
        self._thread = None
        self._progress = {"kind": "", "running": False, "message": ""}
        self._last_result = None
        self._data_dir = None
        self._logbook = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def init_plugin(self, config: dict = None):
        self._conf = normalize_config(config or {})
        self._enabled = bool(self._conf.get("enabled"))
        self._data_dir = str(self.get_data_path())
        os.makedirs(self._data_dir, exist_ok=True)
        self._logbook = LogBook(os.path.join(self._data_dir, "relocator.log"))
        self._logbook.info(
            "插件初始化：enabled=%s mode=%s cs_root=%s cron=%s"
            % (self._enabled, self._conf.get("apply_mode"), self._conf.get("cs_root"), self._conf.get("cron"))
        )
        logger.info(
            "【CrossSeedRelocator】初始化完成：enabled=%s mode=%s"
            % (self._enabled, self._conf.get("apply_mode"))
        )

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        # MP 会把 remoteEntry 拼成 /plugin/file/<pid>/<dist_path>/remoteEntry.js
        return "vue", "frontend/dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        return None, DEFAULT_CONFIG

    def get_page(self) -> Optional[List[dict]]:
        return None

    def get_sidebar_nav(self) -> List[dict]:
        return [
            {
                "nav_key": "main",
                "title": "辅种路径回迁",
                "icon": "mdi-swap-horizontal-bold",
                "section": "system",
                "permission": "admin",
                "order": 26,
            }
        ]

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        return [{"key": "main", "name": "辅种路径回迁"}]

    def get_dashboard(self, key: str = "main", **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], Optional[List[dict]]]]:
        journal = self._journal()
        last_run = journal.last_run() or {}
        entries = journal.entries() or {}
        success = len([1 for item in entries.values() if item.get("status") == "success"])
        no_source = len(journal.data().get("no_source") or {})
        col_config = {"cols": 12, "md": 6}
        global_config = {
            "refresh": 60,
            "border": True,
            "title": "CrossSeed辅种路径回迁",
            "subtitle": "已回迁 %d 个 / 无源 %d 个" % (success, no_source),
        }
        return col_config, global_config, None

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        config = self._conf or {}
        cron = config.get("cron") or DEFAULT_CONFIG["cron"]
        trigger = "cron"
        try:
            from apscheduler.triggers.cron import CronTrigger

            trigger = CronTrigger.from_crontab(cron)
        except Exception as err:  # noqa: BLE001
            logger.warning("【CrossSeedRelocator】cron 表达式无效：%s（%s），已跳过定时任务注册" % (cron, err))
            return []
        return [
            {
                "id": PLUGIN_ID,
                "name": "CrossSeed辅种路径回迁定时任务",
                "trigger": trigger,
                "func": self.run_scheduled,
                "kwargs": {},
            }
        ]

    def stop_service(self):
        self._progress = {"kind": "", "running": False, "message": "插件已停止"}

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _journal(self) -> Journal:
        data_dir = self._data_dir or str(self.get_data_path())
        return Journal(os.path.join(data_dir, "journal.json"))

    def _logbook_or_new(self) -> LogBook:
        if self._logbook is None:
            data_dir = self._data_dir or str(self.get_data_path())
            os.makedirs(data_dir, exist_ok=True)
            self._logbook = LogBook(os.path.join(data_dir, "relocator.log"))
        return self._logbook

    def _runner(self) -> Runner:
        data_dir = self._data_dir or str(self.get_data_path())
        return Runner(self._conf, data_dir, self._logbook_or_new())

    def _config_for_ui(self) -> Dict[str, Any]:
        conf = dict(self._conf)
        conf["_cs_root_exists"] = bool(conf.get("cs_root")) and os.path.isdir(conf.get("cs_root"))
        return conf

    def _start_job(self, kind: str, worker) -> Dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return {"ok": False, "message": "已有任务正在执行，请等待完成后再试"}
            self._progress = {"kind": kind, "running": True, "message": "任务启动中", "started_at": now_text()}
            self._last_result = None

            def _wrap():
                try:
                    result = worker()
                    self._last_result = result
                    self._progress = {
                        "kind": kind,
                        "running": False,
                        "finished": True,
                        "message": "任务完成",
                        "finished_at": now_text(),
                    }
                    try:
                        self._notify(result)
                    except Exception as err:  # noqa: BLE001
                        logger.error("【CrossSeedRelocator】发送通知失败：%s" % err)
                except Exception as err:  # noqa: BLE001
                    logger.error("【CrossSeedRelocator】%s 任务异常：%s" % (kind, err))
                    self._progress = {
                        "kind": kind,
                        "running": False,
                        "finished": True,
                        "message": "任务异常：%s" % err,
                        "finished_at": now_text(),
                    }

            thread = threading.Thread(target=_wrap, name="CrossSeedRelocator-%s" % kind, daemon=True)
            self._thread = thread
            thread.start()
        return {"ok": True, "message": "任务已启动"}

    def _notify(self, result: Dict[str, Any]):
        if not isinstance(result, dict):
            return
        moved = result.get("moved") or []
        failed = result.get("failed") or []
        cleanup = result.get("cleanup") or {}
        is_rollback = result.get("mode") == "rollback"
        ok_flag = self._conf.get("notify_rollback") if is_rollback else self._conf.get("notify_success")
        fail_flag = self._conf.get("notify_rollback") if is_rollback else self._conf.get("notify_failure")
        lines = []
        if moved and ok_flag:
            lines.append("【%s成功 %d 个】" % ("回滚" if is_rollback else "回迁", len(moved)))
            for item in moved[:10]:
                if is_rollback:
                    lines.append("· %s" % item.get("name"))
                else:
                    lines.append("· %s（清理旧文件 %s 个）" % (item.get("name"), item.get("removed_files", 0)))
            if len(moved) > 10:
                lines.append("· …… 其余 %d 个" % (len(moved) - 10))
        if failed and fail_flag:
            lines.append("【失败/异常 %d 个】" % len(failed))
            for item in failed[:10]:
                lines.append("· %s：%s" % (item.get("name"), item.get("reason")))
            if len(failed) > 10:
                lines.append("· …… 其余 %d 个" % (len(failed) - 10))
        if cleanup and not cleanup.get("dry_run") and cleanup.get("deleted_files"):
            lines.append(
                "【清理链接目录】删除 %s 个文件（%s），移除空目录 %s 个"
                % (cleanup.get("deleted_files"), cleanup.get("deleted_human"), cleanup.get("removed_dirs"))
            )
        if lines:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="CrossSeed辅种路径回迁",
                text="\n".join(lines),
            )

    def _plan_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        items = result.get("items") or []
        return {
            "mode": result.get("mode"),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "elapsed_sec": result.get("elapsed_sec"),
            "torrent_client": result.get("torrent_client"),
            "error": result.get("error"),
            "stats": result.get("stats") or {},
            "items": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "size": item.get("size"),
                    "size_text": human_size(item.get("size")),
                    "current_dir": item.get("current_dir"),
                    "target_dir": item.get("target_dir"),
                    "source_id": item.get("source_id"),
                    "source_name": item.get("source_name"),
                    "candidate_count": item.get("candidate_count"),
                    "labels": item.get("labels"),
                    "status": item.get("status"),
                    "reason": item.get("reason"),
                }
                for item in items
            ],
        }

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "summary": "获取插件状态",
            },
            {
                "path": "/preview",
                "endpoint": self.api_preview,
                "methods": ["POST"],
                "summary": "预演：只推断目标路径，不写任何数据",
            },
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "summary": "执行回迁（可指定是否同时清理）",
            },
            {
                "path": "/rollback",
                "endpoint": self.api_rollback,
                "methods": ["POST"],
                "summary": "回滚已回迁的种子",
            },
            {
                "path": "/journal",
                "endpoint": self.api_journal,
                "methods": ["GET"],
                "summary": "获取处理记录",
            },
            {
                "path": "/logs",
                "endpoint": self.api_logs,
                "methods": ["GET"],
                "summary": "获取插件日志",
            },
            {
                "path": "/cleanup_preview",
                "endpoint": self.api_cleanup_preview,
                "methods": ["POST"],
                "summary": "预演清理链接目录",
            },
            {
                "path": "/cleanup_run",
                "endpoint": self.api_cleanup_run,
                "methods": ["POST"],
                "summary": "执行清理链接目录",
            },
            {
                "path": "/test",
                "endpoint": self.api_test,
                "methods": ["POST"],
                "summary": "测试 Transmission 连接",
            },
            {
                "path": "/downloaders",
                "endpoint": self.api_downloaders,
                "methods": ["GET"],
                "summary": "列出 MoviePilot 已配置的下载器",
            },
        ]

    def api_status(self) -> Dict[str, Any]:
        journal = self._journal()
        data = journal.data()
        entries = data.get("entries") or {}
        success_items = [item for item in entries.values() if item.get("status") == "success"]
        last_result = self._last_result or {}
        return {
            "enabled": self._enabled,
            "running": bool(self._progress.get("running")),
            "progress": self._progress,
            "config": self._config_for_ui(),
            "last_run": data.get("last_run") or {},
            "running_count": len([1 for item in entries.values() if item.get("status") == "relocating"]),
            "success_count": len(success_items),
            "failed_count": len([1 for item in entries.values() if item.get("status") == "failed"]),
            "no_source_count": len(data.get("no_source") or {}),
            "stats": (last_result.get("stats") or (data.get("last_run") or {}).get("stats") or {}),
            "last_result": last_result or None,
            "plan_items": self._plan_summary(last_result).get("items") if last_result else [],
        }

    def api_preview(self, payload: dict = None) -> Dict[str, Any]:
        result = self._runner().run(mode="preview")
        # 记住最近一次结果，供 status / 刷新页面时复用
        self._last_result = result
        summary = self._plan_summary(result)
        summary["dry_run"] = True
        return summary

    def api_run(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        mode = str(payload.get("mode") or "preview")
        if mode not in ("preview", "apply"):
            return {"ok": False, "message": "mode 只能是 preview 或 apply"}
        do_cleanup = bool(payload.get("cleanup"))
        if mode == "preview" and not payload.get("force_preview"):
            # 预览走同步接口，方便直接看结果
            return self.api_preview(payload)

        def _work():
            return self._runner().run(mode="apply", do_cleanup=do_cleanup)

        return self._start_job("apply", _work)

    def api_rollback(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        ids = payload.get("ids") or []
        rollback_all = bool(payload.get("all"))

        def _work():
            from .engine.relocator import Relocator

            runner = self._runner()
            client_conf, client = client_from_config(self._conf)
            journal = runner.journal
            entries = journal.entries()
            targets = []
            for tid, entry in entries.items():
                if entry.get("status") not in ("success", "relocating"):
                    continue
                if ids and int(tid) not in [int(x) for x in ids if str(x).isdigit()]:
                    continue
                if not ids and not rollback_all:
                    continue
                try:
                    target_id = int(tid)
                except (TypeError, ValueError):
                    target_id = entry.get("id") or tid
                targets.append((target_id, entry))
            relocator = Relocator(client, self._conf, journal, self._logbook_or_new())
            results = {"ok": [], "failed": []}
            for tid, entry in targets:
                outcome = relocator.rollback_entry(tid, entry)
                if outcome.get("ok"):
                    results["ok"].append(outcome)
                else:
                    results["failed"].append(outcome)
            return {
                "mode": "rollback",
                "torrent_client": client_conf.get("name"),
                "started_at": now_text(),
                "moved": results["ok"],
                "failed": results["failed"],
            }

        if not ids and not rollback_all:
            return {"ok": False, "message": "请提供要回滚的种子 id，或勾选回滚全部"}
        return self._start_job("rollback", _work)

    def api_journal(self, limit: int = 200) -> Dict[str, Any]:
        journal = self._journal()
        data = journal.data()
        entries = list((data.get("entries") or {}).values())
        entries.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return {
            "entries": entries[: max(1, min(int(limit or 200), 2000))],
            "runs": (data.get("runs") or [])[:20],
            "no_source": list((data.get("no_source") or {}).values()),
        }

    def api_logs(self, lines: int = 300) -> Dict[str, Any]:
        return {"lines": self._logbook_or_new().tail(lines)}

    def api_cleanup_preview(self, payload: dict = None) -> Dict[str, Any]:
        try:
            _conf, client = client_from_config(self._conf)
            torrents = client.torrent_get(
                ["id", "name", "downloadDir", "files", "percentDone", "status", "error"]
            )
            from .engine.cleanup import run_cleanup

            return run_cleanup(self._conf, torrents, dry_run=True, log=self._logbook_or_new())
        except Exception as err:  # noqa: BLE001
            return {"error": "预演清理失败：%s" % err}

    def api_cleanup_run(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        dry_run = bool(payload.get("dry_run", True))

        def _work():
            _conf, client = client_from_config(self._conf)
            torrents = client.torrent_get(
                ["id", "name", "downloadDir", "files", "percentDone", "status", "error"]
            )
            from .engine.cleanup import run_cleanup

            report = run_cleanup(self._conf, torrents, dry_run=dry_run, log=self._logbook_or_new())
            return {"mode": "cleanup", "cleanup": report, "moved": [], "failed": []}

        return self._start_job("cleanup", _work)

    def api_downloaders(self) -> Dict[str, Any]:
        """列出 MoviePilot 中已配置的下载器，供配置页下拉选择。"""
        items: List[Dict[str, Any]] = []
        source = ""
        try:
            from app.helper.service import ServiceConfigHelper  # type: ignore

            for conf in ServiceConfigHelper.get_downloader_configs():
                items.append(
                    {
                        "name": str(getattr(conf, "name", "") or ""),
                        "type": str(getattr(conf, "type", "") or ""),
                        "enabled": bool(getattr(conf, "enabled", False)),
                        "host": str(getattr(conf, "host", "") or ""),
                        "port": getattr(conf, "port", None),
                    }
                )
            source = "ServiceConfigHelper"
        except Exception as err:  # noqa: BLE001
            logger.warning("【CrossSeedRelocator】ServiceConfigHelper 读取下载器失败（%s），改用 DownloaderHelper" % err)
            try:
                from app.helper.downloader import DownloaderHelper  # type: ignore

                configs = DownloaderHelper().get_configs(include_disabled=True) or {}
                for name, conf in configs.items():
                    items.append(
                        {
                            "name": str(name or getattr(conf, "name", "") or ""),
                            "type": str(getattr(conf, "type", "") or ""),
                            "enabled": bool(getattr(conf, "enabled", True)),
                            "host": str(getattr(conf, "host", "") or ""),
                            "port": getattr(conf, "port", None),
                        }
                    )
                source = "DownloaderHelper"
            except Exception as err2:  # noqa: BLE001
                return {
                    "ok": False,
                    "items": [],
                    "message": "读取下载器配置失败：%s" % err2,
                }
        items = [item for item in items if item.get("name")]
        items.sort(
            key=lambda item: (
                item.get("type") != "transmission",
                not item.get("enabled"),
                str(item.get("name") or ""),
            )
        )
        suggested = ""
        for item in items:
            if item.get("type") == "transmission" and item.get("enabled"):
                suggested = item["name"]
                break
        return {"ok": True, "items": items, "suggested": suggested, "source": source}

    def api_test(self) -> Dict[str, Any]:
        try:
            conf, client = client_from_config(self._conf)
            info = client.test()
            return {"ok": True, "client": conf.get("name"), "info": info}
        except Exception as err:  # noqa: BLE001
            return {"ok": False, "message": str(err)}

    # ------------------------------------------------------------------
    # 定时任务
    # ------------------------------------------------------------------
    def run_scheduled(self):
        if not self._enabled:
            return
        mode = self._conf.get("apply_mode") or "preview"
        do_cleanup = bool(self._conf.get("cleanup_enabled"))
        if mode != "apply":
            self._logbook_or_new().info("定时任务处于预览模式，本轮只推断不执行")
        result = self._runner().run(mode=mode, do_cleanup=do_cleanup)
        self._last_result = result
        self._notify(result)