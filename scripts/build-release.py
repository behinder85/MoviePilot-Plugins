#!/usr/bin/env python3
"""按官方仓库发布规范生成插件 Release 压缩包与发布清单。

用法：
    python scripts/build-release.py --out dist

规范（对应 jxxghp/MoviePilot-Plugins 的发布约定）：
    - 只处理索引中声明 release=true 的插件
    - Tag 为 {插件ID}_v{版本}，资产名为 {插件目录小写}_v{版本}.zip
    - 压缩包顶层为 {插件目录小写}/，解压后即为插件目录内容
    - 索引 version 必须与插件类中的 plugin_version 一致
    - 排除 __pycache__、*.pyc、*.pyo、node_modules、.DS_Store

产物：
    dist/{插件目录小写}_v{版本}.zip
    dist/release-manifest.json
"""

import argparse
import json
import re
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = REPO_ROOT / "package.v2.json"
PLUGIN_ROOT = REPO_ROOT / "plugins.v2"
VERSION_PATTERN = re.compile(r'^\s*plugin_version\s*=\s*"([^"]*)"', re.M)
EXCLUDED_DIRS = {"__pycache__", "node_modules"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {".DS_Store"}


def load_package() -> OrderedDict:
    """读取插件索引，兼容带 BOM 的历史文件。"""
    return json.loads(PACKAGE_FILE.read_text(encoding="utf-8-sig"), object_pairs_hook=OrderedDict)


def source_version(init_file: Path) -> str:
    """读取插件类中声明的 plugin_version。"""
    match = VERSION_PATTERN.search(init_file.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"{init_file} 中未找到 plugin_version")
    return match.group(1).strip()


def iter_files(plugin_dir: Path):
    """遍历需要打包的文件，跳过缓存与依赖目录。"""
    for path in sorted(plugin_dir.rglob("*")):
        relative = path.relative_to(plugin_dir)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if not path.is_file():
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        yield path, relative


def build(plugin_id: str, info: dict, out_dir: Path) -> dict:
    """打包单个插件并返回发布清单项。"""
    version = str(info.get("version") or "").strip()
    if not version:
        raise SystemExit(f"{plugin_id} 未声明 version")

    directory = plugin_id.lower()
    plugin_dir = PLUGIN_ROOT / directory
    init_file = plugin_dir / "__init__.py"
    if not init_file.is_file():
        raise SystemExit(f"插件目录不存在或缺少 __init__.py：{plugin_dir}")

    actual_version = source_version(init_file)
    if actual_version != version:
        raise SystemExit(f"{plugin_id} 版本不一致：索引={version}，插件={actual_version}")

    tag = f"{plugin_id}_v{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    asset = out_dir / f"{directory}_v{version}.zip"

    count = 0
    with zipfile.ZipFile(asset, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, relative in iter_files(plugin_dir):
            archive.write(path, f"{directory}/{relative.as_posix()}")
            count += 1
    if not count:
        raise SystemExit(f"{plugin_id} 未收集到任何文件")

    with zipfile.ZipFile(asset) as archive:
        names = set(archive.namelist())
    required = f"{directory}/__init__.py"
    if required not in names:
        raise SystemExit(f"压缩包缺少必需文件：{required}")

    print(f"已生成 {asset} （{count} 个文件）")
    return {
        "id": plugin_id,
        "tag": tag,
        "asset": asset.as_posix(),
        "title": f"{info.get('name') or plugin_id} v{version}",
        "notes": str((info.get("history") or {}).get(f"v{version}") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成插件 Release 压缩包")
    parser.add_argument("--out", default="dist", help="压缩包输出目录，默认 dist")
    parser.add_argument("--plugin-id", default="", help="插件 ID，默认处理索引中全部 release=true 插件")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    package = load_package()
    targets = [args.plugin_id] if args.plugin_id else list(package)
    manifest = []
    for plugin_id in targets:
        info = package.get(plugin_id)
        if not isinstance(info, dict):
            raise SystemExit(f"索引中不存在插件：{plugin_id}")
        if info.get("release") is not True:
            print(f"{plugin_id} 未声明 release=true，已跳过打包")
            continue
        manifest.append(build(plugin_id, info, out_dir))

    if not manifest:
        print("没有需要打包的插件。")
        return 1

    manifest_file = out_dir / "release-manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"已生成发布清单 {manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
