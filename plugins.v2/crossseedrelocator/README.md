# CrossSeed辅种路径回迁（CrossSeedRelocator）

用于 Transmission + cross-seed 组合下的辅种路径治理：

- 把 cross-seed 注入到链接目录（如 `/机械/Cross-Seek`）的辅种，保存路径回迁到原始下载路径（`/机械/download` 等），并去掉 `cross-seed` 标签；
- 找不到源（季包聚合生成、源种子已删除）的种子原地保留，并保留 `cross-seed` 标签作为标识，不会误删数据；
- 定期清理链接目录中未被 Transmission 引用的文件与空目录，默认仅预演。

## 配置

在插件配置页设置：运行开关、cron（默认 `0 3 */7 * *`）、单轮上限（不限 / 数量 / 体积 / 时长，可组合）、目标路径优先级与排除路径、清理开关与预演模式、通知项。

Transmission 连接复用 MoviePilot 已配置的下载器（名称默认 `Transmission`），无需重复填写地址与凭据。

## 使用

1. 配置页点「保存」后进入主控台，先点「预演」查看待处理清单与推断目标路径；
2. 确认无误后点「执行」，任务在后台线程运行，轮询校验通过才去标签、清链接；
3. 单条失败会自动回退旧路径并支持回滚；AppPage 可查看历史、无源清单、清理预演与日志。

## 说明

- 回迁使用 Transmission `torrent-set-location`（会触发一次校验，属正常现象，日增辅种量通常为个位数）；
- 前端为 Vue 联邦模式（`frontend/dist/assets`），无需额外构建即可安装。
