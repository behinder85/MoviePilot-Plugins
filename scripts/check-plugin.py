#!/usr/bin/env python3
"""静态校验插件是否符合 MoviePilot V2 插件规范。

用法：
    python scripts/check-plugin.py

对应官方规范与 MoviePilot V2 运行时行为，校验：
    1. package.v2.json 使用 UTF-8 无 BOM，且可被 json.loads 直接解析
    2. 索引键、插件目录名、插件主类名三者一致
    3. 三处版本一致：索引 version、类中的 plugin_version、history 最新键
    4. 插件类实现 _PluginBase 的全部抽象方法（含 get_api / get_page）
    5. get_form 返回官方 Vuetify 组件结构，且表单绑定字段都能在默认数据结构中找到
"""

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = REPO_ROOT / "package.v2.json"
PLUGIN_ROOT = REPO_ROOT / "plugins.v2"

# app/plugins/__init__.py 中 _PluginBase 的抽象方法，缺一即无法实例化。
REQUIRED_METHODS = ("init_plugin", "get_state", "get_api", "get_form", "get_page", "stop_service")
# 旧版自定义表单描述，不被 MoviePilot 前端识别。
VERSION_PATTERN = re.compile(r'^(\s*plugin_version\s*=\s*")([^"]*)(")', re.M)


def constant_keys(node: ast.Dict) -> dict:
    """取出字典字面量中的常量键，值保留 AST 节点。"""
    result = {}
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            result[key.value] = value
    return result


def resolve(node, method):
    """把 `form = [...]` + `return form` 这类写法还原成字面量节点。"""
    seen = set()
    while isinstance(node, ast.Name) and node.id not in seen:
        seen.add(node.id)
        target = None
        for child in ast.walk(method):
            if isinstance(child, ast.Assign) and any(
                isinstance(item, ast.Name) and item.id == node.id for item in child.targets
            ):
                target = child.value
                break
        if target is None:
            break
        node = target
    return node


def class_of(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def check_plugin(plugin_id: str, meta: dict, errors: list, notes: list) -> None:
    plugin_dir = PLUGIN_ROOT / plugin_id.lower()
    entry = plugin_dir / "__init__.py"
    if not entry.is_file():
        errors.append(f"{plugin_id}: 缺少插件入口 {entry.relative_to(REPO_ROOT)}")
        return

    source = entry.read_text(encoding="utf-8")
    if entry.read_bytes()[:3] == b"\xef\xbb\xbf":
        errors.append(f"{plugin_id}: {entry.name} 带 UTF-8 BOM")
    tree = ast.parse(source)
    cls = class_of(tree, plugin_id)
    if cls is None:
        errors.append(f"{plugin_id}: 未找到与索引键同名的插件类")
        return

    base_names = [ast.unparse(base) for base in cls.bases]
    if "_PluginBase" not in base_names:
        errors.append(f"{plugin_id}: 插件类未继承 _PluginBase（当前：{base_names}）")

    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    missing = [name for name in REQUIRED_METHODS if name not in methods]
    if missing:
        errors.append(f"{plugin_id}: 缺少抽象方法实现 -> {', '.join(missing)}")
    else:
        notes.append(f"{plugin_id}: 抽象方法完整（{', '.join(REQUIRED_METHODS)}）")

    version_match = VERSION_PATTERN.search(source)
    declared = version_match.group(2) if version_match else ""
    if declared != meta.get("version"):
        errors.append(f"{plugin_id}: plugin_version={declared!r} 与索引 version={meta.get('version')!r} 不一致")
    else:
        notes.append(f"{plugin_id}: 版本一致（{declared}）")

    history = meta.get("history") or {}
    expected_key = f"v{meta.get('version')}"
    if list(history) and list(history)[0] != expected_key:
        errors.append(f"{plugin_id}: history 最新条目为 {list(history)[0]!r}，应为 {expected_key!r}")

    icon = str(meta.get("icon") or "")
    icon_name = icon.rsplit("/", 1)[-1]
    if not (REPO_ROOT / "icons" / icon_name).is_file():
        errors.append(f"{plugin_id}: 索引图标 icons/{icon_name} 不存在")

    check_form(plugin_id, methods.get("get_form"), errors, notes)
    check_contract(plugin_id, methods.get("get_api"), "[]", errors)
    check_contract(plugin_id, methods.get("get_page"), "None", errors)


def check_contract(plugin_id: str, method, expected_code: str, errors: list) -> None:
    """确认 get_api / get_page 返回 MoviePilot 可接受的空值，而不是 None 之外的意外类型。"""
    if method is None or len(method.body) != 1:
        return
    statement = method.body[0]
    if not isinstance(statement, ast.Return):
        return
    try:
        code = ast.unparse(statement.value)
    except Exception:  # pragma: no cover - 仅防御性处理
        return
    if code not in {expected_code, "None", "[]"}:
        errors.append(f"{plugin_id}: {method.name} 返回值 {code} 需人工确认")


def check_form(plugin_id: str, method, errors: list, notes: list) -> None:
    """按 MoviePilot V2 前端 FormRender 的要求校验表单结构。"""
    if method is None:
        return
    returns = [node for node in ast.walk(method) if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Tuple):
        errors.append(f"{plugin_id}: get_form 必须返回 (页面配置, 默认数据结构) 二元组")
        return
    form_node, model_node = (resolve(item, method) for item in returns[0].value.elts[:2])
    if not isinstance(form_node, ast.List) or not form_node.elts:
        errors.append(f"{plugin_id}: get_form 第一个返回值应为非空的页面配置列表")
        return

    root_component = getattr(constant_keys(form_node.elts[0]).get("component"), "value", None)
    if root_component != "VForm":
        errors.append(f"{plugin_id}: get_form 根节点应为 VForm，当前为 {root_component!r}")

    # 页面配置是 component/props/content 节点树，除 props 外每个节点都必须声明 component。
    legacy, node_count = [], 0
    stack = [(child, "根节点") for child in form_node.elts]
    while stack:
        node, position = stack.pop()
        if not isinstance(node, ast.Dict):
            errors.append(f"{plugin_id}: {position} 不是组件字典")
            continue
        keys = constant_keys(node)
        component = getattr(keys.get("component"), "value", None)
        if not component:
            declared = getattr(keys.get("type"), "value", None)
            legacy.append(f"{position} 使用了 type={declared!r}" if declared else f"{position} 缺少 component")
            continue
        node_count += 1
        content = keys.get("content")
        if isinstance(content, ast.List):
            stack.extend((child, f"{component}.content") for child in content.elts)
    if legacy:
        errors.append(f"{plugin_id}: get_form 存在无法渲染的节点（{'; '.join(legacy[:3])}），"
                      "应按官方规范改用 component 结构")

    if not isinstance(model_node, ast.Dict):
        errors.append(f"{plugin_id}: get_form 第二个返回值应为默认数据结构字典")
        return
    model_keys = set(constant_keys(model_node))

    bound = set()
    for node in ast.walk(form_node):
        if not isinstance(node, ast.Dict):
            continue
        props = constant_keys(node).get("props")
        if not isinstance(props, ast.Dict):
            continue
        model = constant_keys(props).get("model")
        if isinstance(model, ast.Constant) and isinstance(model.value, str):
            bound.add(model.value)
    if not bound:
        errors.append(f"{plugin_id}: get_form 没有任何绑定到数据结构的字段")
        return
    unknown = sorted(bound - model_keys)
    if unknown:
        errors.append(f"{plugin_id}: 表单绑定了默认数据结构中不存在的字段 -> {', '.join(unknown)}")
    else:
        notes.append(f"{plugin_id}: 表单 {node_count} 个组件节点、{len(bound)} 个字段与默认数据结构一致")


def main() -> int:
    errors: list = []
    notes: list = []

    raw = PACKAGE_FILE.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        errors.append("package.v2.json 带 UTF-8 BOM，MoviePilot 会解析失败")
    try:
        index = json.loads(raw.decode("utf-8"))
    except Exception as error:
        print(f"package.v2.json 解析失败：{error}")
        return 1

    for plugin_id, meta in index.items():
        check_plugin(plugin_id, meta, errors, notes)

    print("=== 通过项 ===")
    for note in notes:
        print(f"  OK   {note}")
    print("=== 错误 ===")
    for error in errors:
        print(f"  FAIL {error}")
    print(f"结果：{len(errors)} 个错误")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
