"""搜索渠道共享的资源类型定义。"""

import re
from urllib.parse import urlparse

TYPE_ALIASES = {
    "115pan": "115",
    "123pan": "123",
    "ali": "alipan",
    "aliyun": "alipan",
    "189": "tianyi",
    "139": "yun139",
    "magnetlink": "magnet",
}
TYPE_HOSTS = {
    "115": {"115.com", "115cdn.com", "anxia.com"},
    "123": {
        "123pan.com", "123pan.cn", "123.cn", "123684.com", "123685.com",
        "123865.com", "123912.com", "123592.com",
    },
    "quark": {"quark.cn"},
    "alipan": {"alipan.com", "aliyundrive.com", "aliyundrive.net"},
    "tianyi": {"cloud.189.cn"},
    "yun139": {"yun.139.com", "caiyun.feixin.10086.cn"},
    "guangya": {"guangyapan.com"},
}
#: 资源类型的展示元数据：名称、图标、配色、可预览与离线标记。
#: 前端只渲染这里下发的内容，不再自行维护任何类型映射表。
RESOURCE_TYPE_DISPLAY = {
    "115": {"name": "115网盘", "icon": "mdi-cloud", "color": "primary", "previewable": True},
    "123": {"name": "123网盘", "icon": "mdi-cloud-refresh-outline", "color": "purple", "previewable": True},
    "quark": {"name": "夸克网盘", "icon": "mdi-cloud-outline", "color": "amber-darken-3", "previewable": True},
    "alipan": {"name": "阿里云盘", "icon": "mdi-cloud-sync-outline", "color": "blue", "previewable": True},
    "baidu": {"name": "百度网盘", "icon": "mdi-cloud-circle-outline", "color": "indigo", "previewable": True},
    "uc": {"name": "UC网盘", "icon": "mdi-cloud-download-outline", "color": "deep-orange", "previewable": True},
    "tianyi": {"name": "天翼云盘", "icon": "mdi-cloud-check-outline", "color": "teal", "previewable": True},
    "guangya": {"name": "光鸭网盘", "icon": "mdi-cloud-outline", "color": "teal-darken-1", "previewable": True},
    "yun139": {"name": "移动云盘", "icon": "mdi-cloud-arrow-up-outline", "color": "teal-darken-2", "previewable": True},
    "xunlei": {"name": "迅雷网盘", "icon": "mdi-flash", "color": "light-blue-darken-1"},
    "pikpak": {"name": "PikPak", "icon": "mdi-cloud-upload-outline", "color": "deep-purple"},
    "magnet": {"name": "磁力链接", "icon": "mdi-magnet", "color": "red-darken-1", "previewable": True},
    "ed2k": {"name": "电驴链接", "icon": "mdi-link-variant", "color": "blue-grey-darken-1", "offline": True},
    "torrent": {"name": "BT种子", "icon": "mdi-seed", "color": "deep-purple", "previewable": True},
    "cloud": {"name": "网盘路径", "icon": "mdi-folder-network-outline", "color": "blue-grey", "offline": True},
    "share": {"name": "网盘分享", "icon": "mdi-link-variant", "color": "blue-grey"},
    "other": {"name": "其他来源", "icon": "mdi-folder-outline", "color": "blue-grey"},
    "unknown": {"name": "未知", "icon": "mdi-help-circle-outline", "color": "blue-grey"},
}
TYPE_NAMES = {key: value["name"] for key, value in RESOURCE_TYPE_DISPLAY.items()}

SUPPORTED_CLOUD_TYPES = tuple(TYPE_HOSTS)
RESOURCE_TYPE_ORDER = (
    "115", "123", "quark", "guangya", "tianyi", "yun139", "alipan",
    "ed2k", "magnet",
)
SUPPORTED_RESOURCE_TYPES = frozenset(RESOURCE_TYPE_ORDER)
RESOURCE_TYPE_PRIORITY = {
    resource_type: index
    for index, resource_type in enumerate(RESOURCE_TYPE_ORDER)
}
PANSOU_RESOURCE_TYPES = (
    "aliyun", "quark", "guangya", "tianyi", "yun139",
    "115", "123", "magnet", "ed2k",
)
#: 分享提取码的承载方式：写入查询参数，或作为“提取码: xxx”附言。
SHARE_PASSWORD_QUERY_KEYS = {
    "115": "password",
    "123": "pwd",
    "baidu": "pwd",
    "guangya": "code",
}
#: 候选归一化阶段可直接回填的类型键：驱动类型、别名与无驱动的直通类型；
#: share 只是描述性文案，仍需按链接继续判定真实来源。
CANDIDATE_RESOURCE_TYPES = frozenset(
    {*TYPE_NAMES, *TYPE_ALIASES.values(), "uc"} - {"share"}
)
#: 只接受附言、无法参数化提取码的网盘。
TEXT_PASSWORD_TYPES = frozenset({"quark", "alipan", "tianyi", "yun139"})
PREVIEW_PROVIDER_KEYS = {
    "115": "115",
    "123": "123",
    "quark": "quark",
    "guangya": "guangya",
    "tianyi": "tianyi",
    "yun139": "yun139",
    "alipan": "alipan",
}
PREVIEW_RESOURCE_TYPES = frozenset({*PREVIEW_PROVIDER_KEYS, "magnet"})

_TYPE_TEXT_MARKERS = {
    "115": ("115网盘", "115.com", "115cdn.com", "anxia.com"),
    "123": ("123云盘", "123网盘", "123pan"),
    "quark": ("夸克", "quark"),
    "guangya": ("光鸭", "guangya"),
    "tianyi": ("天翼", "cloud.189.cn"),
    "yun139": ("移动云盘", "中国移动云盘", "yun.139.com", "139云盘"),
    "alipan": ("阿里云盘", "阿里网盘", "alipan", "aliyundrive"),
    "ed2k": ("ed2k://", "电驴"),
    "magnet": ("magnet:?", "磁力"),
}


def normalize_resource_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return TYPE_ALIASES.get(normalized, normalized)


def resource_type_from_url(value: str) -> str:
    """根据标准链接 scheme 或域名识别内部资源类型。"""
    target = str(value or "").strip()
    lowered = target.casefold()
    if lowered.startswith("magnet:?"):
        return "magnet"
    if lowered.startswith("ed2k://"):
        return "ed2k"
    try:
        host = str(urlparse(target).hostname or "").casefold()
    except ValueError:
        return ""
    for resource_type, domains in TYPE_HOSTS.items():
        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return resource_type
    return ""


def resource_type_from_text(value: str) -> str:
    """从外部类型值、链接或资源描述中识别内部资源类型。"""
    text = str(value or "").strip()
    normalized = normalize_resource_type(text)
    if normalized in SUPPORTED_RESOURCE_TYPES:
        return normalized
    from_url = resource_type_from_url(text)
    if from_url:
        return from_url
    lowered = text.casefold()
    for resource_type in RESOURCE_TYPE_ORDER:
        if any(marker in lowered for marker in _TYPE_TEXT_MARKERS[resource_type]):
            return resource_type
    return ""


def resource_type_name(value: str, fallback: str = "") -> str:
    normalized = normalize_resource_type(value)
    return TYPE_NAMES.get(normalized) or str(fallback or normalized).strip()


def resource_type_catalog() -> list[dict]:
    """返回资源类型展示目录：顺序、名称、图标、配色与预览/离线标记。"""
    ordered = list(RESOURCE_TYPE_ORDER) + [
        key for key in RESOURCE_TYPE_DISPLAY
        if key not in RESOURCE_TYPE_PRIORITY
    ]
    catalog = []
    for key in ordered:
        meta = RESOURCE_TYPE_DISPLAY.get(key)
        if not meta:
            continue
        catalog.append({
            "value": key,
            "name": meta["name"],
            "icon": meta.get("icon") or "mdi-folder-outline",
            "color": meta.get("color") or "blue-grey",
            "previewable": bool(meta.get("previewable")),
            "offline": bool(meta.get("offline")),
        })
    return catalog


def resource_type_aliases() -> dict:
    """返回外部类型值到内部类型键的别名表。"""
    return dict(TYPE_ALIASES)


def append_share_password(resource_type: str, target: str, password: str) -> str:
    """把提取码附加到分享直链：优先写查询参数，其余网盘以“提取码: xxx”附言。"""
    password = str(password or "").strip()
    normalized = normalize_resource_type(resource_type)
    if not password or normalized in {"magnet", "ed2k"}:
        return target
    key = SHARE_PASSWORD_QUERY_KEYS.get(normalized)
    if not key:
        if normalized in TEXT_PASSWORD_TYPES and "提取码" not in str(target):
            return f"{target} 提取码: {password}"
        return target
    if any(
            re.search(rf"[?&]{name}=", str(target), re.IGNORECASE)
            for name in SHARE_PASSWORD_QUERY_KEYS.values()
    ):
        return target
    return f"{target}{'&' if '?' in str(target) else '?'}{key}={password}"
