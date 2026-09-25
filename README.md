# MoviePilot HDHive / Dian115 签到插件

从 [odomu/MoviePilot-Plugins](https://github.com/odomu/MoviePilot-Plugins) 中仅提取 **HDHive** 与 **Dian115** 的签到相关代码，按 [jxxghp/MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins) 官方仓库规范重新打包为独立的 MoviePilot 插件市场仓库。

网盘、订阅、搜索、转存、刮削等冗余功能已全部删除。

## 在 MoviePilot 中使用

1. 打开 MoviePilot → 设定 → 插件 → 插件市场。
2. 在“插件市场地址”中追加本仓库地址（多个地址用英文逗号分隔）：

   ```text
   https://github.com/behinder85/MoviePilot-Plugins
   ```

3. 刷新插件市场，找到 **HDHive / Dian115 签到** 并安装。
4. 安装后在插件配置页填写账号信息并启用。

> 插件市场只读取仓库 `main` 分支，因此本仓库的默认分支必须保持为 `main`。

## 插件配置

- `启用插件`：关闭后签到调度停止。
- `签到执行周期`：默认 `0 8 * * *`，即时区为 MoviePilot 的 `TZ`。
- `发送通知` / `通知渠道`：签到结果通知。
- `代理地址`：选填，例如 `http://127.0.0.1:7890`。
- HDHive：
  - `查询模式` 选择 `WebAPI（账号密码）` 时填写用户名和密码。
  - `查询模式` 选择 `OpenAPI（应用授权）` 时填写应用 Secret、Client ID、回调地址，按日志中的授权链接完成授权后再填入授权码。
  - `签到模式` 支持普通签到与赌狗签到；`请求间隔（秒）` 会被限制在 2-10 秒，风控较高时不要调小。
- Dian115：填写邮箱和密码，可选启用幸运转盘及转盘次数。

配置表单按 V2 官方规范使用 `VForm` / `VCard` / `VRow` / `VCol` 组件拼装，`get_form` 同时返回完整的默认数据结构，保证配置页可以正常渲染、绑定与保存。

**WebAPI / OpenAPI 条件显示**：`查询模式` 决定 HDHive 的登录方式，表单会按选择自动切换，两者互不干扰。

- 选择 `WebAPI（账号密码）`：只显示 `HDHive 用户名` 与 `HDHive 密码`，不读取也不校验任何 OpenAPI 配置。
- 选择 `OpenAPI（应用授权）`：只显示 `OpenAPI 站点地址`、`OpenAPI 应用 Secret`、`OpenAPI Client ID`、`OpenAPI 回调地址`、`授权回调模式` 与 `OpenAPI 授权码`。

因此使用 WebAPI 时不会再出现 `HDHive OpenAPI: 缺少应用 Secret` 之类的告警。

**保存后立即执行一次**：HDHive 与 Dian115 各有一个 `保存后立即执行一次` 开关。打开后保存配置，插件会在约 3 秒后提交一次性签到任务，并自动关闭开关、写回配置，不影响签到周期等其他设置。

插件同时提供三个手动命令：`/hdhive_checkin`、`/dian115_checkin`、`/checkin_all`。

## 上游契约适配

`search/` 下的客户端代码由上游同步，方法签名会随上游重构而变化。本仓库的 `checkin_service.py` 做了一层契约适配：

- 构造客户端时按真实签名过滤关键字参数，上游新增或改名参数都不会抛出 `unexpected keyword argument`；上游新增必填参数时由契约校验直接拦下。
- 调用签到入口时按真实签名分发：优先 `checkin(mode=...)`，其次兼容旧版 `checkin(is_gambler=...)`，再退化到位置参数或无参调用；旧版只提供 `signin` 的 Dian115 客户端会走 `signin + run_lottery` 兜底。
- 签到记录里的 `points_change`、`signin_points`、`signin_days` 由服务层统一折算，即使渠道只回传 `points_before` / `points_after` 也能得到正确结果。

`scripts/check-client-contract.py` 会核对上述契约（签到入口、签到模式、账号凭据、Dian115 转盘能力、构造必填参数、同步清单覆盖）。只要上游改动破坏了其中任何一项，同步与发布 Workflow 都会直接失败并打印适配提示，不会把无法签到的版本自动发布出去；契约通过且文件有变化时才会自动升版本并重建 Release。

## 详情数据页

插件实现了 `get_page`，因此插件卡片的配置页会出现 **查看数据** 按钮，点开后即为详情数据页：

- **运行状态**：插件状态、签到周期、下次执行时间、最近执行时间，右上角带刷新按钮。
- **渠道状态**：HDHive 与 Dian115 各自的启用与配置状态、当前账号、签到模式、可用积分和最近一次签到结果。
- **最近签到记录**：`VTable` 表格按时间倒序展示时间、渠道、模式、触发方式、状态、积分变化与说明，最多 15 条。
- **手动执行**：`立即执行全部` / `立即执行 HDHive` / `立即执行 Dian115` 三个按钮，点击后立即调用签到接口并刷新页面数据。手动执行不受 `启用 HDHive 签到` / `启用 Dian115 签到` 开关限制，`立即执行全部` 只执行已启用且账号配置完整的渠道。

手动执行与刷新由 `get_api` 注册的接口提供：

```text
POST /api/v1/plugin/HDHiveDian115Checkin/checkin/{provider}   # provider：all / hdhive / dian115
GET  /api/v1/plugin/HDHiveDian115Checkin/refresh
```

## 目录结构

```text
.
├── .github/workflows/
│   ├── release.yml                      # 索引变更 / 手动触发时打包发布 Release
│   └── sync-upstream.yml                # 每日同步上游客户端并自动升版本发布
├── icons/hdhivedian115checkin.png
├── plugins.v2/hdhivedian115checkin/     # 目录名 = 插件类名小写
│   ├── __init__.py                      # 插件入口、配置表单与调度
│   ├── checkin_service.py               # 精简签到编排
│   ├── requirements.txt
│   ├── search/hdhive/                   # 上游 HDHive 客户端
│   ├── search/dian115/                  # 上游 Dian115 客户端
│   ├── search/…                         # 共用 HTTP / 风控 / 资源类型模块
│   └── utils/…                          # 共用缓存、HTTP、文件解析模块
├── scripts/
│   ├── sync-upstream.py                 # 上游代码同步
│   ├── bump-version.py                  # 版本与更新日志维护
│   ├── check-plugin.py                  # 插件规范静态校验
│   ├── check-client-contract.py         # 上游签到客户端契约校验
│   ├── build-release.py                 # 生成 Release 压缩包与发布清单
│   ├── publish-release.py               # 发布 GitHub Release
│   └── upload-to-github.ps1             # 本地首次上传脚本
└── package.v2.json                      # V2 插件市场索引（UTF-8 无 BOM）
```

## 与官方规范的对应关系

- **插件基类方法完整**：`init_plugin`、`get_state`、`get_api`、`get_form`、`get_page`、`stop_service` 在 `_PluginBase` 中都是抽象方法，缺少任何一个都会让 MoviePilot 实例化插件失败，现象是插件能安装、但配置页直接提示“配置加载失败”。
- **目录名 = 插件主类名小写**：`class HDHiveDian115Checkin` 对应 `plugins.v2/hdhivedian115checkin/`，MoviePilot 通过 `package.v2.json` 的键定位该目录。
- **三处版本一致**：`package.v2.json` 的 `version`、插件类中的 `plugin_version`、`history` 中最新的 `v{版本}` 必须相同。`scripts/build-release.py` 会在打包前强制校验。
- **Release 发布**：索引声明 `"release": true`，Tag 为 `HDHiveDian115Checkin_v{版本}`，资产为 `hdhivedian115checkin_v{版本}.zip`，压缩包顶层即插件目录。MoviePilot 优先按 Release 安装，失败时自动回退到文件列表安装。
- **系统版本约束**：`system_version` 声明为 `>=2.14.6`，不满足的 MoviePilot 会拒绝安装。
- **依赖**：V2 插件使用插件目录内的 `requirements.txt`。
- **插件接口与详情页**：`get_api()` 注册的接口会被挂载到 `/api/v1/plugin/{PluginID}{path}`（同时注册 `/api/v2` 别名）；只有 `get_page()` 返回非空的 `component` 节点树时，MoviePilot 才会把 `has_page` 置为 `True` 并显示“查看数据”按钮。

> MoviePilot V3 在没有 V3 专用实现时会回退加载 V2 实现，因此本插件同时适用于 MoviePilot V2 与 V3。MoviePilot V1 只读取 `package.json` 与 `plugins/`，本仓库不再提供该代实现。

## 自动更新

`.github/workflows/sync-upstream.yml` 每天 UTC 16:00（北京时间 00:00）执行：

1. 克隆上游 `odomu/MoviePilot-Plugins`。
2. 运行 `python scripts/sync-upstream.py /tmp/MoviePilot-Plugins`，只覆盖 HDHive / Dian115 客户端及最小依赖文件。
3. 运行 `python scripts/check-client-contract.py` 校验上游签到契约；失败则直接终止，等待人工适配。
4. 检测到变化时运行 `python scripts/bump-version.py`，自动提升补丁版本并写入更新日志。
5. 推送变更，随后重建 GitHub Release。

上游提交后，MoviePilot 会在下一次刷新插件市场时看到新版本。也可以手动触发该 Workflow 立即同步。

`release.yml` 用于人工维护：只要 `package*.json` 被推送或手动触发，就会按索引版本重新打包并发布 Release。

## 本地维护

```powershell
# 同步上游（需先克隆上游仓库）
python scripts/sync-upstream.py C:\path\to\MoviePilot-Plugins

# 提升版本（默认 patch）
python scripts/bump-version.py --message "说明本次变更"

# 本地校验：规范检查 + 上游契约 + 编译 + 打包
python scripts/check-plugin.py
python scripts/check-client-contract.py
python -m compileall plugins.v2 scripts
python scripts/build-release.py --out dist
python scripts/publish-release.py --dist dist --dry-run
```

首次推送到新仓库：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\upload-to-github.ps1 -RepoUrl "https://github.com/<用户名>/<仓库>" -Token "<PAT>"
```

## 许可

遵循上游仓库的 GPL-3.0 许可，见 [LICENSE](LICENSE)。
