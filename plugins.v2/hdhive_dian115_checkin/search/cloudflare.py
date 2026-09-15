"""搜索渠道共用的 Cloudflare 页面识别与浏览器操作。"""

from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse, urlsplit

from .http_client import normalize_proxies


def browser_proxy(proxy: Any) -> Optional[Dict[str, str]]:
    """将请求代理转换成 Playwright/CloakBrowser 的代理配置。"""
    proxies = normalize_proxies(proxy) or {}
    address = proxies.get("https") or proxies.get("http")
    if not address:
        return None
    parsed = urlparse(str(address))
    if not parsed.scheme or not parsed.hostname:
        return None
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    server = f"{parsed.scheme}://{host}"
    if parsed.port:
        server += f":{parsed.port}"
    result = {"server": server}
    if parsed.username:
        result["username"] = unquote(parsed.username)
    if parsed.password:
        result["password"] = unquote(parsed.password)
    return result


def is_cloudflare_challenge(text: str = "", status_code: int = 200,
                            headers: Optional[dict] = None) -> bool:
    headers = {str(key).lower(): str(value).lower()
               for key, value in (headers or {}).items()}
    lowered = str(text or "").lower()
    return (
            headers.get("cf-mitigated") == "challenge"
            or any(marker in lowered for marker in (
        "cf-chl-", "challenges.cloudflare.com",
        "cdn-cgi/challenge-platform", "enable javascript and cookies",
        "<title>just a moment",
    ))
            or (status_code in {403, 503} and headers.get("server") == "cloudflare")
    )


def click_challenge_frame(page) -> bool:
    """仅点击可见的 Cloudflare 验证框；页面轮询由渠道控制。"""
    for frame in page.frames:
        if urlsplit(frame.url).hostname != "challenges.cloudflare.com":
            continue
        try:
            element = frame.frame_element()
            if not element.is_visible():
                continue
            box = element.bounding_box()
            if box and box["width"] >= 60 and box["height"] >= 30:
                page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
                return True
        except Exception:
            continue
    return False


def launch_challenge_context(proxy: Any):
    from app.core.config import settings
    from cloakbrowser import launch_context

    return launch_context(
        headless=True, proxy=browser_proxy(proxy),
        humanize=getattr(settings, "CLOAKBROWSER_HUMANIZE", True),
        human_preset="careful",
    )


def playwright_snapshot(url: str, proxy: Any, timeout: int, gate):
    """使用平台浏览器获取页面和同一浏览器会话的 Cookie/UA。"""
    from app.helper.browser import PlaywrightHelper

    def snapshot(page):
        return {
            "text": page.content() or "",
            "cookies": page.context.cookies(),
            "user_agent": page.evaluate("navigator.userAgent") or "",
        }

    return gate.run(lambda: PlaywrightHelper().action(
        url=url, callback=snapshot, proxies=browser_proxy(proxy),
        headless=True, timeout=timeout,
    ))
