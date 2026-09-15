#!/usr/bin/env python3
"""按官方仓库规范提升插件版本并写入更新日志。

用法：
    python scripts/bump-version.py --message "同步上游 HDHive/Dian115 客户端代码"
    python scripts/bump-version.py --part minor --message "新增 xxx 能力"

行为：
    1. 读取 package.v2.json（兼容 UTF-8 BOM）
    2. 按 --part 提升索引中的 version
    3. 在 history 顶部写入 v{新版本}: {message}
    4. 同步 plugins.v2/<插件目录>/__init__.py 中的 plugin_version
    5. 以 UTF-8（无 BOM）+ LF 写回索引
"""

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = REPO_ROOT / "package.v2.json"
VERSION_PATTERN = re.compile(r'^(\s*plugin_version\s*=\s*")([^"]*)(")', re.M)


def load_package() -> OrderedDict:
    """读取索引文件，兼容带 BOM 的历史文件。"""
    return json.loads(PACKAGE_FILE.read_text(encoding="utf-8-sig"), object_pairs_hook=OrderedDict)


def bump(version: str, part: str) -> str:
    """按语义版本提升指定段位。"""
    numbers = version.split(".")
    if len(numbers) != 3 or not all(item.isdigit() for item in numbers):
        raise SystemExit(f"无法解析插件版本号：{version}")
    major, minor, patch = (int(item) for item in numbers)
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def main() -> int:
    parser = argparse.ArgumentParser(description="提升插件版本并写入更新日志")
    parser.add_argument("--plugin-id", default="", help="插件 ID，默认取索引中的唯一插件")
    parser.add_argument("--part", default="patch", choices=("patch", "minor", "major"))
    parser.add_argument("--message", default="同步上游 HDHive/Dian115 客户端代码")
    args = parser.parse_args()

    package = load_package()
    if args.plugin_id:
        if args.plugin_id not in package:
            raise SystemExit(f"索引中不存在插件：{args.plugin_id}")
        plugin_id = args.plugin_id
    elif len(package) == 1:
        plugin_id = next(iter(package))
    else:
        raise SystemExit("索引中存在多个插件，请通过 --plugin-id 指定")

    info = package[plugin_id]
    current_version = str(info.get("version") or "").strip()
    if not current_version:
        raise SystemExit(f"{plugin_id} 未声明 version")

    new_version = bump(current_version, args.part)
    init_file = REPO_ROOT / "plugins.v2" / plugin_id.lower() / "__init__.py"
    if not init_file.is_file():
        raise SystemExit(f"插件入口不存在：{init_file}")

    source = init_file.read_text(encoding="utf-8")
    if not VERSION_PATTERN.search(source):
        raise SystemExit(f"{init_file} 中未找到 plugin_version")
    init_file.write_text(
        VERSION_PATTERN.sub(lambda m: f"{m.group(1)}{new_version}{m.group(3)}", source, count=1),
        encoding="utf-8",
        newline="\n",
    )

    history = OrderedDict()
    history[f"v{new_version}"] = args.message
    for key, value in (info.get("history") or {}).items():
        if key not in history:
            history[key] = value
    info["version"] = new_version
    info["history"] = history

    PACKAGE_FILE.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{plugin_id}: {current_version} -> {new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
