"""搜索渠道共用的 Cloudflare 页面识别与浏览器操作。"""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse, urlsplit

from app.core.config import settings
from app.helper.browser import PlaywrightHelper
from app.log import logger

try:
    from cloakbrowser import launch_context
except ImportError:
    launch_context = None

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
    if headers.get("cf-mitigated") == "challenge":
        return True
    if any(marker in lowered for marker in (
        "cf-chl-", "challenges.cloudflare.com",
        "cdn-cgi/challenge-platform", "enable javascript and cookies",
        "<title>just a moment",
    )):
        return True
    # 若返回有效 JSON 业务响应，不能因为 server: cloudflare 就误判为 CF 质询
    content_type = headers.get("content-type", "")
    stripped = lowered.strip()
    if "json" in content_type or (stripped.startswith("{") and stripped.endswith("}")):
        return False
    return (
            status_code in {403, 503}
            and headers.get("server") == "cloudflare"
            and any(marker in lowered for marker in (
        "cloudflare", "attention required", "error 1020", "ray id:", "access denied"
    ))
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
    if launch_context is None:
        raise RuntimeError("未安装 cloakbrowser，无法拉起反盾浏览器上下文")
    return launch_context(
        headless=True, proxy=browser_proxy(proxy),
        humanize=getattr(settings, "CLOAKBROWSER_HUMANIZE", True),
        human_preset="careful",
    )


def playwright_snapshot(url: str, proxy: Any, timeout: int, gate):
    """使用平台浏览器获取页面和同一浏览器会话的 Cookie/UA。"""

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


_CF_SOLVE_LOCK = threading.Lock()


def is_cloudflare_response(response: Any) -> bool:
    """统一判断 HTTP 响应是否命中 Cloudflare 拦截质询页。"""
    if response is None:
        return False
    try:
        status = int(getattr(response, "status_code", 0) or 0)
        headers = getattr(response, "headers", {}) or {}
        if str(headers.get("cf-mitigated") or "").lower() == "challenge":
            return True
        if status in {403, 503}:
            server = str(headers.get("server") or "").lower()
            if "cloudflare" in server:
                body = ""
                try:
                    body = str(getattr(response, "text", "") or "")[:4096]
                except Exception:
                    pass
                return is_cloudflare_challenge(text=body, status_code=status, headers=headers)
    except Exception:
        pass
    return False


class CloudflareChallengeSolver:
    """复用常驻轻量浏览器，穿透 Cloudflare 质询盾并提取凭证与页面。"""

    def __init__(self):
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="CF-Challenge-Pool"
        )
        self._context = None
        self._page = None
        self._current_proxy = None
        self._user_agent = ""
        self._lock = threading.RLock()

    def _prepare_page(self, proxy: Any):
        if self._context is not None and self._current_proxy != proxy:
            self._close_browser()

        if self._page is not None and not self._page.is_closed():
            return self._page

        self._close_browser()
        self._current_proxy = proxy
        self._context = launch_challenge_context(proxy)
        self._page = self._context.new_page()
        try:
            self._user_agent = str(self._page.evaluate("navigator.userAgent") or "").strip()
        except Exception:
            self._user_agent = ""

        # 静态资源请求拦截：过滤图片、多媒体、字体等无关资源，大幅降低网络开销与渲染耗时
        def _route_filter(route):
            try:
                res_type = route.request.resource_type
                if res_type in {"image", "media", "font"}:
                    route.abort()
                    return
            except Exception:
                pass
            try:
                route.continue_()
            except Exception:
                pass

        try:
            self._page.route("**/*", _route_filter)
        except Exception:
            pass

        return self._page

    def _solve(self, url: str, proxy: Any, timeout: int) -> Optional[Dict[str, Any]]:
        started = time.monotonic()
        deadline = started + max(15, int(timeout or 35))
        page = self._prepare_page(proxy)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        passed = False
        while time.monotonic() < deadline:
            try:
                title = page.title()
            except Exception:
                page.wait_for_timeout(300)
                continue

            title_lower = title.lower()
            cookies = self._context.cookies()
            has_cf = any(c.get("name") == "cf_clearance" for c in cookies)

            if (
                    has_cf
                    and "just a moment" not in title_lower
                    and "attention required" not in title_lower
                    and len(title.strip()) > 0
            ):
                passed = True
                break

            click_challenge_frame(page)
            page.wait_for_timeout(400)

        if not passed:
            self._close_browser()
            return None

        ua = self._user_agent
        if not ua:
            for _ in range(5):
                try:
                    ua = str(page.evaluate("navigator.userAgent") or "").strip()
                    if ua:
                        self._user_agent = ua
                        break
                except Exception:
                    page.wait_for_timeout(200)

        content = ""
        try:
            content = page.content() or ""
        except Exception:
            pass

        return {
            "cookies": self._context.cookies(),
            "user_agent": ua,
            "html": content,
        }

    def solve(
            self, url: str, proxy: Any = None, timeout: int = 35
    ) -> Optional[Dict[str, Any]]:
        if launch_context is None:
            return None
        host = urlsplit(url).netloc or url
        logger.info(f"Cloudflare: 检测到安全质询拦截 [{host}]，正在拉起反盾浏览器自动过盾...")
        started = time.monotonic()
        with self._lock:
            try:
                result = self._executor.submit(
                    self._solve, url, proxy, timeout
                ).result(timeout=timeout + 20)
                elapsed = time.monotonic() - started
                if result and result.get("cookies"):
                    logger.info(
                        f"Cloudflare: 自动过盾成功 [{host}]，已提取凭证与指纹（耗时 {elapsed:.2f}s）"
                    )
                else:
                    logger.warning(
                        f"Cloudflare: 自动过盾未通过或超时 [{host}]（耗时 {elapsed:.2f}s）"
                    )
                return result
            except Exception as e:
                elapsed = time.monotonic() - started
                logger.warning(
                    f"Cloudflare: 自动过盾异常 [{host}]：{e}（耗时 {elapsed:.2f}s）"
                )
                try:
                    self._executor.submit(self._close_browser).result(timeout=5)
                except Exception:
                    pass
                return None

    def _close_browser(self) -> None:
        context, self._context = self._context, None
        self._page = None
        self._user_agent = ""
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self._executor.submit(self._close_browser).result(timeout=5)
        except Exception:
            pass


_SOLVER_INSTANCE: Optional[CloudflareChallengeSolver] = None
_SOLVER_LOCK = threading.Lock()


def get_cloudflare_solver() -> CloudflareChallengeSolver:
    global _SOLVER_INSTANCE
    if _SOLVER_INSTANCE is None:
        with _SOLVER_LOCK:
            if _SOLVER_INSTANCE is None:
                _SOLVER_INSTANCE = CloudflareChallengeSolver()
    return _SOLVER_INSTANCE


def solve_cloudflare_challenge(
        url: str, proxy: Any = None, timeout: int = 35
) -> Optional[Dict[str, Any]]:
    """在常驻单例轻量浏览器池中穿透 Cloudflare 盾，提取 cookies、user_agent 与页面 HTML。"""
    return get_cloudflare_solver().solve(url, proxy=proxy, timeout=timeout)


def bypass_cloudflare_session(
        session: Any, url: str, proxy: Any = None, timeout: int = 35
) -> bool:
    """自动穿透 Cloudflare 盾并将 cf_clearance 与匹配的 User-Agent 注入到 Session。"""
    if session is None or not url:
        return False
    data = solve_cloudflare_challenge(url, proxy=proxy, timeout=timeout)
    if not data:
        return False

    ua = str(data.get("user_agent") or "").strip()
    if ua and hasattr(session, "headers"):
        session.headers["user-agent"] = ua
        session.headers["User-Agent"] = ua

    parsed = urlsplit(url)
    default_domain = f".{parsed.hostname}" if parsed.hostname else ""

    cookies = data.get("cookies") or []
    for c in cookies:
        name = str(c.get("name") or "").strip()
        val = str(c.get("value") or "").strip()
        if not name:
            continue
        raw_domain = str(c.get("domain") or default_domain).strip()
        domain = raw_domain if raw_domain.startswith(".") or raw_domain == "localhost" else f".{raw_domain}"
        try:
            session.cookies.set(
                name, val,
                domain=domain,
                path=str(c.get("path") or "/"),
                secure=bool(c.get("secure", True)),
            )
            if domain.startswith(".") and len(domain) > 1:
                session.cookies.set(
                    name, val,
                    domain=domain.lstrip("."),
                    path=str(c.get("path") or "/"),
                    secure=bool(c.get("secure", True)),
                )
        except Exception:
            pass
    return True


def fetch_cloudflare_html(url: str, proxy: Any = None, timeout: int = 35) -> str:
    """在独立线程拉起反盾浏览器穿透 Cloudflare 盾并获取渲染后的 HTML 内容。"""
    data = solve_cloudflare_challenge(url, proxy=proxy, timeout=timeout)
    if not data or not data.get("html"):
        raise TimeoutError("Cloudflare 验证等待超时")
    return str(data["html"])
