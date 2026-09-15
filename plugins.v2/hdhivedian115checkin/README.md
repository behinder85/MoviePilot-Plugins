# HDHive / Dian115 签到

该插件仅包含 HDHive 与 Dian115 两个渠道的每日签到、Dian115 转盘和结果通知。

- 目录名固定为 `hdhivedian115checkin`，即插件主类名 `HDHiveDian115Checkin` 的小写形式，修改目录名会导致 MoviePilot 无法安装。
- `search/`、`utils/` 下的客户端核心代码由上游 [odomu/MoviePilot-Plugins](https://github.com/odomu/MoviePilot-Plugins) 自动同步。
- `__init__.py`、`checkin_service.py` 为本仓库维护的入口与签到编排，不会被上游同步覆盖。
