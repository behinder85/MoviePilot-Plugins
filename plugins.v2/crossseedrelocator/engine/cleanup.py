# -*- coding: utf-8 -*-
"""链接目录清理：删除 Cross-Seed 下没有被任何种子引用的文件与空目录。"""
import os
import posixpath
import time
from collections import Counter

from .util import human_size, is_under, join_path, norm


def build_protected(torrents):
    """构建保护集：所有种子的保存目录 + 所有种子文件路径引用计数。"""
    protected_roots = set()
    references = Counter()
    for torrent in torrents:
        dl = norm(torrent.get("downloadDir"))
        if dl:
            protected_roots.add(dl)
        for item in torrent.get("files") or []:
            references[join_path(dl, item.get("name") or "")] += 1
    return protected_roots, references


def run_cleanup(cfg, torrents, dry_run=True, log=None):
    """扫描并（可选）删除链接目录中的未引用文件。"""
    cs_root = norm(cfg.get("cs_root"))
    min_age = int(cfg.get("cleanup_min_age_hours") or 0) * 3600
    protected_roots, references = build_protected(torrents)
    report = {
        "cs_root": cs_root,
        "dry_run": bool(dry_run),
        "readable": bool(cs_root) and os.path.isdir(cs_root),
        "scanned_files": 0,
        "scanned_bytes": 0,
        "protected_files": 0,
        "deletable_files": 0,
        "deletable_bytes": 0,
        "deleted_files": 0,
        "deleted_bytes": 0,
        "removed_dirs": 0,
        "errors": [],
        "sample": [],
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "message": "",
    }
    if log:
        log.info("开始清理扫描 %s（dry_run=%s）" % (cs_root, dry_run))
    if not report["readable"]:
        report["message"] = "链接目录当前不可访问（容器未挂载或路径错误），已跳过"
        return report

    now = time.time()
    for root, _dirs, files in os.walk(cs_root, topdown=False):
        root_path = norm(root)
        if not is_under(root_path, cs_root):
            continue
        for name in files:
            path = norm(posixpath.join(root_path, name))
            if not is_under(path, cs_root):
                continue
            try:
                stat = os.stat(path)
            except OSError as err:
                report["errors"].append("%s：%s" % (path, err))
                continue
            report["scanned_files"] += 1
            report["scanned_bytes"] += stat.st_size
            if references.get(path, 0) > 0:
                report["protected_files"] += 1
                continue
            if any(is_under(path, item) for item in protected_roots):
                report["protected_files"] += 1
                continue
            if min_age and now - stat.st_mtime < min_age:
                report["protected_files"] += 1
                continue
            report["deletable_files"] += 1
            report["deletable_bytes"] += stat.st_size
            if len(report["sample"]) < 200:
                report["sample"].append(path)
            if not dry_run:
                try:
                    os.remove(path)
                    report["deleted_files"] += 1
                    report["deleted_bytes"] += stat.st_size
                except OSError as err:
                    report["errors"].append("%s：%s" % (path, err))

    if not dry_run:
        for root, _dirs, _files in os.walk(cs_root, topdown=False):
            root_path = norm(root)
            if root_path == cs_root or not is_under(root_path, cs_root):
                continue
            try:
                os.rmdir(root_path)
                report["removed_dirs"] += 1
            except OSError:
                pass

    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    report["deletable_human"] = human_size(report["deletable_bytes"])
    report["deleted_human"] = human_size(report["deleted_bytes"])
    if log:
        log.info(
            "清理扫描完成：扫描 %d 个文件，可删 %d 个(%s)，已删 %d 个(%s)，错误 %d 条"
            % (
                report["scanned_files"],
                report["deletable_files"],
                report["deletable_human"],
                report["deleted_files"],
                report["deleted_human"],
                len(report["errors"]),
            )
        )
    return report
