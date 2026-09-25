"""HDHive / Dian115 每日签到插件。

只保留上游 MoviePilot-Plugins 中的 HDHive 和 Dian115 签到能力，
删除网盘、订阅、搜索、转存等冗余模块。
"""

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

from .checkin_service import HDHiveDian115CheckinService
from .search.hdhive import HDHiveOpenAPIClient, HDHiveOpenAPIError


class HDHiveDian115Checkin(_PluginBase):
    """HDHive / Dian115 签到插件。"""

    plugin_name = "HDHive / Dian115 签到"
    plugin_desc = "仅保留 HDHive 与 Dian115 两个渠道的每日签到、转盘和通知功能。"
    plugin_icon = "https://raw.githubusercontent.com/behinder85/MoviePilot-Plugins/main/icons/hdhivedian115checkin.png"
    plugin_version = "1.0.12"
    plugin_author = "odomu"
    author_url = "https://github.com/odomu/MoviePilot-Plugins"
    plugin_config_prefix = "hdhive_dian115_checkin_"
    plugin_order = 1
    auth_level = 1

    _scheduler: Optional[BackgroundScheduler] = None
    _stop_event: Optional[threading.Event] = None

    _enabled: bool = True
    _onlyonce_hdhive: bool = False
    _onlyonce_dian115: bool = False
    _checkin_cron: str = "0 8 * * *"
    _checkin_notify: bool = True
    _notification_type: NotificationType = NotificationType.Plugin
    _proxy: str = ""

    _hdhive_checkin_enabled: bool = False
    _hdhive_query_mode: str = "web"
    _hdhive_username: str = ""
    _hdhive_password: str = ""
    _hdhive_base_url: str = "https://re0.me"
    _hdhive_checkin_mode: str = "normal"
    _hdhive_request_interval: float = 5.0
    _hdhive_api_key: str = ""
    _hdhive_client_id: str = ""
    _hdhive_redirect_uri: str = ""
    _hdhive_response_mode: str = "redirect"
    _hdhive_auth_code: str = ""
    _hdhive_access_token: str = ""
    _hdhive_refresh_token: str = ""
    _hdhive_token_expires_at: float = 0

    _dian115_checkin_enabled: bool = False
    _dian115_email: str = ""
    _dian115_password: str = ""
    _dian115_base_url: str = "https://m.dian115.com"
    _dian115_checkin_mode: str = "normal"
    _dian115_request_interval: float = 1.0
    _dian115_lottery_enabled: bool = False
    _dian115_lottery_count: int = 1

    def init_plugin(self, config: dict = None):
        self.stop_service()
        self._stop_event = threading.Event()
        self._apply_config(config or {})
        self._checkin_service = HDHiveDian115CheckinService(self)

        data_path = Path(self.get_data_path())
        data_path.mkdir(parents=True, exist_ok=True)

        if self._hdhive_query_mode == "api":
            self._init_hdhive_openapi_client()

        self._setup_scheduler()
        self._schedule_once()

    def _apply_config(self, config: Dict[str, Any]) -> None:
        self._enabled = bool(config.get("enabled", True))
        self._onlyonce_hdhive = bool(config.get("onlyonce_hdhive", False))
        self._onlyonce_dian115 = bool(config.get("onlyonce_dian115", False))
        self._checkin_cron = str(
            config.get("checkin_cron", "0 8 * * *") or "0 8 * * *"
        ).strip()
        self._checkin_notify = bool(config.get("checkin_notify", True))
        self._notification_type = self._resolve_notification_type(
            config.get("notification_type", NotificationType.Plugin.name)
        )
        self._proxy = str(config.get("proxy", "") or "").strip()

        self._hdhive_checkin_enabled = bool(
            config.get("hdhive_checkin_enabled", False)
        )
        self._hdhive_query_mode = str(
            config.get("hdhive_query_mode", "web") or "web"
        ).strip().lower()
        if self._hdhive_query_mode not in {"web", "api"}:
            self._hdhive_query_mode = "web"
        self._hdhive_username = str(
            config.get("hdhive_username", "") or ""
        ).strip()
        self._hdhive_password = str(config.get("hdhive_password", "") or "")
        self._hdhive_base_url = str(
            config.get("hdhive_base_url", "https://re0.me") or "https://re0.me"
        ).strip()
        self._hdhive_checkin_mode = str(
            config.get("hdhive_checkin_mode", "normal") or "normal"
        ).strip().lower()
        if self._hdhive_checkin_mode not in {"normal", "gambler"}:
            self._hdhive_checkin_mode = "normal"
        self._hdhive_request_interval = max(
            2.0,
            min(float(config.get("hdhive_request_interval", 5) or 5), 10.0),
        )
        self._hdhive_api_key = str(config.get("hdhive_api_key", "") or "")
        self._hdhive_client_id = str(config.get("hdhive_client_id", "") or "")
        self._hdhive_redirect_uri = str(
            config.get("hdhive_redirect_uri", "") or ""
        ).strip()
        self._hdhive_response_mode = str(
            config.get("hdhive_response_mode", "redirect") or "redirect"
        ).strip().lower()
        if self._hdhive_response_mode not in {"redirect", "postmessage"}:
            self._hdhive_response_mode = "redirect"
        self._hdhive_auth_code = str(config.get("hdhive_auth_code", "") or "")
        self._hdhive_access_token = str(
            config.get("hdhive_access_token", "") or ""
        ).strip()
        self._hdhive_refresh_token = str(
            config.get("hdhive_refresh_token", "") or ""
        ).strip()
        self._hdhive_token_expires_at = float(
            config.get("hdhive_token_expires_at", 0) or 0
        )

        self._dian115_checkin_enabled = bool(
            config.get("dian115_checkin_enabled", False)
        )
        self._dian115_email = str(config.get("dian115_email", "") or "").strip()
        self._dian115_password = str(config.get("dian115_password", "") or "")
        self._dian115_base_url = str(
            config.get("dian115_base_url", "https://m.dian115.com")
            or "https://m.dian115.com"
        ).strip()
        self._dian115_checkin_mode = str(
            config.get("dian115_checkin_mode", "normal") or "normal"
        ).strip().lower()
        if self._dian115_checkin_mode not in {"normal", "lucky"}:
            self._dian115_checkin_mode = "normal"
        self._dian115_request_interval = max(
            0.2,
            min(float(config.get("dian115_request_interval", 1) or 1), 10.0),
        )
        self._dian115_lottery_enabled = bool(
            config.get("dian115_lottery_enabled", False)
        )
        self._dian115_lottery_count = max(
            1, min(20, int(config.get("dian115_lottery_count", 1) or 1))
        )

    @staticmethod
    def _resolve_notification_type(value: Any) -> NotificationType:
        if isinstance(value, NotificationType):
            return value
        configured = str(value or NotificationType.Plugin.name).strip()
        if configured in NotificationType.__members__:
            return NotificationType[configured]
        for item in NotificationType:
            if item.value == configured:
                return item
        logger.warning(f"未知消息通知类型：{configured}，已回退为插件")
        return NotificationType.Plugin

    @staticmethod
    def _cron_is_valid(cron_expr: str) -> bool:
        cron_expr = (cron_expr or "").strip()
        if not cron_expr:
            return False
        try:
            CronTrigger.from_crontab(
                cron_expr, timezone=pytz.timezone(settings.TZ)
            )
            return True
        except Exception:
            return False

    def _setup_scheduler(self) -> None:
        if self._scheduler:
            try:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._scheduler = None

        if not self._enabled:
            return
        if not (self._hdhive_checkin_enabled or self._dian115_checkin_enabled):
            return
        if not self._cron_is_valid(self._checkin_cron):
            logger.warning(
                f"HDHive/Dian115 签到 cron 表达式无效：{self._checkin_cron}"
            )
            return

        self._scheduler = BackgroundScheduler(timezone=pytz.timezone(settings.TZ))
        self._scheduler.add_job(
            self._checkin_service.run_scheduled_checkins,
            trigger=CronTrigger.from_crontab(
                self._checkin_cron, timezone=pytz.timezone(settings.TZ)
            ),
            id="hdhive_dian115_checkin",
            name="HDHive / Dian115 每日签到",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            f"HDHive/Dian115 签到调度已启动：{self._checkin_cron}"
        )

    def _close_hdhive_openapi_client(self) -> None:
        """释放并清空 OpenAPI 客户端，切回 WebAPI 模式时调用。"""
        open_client = getattr(self, "_hdhive_open_client", None)
        if open_client:
            try:
                open_client.close()
            except Exception:
                pass
        self._hdhive_open_client = None

    def _init_hdhive_openapi_client(self) -> None:
        """仅在 OpenAPI 模式初始化，WebAPI 模式不读取也不校验 OpenAPI 配置。"""
        if self._hdhive_query_mode != "api":
            self._close_hdhive_openapi_client()
            return
        from .search.http_client import normalize_proxies

        self._hdhive_open_client = HDHiveOpenAPIClient(
            app_secret=self._hdhive_api_key,
            client_id=self._hdhive_client_id,
            access_token=self._hdhive_access_token,
            refresh_token=self._hdhive_refresh_token,
            token_expires_at=self._hdhive_token_expires_at,
            base_url=self._hdhive_base_url,
            proxy=normalize_proxies(self._proxy),
            request_interval=self._hdhive_request_interval,
            on_token_update=self._on_hdhive_token_update,
        )

        client = self._hdhive_open_client
        if not client.app_secret:
            if self._hdhive_checkin_enabled:
                logger.warning(
                    "HDHive OpenAPI: 缺少应用 Secret；Token 已加载但无法调用官方接口"
                )
            return

        if self._hdhive_auth_code and self._hdhive_redirect_uri:
            try:
                client.exchange_code(
                    self._hdhive_auth_code, self._hdhive_redirect_uri
                )
                self._hdhive_auth_code = ""
                self._persist_config_values(hdhive_auth_code="")
            except HDHiveOpenAPIError as error:
                logger.error(
                    f"HDHive OpenAPI: 授权码换取 Token 失败，授权码已保留: "
                    f"[{error.code}] {error.message} {error.description}"
                )
            except Exception as error:
                logger.error(
                    f"HDHive OpenAPI: 授权码换取 Token 异常，授权码已保留: {error}"
                )
        elif not client.access_token and client.refresh_token:
            try:
                client.refresh_access_token()
            except HDHiveOpenAPIError as error:
                logger.error(
                    f"HDHive OpenAPI: 使用 Refresh Token 获取 Access Token 失败: "
                    f"[{error.code}] {error.message} {error.description}"
                )

        if not client.is_ready and self._hdhive_client_id and self._hdhive_redirect_uri:
            try:
                authorize_url = client.build_authorize_url(
                    self._hdhive_redirect_uri,
                    response_mode=self._hdhive_response_mode,
                )
                logger.warning(
                    "HDHive OpenAPI: 尚未完成用户授权，请在浏览器打开以下链接完成授权，"
                    "然后将回调地址中的 code 参数填入插件配置的「授权码」并保存：\n"
                    f"{authorize_url}"
                )
            except HDHiveOpenAPIError as error:
                logger.warning(
                    f"HDHive OpenAPI: 生成授权链接失败: [{error.code}] {error.message}"
                )
        elif not client.is_ready:
            missing = []
            if not self._hdhive_client_id:
                missing.append("Client ID")
            if not self._hdhive_redirect_uri:
                missing.append("回调地址")
            if not client.access_token and not client.refresh_token:
                missing.append("Access/Refresh Token")
            logger.warning(
                "HDHive OpenAPI: 当前配置尚不能完成用户授权，缺少："
                f"{', '.join(missing)}"
            )

    def _on_hdhive_token_update(self, tokens: Dict[str, Any]) -> None:
        self._hdhive_access_token = str(
            tokens.get("access_token") or self._hdhive_access_token
        ).strip()
        self._hdhive_refresh_token = str(
            tokens.get("refresh_token") or self._hdhive_refresh_token
        ).strip()
        self._hdhive_token_expires_at = float(
            tokens.get("token_expires_at") or self._hdhive_token_expires_at or 0
        )
        self._persist_config_values(
            hdhive_access_token=self._hdhive_access_token,
            hdhive_refresh_token=self._hdhive_refresh_token,
            hdhive_token_expires_at=self._hdhive_token_expires_at,
        )

    def _persist_config_values(self, **kwargs) -> None:
        """基于当前完整配置更新少量运行时值，避免覆盖其它配置项。"""
        try:
            config = dict(self.get_config() or {})
            config.update(kwargs)
            self.update_config(config)
        except Exception as error:
            logger.debug(f"持久化 HDHive/Dian115 签到配置失败：{error}")

    def get_state(self) -> bool:
        return bool(self._enabled)

    def _schedule_once(self) -> None:
        """处理「保存后立即执行一次」开关：提交一次性任务后自动关闭开关。"""
        targets = []
        if self._onlyonce_hdhive:
            targets.append("hdhive")
        if self._onlyonce_dian115:
            targets.append("dian115")
        if not targets:
            return

        self._onlyonce_hdhive = False
        self._onlyonce_dian115 = False
        self._persist_config_values(
            onlyonce_hdhive=False, onlyonce_dian115=False
        )

        service = getattr(self, "_checkin_service", None)
        if service is None:
            return
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler(timezone=pytz.timezone(settings.TZ))
            self._scheduler.start()

        run_at = datetime.now(pytz.timezone(settings.TZ)) + timedelta(seconds=3)
        for provider in targets:
            self._scheduler.add_job(
                service.run_quick_checkin,
                trigger="date",
                run_date=run_at,
                kwargs={"provider": provider},
                id=f"hdhive_dian115_once_{provider}",
                name=f"{provider} 立即签到",
                replace_existing=True,
            )
        logger.info(f"HDHive/Dian115 签到已提交立即执行：{', '.join(targets)}")

    @staticmethod
    def _mode_label(mode: Any) -> str:
        return {
            "normal": "普通签到",
            "gambler": "赌狗签到",
            "lucky": "运气签到",
        }.get(str(mode or "").strip().lower(), "普通签到")

    @staticmethod
    def _trigger_label(trigger: Any) -> str:
        return {
            "manual": "手动",
            "scheduled": "定时",
        }.get(str(trigger or "").strip().lower(), str(trigger or "未知"))

    @staticmethod
    def _signed_points_text(value: Any) -> str:
        try:
            return f"{int(value):+d}"
        except (TypeError, ValueError):
            return "未知"

    def get_page(self) -> Optional[List[dict]]:
        """拼装插件详情页面：运行概览、渠道状态、签到记录与手动执行。"""
        try:
            return self._build_page()
        except Exception as error:
            logger.error(f"HDHive/Dian115 签到详情页生成失败：{error}")
            return [self._page_card(
                "运行状态", "mdi-alert-circle-outline",
                [{
                    "component": "VAlert",
                    "props": {
                        "type": "error", "variant": "tonal",
                        "text": f"详情页数据生成失败：{error}",
                    },
                }],
            )]

    def _api_base(self) -> str:
        """详情页按钮调用的插件接口前缀。"""
        return f"plugin/{type(self).__name__}"

    def _build_page(self) -> List[dict]:
        service = getattr(self, "_checkin_service", None)
        overview = service.provider_overview() if service is not None else []
        records = service.recent_records(limit=15) if service is not None else []
        return [
            self._page_overview_card(records),
            self._page_provider_card(overview),
            self._page_history_card(records),
            self._page_action_card(),
        ]

    @staticmethod
    def _page_card(
            title: str,
            icon: str,
            content: List[dict],
            title_extra: Optional[List[dict]] = None,
    ) -> dict:
        """生成官方插件风格的卡片：圆角描边、投影与图标标题。"""
        title_content: List[dict] = [
            {
                "component": "VIcon",
                "props": {"color": "primary", "class": "mr-3", "size": "default"},
                "text": icon,
            },
            {"component": "span", "text": title},
        ]
        if title_extra:
            title_content.extend(title_extra)
        return {
            "component": "VCard",
            "props": {
                "variant": "flat",
                "class": "mb-4 elevation-2",
                "style": "border-radius: 16px;",
            },
            "content": [
                {
                    "component": "VCardItem",
                    "props": {"class": "pa-6 pb-0"},
                    "content": [
                        {
                            "component": "VCardTitle",
                            "props": {"class": "d-flex align-center text-h6"},
                            "content": title_content,
                        },
                    ],
                },
                {
                    "component": "VCardText",
                    "props": {"class": "pa-6"},
                    "content": content,
                },
            ],
        }

    def _page_overview_card(self, records: List[Dict[str, Any]]) -> dict:
        next_run = "未启用"
        if self._scheduler is not None:
            job = self._scheduler.get_job("hdhive_dian115_checkin")
            next_run_time = getattr(job, "next_run_time", None) if job else None
            if next_run_time:
                next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        running = bool(
            self._enabled
            and (self._hdhive_checkin_enabled or self._dian115_checkin_enabled)
        )
        stats = [
            ("插件状态", "已启用" if self._enabled else "已停用"),
            ("签到周期", self._checkin_cron or "未设置"),
            ("下次执行", next_run),
            ("最近执行", str(records[0].get("executed_at") or "-") if records else "暂无记录"),
        ]
        content: List[dict] = [{
            "component": "VRow",
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 6, "md": 3},
                    "content": [
                        {
                            "component": "div",
                            "props": {"class": "text-caption text-medium-emphasis"},
                            "text": label,
                        },
                        {
                            "component": "div",
                            "props": {"class": "text-body-1 font-weight-medium"},
                            "text": value,
                        },
                    ],
                }
                for label, value in stats
            ],
        }]
        if not self._enabled:
            content.append({
                "component": "VAlert",
                "props": {
                    "type": "warning", "variant": "tonal", "class": "mt-3",
                    "text": "插件当前已停用，定时签到不会执行，仍可在下方手动执行一次。",
                },
            })
        elif not (self._hdhive_checkin_enabled or self._dian115_checkin_enabled):
            content.append({
                "component": "VAlert",
                "props": {
                    "type": "info", "variant": "tonal", "class": "mt-3",
                    "text": "尚未启用任何渠道的每日签到，可在插件配置中打开，或使用下方的手动执行。",
                },
            })
        return self._page_card(
            "运行状态", "mdi-calendar-clock", content,
            title_extra=[
                {
                    "component": "VChip",
                    "props": {
                        "color": "success" if running else "grey",
                        "size": "small", "variant": "tonal", "class": "ml-3",
                    },
                    "text": "运行中" if running else "未运行",
                },
                {"component": "VSpacer"},
                {
                    "component": "VBtn",
                    "props": {
                        "icon": "mdi-refresh", "color": "primary",
                        "variant": "text", "size": "small",
                    },
                    "events": {
                        "click": {
                            "api": f"{self._api_base()}/refresh",
                            "method": "get",
                        },
                    },
                },
            ],
        )

    @staticmethod
    def _points_text(value: Any) -> str:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)

    def _page_provider_card(self, overview: List[Dict[str, Any]]) -> dict:
        icons = {"hdhive": "mdi-web", "dian115": "mdi-cloud-download"}
        columns = []
        for item in overview:
            last = item.get("last_record") or {}
            enabled = bool(item.get("enabled"))
            ready = bool(item.get("ready"))
            if enabled and ready:
                state_text, state_color = "运行中", "success"
            elif enabled:
                state_text, state_color = "待完善配置", "warning"
            else:
                state_text, state_color = "已停用", "grey"
            header = [
                {
                    "component": "VAvatar",
                    "props": {
                        "color": state_color, "size": "small",
                        "variant": "tonal", "class": "mr-2",
                    },
                    "content": [{
                        "component": "VIcon",
                        "text": icons.get(str(item.get("key")), "mdi-account"),
                    }],
                },
                {
                    "component": "span",
                    "props": {"class": "text-subtitle-1 font-weight-medium"},
                    "text": item.get("name"),
                },
                {
                    "component": "VChip",
                    "props": {"color": state_color, "size": "small", "variant": "tonal"},
                    "text": state_text,
                },
                {
                    "component": "VChip",
                    "props": {"color": "info", "size": "small", "variant": "text"},
                    "text": self._mode_label(item.get("mode")),
                },
            ]
            points_after = last.get("points_after")
            if points_after is not None:
                header.append({
                    "component": "VChip",
                    "props": {"color": "primary", "size": "small", "variant": "tonal"},
                    "text": f"可用积分 {self._points_text(points_after)}",
                })
            rows: List[dict] = [
                {
                    "component": "div",
                    "props": {"class": "d-flex align-center flex-wrap ga-2"},
                    "content": header,
                },
                {
                    "component": "div",
                    "props": {"class": "text-body-2 mt-2"},
                    "text": f"账号：{item.get('account') or '未配置'}",
                },
            ]
            if last:
                rows.append({
                    "component": "div",
                    "props": {"class": "text-body-2"},
                    "text": (
                        f"最近签到：{last.get('executed_at') or '-'} ｜ "
                        f"{last.get('status') or ('签到成功' if last.get('success') else '签到失败')}"
                    ),
                })
                rows.append({
                    "component": "div",
                    "props": {"class": "text-caption text-medium-emphasis"},
                    "text": (
                        f"触发：{self._trigger_label(last.get('trigger'))} ｜ "
                        f"积分：{self._signed_points_text(last.get('points_change'))}"
                    ),
                })
            else:
                rows.append({
                    "component": "div",
                    "props": {"class": "text-body-2 text-medium-emphasis"},
                    "text": "暂无签到记录",
                })
            columns.append({
                "component": "VCol",
                "props": {"cols": 12, "md": 6},
                "content": [
                    {
                        "component": "VCard",
                        "props": {
                            "variant": "tonal", "class": "h-100",
                            "style": "border-radius: 12px;",
                        },
                        "content": [
                            {
                                "component": "VCardText",
                                "props": {"class": "pa-4"},
                                "content": rows,
                            },
                        ],
                    },
                ],
            })
        content: List[dict] = []
        if columns:
            content.append({"component": "VRow", "content": columns})
        else:
            content.append({
                "component": "div",
                "props": {"class": "text-body-2 text-medium-emphasis"},
                "text": "暂无渠道信息",
            })
        return self._page_card("渠道状态", "mdi-account-check-outline", content)

    def _page_history_card(self, records: List[Dict[str, Any]]) -> dict:
        if not records:
            return self._page_card(
                "最近签到记录", "mdi-history",
                [{
                    "component": "div",
                    "props": {"class": "text-body-2 text-medium-emphasis"},
                    "text": "暂无签到记录，可点击下方「手动执行」立即签到一次。",
                }],
            )
        headers = ["时间", "渠道", "模式", "触发", "状态", "积分", "说明"]
        rows = []
        for record in records:
            success = bool(record.get("success"))
            status = str(record.get("status") or ("签到成功" if success else "签到失败"))
            message = str(record.get("message") or "").strip()
            rows.append({
                "component": "tr",
                "content": [
                    {
                        "component": "td",
                        "props": {"class": "text-no-wrap"},
                        "text": str(record.get("executed_at") or "-"),
                    },
                    {
                        "component": "td",
                        "text": str(
                            record.get("provider_name") or record.get("provider") or "-"
                        ),
                    },
                    {"component": "td", "text": self._mode_label(record.get("mode"))},
                    {"component": "td", "text": self._trigger_label(record.get("trigger"))},
                    {
                        "component": "td",
                        "content": [{
                            "component": "VChip",
                            "props": {
                                "color": "success" if success else "error",
                                "size": "x-small", "variant": "flat",
                            },
                            "content": [
                                {
                                    "component": "VIcon",
                                    "props": {"size": "x-small", "start": True},
                                    "text": ("mdi-check-circle" if success
                                             else "mdi-alert-circle"),
                                },
                                {"component": "span", "text": status},
                            ],
                        }],
                    },
                    {
                        "component": "td",
                        "text": self._signed_points_text(record.get("points_change")),
                    },
                    {
                        "component": "td",
                        "props": {"class": "text-caption text-medium-emphasis"},
                        "text": message or status,
                    },
                ],
            })
        content: List[dict] = [
            {
                "component": "VTable",
                "props": {
                    "hover": True, "density": "comfortable",
                    "class": "rounded-lg",
                },
                "content": [
                    {
                        "component": "thead",
                        "content": [{
                            "component": "tr",
                            "content": [
                                {
                                    "component": "th",
                                    "props": {"class": "text-left"},
                                    "text": name,
                                }
                                for name in headers
                            ],
                        }],
                    },
                    {"component": "tbody", "content": rows},
                ],
            },
            {
                "component": "div",
                "props": {"class": "text-caption text-medium-emphasis mt-2"},
                "text": f"共显示 {len(records)} 条签到记录",
            },
        ]
        return self._page_card("最近签到记录", "mdi-history", content)

    def _page_action_card(self) -> dict:
        buttons = [
            ("立即执行全部", "primary", "mdi-play-circle", "all"),
            ("立即执行 HDHive", "success", "mdi-web", "hdhive"),
            ("立即执行 Dian115", "info", "mdi-cloud-download", "dian115"),
        ]
        return self._page_card(
            "手动执行", "mdi-play-circle-outline",
            [
                {
                    "component": "div",
                    "props": {"class": "d-flex flex-wrap ga-2"},
                    "content": [
                        {
                            "component": "VBtn",
                            "props": {
                                "color": color, "variant": "tonal",
                                "size": "small", "prepend-icon": icon,
                            },
                            "text": label,
                            "events": {
                                "click": {
                                    "api": f"{self._api_base()}/checkin/{provider}",
                                    "method": "post",
                                },
                            },
                        }
                        for label, color, icon, provider in buttons
                    ],
                },
                {
                    "component": "div",
                    "props": {"class": "text-caption text-medium-emphasis mt-2"},
                    "text": (
                        "手动执行会立刻调用签到接口并写入签到记录，不受「每日签到」开关限制；"
                        "「立即执行全部」只执行已启用且配置完整的渠道。"
                    ),
                },
            ],
        )

    def get_api(self) -> List[Dict[str, Any]]:
        """注册详情页「手动执行」与「刷新」按钮使用的插件接口。"""
        return [
            {
                "path": "/checkin/{provider}",
                "endpoint": self.api_checkin_now,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行 HDHive / Dian115 签到",
                "description": "provider 支持 all、hdhive、dian115",
            },
            {
                "path": "/refresh",
                "endpoint": self.api_refresh,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "刷新 HDHive / Dian115 签到详情页数据",
                "description": "返回各渠道状态与最近的签到记录",
            },
        ]

    def api_refresh(self) -> Dict[str, Any]:
        """详情页刷新按钮入口。"""
        service = getattr(self, "_checkin_service", None)
        if service is None:
            return {"success": False, "message": "签到服务尚未初始化，请先保存一次插件配置"}
        records = service.recent_records(limit=15)
        return {
            "success": True,
            "message": f"已刷新，共 {len(records)} 条签到记录",
            "data": {
                "providers": service.provider_overview(),
                "records": records,
            },
        }

    def api_checkin_now(self, provider: str = "all", mode: str = "") -> Dict[str, Any]:
        """详情页手动执行入口。"""
        service = getattr(self, "_checkin_service", None)
        if service is None:
            return {"success": False, "message": "签到服务尚未初始化，请先保存一次插件配置"}
        if not self._enabled:
            return {"success": False, "message": "插件未启用，请先在插件配置中启用"}
        result = service.run_quick_checkin(provider=provider, mode=mode)
        logger.info(
            f"HDHive/Dian115 手动签到（{provider or 'all'}）："
            f"{result.get('message') or result.get('success')}"
        )
        return result

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """
        拼装插件配置页面，按 MoviePilot V2 插件规范返回 Vuetify 组件配置与默认数据结构。
        """
        notification_options = [
            {"title": item.value or item.name, "value": item.name}
            for item in NotificationType
        ]
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VCard',
                        'props': {'class': 'mt-0'},
                        'content': [
                            {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                                {'component': 'VIcon', 'props': {'color': 'info', 'class': 'mr-2'}, 'text': 'mdi-cog'},
                                {'component': 'span', 'text': '基础设置'},
                            ]},
                            {'component': 'VDivider'},
                            {'component': 'VCardText', 'content': [
                                {'component': 'VAlert', 'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'class': 'mb-3',
                                    'text': '仅保留 HDHive 与 Dian115 两个签到渠道，支持每日签到、转盘与消息通知。',
                                }},
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'enabled', 'label': '启用插件', 'color': 'primary'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'checkin_notify', 'label': '发送通知', 'color': 'info'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [
                                        {'component': 'VSelect', 'props': {
                                            'model': 'notification_type', 'label': '通知渠道',
                                            'items': notification_options}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [
                                        {'component': 'VCronField', 'props': {
                                            'model': 'checkin_cron', 'label': '签到执行周期',
                                            'placeholder': '5位 cron 表达式，如 0 8 * * *'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'proxy', 'label': '代理地址',
                                            'placeholder': 'http://127.0.0.1:7890', 'clearable': True}},
                                    ]},
                                ]},
                            ]},
                        ],
                    },
                    {
                        'component': 'VCard',
                        'props': {'class': 'mt-3'},
                        'content': [
                            {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                                {'component': 'VIcon', 'props': {'color': 'info', 'class': 'mr-2'}, 'text': 'mdi-web'},
                                {'component': 'span', 'text': 'HDHive'},
                            ]},
                            {'component': 'VDivider'},
                            {'component': 'VCardText', 'content': [
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'hdhive_checkin_enabled', 'label': '启用 HDHive 签到',
                                            'color': 'primary'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSelect', 'props': {
                                            'model': 'hdhive_query_mode', 'label': '查询模式',
                                            'items': [
                                                {'title': 'WebAPI（账号密码）', 'value': 'web'},
                                                {'title': 'OpenAPI（应用授权）', 'value': 'api'},
                                            ]}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSelect', 'props': {
                                            'model': 'hdhive_checkin_mode', 'label': '签到模式',
                                            'items': [
                                                {'title': '普通签到', 'value': 'normal'},
                                                {'title': '赌狗签到', 'value': 'gambler'},
                                            ]}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_request_interval', 'label': '请求间隔（秒）',
                                            'type': 'number', 'placeholder': '建议保持 5 秒以上'}},
                                    ]},
                                ]},
                                {'component': 'VAlert', 'props': {
                                    'type': 'info', 'variant': 'tonal', 'class': 'mb-3',
                                    'text': 'WebAPI 使用账号密码登录，功能完整；OpenAPI 需要先在 HDHive 申请应用并完成用户授权。'
                                            '下面只会显示当前查询模式对应的配置项。'}},
                                {'component': 'VRow', 'props': {'v-show': "hdhive_query_mode === 'web'"}, 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_username', 'label': 'HDHive 用户名',
                                            'placeholder': 'WebAPI 模式必填', 'clearable': True}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_password', 'label': 'HDHive 密码',
                                            'type': 'password', 'autocomplete': 'new-password',
                                            'placeholder': 'WebAPI 模式必填'}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'props': {'v-show': "hdhive_query_mode === 'api'"}, 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_base_url', 'label': 'OpenAPI 站点地址',
                                            'placeholder': 'https://re0.me', 'clearable': True}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_api_key', 'label': 'OpenAPI 应用 Secret',
                                            'type': 'password', 'autocomplete': 'new-password'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_client_id', 'label': 'OpenAPI Client ID',
                                            'clearable': True}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'props': {'v-show': "hdhive_query_mode === 'api'"}, 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_redirect_uri', 'label': 'OpenAPI 回调地址',
                                            'clearable': True}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSelect', 'props': {
                                            'model': 'hdhive_response_mode', 'label': '授权回调模式',
                                            'items': [
                                                {'title': 'redirect', 'value': 'redirect'},
                                                {'title': 'postmessage', 'value': 'postmessage'},
                                            ]}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_auth_code', 'label': 'OpenAPI 授权码',
                                            'placeholder': '保存后自动换取 Token', 'clearable': True}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'onlyonce_hdhive', 'label': '保存后立即执行一次',
                                            'color': 'success'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 8}, 'content': [
                                        {'component': 'div',
                                         'props': {'class': 'text-caption text-medium-emphasis mt-3'},
                                         'text': '打开后保存配置会立刻执行一次 HDHive 签到并自动关闭，不受「启用 HDHive 签到」开关限制。'},
                                    ]},
                                ]},
                            ]},
                        ],
                    },
                    {
                        'component': 'VCard',
                        'props': {'class': 'mt-3'},
                        'content': [
                            {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                                {'component': 'VIcon', 'props': {'color': 'info', 'class': 'mr-2'}, 'text': 'mdi-cloud-download'},
                                {'component': 'span', 'text': 'Dian115'},
                            ]},
                            {'component': 'VDivider'},
                            {'component': 'VCardText', 'content': [
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'dian115_checkin_enabled', 'label': '启用 Dian115 签到',
                                            'color': 'primary'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'dian115_email', 'label': 'Dian115 邮箱',
                                            'placeholder': '登录邮箱', 'clearable': True}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'dian115_password', 'label': 'Dian115 密码',
                                            'type': 'password', 'autocomplete': 'new-password'}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSelect', 'props': {
                                            'model': 'dian115_checkin_mode', 'label': '签到模式',
                                            'items': [
                                                {'title': '普通签到', 'value': 'normal'},
                                                {'title': '运气签到', 'value': 'lucky'},
                                            ]}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'dian115_request_interval', 'label': '请求间隔（秒）',
                                            'type': 'number'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'dian115_base_url', 'label': 'Dian115 站点地址',
                                            'placeholder': 'https://m.dian115.com', 'clearable': True}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'dian115_lottery_enabled', 'label': '启用幸运转盘',
                                            'color': 'warning'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'dian115_lottery_count', 'label': '转盘次数',
                                            'type': 'number', 'placeholder': '范围 1-20'}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VSwitch', 'props': {
                                            'model': 'onlyonce_dian115', 'label': '保存后立即执行一次',
                                            'color': 'success'}},
                                    ]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 8}, 'content': [
                                        {'component': 'div',
                                         'props': {'class': 'text-caption text-medium-emphasis mt-3'},
                                         'text': '打开后保存配置会立刻执行一次 Dian115 签到并自动关闭，不受「启用 Dian115 签到」开关限制。'},
                                    ]},
                                ]},
                            ]},
                        ],
                    },
                ],
            }
        ], {
            "enabled": True,
            "checkin_cron": "0 8 * * *",
            "checkin_notify": True,
            "notification_type": "Plugin",
            "proxy": "",
            "hdhive_checkin_enabled": False,
            "hdhive_query_mode": "web",
            "hdhive_username": "",
            "hdhive_password": "",
            "hdhive_checkin_mode": "normal",
            "hdhive_request_interval": 5,
            "hdhive_base_url": "https://re0.me",
            "hdhive_api_key": "",
            "hdhive_client_id": "",
            "hdhive_redirect_uri": "",
            "hdhive_response_mode": "redirect",
            "hdhive_auth_code": "",
            "dian115_checkin_enabled": False,
            "dian115_email": "",
            "dian115_password": "",
            "dian115_checkin_mode": "normal",
            "dian115_request_interval": 1,
            "dian115_base_url": "https://m.dian115.com",
            "dian115_lottery_enabled": False,
            "dian115_lottery_count": 1,
            "onlyonce_hdhive": False,
            "onlyonce_dian115": False,
        }

    def get_command(self) -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/hdhive_checkin",
                "event": EventType.PluginAction,
                "desc": "手动执行 HDHive 签到",
                "category": "签到",
                "data": {"action": "hdhive_checkin"},
            },
            {
                "cmd": "/dian115_checkin",
                "event": EventType.PluginAction,
                "desc": "手动执行 Dian115 签到",
                "category": "签到",
                "data": {"action": "dian115_checkin"},
            },
            {
                "cmd": "/checkin_all",
                "event": EventType.PluginAction,
                "desc": "手动执行全部已启用签到",
                "category": "签到",
                "data": {"action": "checkin_all"},
            },
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        event_data = getattr(event, "event_data", None) if event else None
        if not isinstance(event_data, dict):
            return
        action = str(event_data.get("action") or "").strip()
        if action == "hdhive_checkin":
            return self._checkin_service.start_manual_checkin("hdhive")
        if action == "dian115_checkin":
            return self._checkin_service.start_manual_checkin("dian115")
        if action == "checkin_all":
            return self._checkin_service.run_quick_checkin("all")

    def stop_service(self):
        if self._scheduler:
            try:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._scheduler = None
        service = getattr(self, "_checkin_service", None)
        if service:
            service.close()
        self._close_hdhive_openapi_client()
