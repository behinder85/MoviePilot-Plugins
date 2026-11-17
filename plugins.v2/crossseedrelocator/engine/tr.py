# -*- coding: utf-8 -*-
"""Transmission RPC 客户端（纯标准库实现，便于在 MP 之外做 dry-run 调试）。

关键事实（Transmission 4.0.5）：
- torrent-add 支持 download-dir，但只在添加种子时生效；
- 已存在的种子改保存路径只有 torrent-set-location（必然触发搜索/重新校验）；
- torrent-set 参数表里没有 download-dir。
"""
import base64
import json
import urllib.error
import urllib.request

import os


class TRError(Exception):
    """Transmission RPC 调用失败。"""


def normalize_rpc_url(url):
    """把 host:port / http://host:port 统一成 http://host:port/transmission/rpc。"""
    url = (url or "").strip()
    if not url:
        raise TRError("Transmission 地址为空")
    if not url.lower().startswith("http"):
        url = "http://" + url
    if "/transmission/rpc" not in url:
        url = url.rstrip("/") + "/transmission/rpc"
    return url


class TRClient:
    def __init__(self, url, username="", password="", timeout=60):
        self.url = normalize_rpc_url(url)
        self.username = username or ""
        self.password = password or ""
        self.timeout = timeout
        self.session_id = ""

    def _call(self, method, arguments=None):
        payload = {"method": method, "arguments": arguments or {}}
        data = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(3):
            req = urllib.request.Request(self.url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            if self.session_id:
                req.add_header("X-Transmission-Session-Id", self.session_id)
            if self.username:
                token = base64.b64encode(
                    ("%s:%s" % (self.username, self.password)).encode("utf-8")
                ).decode("ascii")
                req.add_header("Authorization", "Basic " + token)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8", "replace")
                result = json.loads(body)
                if result.get("result") != "success":
                    raise TRError("RPC 返回失败: %s" % (result.get("result") or body[:200]))
                return result.get("arguments") or {}
            except urllib.error.HTTPError as err:
                if err.code == 409 and attempt < 2:
                    session_id = err.headers.get("X-Transmission-Session-Id")
                    if not session_id:
                        raise TRError("409 未返回 X-Transmission-Session-Id")
                    self.session_id = session_id
                    continue
                if err.code == 401:
                    raise TRError("认证失败（401），请检查下载器用户名/密码")
                raise TRError("HTTP %s: %s" % (err.code, err.read()[:300]))
            except urllib.error.URLError as err:
                last_error = err
                raise TRError("连接失败: %s" % (getattr(err, "reason", err)))
            except (ValueError, json.JSONDecodeError):
                raise TRError("返回内容不是合法 JSON")
        raise TRError("RPC 调用失败: %s" % last_error)

    # ---- 常用封装 ----
    def torrent_get(self, fields, ids=None):
        arguments = {"fields": list(fields)}
        if ids:
            arguments["ids"] = list(ids) if not isinstance(ids, (str, int)) else [ids]
        result = self._call("torrent-get", arguments)
        return result.get("torrents") or []

    def torrent_set(self, ids, **kwargs):
        arguments = {"ids": list(ids) if not isinstance(ids, (str, int)) else [ids]}
        arguments.update(kwargs)
        self._call("torrent-set", arguments)
        return True

    def set_location(self, ids, location, move=False):
        self._call(
            "torrent-set-location",
            {
                "ids": list(ids) if not isinstance(ids, (str, int)) else [ids],
                "location": location,
                "move": bool(move),
            },
        )
        return True

    def start(self, ids):
        self._call("torrent-start", {"ids": list(ids) if not isinstance(ids, (str, int)) else [ids]})
        return True

    def stop(self, ids):
        self._call("torrent-stop", {"ids": list(ids) if not isinstance(ids, (str, int)) else [ids]})
        return True

    def session_get(self):
        return self._call("session-get")

    def test(self):
        info = self.session_get()
        result = {
            "version": info.get("version"),
            "rpc_version": info.get("rpc-version"),
            "download_dir": info.get("download-dir"),
            "torrent_count": None,
        }
        try:
            stats = self._call("session-stats")
            result["torrent_count"] = stats.get("torrentCount")
        except Exception:
            pass
        return result


def _pick_transmission(configs, name=""):
    """从 MP 下载器配置中挑一个 Transmission。"""
    if not isinstance(configs, dict) or not configs:
        raise TRError("未找到任何已启用的下载器配置")
    if name:
        conf = configs.get(name)
        if not conf:
            raise TRError("未找到名为 %s 的下载器" % name)
        if str(getattr(conf, "type", "")).lower() != "transmission":
            raise TRError("下载器 %s 不是 Transmission" % name)
        return name, conf
    for conf_name, conf in configs.items():
        if str(getattr(conf, "type", "")).lower() == "transmission":
            return conf_name, conf
    raise TRError("未找到已启用的 Transmission 下载器")


def resolve_tr_config(plugin_conf):
    """解析出 Transmission 的 RPC 地址与凭据。

    优先复用 MoviePilot 中已配置的下载器；脱离 MP 调试时回退到环境变量：
    TR_URL / TR_USER / TR_PASS。
    """
    name = (plugin_conf.get("tr_name") or "").strip()
    try:
        from app.helper.downloader import DownloaderHelper  # type: ignore
    except Exception:
        DownloaderHelper = None  # noqa: N806
    if DownloaderHelper is not None:
        configs = DownloaderHelper().get_configs() or {}
        conf_name, conf = _pick_transmission(configs, name)
        host = str(getattr(conf, "host", "") or "").strip()
        port = getattr(conf, "port", None)
        if not host:
            raise TRError("下载器 %s 未配置地址" % conf_name)
        if port:
            host = "%s:%s" % (host, port)
        return {
            "name": conf_name,
            "url": normalize_rpc_url(host),
            "username": str(getattr(conf, "username", "") or ""),
            "password": str(getattr(conf, "password", "") or ""),
        }
    url = os.environ.get("TR_URL", "").strip()
    if not url:
        raise TRError("无法获取 Transmission 配置（MP 下载器未配置，且未设置 TR_URL 环境变量）")
    return {
        "name": "env",
        "url": normalize_rpc_url(url),
        "username": os.environ.get("TR_USER", ""),
        "password": os.environ.get("TR_PASS", ""),
    }


def client_from_config(plugin_conf, timeout=60):
    conf = resolve_tr_config(plugin_conf)
    client = TRClient(conf["url"], conf["username"], conf["password"], timeout=timeout)
    return conf, client
