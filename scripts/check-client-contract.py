#!/usr/bin/env python3
"""校验上游同步的签到客户端契约，防止上游重构后签到静默失效。

用法：
    python scripts/check-client-contract.py

上游 MoviePilot-Plugins 已把两个渠道统一成 ``客户端.checkin(mode)``，并会随
版本调整构造参数。本脚本用 AST 读取已同步进本插件的客户端源码，核对
``checkin_service.py`` 依赖的最小契约：

    1. 三个客户端类都存在，且提供签到入口（checkin，兼容旧版 signin）
    2. 签到入口能接收签到模式（mode / is_gambler / 位置参数 / **kwargs）
    3. 账号凭据参数仍然存在（email/password 或 username/password）
    4. Dian115 仍具备转盘能力（构造参数 lottery_enabled/lottery_count 或 run_lottery）
    5. 服务层传给构造函数的关键字都能被真实签名接收，且不缺必填参数
    6. 适配层的签名过滤能力与同步清单仍然覆盖签到客户端

任何硬性缺口都会以非 0 退出，阻止 CI 自动发布一个无法签到的新版本。
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins.v2" / "hdhivedian115checkin"
SERVICE_FILE = PLUGIN_ROOT / "checkin_service.py"
ENTRY_FILE = PLUGIN_ROOT / "__init__.py"
SYNC_FILE = REPO_ROOT / "scripts" / "sync-upstream.py"

# 上游签到客户端契约；entries 为可接受的签到入口，按优先级排列。
CLIENTS = (
    {
        "name": "HDHiveClient",
        "label": "HDHive WebAPI",
        "path": PLUGIN_ROOT / "search" / "hdhive" / "web" / "client.py",
        "credentials": ("username", "password"),
        "entries": ("checkin",),
        "requires": ("close",),
    },
    {
        "name": "HDHiveOpenAPIClient",
        "label": "HDHive OpenAPI",
        "path": PLUGIN_ROOT / "search" / "hdhive" / "open" / "client.py",
        "credentials": ("app_secret", "access_token"),
        "entries": ("checkin",),
        "requires": ("close", "is_ready"),
    },
    {
        "name": "Dian115Client",
        "label": "Dian115",
        "path": PLUGIN_ROOT / "search" / "dian115" / "client.py",
        "credentials": ("email", "password"),
        "entries": ("checkin", "signin"),
        "requires": ("close",),
    },
)


class Signature:
    """函数签名信息，用于判断适配层能否安全调用。"""

    def __init__(self, node):
        arguments = node.args
        positional = [item.arg for item in arguments.posonlyargs + arguments.args]
        keyword = [item.arg for item in arguments.kwonlyargs]
        self.positional = positional
        self.names = set(positional) | set(keyword)
        self.var_positional = arguments.vararg is not None
        self.var_keyword = arguments.kwarg is not None
        if arguments.defaults:
            required = positional[:len(positional) - len(arguments.defaults)]
        else:
            required = list(positional)
        required += [
            item.arg
            for item, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
            if default is None
        ]
        self.required = set(required)

    def unbind(self):
        """去掉 self，得到实例方法可用的参数信息。"""
        self.positional = self.positional[1:]
        self.names.discard("self")
        self.required.discard("self")
        return self

    def accepts(self, name):
        return name in self.names or self.var_keyword

    def accepts_positional(self):
        return bool(self.positional) or self.var_positional

    def mode_strategy(self):
        """适配层实际会采用的调用方式。"""
        if self.accepts("mode"):
            return "checkin(mode=...)"
        if self.accepts("is_gambler"):
            return "checkin(is_gambler=...)"
        if self.accepts_positional():
            return "checkin(mode)"
        if self.var_keyword:
            return "checkin(**kwargs)"
        return ""


def collect_methods(class_node):
    methods = {}
    for child in class_node.body:
        if isinstance(child, ast.FunctionDef):
            methods[child.name] = Signature(child).unbind()
    return methods


def load_class(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def collect_calls(paths, class_names):
    """收集服务层对客户端构造入口的关键字调用参数。"""
    calls = {}
    for path in paths:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = None
            if isinstance(node.func, ast.Name):
                target = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target = node.func.attr
            if target == "_build_client" and node.args:
                first = node.args[0]
                target = first.id if isinstance(first, ast.Name) else None
            if target in class_names:
                calls.setdefault(target, set()).update(
                    keyword.arg for keyword in node.keywords if keyword.arg
                )
    return calls


def collect_sync_targets():
    if not SYNC_FILE.is_file():
        return set()
    tree = ast.parse(SYNC_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "FILES"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Dict):
            return {
                value.value
                for value in node.value.values
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            }
    return set()


def main() -> int:
    errors = []
    warnings = []
    notes = []

    if not SERVICE_FILE.is_file():
        print(f"找不到签到服务文件：{SERVICE_FILE}")
        return 1
    service_source = SERVICE_FILE.read_text(encoding="utf-8")

    class_names = {client["name"] for client in CLIENTS}
    calls = collect_calls([SERVICE_FILE, ENTRY_FILE], class_names)
    sync_targets = collect_sync_targets()

    for client in CLIENTS:
        name = client["name"]
        label = client["label"]
        if not client["path"].is_file():
            errors.append(f"{label}: 缺少客户端文件 {client['path'].relative_to(REPO_ROOT)}")
            continue
        class_node = load_class(client["path"], name)
        if class_node is None:
            errors.append(f"{label}: {client['path'].name} 中找不到类 {name}")
            continue
        methods = collect_methods(class_node)
        init = methods.get("__init__")
        if init is None:
            errors.append(f"{label}: {name} 缺少 __init__")
            continue

        entry = next(
            (item for item in client["entries"] if item in methods), None
        )
        if entry is None:
            errors.append(
                f"{label}: {name} 缺少签到入口（需要 {' 或 '.join(client['entries'])}）"
            )
        else:
            strategy = methods[entry].mode_strategy()
            if not strategy:
                errors.append(
                    f"{label}: {name}.{entry} 无法接收签到模式，"
                    "适配层只能按无参调用"
                )
            else:
                notes.append(f"{label}: {name}.{entry} 适配为 {strategy}")

        missing_credentials = [
            item for item in client["credentials"] if not init.accepts(item)
        ]
        if missing_credentials and not init.var_keyword:
            errors.append(
                f"{label}: {name}.__init__ 缺少凭据参数 -> "
                + ", ".join(missing_credentials)
            )

        missing_attrs = [item for item in client["requires"] if item not in methods]
        if missing_attrs:
            errors.append(
                f"{label}: {name} 缺少签到服务依赖的属性 -> " + ", ".join(missing_attrs)
            )

        if name == "Dian115Client":
            lottery_args = init.accepts("lottery_enabled") and init.accepts("lottery_count")
            if not lottery_args and "run_lottery" not in methods:
                errors.append(
                    f"{label}: {name} 既没有转盘构造参数也没有 run_lottery，"
                    "转盘签到将不可用"
                )
            else:
                mode = "构造参数" if lottery_args else "run_lottery 兜底"
                notes.append(f"{label}: 转盘能力来自 {mode}")

        passed = calls.get(name, set())
        if not passed:
            errors.append(
                f"{label}: 签到服务没有构造 {name}，请检查适配层是否被误删"
            )
            continue
        uncovered = sorted(init.required - passed)
        if uncovered and not init.var_keyword:
            errors.append(
                f"{label}: 构造 {name} 时缺少必填参数 -> " + ", ".join(uncovered)
            )
        unknown = sorted(passed - init.names)
        if unknown and not init.var_keyword:
            warnings.append(
                f"{label}: 传入 {name} 的关键字不在签名中，将被过滤 -> "
                + ", ".join(unknown)
            )

        relative = client["path"].relative_to(PLUGIN_ROOT).as_posix()
        if sync_targets and relative not in sync_targets:
            errors.append(f"{label}: 同步清单没有覆盖 {relative}，上游更新不会进入本插件")

    if "_build_client" not in service_source:
        errors.append("签到服务缺少 _build_client 签名过滤，上游改参数会直接抛出 TypeError")
    else:
        notes.append("适配层保留了 _build_client 签名过滤")
    for marker, hint in (
        ("_accepts", "关键字能力检测"),
        ("is_gambler", "旧版 HDHive 参数兼容"),
        ("signin", "旧版 Dian115 入口兼容"),
    ):
        if marker in service_source:
            notes.append(f"适配层保留 {hint}")
        else:
            warnings.append(f"适配层可能丢失 {hint}（未找到 {marker}）")

    print("=== 通过项 ===")
    for note in notes:
        print(f"  OK   {note}")
    print("=== 警告 ===")
    for warning in warnings:
        print(f"  WARN {warning}")
    print("=== 错误 ===")
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print("上游签到契约已变化：请更新 plugins.v2/hdhivedian115checkin/checkin_service.py")
        print("（或 plugins.v2/hdhivedian115checkin/__init__.py），核对")
        print("search/ 下的新签名后提交，CI 才会发布新版本。")
    print(f"结果：{len(errors)} 个错误，{len(warnings)} 个警告")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
