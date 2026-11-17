# -*- coding: utf-8 -*-
"""通用工具：路径判定、数量格式化。

说明：这里的路径全部是 Transmission（Linux 容器）视角的绝对路径，
因此统一使用 posixpath 处理，避免在 Windows 上调试时出现分隔符不一致。
"""
import posixpath
import time


def norm(path):
    """规范化 TR 路径（POSIX 风格）。"""
    if not path:
        return ""
    p = str(path).strip().replace("\\", "/")
    p = posixpath.normpath(p)
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def is_under(path, root):
    """判断 path 是否位于 root 目录内（含 root 本身）。"""
    p = norm(path)
    r = norm(root)
    if not p or not r:
        return False
    if p == r:
        return True
    if not r.endswith("/"):
        r += "/"
    return p.startswith(r)


def join_path(download_dir, relative):
    """把 downloadDir 与种子内的相对路径拼成绝对路径。"""
    if not download_dir:
        return norm(relative)
    return norm(posixpath.join(download_dir, relative or ""))


def split_lines(text):
    """把多行文本配置切成去空行列表。"""
    if not text:
        return []
    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in raw.split("\n") if line.strip()]


def human_size(size):
    try:
        size = float(size)
    except (TypeError, ValueError):
        return "-"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    if idx == 0:
        return "%d%s" % (int(size), units[idx])
    return "%.2f%s" % (size, units[idx])


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def now_ts():
    return int(time.time())
