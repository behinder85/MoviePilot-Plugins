"""HDHive / Dian115 每日签到执行、通知与历史持久化。

仅保留上游 MoviePilot-Plugins 中 HDHive 与 Dian115 两个签到渠道，
客户端代码位于本插件的 search 子包内，供 GitHub Actions 从上游自动更新。
"""

import copy
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

import pytz
from app.core.config import settings
from app.log import logger

from .search.dian115 import Dian115Client, Dian115Error
from .search.hdhive import (
    HDHiveClient,
    HDHiveOpenAPIClient,
    HDHiveOpenAPIError,
    HDHiveWebError,
)
from .search.http_client import normalize_proxies


@dataclass(frozen=True)
class CheckinProvider:
    """签到提供方的最小适配契约。"""

    key: str
    name: str
    credential_attrs: Tuple[str, ...]
    error_types: Tuple[Type[Exception], ...]
    modes: Tuple[str, ...]

    @property
    def history_key(self) -> str:
        return f"{self.key}_checkin_history"


class HDHiveDian115CheckinService:
    """编排 HDHive 与 Dian115 的签到、通知和历史。"""

    _PROVIDERS = {
        "hdhive": CheckinProvider(
            key="hdhive",
            name="HDHive",
            credential_attrs=("_hdhive_username", "_hdhive_password"),
            error_types=(HDHiveWebError, HDHiveOpenAPIError),
            modes=("normal", "gambler"),
        ),
        "dian115": CheckinProvider(
            key="dian115",
            name="Dian115",
            credential_attrs=("_dian115_email", "_dian115_password"),
            error_types=(Dian115Error,),
            modes=("normal", "lucky"),
        ),
    }
    _HISTORY_LIMIT = 60

    def __init__(self, owner):
        self._owner = owner
        self._run_lock = threading.Lock()
        self._schedule_lock = threading.Lock()
        self._history_lock = threading.RLock()
        self._hdhive_web_client: Optional[HDHiveClient] = None
        self._hdhive_web_signature = None
        self._dian115_client: Optional[Dian115Client] = None
        self._dian115_signature = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(pytz.timezone(settings.TZ))

    @staticmethod
    def _now_text() -> str:
        return HDHiveDian115CheckinService._now().isoformat(timespec="seconds")

    @classmethod
    def _resolve_provider(cls, provider: str) -> Optional[CheckinProvider]:
        return cls._PROVIDERS.get(str(provider or "").strip().lower())

    def _normalized_proxy(self):
        try:
            return normalize_proxies(getattr(self._owner, "_proxy", ""))
        except Exception as error:
            logger.warning(f"代理配置解析失败，签到将使用直连：{error}")
            return None

    def _checkin_credentials_ready(self, provider: CheckinProvider) -> bool:
        if (
                provider.key == "hdhive"
                and str(getattr(self._owner, "_hdhive_query_mode", "web")) == "api"
        ):
            client = getattr(self._owner, "_hdhive_open_client", None)
            return bool(client and client.is_ready)
        return all(
            bool(getattr(self._owner, attr, None))
            for attr in provider.credential_attrs
        )

    def _checkin_configuration_message(self, provider: CheckinProvider) -> str:
        if (
                provider.key == "hdhive"
                and str(getattr(self._owner, "_hdhive_query_mode", "web")) == "api"
        ):
            return "请先配置 HDHive OpenAPI 应用 Secret 和用户授权"
        return f"请先配置并保存 {provider.name} 账号和密码"

    def _get_hdhive_client(self):
        owner = self._owner
        if str(getattr(owner, "_hdhive_query_mode", "web")) == "api":
            client = getattr(owner, "_hdhive_open_client", None)
            if client is None:
                owner._init_hdhive_openapi_client()
                client = getattr(owner, "_hdhive_open_client", None)
            if not client or not client.is_ready:
                raise HDHiveOpenAPIError(
                    "OPENAPI_USER_REQUIRED",
                    "HDHive OpenAPI 应用配置或用户授权不完整",
                )
            return client

        signature = (
            str(getattr(owner, "_hdhive_username", "") or "").strip(),
            str(getattr(owner, "_hdhive_password", "") or ""),
            str(getattr(owner, "_proxy", "") or "").strip(),
            max(
                2.0,
                min(
                    float(getattr(owner, "_hdhive_request_interval", 5.0) or 5.0),
                    10.0,
                ),
            ),
        )
        client = self._hdhive_web_client
        if client is None or self._hdhive_web_signature != signature:
            if client is not None:
                try:
                    client.close()
                except Exception as error:
                    logger.debug(f"关闭旧 HDHive 客户端失败：{error}")
            client = HDHiveClient(
                username=str(getattr(owner, "_hdhive_username", "") or "").strip(),
                password=str(getattr(owner, "_hdhive_password", "") or ""),
                proxy=self._normalized_proxy(),
                request_interval=signature[3],
                should_stop=lambda: bool(
                    getattr(owner, "_stop_event", None)
                    and owner._stop_event.is_set()
                ),
            )
            self._hdhive_web_client = client
            self._hdhive_web_signature = signature
        return client

    def _get_dian115_client(self):
        owner = self._owner
        signature = (
            str(getattr(owner, "_dian115_email", "") or "").strip(),
            str(getattr(owner, "_dian115_password", "") or ""),
            str(getattr(owner, "_dian115_base_url", "https://m.dian115.com") or "https://m.dian115.com").strip(),
            str(getattr(owner, "_proxy", "") or "").strip(),
            max(
                0.2,
                min(
                    float(getattr(owner, "_dian115_request_interval", 1.0) or 1.0),
                    10.0,
                ),
            ),
        )
        client = self._dian115_client
        if client is None or self._dian115_signature != signature:
            if client is not None:
                try:
                    client.close()
                except Exception as error:
                    logger.debug(f"关闭旧 Dian115 客户端失败：{error}")
            client = Dian115Client(
                email=signature[0],
                password=signature[1],
                base_url=signature[2],
                proxy=self._normalized_proxy(),
                request_interval=signature[4],
                unlocks_per_minute=6,
                get_data_func=self._owner.get_data,
                save_data_func=self._owner.save_data,
            )
            self._dian115_client = client
            self._dian115_signature = signature
        return client

    def _get_checkin_client(self, provider: CheckinProvider):
        if provider.key == "hdhive":
            return self._get_hdhive_client()
        if provider.key == "dian115":
            return self._get_dian115_client()
        raise ValueError(f"不支持的签到提供方：{provider.key}")

    def _provider_account(self, provider: CheckinProvider) -> str:
        """渠道当前使用的账号描述。"""
        if provider.key == "hdhive":
            if str(getattr(self._owner, "_hdhive_query_mode", "web")) == "api":
                client = getattr(self._owner, "_hdhive_open_client", None)
                authorized = bool(client and client.is_ready)
                return f"OpenAPI 应用授权（{'已授权' if authorized else '未授权'}）"
            return str(getattr(self._owner, "_hdhive_username", "") or "") or "未配置"
        return str(getattr(self._owner, f"_{provider.key}_email", "") or "") or "未配置"

    def provider_overview(self) -> List[Dict[str, Any]]:
        """各渠道的启用状态、账号信息与最近一次签到记录。"""
        items = []
        for provider in self._PROVIDERS.values():
            history = self._load_history(provider)
            last = history[-1] if history else None
            items.append({
                "key": provider.key,
                "name": provider.name,
                "enabled": bool(getattr(
                    self._owner, f"_{provider.key}_checkin_enabled", False
                )),
                "ready": self._checkin_credentials_ready(provider),
                "account": self._provider_account(provider),
                "mode": str(getattr(
                    self._owner, f"_{provider.key}_checkin_mode", "normal"
                ) or "normal"),
                "modes": list(provider.modes),
                "last_record": self._public_record(last) if last else None,
            })
        return items

    def recent_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        """按时间倒序返回所有渠道最近的签到记录。"""
        records: List[Dict[str, Any]] = []
        for provider in self._PROVIDERS.values():
            records.extend(self._load_history(provider))
        records.sort(key=lambda item: str(item.get("executed_at") or ""), reverse=True)
        return [
            self._public_record(item)
            for item in records[:max(1, int(limit or 10))]
        ]

    def _load_history(self, provider: CheckinProvider) -> List[Dict[str, Any]]:
        stored = self._owner.get_data(provider.history_key) or []
        if not isinstance(stored, list):
            return []
        return [
            copy.deepcopy(item)
            for item in stored[-self._HISTORY_LIMIT:]
            if isinstance(item, dict)
        ]

    def _save_history(self, provider: CheckinProvider, record: Dict[str, Any]) -> None:
        with self._history_lock:
            history = self._load_history(provider)
            history.append(copy.deepcopy(record))
            self._owner.save_data(
                provider.history_key,
                history[-self._HISTORY_LIMIT:],
            )

    def get_checkin_history(
            self, provider: str, limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        adapter = self._resolve_provider(provider)
        if adapter is None:
            return None
        with self._history_lock:
            history = self._load_history(adapter)
        normalized_limit = max(1, min(int(limit or 20), self._HISTORY_LIMIT))
        return {
            "total": len(history),
            "limit": normalized_limit,
            "items": list(reversed(history))[:normalized_limit],
        }

    @staticmethod
    def _signed_points(value: Any) -> str:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return "未知"
        return f"{normalized:+d}"

    @staticmethod
    def _public_record(record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: copy.deepcopy(record.get(key))
            for key in (
                "id", "provider", "provider_name", "executed_at", "trigger",
                "mode", "success", "status", "points_change",
                "points_before", "points_after", "signin_days",
                "signin_points", "message",
                "lottery_target_count", "lottery_executed",
                "lottery_cost_points", "lottery_award_points",
                "lottery_vip_days",
            )
        }

    def _build_record(
            self,
            provider: CheckinProvider,
            trigger: str,
            mode: str,
            result: Optional[Dict[str, Any]] = None,
            error: Optional[Exception] = None,
    ) -> Dict[str, Any]:
        data = result or {}
        lottery = data.get("lottery") if isinstance(data, dict) else None
        lottery = lottery if isinstance(lottery, dict) else {}
        success = bool(data.get("success")) if result is not None else False
        default_message = "" if result is not None else str(error or "签到失败")
        return {
            "id": f"{provider.key}-{uuid.uuid4().hex}",
            "provider": provider.key,
            "provider_name": provider.name,
            "executed_at": self._now_text(),
            "trigger": str(trigger or "manual"),
            "mode": mode,
            "success": success,
            "status": str(data.get("status") or (
                "签到成功" if success else "签到失败"
            )),
            "message": str(data.get("message") or default_message),
            "points_change": data.get("points_change"),
            "points_before": data.get("points_before"),
            "points_after": data.get("points_after"),
            "signin_days": data.get("signin_days"),
            "signin_points": data.get("signin_points"),
            "lottery_target_count": lottery.get("target_count"),
            "lottery_executed": lottery.get(
                "used_after", lottery.get("executed")
            ),
            "lottery_cost_points": lottery.get("cost_points"),
            "lottery_award_points": lottery.get("award_points"),
            "lottery_vip_days": lottery.get("vip_days"),
            "http_status": int(
                data.get("status_code")
                or getattr(error, "status_code", 0)
                or getattr(error, "status", 0)
                or 0
            ),
            "error_code": str(
                data.get("error_code")
                or getattr(error, "code", "")
                or ("unexpected_error" if error is not None else "")
            ),
            "captcha_verified": bool(data.get("captcha_verified")),
        }

    def _notify_checkin(
            self, provider: CheckinProvider, record: Dict[str, Any]
    ) -> None:
        if not getattr(self._owner, "_checkin_notify", False):
            return
        delta = record.get("points_change")
        balance = record.get("points_after")
        signin_days = record.get("signin_days")
        mode = {
            "gambler": "赌狗签到",
            "lucky": "运气签到",
        }.get(record.get("mode"), "普通签到")
        lines = [
            f"模式：{mode}",
            f"状态：{record.get('status') or '未知'}",
            f"积分：{self._signed_points(delta)}，余额 {balance if balance is not None else '未知'}",
            f"累计：{signin_days if signin_days is not None else '未知'} 天",
        ]
        if record.get("lottery_target_count"):
            lines.append(
                f"转盘：{record.get('lottery_executed') or 0}/"
                f"{record.get('lottery_target_count')} 次，净积分 "
                f"{self._signed_points((record.get('lottery_award_points') or 0) - (record.get('lottery_cost_points') or 0))}"
            )
        if not record.get("success") and record.get("message"):
            lines.append(f"原因：{record.get('message')}")
        self._owner.post_message(
            mtype=self._owner._notification_type,
            title=(
                f"【HDHive/Dian115签到】{provider.name} 签到完成"
                if record.get("success")
                else f"【HDHive/Dian115签到】{provider.name} 签到失败"
            ),
            text="\n".join(lines),
        )

    def _notify_checkin_summary(
            self, results: List[Dict[str, Any]], title: str
    ) -> None:
        if not getattr(self._owner, "_checkin_notify", False) or not results:
            return
        lines = []
        for item in results:
            record = item.get("data") if isinstance(item, dict) else None
            record = record if isinstance(record, dict) else {}
            provider_name = str(
                item.get("provider_name") or record.get("provider_name")
                or item.get("provider") or record.get("provider") or "未知渠道"
            )
            success = bool(item.get("success") or record.get("success"))
            status = str(
                record.get("status") or item.get("message")
                or ("签到成功" if success else "签到失败")
            )
            details = ["成功" if success else "失败", status]
            if record.get("points_change") is not None:
                details.append(f"积分 {self._signed_points(record.get('points_change'))}")
            if not success and record.get("message"):
                message = str(record.get("message"))
                if message != status:
                    details.append(message[:36])
            lines.append(f"{provider_name}：{'，'.join(details)}")
        self._owner.post_message(
            mtype=self._owner._notification_type,
            title=f"【HDHive/Dian115签到】{title}",
            text="\n".join(lines),
        )

    def _run_dian115_actions(
            self, client: Dian115Client, mode: str
    ) -> Dict[str, Any]:
        before = client.get_account_info()
        signin = client.signin(mode=mode)
        lottery_count = (
            int(getattr(self._owner, "_dian115_lottery_count", 0) or 0)
            if getattr(self._owner, "_dian115_lottery_enabled", False)
            else 0
        )
        lottery = (
            client.run_lottery(lottery_count)
            if lottery_count else {
                "success": True,
                "target_count": 0,
                "executed": 0,
                "cost_points": 0,
                "award_points": 0,
                "vip_days": 0,
            }
        )
        try:
            after = client.get_account_info()
        except Dian115Error:
            after = dict(before)
            fallback_balance = (
                lottery.get("new_balance")
                if lottery.get("new_balance") is not None
                else signin.get("new_balance")
            )
            if fallback_balance is not None:
                after["points"] = fallback_balance
        points_before = int(before.get("points") or 0)
        points_after = int(after.get("points") or 0)
        signin_points = signin.get("award_points")
        if signin_points is None:
            signin_points = (
                    points_after - points_before
                    - int(lottery.get("points_change") or 0)
            )
        signin_label = (
            "今日已签到"
            if signin.get("already_checked_in")
            else f"签到 {self._signed_points(signin_points)}"
        )
        parts = [signin_label]
        if lottery_count:
            parts.append(
                f"转盘 {lottery.get('used_after') or 0}/"
                f"{lottery.get('target_count') or lottery_count}"
            )
        if not lottery.get("success"):
            parts.append(
                f"转盘未完成：{lottery.get('message') or '接口返回失败'}"
            )
        success = bool(signin.get("success") and lottery.get("success"))
        return {
            "success": success,
            "status": (
                "今日已签到"
                if signin.get("already_checked_in") and not lottery_count
                else "签到完成" if success else "签到未完成"
            ),
            "message": "；".join(parts),
            "mode": mode,
            "signin_points": signin_points,
            "points_change": points_after - points_before,
            "points_before": points_before,
            "points_after": points_after,
            "signin_days": int(
                after.get("consecutive_signin")
                or signin.get("signin_days")
                or 0
            ),
            "status_code": int(
                lottery.get("status_code") or signin.get("status_code") or 0
            ),
            "error_code": str(
                lottery.get("error_code") or signin.get("error_code") or ""
            ),
            "lottery": lottery,
        }

    def _execute_provider_checkin(
            self, provider: CheckinProvider, client, mode: str
    ) -> Dict[str, Any]:
        if provider.key == "dian115":
            return self._run_dian115_actions(client, mode)
        if provider.key == "hdhive":
            return client.checkin(is_gambler=mode == "gambler")
        return client.checkin()

    def _prepare_checkin(
            self, provider: str, mode: str, require_enabled: bool = True
    ) -> Tuple[Optional[CheckinProvider], str, Optional[Dict[str, Any]]]:
        adapter = self._resolve_provider(provider)
        if adapter is None:
            return None, "", {
                "success": False,
                "message": "不支持的签到提供方",
            }
        if require_enabled and not bool(getattr(
                self._owner, f"_{adapter.key}_checkin_enabled", False
        )):
            return adapter, "", {
                "success": False,
                "message": f"{adapter.name} 每日签到未启用",
            }
        if not self._checkin_credentials_ready(adapter):
            return adapter, "", {
                "success": False,
                "message": self._checkin_configuration_message(adapter),
            }
        default_mode = getattr(
            self._owner, f"_{adapter.key}_checkin_mode", "normal"
        )
        normalized_mode = str(mode or default_mode).strip().lower()
        if normalized_mode not in adapter.modes:
            return adapter, normalized_mode, {
                "success": False,
                "message": f"{adapter.name} 签到模式无效",
            }
        return adapter, normalized_mode, None

    def start_manual_checkin(
            self, provider: str, mode: str = "", require_enabled: bool = False
    ) -> Dict[str, Any]:
        """手动触发单个渠道签到；显式调用不要求每日签到开关已打开。"""
        adapter, normalized_mode, error = self._prepare_checkin(
            provider, mode, require_enabled=require_enabled
        )
        if error:
            return error
        if not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "message": f"{adapter.name} 签到正在执行，请稍后重试",
            }
        try:
            threading.Thread(
                target=self.run_checkin,
                kwargs={
                    "provider": adapter.key,
                    "trigger": "manual",
                    "mode": normalized_mode,
                    "lock_acquired": True,
                },
                daemon=True,
                name=f"hdhive-dian115-checkin-{adapter.key}",
            ).start()
        except Exception:
            self._run_lock.release()
            raise
        return {
            "success": True,
            "message": f"{adapter.name} 签到任务已提交",
            "data": {
                "provider": adapter.key,
                "mode": normalized_mode,
                "running": True,
            },
        }

    def run_checkin(
            self,
            provider: str,
            trigger: str = "manual",
            mode: str = "",
            lock_acquired: bool = False,
            notify: bool = True,
            require_enabled: bool = True,
    ) -> Dict[str, Any]:
        adapter, normalized_mode, error = self._prepare_checkin(
            provider, mode, require_enabled=require_enabled
        )
        if error:
            if lock_acquired:
                self._run_lock.release()
            return error
        if not lock_acquired and not self._run_lock.acquire(blocking=False):
            return {
                "success": False,
                "message": f"{adapter.name} 签到正在执行，请稍后重试",
            }
        try:
            try:
                client = self._get_checkin_client(adapter)
                result = self._execute_provider_checkin(
                    adapter, client, normalized_mode
                )
                record = self._build_record(
                    adapter, trigger, normalized_mode, result=result
                )
            except Exception as error:
                if not isinstance(error, adapter.error_types):
                    logger.error(
                        f"{adapter.name} 签到异常："
                        f"{type(error).__name__}: {error}"
                    )
                record = self._build_record(
                    adapter, trigger, normalized_mode, error=error
                )
            self._save_history(adapter, record)
            if notify:
                self._notify_checkin(adapter, record)
            log_func = logger.info if record["success"] else logger.warning
            log_func(
                f"{adapter.name} 签到结果："
                f"模式={normalized_mode}，状态={record['status']}，"
                f"积分变化={record['points_change']}，消息={record['message']}"
            )
            return {
                "success": bool(record["success"]),
                "message": record["message"],
                "data": copy.deepcopy(record),
            }
        finally:
            self._run_lock.release()

    def run_quick_checkin(
            self, provider: str = "", mode: str = ""
    ) -> Dict[str, Any]:
        provider_key = str(provider or "").strip().lower()
        if provider_key in {"all", "全部"}:
            provider_key = ""
        if provider_key:
            adapter = self._resolve_provider(provider_key)
            if adapter is None:
                return {"success": False, "message": "不支持的签到提供方"}
            providers = [adapter]
        else:
            providers = self._ready_providers()
        if not providers:
            return {
                "success": False,
                "message": "没有已启用且配置完整的签到渠道",
            }

        requested_mode = str(mode or "").strip().lower()
        if requested_mode and not all(
                requested_mode in item.modes for item in providers
        ):
            supported = sorted({mode for item in providers for mode in item.modes})
            return {
                "success": False,
                "message": f"所选渠道签到模式仅支持 {', '.join(supported)}",
            }
        items = []
        aggregate = not provider_key
        for item in providers:
            result = self.run_checkin(
                provider=item.key,
                trigger="manual",
                mode=requested_mode,
                notify=not aggregate,
                require_enabled=aggregate,
            )
            public_result = dict(result)
            if isinstance(result.get("data"), dict):
                public_result["data"] = self._public_record(result["data"])
            items.append({
                "provider": item.key,
                "provider_name": item.name,
                **public_result,
            })
        if aggregate:
            self._notify_checkin_summary(items, "签到汇总")
        success = bool(items) and all(item.get("success") for item in items)
        if len(items) == 1:
            message = str(items[0].get("message") or "")
            if not message:
                message = "签到完成" if success else "签到失败"
        elif success:
            message = f"已完成 {len(items)} 个渠道签到"
        else:
            message = f"已执行 {len(items)} 个渠道，存在签到失败"
        return {
            "success": success,
            "message": message,
            "data": {"items": items},
        }

    def _ready_providers(self) -> List[CheckinProvider]:
        return [
            provider
            for provider in self._PROVIDERS.values()
            if bool(getattr(
                self._owner, f"_{provider.key}_checkin_enabled", False
            ))
            and self._checkin_credentials_ready(provider)
        ]

    def run_scheduled_checkins(self) -> Dict[str, Any]:
        if not self._schedule_lock.acquire(blocking=False):
            return {
                "success": False,
                "message": "签到调度正在执行",
                "data": {"skipped": True, "items": []},
            }
        try:
            providers = self._ready_providers()
            if not providers:
                return {
                    "success": True,
                    "message": "没有需要执行的签到渠道",
                    "data": {"items": []},
                }
            results = []
            for provider in providers:
                result = self.run_checkin(
                    provider=provider.key,
                    trigger="scheduled",
                    notify=False,
                )
                results.append({
                    "provider": provider.key,
                    "provider_name": provider.name,
                    **result,
                })
            self._notify_checkin_summary(results, "签到汇总")
            success = bool(results) and all(
                item.get("success") for item in results
            )
            return {
                "success": success,
                "message": (
                    f"已完成 {len(results)} 个渠道签到"
                    if success else f"已执行 {len(results)} 个渠道，存在签到失败"
                ),
                "data": {"items": results},
            }
        finally:
            self._schedule_lock.release()

    def close(self) -> None:
        for client in (self._hdhive_web_client, self._dian115_client):
            if client is None:
                continue
            try:
                client.close()
            except Exception as error:
                logger.debug(f"关闭签到客户端失败：{error}")
        self._hdhive_web_client = None
        self._dian115_client = None
