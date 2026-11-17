# -*- coding: utf-8 -*-
"""目标路径推断：为 cross-seed 注入的种子找回它的原始保存路径。

匹配口径：不做模糊匹配，只认「种子内文件清单（相对路径 + 字节长度）完全一致」的源，
且源目录里的文件必须真实存在；多个源按 path_priority 排序取最优。

性能设计：先用不含 files 的全库快照做体积分组，只对体积相同的少量候选拉取 files，
避免一次性把 4 万多个种子的文件列表全部读进内存。
"""
import os

from .util import is_under, join_path, norm, split_lines

LABEL_CS = "cross-seed"

BRIEF_FIELDS = [
    "id",
    "name",
    "hashString",
    "downloadDir",
    "labels",
    "percentDone",
    "status",
    "error",
    "errorString",
    "totalSize",
    "addedDate",
    "doneDate",
]

TARGET_FIELDS = BRIEF_FIELDS + ["files"]


def signature(torrent):
    """种子文件签名：sorted[(相对路径, 长度)]。"""
    result = []
    for item in torrent.get("files") or []:
        try:
            length = int(item.get("length") or 0)
        except (TypeError, ValueError):
            length = 0
        result.append((str(item.get("name") or ""), length))
    result.sort()
    return tuple(result)


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _priority_index(download_dir, prefixes):
    for idx, prefix in enumerate(prefixes):
        if is_under(download_dir, prefix):
            return idx
    return len(prefixes) + 1


def _excluded(download_dir, excludes):
    for prefix in excludes:
        if is_under(download_dir, prefix):
            return True
    return False


def files_present(download_dir, files):
    """校验源目录中每个文件都存在且大小一致。"""
    if not download_dir or not files:
        return False, "文件列表为空"
    for item in files:
        path = join_path(download_dir, item.get("name") or "")
        try:
            stat = os.stat(path)
        except OSError:
            return False, "缺少文件：%s" % path
        expected = _to_int(item.get("length"))
        if expected and int(stat.st_size) != expected:
            return False, "大小不一致：%s" % path
    return True, ""


def _item_of(torrent):
    return {
        "id": _to_int(torrent.get("id")),
        "name": str(torrent.get("name") or ""),
        "hash": str(torrent.get("hashString") or ""),
        "size": _to_int(torrent.get("totalSize")),
        "current_dir": norm(torrent.get("downloadDir")),
        "labels": list(torrent.get("labels") or []),
        "added_date": _to_int(torrent.get("addedDate")),
        "status": "unknown",
        "reason": "",
        "target_dir": "",
        "source_id": None,
        "source_name": "",
        "source_dir": "",
        "candidate_count": 0,
    }


def _is_candidate(torrent, cs_root, excludes):
    dl = norm(torrent.get("downloadDir"))
    if not dl or not cs_root:
        return False
    if is_under(dl, cs_root):
        return False
    if _excluded(dl, excludes):
        return False
    if _to_float(torrent.get("percentDone")) < 0.9999:
        return False
    if _to_int(torrent.get("error")) != 0:
        return False
    if _to_int(torrent.get("status")) in (3, 4):
        return False
    return True


def _rank(candidates, prefixes):
    def key(torrent):
        dl = norm(torrent.get("downloadDir"))
        return (_priority_index(dl, prefixes), _to_int(torrent.get("addedDate")), len(dl))

    return sorted(candidates, key=key)


def _pick_best(target, candidates, cfg, fs_ok, priorities):
    """从候选源中挑出最合适的一个，返回 (best, reason, candidate_count)。"""
    ranked = _rank(candidates, priorities)
    target_sig = signature(target)
    matched = []
    for candidate in ranked:
        if _to_int(candidate.get("id")) == _to_int(target.get("id")):
            continue
        if candidate.get("files") is None:
            continue
        if signature(candidate) != target_sig:
            continue
        matched.append(candidate)
    reason = ""
    for candidate in matched:
        if fs_ok:
            ok, why = files_present(norm(candidate.get("downloadDir")), candidate.get("files"))
            if not ok:
                reason = why
                continue
        return candidate, "", len(matched)
    return None, reason, len(matched)


def _new_stats(total):
    return {
        "torrents": total,
        "targets": 0,
        "ready": 0,
        "no_source": 0,
        "waiting": 0,
        "fs_checked": False,
    }


def _waiting_item(item, reason):
    item.update(status="waiting", reason=reason)
    return item


def build_plan_phased(client, cfg, journal=None, brief=None):
    """两阶段快照：全库简表 + 仅相关种子的文件列表。

    brief 可由调用方预先取好复用，避免重复拉一次全库。
    """
    cs_root = norm(cfg.get("cs_root"))
    priorities = split_lines(cfg.get("path_priority"))
    excludes = split_lines(cfg.get("path_exclude"))
    fs_ok = bool(cs_root) and os.path.isdir(cs_root)

    if brief is None:
        brief = client.torrent_get(BRIEF_FIELDS)
    stats = _new_stats(len(brief))
    stats["fs_checked"] = fs_ok
    targets = []
    for torrent in brief:
        if cs_root and is_under(norm(torrent.get("downloadDir")), cs_root):
            targets.append(torrent)
    stats["targets"] = len(targets)
    if not targets:
        return {"items": [], "stats": stats, "cs_root": cs_root, "fs_checked": fs_ok}

    # 1) 目标种子的文件列表
    target_files = {}
    for torrent in targets:
        tid = torrent.get("id")
        rows = client.torrent_get(["id", "files"], ids=[tid])
        target_files[tid] = (rows[0].get("files") if rows else []) or []
    for torrent in targets:
        torrent["files"] = target_files.get(torrent.get("id")) or []

    # 2) 按体积分组筛选候选，再按需拉文件列表
    by_size = {}
    for torrent in brief:
        if not _is_candidate(torrent, cs_root, excludes):
            continue
        by_size.setdefault(_to_int(torrent.get("totalSize")), []).append(torrent)

    needed = {}
    for torrent in targets:
        size = _to_int(torrent.get("totalSize"))
        if size <= 0:
            continue
        for candidate in by_size.get(size, []):
            needed[_to_int(candidate.get("id"))] = candidate
    if needed:
        ids = sorted(needed.keys())
        for start in range(0, len(ids), 200):
            chunk = ids[start:start + 200]
            rows = client.torrent_get(["id", "files"], ids=chunk)
            for row in rows:
                candidate = needed.get(_to_int(row.get("id")))
                if candidate is not None:
                    candidate["files"] = row.get("files") or []

    # 3) 逐目标匹配
    items = []
    for torrent in targets:
        item = _item_of(torrent)
        status = _to_int(torrent.get("status"))
        if status in (1, 2):
            stats["waiting"] += 1
            items.append(_waiting_item(item, "种子正在校验，下一轮再处理"))
            continue
        if _to_int(torrent.get("totalSize")) <= 0:
            stats["waiting"] += 1
            items.append(_waiting_item(item, "无法获取种子体积，本轮跳过"))
            continue
        pool = by_size.get(_to_int(torrent.get("totalSize")), [])
        best, reason, matched_count = _pick_best(torrent, pool, cfg, fs_ok, priorities)
        if best is None:
            item.update(
                status="no_source",
                reason=reason or "无匹配源（季包聚合或源已删除）",
                candidate_count=matched_count,
            )
            stats["no_source"] += 1
            if journal is not None:
                journal.set_no_source(item["id"], item)
        else:
            item.update(
                status="ready",
                target_dir=norm(best.get("downloadDir")),
                source_id=_to_int(best.get("id")),
                source_name=str(best.get("name") or ""),
                source_dir=norm(best.get("downloadDir")),
                candidate_count=matched_count,
            )
            stats["ready"] += 1
            if journal is not None:
                journal.drop_no_source(item["id"])
        items.append(item)

    items.sort(key=lambda entry: (0 if entry["status"] == "ready" else 1, -entry["size"]))
    return {"items": items, "stats": stats, "cs_root": cs_root, "fs_checked": fs_ok}


def build_plan(torrents, cfg, journal=None):
    """全量数据版本（torrents 内已含 files），便于离线测试。"""
    cs_root = norm(cfg.get("cs_root"))
    priorities = split_lines(cfg.get("path_priority"))
    excludes = split_lines(cfg.get("path_exclude"))
    fs_ok = bool(cs_root) and os.path.isdir(cs_root)
    stats = _new_stats(len(torrents))
    stats["fs_checked"] = fs_ok
    targets = [
        torrent
        for torrent in torrents
        if cs_root and is_under(norm(torrent.get("downloadDir")), cs_root)
    ]
    stats["targets"] = len(targets)
    pool = [torrent for torrent in torrents if _is_candidate(torrent, cs_root, excludes)]
    items = []
    for torrent in targets:
        item = _item_of(torrent)
        if _to_int(torrent.get("status")) in (1, 2):
            stats["waiting"] += 1
            items.append(_waiting_item(item, "种子正在校验，下一轮再处理"))
            continue
        best, reason, matched_count = _pick_best(torrent, pool, cfg, fs_ok, priorities)
        if best is None:
            item.update(status="no_source", reason=reason or "无匹配源（季包聚合或源已删除）", candidate_count=matched_count)
            stats["no_source"] += 1
        else:
            item.update(
                status="ready",
                target_dir=norm(best.get("downloadDir")),
                source_id=_to_int(best.get("id")),
                source_name=str(best.get("name") or ""),
                source_dir=norm(best.get("downloadDir")),
                candidate_count=matched_count,
            )
            stats["ready"] += 1
        items.append(item)
    items.sort(key=lambda entry: (0 if entry["status"] == "ready" else 1, -entry["size"]))
    return {"items": items, "stats": stats, "cs_root": cs_root, "fs_checked": fs_ok}
