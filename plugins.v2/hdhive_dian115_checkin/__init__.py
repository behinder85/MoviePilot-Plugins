"""HDHive / Dian115 每日签到插件。

只保留上游 MoviePilot-Plugins 中的 HDHive 和 Dian115 签到能力，
删除网盘、订阅、搜索、转存等冗余模块。
"""

import threading
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
from .search.hdhive import HDHiveClient, HDHiveOpenAPIClient, HDHiveOpenAPIError


class HDHiveDian115Checkin(_PluginBase):
    """HDHive / Dian115 签到插件。"""

    plugin_name = "HDHive / Dian115 签到"
    plugin_desc = "仅保留 HDHive 与 Dian115 两个渠道的每日签到、转盘和通知功能。"
    plugin_icon = "https://raw.githubusercontent.com/behinder85/MoviePilot-Plugins/main/icons/hdhive_dian115_checkin.png"
    plugin_version = "1.0.0"
    plugin_author = "odomu"
    author_url = "https://github.com/odomu/MoviePilot-Plugins"
    plugin_config_prefix = "hdhive_dian115_checkin_"
    plugin_order = 1
    auth_level = 1

    _scheduler: Optional[BackgroundScheduler] = None
    _stop_event: Optional[threading.Event] = None

    _enabled: bool = True
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
        HDHiveClient._SESSION_FILE = data_path / "hdhive-curl-session.json"

        if self._hdhive_query_mode == "api":
            self._init_hdhive_openapi_client()

        self._setup_scheduler()

    def _apply_config(self, config: Dict[str, Any]) -> None:
        self._enabled = bool(config.get("enabled", True))
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

    def _init_hdhive_openapi_client(self) -> None:
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
        try:
            self.update_config(kwargs)
        except Exception as error:
            logger.debug(f"持久化 HDHive/Dian115 签到配置失败：{error}")

    def get_state(self) -> bool:
        return bool(self._enabled)

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        form = [
            {
                "type": "details",
                "content": "仅保留 HDHive 与 Dian115 两个签到渠道；客户端代码可由上游自动同步。",
            },
            {
                "type": "switch",
                "name": "enabled",
                "label": "启用插件",
                "default": True,
                "help": "关闭后签到调度会停止。",
            },
            {
                "type": "text",
                "name": "checkin_cron",
                "label": "每日签到时间（cron）",
                "default": "0 8 * * *",
                "required": True,
                "help": "例如每天 08:00 为 0 8 * * *。",
            },
            {
                "type": "switch",
                "name": "checkin_notify",
                "label": "签到后发送通知",
                "default": True,
            },
            {
                "type": "select",
                "name": "notification_type",
                "label": "通知渠道",
                "default": "Plugin",
                "options": [
                    {"value": item.name, "label": item.value or item.name}
                    for item in NotificationType
                ],
            },
            {
                "type": "text",
                "name": "proxy",
                "label": "HTTP/HTTPS 代理",
                "default": "",
                "help": "选填，例如 http://127.0.0.1:7890。",
            },
            {"type": "details", "content": "HDHive"},
            {
                "type": "switch",
                "name": "hdhive_checkin_enabled",
                "label": "启用 HDHive 签到",
                "default": False,
            },
            {
                "type": "select",
                "name": "hdhive_query_mode",
                "label": "HDHive 模式",
                "default": "web",
                "options": [
                    {"value": "web", "label": "WebAPI（账号密码）"},
                    {"value": "api", "label": "OpenAPI（应用授权）"},
                ],
            },
            {
                "type": "text",
                "name": "hdhive_username",
                "label": "HDHive 用户名",
                "default": "",
                "help": "WebAPI 模式必填。",
            },
            {
                "type": "password",
                "name": "hdhive_password",
                "label": "HDHive 密码",
                "default": "",
                "help": "WebAPI 模式必填。",
            },
            {
                "type": "select",
                "name": "hdhive_checkin_mode",
                "label": "HDHive 签到模式",
                "default": "normal",
                "options": [
                    {"value": "normal", "label": "普通签到"},
                    {"value": "gambler", "label": "赌狗签到"},
                ],
            },
            {
                "type": "number",
                "name": "hdhive_request_interval",
                "label": "HDHive 请求间隔（秒）",
                "default": 5,
                "help": "建议保持默认，风控较高时不要调太小。",
            },
            {
                "type": "text",
                "name": "hdhive_base_url",
                "label": "HDHive OpenAPI 站点地址",
                "default": "https://re0.me",
                "help": "仅 OpenAPI 模式使用。",
            },
            {
                "type": "password",
                "name": "hdhive_api_key",
                "label": "HDHive OpenAPI 应用 Secret",
                "default": "",
            },
            {
                "type": "text",
                "name": "hdhive_client_id",
                "label": "HDHive OpenAPI Client ID",
                "default": "",
            },
            {
                "type": "text",
                "name": "hdhive_redirect_uri",
                "label": "HDHive OpenAPI 回调地址",
                "default": "",
            },
            {
                "type": "select",
                "name": "hdhive_response_mode",
                "label": "HDHive 授权回调模式",
                "default": "redirect",
                "options": [
                    {"value": "redirect", "label": "redirect"},
                    {"value": "postmessage", "label": "postmessage"},
                ],
            },
            {
                "type": "text",
                "name": "hdhive_auth_code",
                "label": "HDHive OpenAPI 授权码",
                "default": "",
                "help": "保存后自动换取 Token，成功后会被清空。",
            },
            {"type": "details", "content": "Dian115"},
            {
                "type": "switch",
                "name": "dian115_checkin_enabled",
                "label": "启用 Dian115 签到",
                "default": False,
            },
            {
                "type": "text",
                "name": "dian115_email",
                "label": "Dian115 邮箱",
                "default": "",
            },
            {
                "type": "password",
                "name": "dian115_password",
                "label": "Dian115 密码",
                "default": "",
            },
            {
                "type": "select",
                "name": "dian115_checkin_mode",
                "label": "Dian115 签到模式",
                "default": "normal",
                "options": [
                    {"value": "normal", "label": "普通签到"},
                    {"value": "lucky", "label": "运气签到"},
                ],
            },
            {
                "type": "number",
                "name": "dian115_request_interval",
                "label": "Dian115 请求间隔（秒）",
                "default": 1,
            },
            {
                "type": "text",
                "name": "dian115_base_url",
                "label": "Dian115 站点地址",
                "default": "https://m.dian115.com",
            },
            {
                "type": "switch",
                "name": "dian115_lottery_enabled",
                "label": "启用 Dian115 转盘",
                "default": False,
            },
            {
                "type": "number",
                "name": "dian115_lottery_count",
                "label": "Dian115 转盘次数",
                "default": 1,
                "help": "范围 1-20。",
            },
        ]
        return form, {}

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
        open_client = getattr(self, "_hdhive_open_client", None)
        if open_client:
            try:
                open_client.close()
            except Exception:
                pass
