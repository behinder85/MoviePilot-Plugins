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
    plugin_icon = "https://raw.githubusercontent.com/behinder85/MoviePilot-Plugins/main/icons/hdhivedian115checkin.png"
    plugin_version = "1.0.3"
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
        """基于当前完整配置更新少量运行时值，避免覆盖其它配置项。"""
        try:
            config = dict(self.get_config() or {})
            config.update(kwargs)
            self.update_config(config)
        except Exception as error:
            logger.debug(f"持久化 HDHive/Dian115 签到配置失败：{error}")

    def get_state(self) -> bool:
        return bool(self._enabled)

    def get_page(self) -> Optional[List[dict]]:
        """本插件不提供插件详情页面。"""
        return None

    def get_api(self) -> List[Dict[str, Any]]:
        """本插件不注册额外的插件 API。"""
        return []

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
                                ]},
                                {'component': 'VRow', 'content': [
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
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                        {'component': 'VTextField', 'props': {
                                            'model': 'hdhive_request_interval', 'label': '请求间隔（秒）',
                                            'type': 'number', 'placeholder': '建议保持 5 秒以上'}},
                                    ]},
                                ]},
                                {'component': 'VRow', 'content': [
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
                                {'component': 'VRow', 'content': [
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
        open_client = getattr(self, "_hdhive_open_client", None)
        if open_client:
            try:
                open_client.close()
            except Exception:
                pass
