# -*- coding: utf-8 -*-
"""插件配置默认值与归一化。"""

DEFAULT_CONFIG = {
    # 总开关
    "enabled": True,
    # 定时任务表达式（5 段 cron，默认每月 1/8/15/22/29 日 03:00）
    "cron": "0 3 */7 * *",
    # cross-seed 链接根目录（TR 的 downloadDir 在该目录下的种子视为待回迁对象）
    "cs_root": "/机械/Cross-Seed",
    # preview=只预演（默认，安全阀）；apply=真正执行 set-location 回迁
    "apply_mode": "preview",
    # 目标路径优先级（每行一个前缀，越靠前越优先）
    "path_priority": "/机械/download\n/机械/不可说保种",
    # 候选源排除前缀（每行一个）
    "path_exclude": "/机械/刷流",
    # 单轮上限：0 = 不限制；三者可同时生效，先到先停
    "cap_count": 0,
    "cap_size_gb": 0,
    "cap_minutes": 0,
    # 单个种子校验（recheck）等待超时，分钟
    # 改路径后 TR 会重新校验该种子；超过这个时间还没校验完并恢复做种就判失败并回滚。
    # 太小 → 大种子被误判失败；太大 → 卡死的种子会拖长整轮（可用 cap_minutes 兜底）
    "single_timeout_min": 60,
    # 找不到源（季包聚合/源已删除）时保留 cross-seed 标签作为标记
    "keep_label_on_no_source": True,
    # 未做种文件清理
    "cleanup_enabled": False,
    "cleanup_dry_run": True,
    "cleanup_min_age_hours": 12,
    # 通知开关：只在对应事件非空时推送
    "notify_success": True,
    "notify_failure": True,
    "notify_rollback": True,
    # 指定下载器名称；留空则自动选择第一个启用的 Transmission
    "tr_name": "",
}

_BOOL_KEYS = {k for k, v in DEFAULT_CONFIG.items() if isinstance(v, bool)}
_INT_KEYS = {k for k, v in DEFAULT_CONFIG.items() if isinstance(v, int) and not isinstance(v, bool)}
_STR_KEYS = {k for k, v in DEFAULT_CONFIG.items() if isinstance(v, str)}


def _to_bool(value, default):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "y"):
        return True
    if text in ("0", "false", "no", "off", "n", ""):
        return False
    return default


def _to_int(value, default):
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def normalize_config(conf):
    """把持久化配置与默认值合并，并做类型归一。"""
    conf = conf if isinstance(conf, dict) else {}
    result = {}
    for key, default in DEFAULT_CONFIG.items():
        value = conf.get(key, default)
        if key in _BOOL_KEYS:
            result[key] = _to_bool(value, default)
        elif key in _INT_KEYS:
            result[key] = max(0, _to_int(value, default))
        elif key in _STR_KEYS:
            result[key] = "" if value is None else str(value).strip()
        else:
            result[key] = value
    if result["apply_mode"] not in ("preview", "apply"):
        result["apply_mode"] = "preview"
    result["cron"] = result["cron"] or DEFAULT_CONFIG["cron"]
    result["cs_root"] = result["cs_root"] or DEFAULT_CONFIG["cs_root"]
    return result
