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
- `每日签到时间（cron）`：默认 `0 8 * * *`，即时区为 MoviePilot 的 `TZ`。
- `签到后发送通知` / `通知渠道`：签到结果通知。
- `HTTP/HTTPS 代理`：选填，例如 `http://127.0.0.1:7890`。
- HDHive：
  - `WebAPI` 模式填写用户名和密码。
  - `OpenAPI` 模式填写应用 Secret、Client ID、回调地址，按日志中的授权链接完成授权后再填入授权码。
  - `签到模式` 支持普通签到与赌狗签到。
- Dian115：填写邮箱和密码，可选启用转盘及转盘次数。

插件同时提供三个手动命令：`/hdhive_checkin`、`/dian115_checkin`、`/checkin_all`。

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
│   ├── build-release.py                 # 生成 Release 压缩包与发布清单
│   ├── publish-release.py               # 发布 GitHub Release
│   └── upload-to-github.ps1             # 本地首次上传脚本
└── package.v2.json                      # V2 插件市场索引（UTF-8 无 BOM）
```

## 与官方规范的对应关系

- **目录名 = 插件主类名小写**：`class HDHiveDian115Checkin` 对应 `plugins.v2/hdhivedian115checkin/`，MoviePilot 通过 `package.v2.json` 的键定位该目录。
- **三处版本一致**：`package.v2.json` 的 `version`、插件类中的 `plugin_version`、`history` 中最新的 `v{版本}` 必须相同。`scripts/build-release.py` 会在打包前强制校验。
- **Release 发布**：索引声明 `"release": true`，Tag 为 `HDHiveDian115Checkin_v{版本}`，资产为 `hdhivedian115checkin_v{版本}.zip`，压缩包顶层即插件目录。MoviePilot 优先按 Release 安装，失败时自动回退到文件列表安装。
- **系统版本约束**：`system_version` 声明为 `>=2.14.6`，不满足的 MoviePilot 会拒绝安装。
- **依赖**：V2 插件使用插件目录内的 `requirements.txt`。

> MoviePilot V3 在没有 V3 专用实现时会回退加载 V2 实现，因此本插件同时适用于 MoviePilot V2 与 V3。MoviePilot V1 只读取 `package.json` 与 `plugins/`，本仓库不再提供该代实现。

## 自动更新

`.github/workflows/sync-upstream.yml` 每天 UTC 16:00（北京时间 00:00）执行：

1. 克隆上游 `odomu/MoviePilot-Plugins`。
2. 运行 `python scripts/sync-upstream.py /tmp/MoviePilot-Plugins`，只覆盖 HDHive / Dian115 客户端及最小依赖文件。
3. 检测到变化时运行 `python scripts/bump-version.py`，自动提升补丁版本并写入更新日志。
4. 推送变更，随后重建 GitHub Release。

上游提交后，MoviePilot 会在下一次刷新插件市场时看到新版本。也可以手动触发该 Workflow 立即同步。

`release.yml` 用于人工维护：只要 `package*.json` 被推送或手动触发，就会按索引版本重新打包并发布 Release。

## 本地维护

```powershell
# 同步上游（需先克隆上游仓库）
python scripts/sync-upstream.py C:\path\to\MoviePilot-Plugins

# 提升版本（默认 patch）
python scripts/bump-version.py --message "说明本次变更"

# 本地校验：编译 + 打包
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
