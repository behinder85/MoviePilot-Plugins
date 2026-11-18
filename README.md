# MoviePilot 插件库（HDHive/Dian115 签到 + CrossSeed 辅种路径回迁）

本仓库包含两个独立的 MoviePilot v2 插件：

- **HDHive / Dian115 签到**：从 [odomu/MoviePilot-Plugins](https://github.com/odomu/MoviePilot-Plugins) 提取 HDHive 与 Dian115 签到相关代码重新打包，删除网盘、订阅、搜索、转存、刮削等冗余功能。
- **CrossSeed辅种路径回迁（CrossSeedRelocator）**：把 cross-seed 注入到链接目录的辅种在 Transmission 中的保存路径回迁到原始下载路径，去掉 `cross-seed` 标签并清理链接目录；无源种子原地保留，支持链接目录清理（默认仅预演）。

## 使用

在 MoviePilot 插件市场添加本仓库地址：

```text
https://github.com/behinder85/MoviePilot-Plugins
```

然后在市场中安装所需插件。

## HDHive / Dian115 签到

配置说明：

- `checkin_cron`：每日签到时间，默认 `0 8 * * *`
- HDHive：WebAPI 模式填写用户名和密码；OpenAPI 模式填写应用 Secret、Client ID、回调地址，并按日志中的授权链接完成授权
- Dian115：填写邮箱和密码，可选启用转盘

## CrossSeed 辅种路径回迁

适用场景：cross-seed 通过 `linkDirs` 硬链接辅种并将其注入 Transmission，导致种子保存路径停在链接目录（例如 `/机械/Cross-Seek`）、数据被重复统计。插件把这些种子回迁到原始下载路径。

功能：

- **只读预演**：读取 Transmission 全库，列出保存在链接目录下的种子、推断源路径与候选，不产生任何修改；
- **批量回迁**：对每个种子执行 `torrent-set-location`（`move=false`，会触发一次校验）后轮询，校验通过（`pct=1`、状态回到做种、目录已切换）才去掉 `cross-seed` 标签并清理旧链接；
- **无源保留**：季包聚合生成或源已删除的种子原地保留，并保留 `cross-seed` 标签作为标识，避免误删唯一副本；
- **单条回滚**：失败自动回退旧路径，也可按种子手动回滚；
- **链接目录清理**：按 Transmission 当前引用集合保护在种文件，清理链接目录中未做种的文件与空目录，默认仅预演。

配置项：运行开关、cron（默认 `0 3 */7 * *`）、单轮上限（不限 / 数量 / 体积 / 时长，可组合）、目标路径优先级与排除路径、清理开关与预演模式、通知项。Transmission 连接复用 MoviePilot 已配置的下载器，无需重复填写地址与凭据。

## 目录结构

```text
.
├── .github/workflows/sync-upstream.yml   # 自动同步上游签到客户端代码
├── scripts/sync-upstream.py              # 上游同步脚本
├── icons/
├── plugins.v2/hdhive_dian115_checkin/
│   ├── __init__.py                       # 插件入口与调度配置
│   ├── checkin_service.py                # 精简签到编排
│   ├── search/hdhive/                    # 上游 HDHive 客户端
│   ├── search/dian115/                   # 上游 Dian115 客户端
│   ├── search/…                          # 共用 HTTP/风控/资源类型模块
│   └── utils/…                           # 共用缓存、HTTP、文件解析模块
├── plugins.v2/crossseedrelocator/
│   ├── __init__.py                       # 插件入口、调度、API 注册
│   ├── engine/                           # 回迁与清理引擎（TR RPC、推断、执行、日志）
│   └── frontend/                         # Vue 联邦前端（dist 已构建，可直接安装）
├── package.v2.json
└── LICENSE
```

## 自动更新

GitHub Actions 每天 UTC 16:00（北京时间 00:00）克隆一次上游仓库，并执行：

```bash
python scripts/sync-upstream.py /tmp/MoviePilot-Plugins
```

脚本只覆盖 HDHive/Dian115 客户端及其最小依赖文件，不会覆盖本插件的入口、签到编排和 `package.v2.json`，也不会影响 `plugins.v2/crossseedrelocator/`。上游有更新时会自动提交并推送。

首次推送本仓库到 GitHub 后，请手动运行一次 `Sync HDHive/Dian115 Checkin` Workflow，或等待定时任务执行。

## 本地上传

没有安装 `gh` CLI 时，可先创建 GitHub 仓库，然后执行：

```bash
git remote add origin https://github.com/behinder85/MoviePilot-Plugins.git
git branch -M main
git push -u origin main
```

同时请把 `package.v2.json` 和 `plugins.v2/hdhive_dian115_checkin/__init__.py` 中的 `behinder85/MoviePilot-Plugins` 替换为真实地址。

## 发版（Release 安装）

`CrossSeedRelocator` 在 `package.v2.json` 中声明了 `"release": true`，升级时 MoviePilot 会优先从 GitHub Release 下载资产安装（比逐文件拉取更稳）。每次发版请：

1. 推送代码后，在 GitHub 创建 Release，tag 填 `CrossSeedRelocator_v<版本号>`（例如 `CrossSeedRelocator_v1.1.1`）；
2. 上传资产文件 `crossseedrelocator_v<版本号>.zip`（文件名全小写）；
3. zip 根目录直接放插件文件：`__init__.py`、`engine/`、`frontend/dist/`、`README.md`。

Release 尚未就绪时插件仍会回退到文件列表安装，不会装不上。
