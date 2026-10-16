# 一隅前端

由本机 HTTP 服务提供此目录，首页为 `index.html`。无需 npm、CDN 或编译步骤；直接双击 HTML 文件无法使用本机 API。

- 两页：对话、计划日程。设置、连接能力、余额、预算及退出入口在侧面抽屉。
- 所有消息、日程及设置来自 `/api/*`。输入 Enter 发送、Shift + Enter 换行；示例按钮只填充输入，用户点击发送才提交。
- 动作卡片仅通过 `POST /api/actions/{id}/execute` 执行，不直接打开返回的 URL。
- 动作 `prepared` 可点击；`requested` 显示“已请求打开”，`failed` 显示失败，两者禁止重复提交。普通模型回复明确标示来源，不能作为工具已执行的证明。
- 任务支持创建、编辑标题/具体日期/详情、完成、恢复、修改状态和删除，不创建默认任务。编辑表单可清空日期，恢复为未指定时间。
- 设置写入 `provider` 与 `api_generation_enabled`；真实型号 `model` 只读。预算读取 `settings.budget`，兼容 `/api/state`、`/api/settings` 顶层 `budget`。
- “系统语音朗读”使用浏览器 `speechSynthesis`，可用性与声音取决于浏览器及系统配置，未接入 Fish API。
- 手机屏幕适配仅针对布局，尚未实现设备同步、后台监控、定时催促或推送。
- 无本地浏览器存储；刷新时从后端恢复消息、日程及设置。后端需要为历史消息保存 `actions`，才能恢复操作卡片。
- 本机数据导出从 `GET /api/export` 生成 JSON 下载；不调用外部账号接口。

基础检查：`node --check app.js`；HTML ID 唯一且 JavaScript 使用的 ID 均存在。
