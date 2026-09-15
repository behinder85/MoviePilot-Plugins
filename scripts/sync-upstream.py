#!/usr/bin/env python3
"""从上游 MoviePilot-Plugins 同步 HDHive / Dian115 签到客户端代码。

用法：
    python scripts/sync-upstream.py /path/to/MoviePilot-Plugins

只覆盖签到客户端与最小依赖文件，不会覆盖本插件的入口、签到编排和 package.v2.json。
"""

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR_NAME = "hdhivedian115checkin"
PLUGIN_ROOT = REPO_ROOT / "plugins.v2" / PLUGIN_DIR_NAME
UPSTREAM_PLUGIN = "plugins.v2/cloudsubscribe"

# 上游相对路径 -> 本插件内相对路径
FILES = {
    "search/http_client.py": "search/http_client.py",
    "search/cloudflare.py": "search/cloudflare.py",
    "search/matching.py": "search/matching.py",
    "search/types.py": "search/types.py",
    "search/hdhive/web/client.py": "search/hdhive/web/client.py",
    "search/hdhive/web/action.py": "search/hdhive/web/action.py",
    "search/hdhive/web/captcha.py": "search/hdhive/web/captcha.py",
    "search/hdhive/web/captcha.bin": "search/hdhive/web/captcha.bin",
    "search/hdhive/web/parser.py": "search/hdhive/web/parser.py",
    "search/hdhive/web/security.py": "search/hdhive/web/security.py",
    "search/hdhive/open/client.py": "search/hdhive/open/client.py",
    "search/dian115/client.py": "search/dian115/client.py",
    "search/dian115/security.py": "search/dian115/security.py",
    "utils/http_client.py": "utils/http_client.py",
    "utils/cache.py": "utils/cache.py",
    "utils/file_parser.py": "utils/file_parser.py",
}


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "缺少上游目录参数。用法：python scripts/sync-upstream.py UPSTREAM_DIR",
            file=sys.stderr,
        )
        return 2
    upstream_root = Path(sys.argv[1]).resolve()
    if not upstream_root.is_dir():
        print(f"上游目录不存在：{upstream_root}", file=sys.stderr)
        return 2

    copied = []
    missing = []
    for rel_path, dest_rel in FILES.items():
        source = upstream_root / UPSTREAM_PLUGIN / rel_path
        target = PLUGIN_ROOT / dest_rel
        if not source.is_file():
            missing.append(f"{UPSTREAM_PLUGIN}/{rel_path}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(dest_rel)

    print(f"已从 {upstream_root} 同步 {len(copied)} 个文件")
    for item in copied:
        print(f"  + {item}")
    if missing:
        print("上游缺失以下文件：", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
