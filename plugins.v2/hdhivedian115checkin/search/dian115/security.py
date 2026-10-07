"""Dian115 安全验证与前端路由协议的统一入口。"""

import base64
import time
from typing import Any, Optional

from app.log import logger

from ..cloudflare import (
    BrowserPageSession,
    mint_turnstile_token,
    mount_turnstile_page,
)

_KEY_VERSION = 1
_KEY_MASK = (55, 161, 92, 233)


class Dian115Turnstile:
    """复用轻量浏览器，仅生成 Dian115 接口使用的一次性 Turnstile token。"""

    _STATE_NAME = "dian115Verification"

    def __init__(self, base_url: str, proxy=None):
        self._base_url = str(base_url or "").rstrip("/")
        self._session = BrowserPageSession(
            "Dian115-Turnstile",
            proxy=proxy,
            timeout=30,
            prepare=lambda page: mount_turnstile_page(
                page, f"{self._base_url}/login"
            ),
        )

    def token(self, site_key: str, action: str) -> str:
        if action not in {"portal_login", "portal_unlock"} or not site_key:
            raise ValueError("Dian115 验证参数无效")
        return mint_turnstile_token(
            self._session,
            site_key,
            action,
            state_name=self._STATE_NAME,
            label="Dian115",
            deadline=60,
        )

    def close(self) -> None:
        self._session.close()


def encode_resource_key(
        source: str,
        media_type: str,
        resource_id: Any,
        season: Any = 0,
) -> str:
    """编码门户资源键。"""
    raw = (
        f"{_KEY_VERSION}|{str(source or '').strip().lower()}|"
        f"{str(media_type or '').strip().lower()}|{int(resource_id)}|"
        f"{int(season or 0)}"
    ).encode("utf-8")
    encoded = bytes(value ^ _KEY_MASK[index % len(_KEY_MASK)] for index, value in enumerate(raw))
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def resource_path(media_type: str, tmdb_id: Any, season: Any = 0) -> str:
    return f"/r/{encode_resource_key('tmdb', media_type, tmdb_id, season)}"


def share_path(share_id: Any) -> str:
    return f"/s/{encode_resource_key('share', 'other', share_id)}"


def turnstile_token(client: Any, action: str, allow_browser: bool = True) -> Optional[str]:
    """获取登录/解锁所需的 Turnstile token。"""
    client._check_cooldown()
    cached = client._turnstile_policy
    if not cached or cached[1] <= time.monotonic():
        policy = client._request_json(
            "GET", "/api/portal/auth/policy", "/login", require_login=False
        )
        client._turnstile_policy = (policy, time.monotonic() + 300)
    else:
        policy = cached[0]
    if policy.get("turnstile_enabled") is False:
        return None
    if policy.get("turnstile_enabled") is not True:
        raise client.error_type("Dian115 未返回 Cloudflare 验证策略", code="schema_changed")
    site_key = str(policy.get("turnstile_site_key") or "").strip()
    if not site_key:
        raise client.error_type("Dian115 未返回 Cloudflare site key", code="schema_changed")
    if not allow_browser:
        raise client.error_type(
            "Dian115 登录需要 Cloudflare 验证，请先刷新账户登录状态",
            code="browser_login_forbidden",
        )
    try:
        if client._turnstile is None:
            client._turnstile = Dian115Turnstile(client.base_url, client._proxies)
        token = client._turnstile.token(site_key, action)
        if not token:
            raise RuntimeError("Cloudflare 未返回验证 token")
        return token
    except ImportError as error:
        raise client.error_type(
            "Dian115 Cloudflare 验证需要 CloakBrowser 浏览器环境",
            code="browser_unavailable",
        ) from error
    except TimeoutError as error:
        raise client.error_type("Dian115 Cloudflare 验证超时", code="turnstile_timeout") from error
    except RuntimeError as error:
        raise client.error_type(str(error), code="turnstile_failed") from error
    except Exception as error:
        raise client.error_type(
            f"Dian115 Cloudflare 验证失败：{type(error).__name__}", code="turnstile_failed"
        ) from error


__all__ = [
    "Dian115Turnstile",
    "encode_resource_key",
    "resource_path",
    "share_path",
    "turnstile_token",
]
