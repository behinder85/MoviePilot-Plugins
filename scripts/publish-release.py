#!/usr/bin/env python3
"""把 build-release.py 生成的压缩包发布为 GitHub Release。

用法：
    python scripts/publish-release.py --dist dist
    python scripts/publish-release.py --dist dist --dry-run

依赖 GitHub CLI（gh），权限通过 GH_TOKEN / GITHUB_TOKEN 提供。
Tag 为 {插件ID}_v{版本}，资产为 dist/ 下的 {插件目录}_v{版本}.zip。
同名 Release 或 Tag 会先被清理再重建，保证与当前索引版本一致。
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(args, check=True):
    """执行外部命令并回显。"""
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, check=check, text=True, capture_output=True)


def cleanup(tag: str) -> None:
    """删除同名 Release 与残留 Tag，避免发布冲突。"""
    view = subprocess.run(
        ["gh", "release", "view", tag], text=True, capture_output=True
    )
    if view.returncode == 0:
        run(["gh", "release", "delete", tag, "--cleanup-tag", "--yes"], check=False)

    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"],
        text=True,
        capture_output=True,
    )
    if remote.returncode == 0:
        run(["git", "push", "origin", f":refs/tags/{tag}"], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="发布插件 Release")
    parser.add_argument("--dist", default="dist", help="压缩包所在目录，默认 dist")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要执行的动作")
    args = parser.parse_args()

    dist = Path(args.dist)
    if not dist.is_absolute():
        dist = REPO_ROOT / dist

    manifest_file = dist / "release-manifest.json"
    if not manifest_file.is_file():
        print(f"发布清单不存在：{manifest_file}，请先执行 build-release.py", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not manifest:
        print("发布清单为空。", file=sys.stderr)
        return 2

    if not args.dry_run and not shutil.which("gh"):
        print("未找到 GitHub CLI（gh），无法发布 Release。", file=sys.stderr)
        return 2

    target = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip()

    for item in manifest:
        asset = Path(item["asset"])
        if not asset.is_absolute():
            asset = REPO_ROOT / asset
        if not asset.is_file():
            print(f"压缩包不存在：{asset}", file=sys.stderr)
            return 2
        print(f"发布 {item['tag']} -> {asset.name}")
        if args.dry_run:
            continue
        cleanup(item["tag"])
        run(
            [
                "gh",
                "release",
                "create",
                item["tag"],
                str(asset),
                "--title",
                item["title"],
                "--notes",
                item["notes"] or item["title"],
                "--target",
                target,
            ]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
