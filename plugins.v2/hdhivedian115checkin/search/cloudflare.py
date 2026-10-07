"""搜索渠道共用的 Cloudflare 页面识别与浏览器操作。"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional
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


def block_heavy_resources(page) -> None:
    """拦截图片、多媒体与字体等无关资源，降低带宽与渲染耗时。"""

    def _route_filter(route):
        try:
            url = str(route.request.url or "").lower()
            if "challenges.cloudflare.com" in url or "cloudflare" in url:
                route.continue_()
                return
            if route.request.resource_type in {"image", "media", "font"}:
                route.abort()
                return
        except Exception:
            pass
        try:
            route.continue_()
        except Exception:
            pass

    try:
        page.route("**/*", _route_filter)
    except Exception:
        pass


#: 本地 Turnstile 挂载页：渠道用它渲染官方组件并换取一次性 token。
TURNSTILE_MOUNT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" defer></script>
</head><body><div id="verification" style="margin:80px"></div></body></html>"""

_TURNSTILE_RENDER_TEMPLATE = """
({siteKey, action}) => {
    const stateName = '__STATE__';
    const previous = window[stateName];
    try {
        if (previous && previous.widget !== undefined) window.turnstile.remove(previous.widget);
    } catch (e) {}
    const state = {token: '', error: '', interactive: false};
    window[stateName] = state;
    state.widget = window.turnstile.render('#verification', {
        sitekey: siteKey, action: action || 'login', theme: 'light', language: 'zh-CN',
        appearance: 'interaction-only', execution: 'execute',
        'response-field': false,
        callback: token => { state.token = token; },
        'error-callback': code => { state.error = String(code || 'verification_failed'); },
        'expired-callback': () => { state.error = 'token_expired'; },
        'timeout-callback': () => { state.error = 'verification_timeout'; },
        'before-interactive-callback': () => { state.interactive = true; }
    });
    window.turnstile.execute(state.widget);
}
"""


def turnstile_render_script(state_name: str) -> str:
    """生成渲染并执行 Turnstile 的页面脚本；``state_name`` 为状态全局变量名。"""
    return _TURNSTILE_RENDER_TEMPLATE.replace("__STATE__", str(state_name or "verification"))


def mount_turnstile_page(page, url: str) -> None:
    """把本地 Turnstile 挂载页注入指定地址，并等待官方脚本就绪。"""
    page.route(
        url,
        lambda route: route.fulfill(
            status=200, content_type="text/html", body=TURNSTILE_MOUNT_HTML
        ),
    )
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        "() => typeof window.turnstile?.render === 'function'", timeout=30000
    )


class BrowserPageSession:
    """常驻轻量反盾浏览器页：统一 stealth 上下文、资源拦截与人机验证交互。

    浏览器对象只在会话线程内创建和使用（Playwright 同步 API 有线程亲和性），
    调用方通过 :meth:`run` 提交自己的页面流程；代理变更或流程异常时自动重建会话。
    """

    def __init__(
            self,
            name: str,
            proxy: Any = None,
            timeout: int = 30,
            prepare: Optional[Any] = None,
    ) -> None:
        self._name = str(name or "浏览器会话")
        self._proxy = proxy
        self._timeout = max(5, int(timeout or 30))
        self._prepare = prepare
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._name}-Browser"
        )
        self._context = None
        self._page = None
        self._current_proxy = None
        self._generation = 0
        self._lock = threading.RLock()

    @property
    def timeout_ms(self) -> int:
        return max(5000, self._timeout * 1000)

    @property
    def page_generation(self) -> int:
        """页面重建代数；调用方据此判断本次是否复用了既有会话。"""
        with self._lock:
            return self._generation

    def click_challenge(self) -> bool:
        """在会话线程内点击 Cloudflare / Turnstile 复选框。"""
        page = self._page
        if page is None:
            return False
        return click_challenge_frame(page)

    def run(self, callback: Any, proxy: Any = None, wait_timeout: float = 0) -> Any:
        """在会话线程内执行页面流程 ``callback(page)``。"""
        target_proxy = self._proxy if proxy is None else proxy
        budget = float(wait_timeout or 0) or (self._timeout + 60)
        future = self._executor.submit(self._run, callback, target_proxy)
        return future.result(timeout=budget)

    def _run(self, callback: Any, proxy: Any) -> Any:
        with self._lock:
            page = self._ensure_page(proxy)
            try:
                return callback(page)
            except Exception:
                self._close_locked()
                raise

    def _ensure_page(self, proxy: Any):
        if self._context is not None and self._current_proxy != proxy:
            self._close_locked()
        if self._page is not None and not self._page.is_closed():
            return self._page

        self._close_locked()
        self._current_proxy = proxy
        self._context = launch_challenge_context(proxy)
        self._page = self._context.new_page()
        try:
            self._page.set_default_timeout(self.timeout_ms)
        except Exception:
            pass
        block_heavy_resources(self._page)
        self._generation += 1
        if self._prepare is not None:
            self._prepare(self._page)
        return self._page

    def _close_locked(self) -> None:
        context, self._context = self._context, None
        self._page = None
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self._executor.submit(self._close_locked).result(timeout=5)
        except Exception:
            pass


def turnstile_page_token(
        page,
        site_key: str,
        action: str,
        *,
        state_name: str,
        label: str = "",
        deadline: float = 45.0,
        click_challenge: Optional[Any] = None,
) -> str:
    """在给定页面上渲染并执行 Turnstile，轮询取回一次性 token。

    供已经在会话线程内持有页面的渠道直接调用（避免嵌套会话执行）。
    """
    tag = str(label or "Turnstile")
    page.evaluate(
        turnstile_render_script(state_name),
        {"siteKey": site_key, "action": action},
    )
    clicked = False
    end = time.monotonic() + max(5.0, float(deadline or 45.0))
    while time.monotonic() < end:
        state = page.evaluate(f"() => window.{state_name} || {{}}") or {}
        token = str(state.get("token") or "")
        if token:
            page.evaluate(
                "(name) => { try { const s = window[name];"
                " if (s && s.widget !== undefined) window.turnstile.remove(s.widget); }"
                " catch (e) {} window[name] = null; }",
                state_name,
            )
            return token
        error = str(state.get("error") or "")
        if error:
            raise RuntimeError(f"{tag} Cloudflare 验证失败：{error}")
        if state.get("interactive") and not clicked and click_challenge is not None:
            clicked = bool(click_challenge())
        page.wait_for_timeout(200)
    raise TimeoutError(f"{tag} Cloudflare 验证超过 {int(deadline)} 秒")


def mint_turnstile_token(
        session: BrowserPageSession,
        site_key: str,
        action: str,
        *,
        state_name: str,
        label: str = "",
        deadline: float = 45.0,
        wait_timeout: float = 0,
) -> str:
    """在常驻浏览器会话中渲染并执行 Turnstile，返回一次性 token。"""
    started = time.monotonic()
    generation = session.page_generation
    tag = str(label or "Turnstile")

    def _flow(page) -> str:
        token = turnstile_page_token(
            page,
            site_key,
            action,
            state_name=state_name,
            label=tag,
            deadline=deadline,
            click_challenge=session.click_challenge,
        )
        logger.debug(
            f"{tag} Turnstile 就绪：action={action}，"
            f"复用={generation == session.page_generation}，"
            f"耗时={time.monotonic() - started:.2f}s"
        )
        return token

    return session.run(
        _flow, wait_timeout=wait_timeout or (float(deadline or 45.0) + 30.0)
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
        self._session = BrowserPageSession("CF-Challenge", timeout=35)

    def _solve(self, url: str, proxy: Any, timeout: int) -> Optional[Dict[str, Any]]:
        started = time.monotonic()
        deadline = started + max(15, int(timeout or 35))

        def _flow(page) -> Dict[str, Any]:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            passed = False
            while time.monotonic() < deadline:
                try:
                    title = page.title()
                except Exception:
                    page.wait_for_timeout(300)
                    continue

                title_lower = title.lower()
                cookies = page.context.cookies()
                has_cf = any(c.get("name") == "cf_clearance" for c in cookies)

                if (
                        has_cf
                        and "just a moment" not in title_lower
                        and "attention required" not in title_lower
                        and len(title.strip()) > 0
                ):
                    passed = True
                    break

                self._session.click_challenge()
                page.wait_for_timeout(400)

            if not passed:
                raise TimeoutError("Cloudflare 质询未通过")

            user_agent = ""
            for _ in range(5):
                try:
                    user_agent = str(page.evaluate("navigator.userAgent") or "").strip()
                except Exception:
                    user_agent = ""
                if user_agent:
                    break
                page.wait_for_timeout(200)

            content = ""
            try:
                content = page.content() or ""
            except Exception:
                pass

            return {
                "cookies": page.context.cookies(),
                "user_agent": user_agent,
                "html": content,
            }

        try:
            return self._session.run(
                _flow, proxy=proxy, wait_timeout=max(15, int(timeout or 35)) + 20
            )
        except Exception:
            return None

    def solve(
            self, url: str, proxy: Any = None, timeout: int = 35
    ) -> Optional[Dict[str, Any]]:
        if launch_context is None:
            return None
        host = urlsplit(url).netloc or url
        logger.debug(f"Cloudflare: 检测到安全质询拦截 [{host}]，正在拉起反盾浏览器自动过盾...")
        started = time.monotonic()
        result = self._solve(url, proxy, timeout)
        elapsed = time.monotonic() - started
        if result and result.get("cookies"):
            logger.debug(
                f"Cloudflare: 自动过盾成功 [{host}]，已提取凭证与指纹（耗时 {elapsed:.2f}s）"
            )
        else:
            logger.debug(
                f"Cloudflare: 自动过盾未通过或超时 [{host}]（耗时 {elapsed:.2f}s）"
            )
        return result

    def close(self) -> None:
        self._session.close()


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
