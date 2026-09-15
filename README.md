# MoviePilot HDHive / Dian115 签到插件

从 [odomu/MoviePilot-Plugins](https://github.com/odomu/MoviePilot-Plugins) 中仅提取 **HDHive** 与 **Dian115** 的签到相关代码，重新打包为一个独立的 MoviePilot v2 插件。删除网盘、订阅、搜索、转存、刮削等冗余功能。

## 使用

在 MoviePilot 插件市场添加本仓库地址：

```text
https://github.com/behinder85/MoviePilot-Plugins
```

安装插件后配置：

- `checkin_cron`：每日签到时间，默认 `0 8 * * *`
- HDHive：WebAPI 模式填写用户名和密码；OpenAPI 模式填写应用 Secret、Client ID、回调地址，并按日志中的授权链接完成授权
- Dian115：填写邮箱和密码，可选启用转盘

## 目录结构

```text
.
├── .github/workflows/sync-upstream.yml  # 自动同步上游签到客户端代码
├── scripts/sync-upstream.py             # 上游同步脚本
├── icons/
├── plugins.v2/hdhive_dian115_checkin/
│   ├── __init__.py                       # 插件入口与调度配置
│   ├── checkin_service.py                # 精简签到编排
│   ├── search/hdhive/                    # 上游 HDHive 客户端
│   ├── search/dian115/                   # 上游 Dian115 客户端
│   ├── search/…                          # 共用 HTTP/风控/资源类型模块
│   └── utils/…                           # 共用缓存、HTTP、文件解析模块
├── package.v2.json
└── LICENSE
```

## 自动更新

GitHub Actions 每天 UTC 16:00（北京时间 00:00）克隆一次上游仓库，并执行：

```bash
python scripts/sync-upstream.py /tmp/MoviePilot-Plugins
```

脚本只覆盖 HDHive/Dian115 客户端及其最小依赖文件，不会覆盖本插件的入口、签到编排和 `package.v2.json`。上游有更新时会自动提交并推送。

首次推送本仓库到 GitHub 后，请手动运行一次 `Sync HDHive/Dian115 Checkin` Workflow，或等待定时任务执行。

## 本地上传

没有安装 `gh` CLI 时，可先创建 GitHub 仓库，然后执行：

```bash
git remote add origin https://github.com/behinder85/MoviePilot-Plugins.git
git branch -M main
git push -u origin main
```

同时请把 `package.v2.json` 和 `plugins.v2/hdhive_dian115_checkin/__init__.py` 中的 `behinder85/MoviePilot-Plugins` 替换为真实地址。
