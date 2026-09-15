#!/usr/bin/env python3
"""Sync HDHive / Dian115 check-in client files from upstream.

Usage:
    python scripts/sync-upstream.py /path/to/MoviePilot-Plugins

The script intentionally does NOT overwrite the plugin glue files:
    - plugins.v2/hdhive_dian115_checkin/__init__.py
    - plugins.v2/hdhive_dian115_checkin/checkin_service.py
    - package.v2.json
"""

import shutil
import sys
from pathlib import Path

UPSTREAM_ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins.v2" / "hdhive_dian115_checkin"

# upstream-relative path -> destination path under PLUGIN_ROOT
FILES = {
    "plugins.v2/cloudsubscribe/search/http_client.py": "search/http_client.py",
    "plugins.v2/cloudsubscribe/search/cloudflare.py": "search/cloudflare.py",
    "plugins.v2/cloudsubscribe/search/matching.py": "search/matching.py",
    "plugins.v2/cloudsubscribe/search/types.py": "search/types.py",
    "plugins.v2/cloudsubscribe/search/hdhive/web/client.py": "search/hdhive/web/client.py",
    "plugins.v2/cloudsubscribe/search/hdhive/web/action.py": "search/hdhive/web/action.py",
    "plugins.v2/cloudsubscribe/search/hdhive/web/captcha.py": "search/hdhive/web/captcha.py",
    "plugins.v2/cloudsubscribe/search/hdhive/web/captcha.bin": "search/hdhive/web/captcha.bin",
    "plugins.v2/cloudsubscribe/search/hdhive/web/parser.py": "search/hdhive/web/parser.py",
    "plugins.v2/cloudsubscribe/search/hdhive/web/security.py": "search/hdhive/web/security.py",
    "plugins.v2/cloudsubscribe/search/hdhive/open/client.py": "search/hdhive/open/client.py",
    "plugins.v2/cloudsubscribe/search/dian115/client.py": "search/dian115/client.py",
    "plugins.v2/cloudsubscribe/search/dian115/security.py": "search/dian115/security.py",
    "plugins.v2/cloudsubscribe/utils/http_client.py": "utils/http_client.py",
    "plugins.v2/cloudsubscribe/utils/cache.py": "utils/cache.py",
    "plugins.v2/cloudsubscribe/utils/file_parser.py": "utils/file_parser.py",
}


def main() -> int:
    if UPSTREAM_ROOT is None or not UPSTREAM_ROOT.is_dir():
        print("Missing upstream directory. Usage: python scripts/sync-upstream.py UPSTREAM_DIR", file=sys.stderr)
        return 2

    copied = []
    missing = []
    for src_rel, dst_rel in FILES.items():
        source = UPSTREAM_ROOT / src_rel
        target = REPO_ROOT / "plugins.v2" / "hdhive_dian115_checkin" / dst_rel
        if not source.is_file():
            missing.append(src_rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(dst_rel)

    print(f"Copied {len(copied)} files from {UPSTREAM_ROOT}")
    for item in copied:
        print(f"  + {item}")
    if missing:
        print("Missing upstream files:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
