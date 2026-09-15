# HDHive / Dian115 签到

该插件仅包含 HDHive 与 Dian115 两个渠道的每日签到、Dian115 转盘和结果通知。

- 目录名固定为 `hdhivedian115checkin`，即插件主类名 `HDHiveDian115Checkin` 的小写形式，修改目录名会导致 MoviePilot 无法安装。
- `search/`、`utils/` 下的客户端核心代码由上游 [odomu/MoviePilot-Plugins](https://github.com/odomu/MoviePilot-Plugins) 自动同步。
- `__init__.py`、`checkin_service.py` 为本仓库维护的入口与签到编排，不会被上游同步覆盖。
- `get_form()` 按 `hdhive_query_mode` 条件显示：`web` 只显示账号密码，`api` 只显示 OpenAPI 应用配置。
- `get_page()` 提供详情数据页（运行概览、渠道状态、签到记录、刷新与手动执行），`get_api()` 注册
  `POST /checkin/{provider}` 与 `GET /refresh` 两个接口供该页面调用。
- `onlyonce_hdhive`、`onlyonce_dian115` 为“保存后立即执行一次”开关，触发后自动关闭并写回配置。
