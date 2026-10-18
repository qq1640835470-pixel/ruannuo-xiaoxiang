# 最小 Agent 状态底座（2026-10-18）

本轮仅提供本机结构化状态接口，不是学习计划生成器或新的长期记忆系统。版本保持0.3.3，历史验收与本轮离线测试分别记录于HANDOFF.md。

## 复用与增量

- 复用server.py的同一SQLite、tasks表、事务连接、本机cookie/Host/Origin检查、预算、模型路由与脱敏日志。persistent_memory.py继续保存有来源的用户原话，local_adaptation.py继续处理有界偏好/纠正，不复制目标或进度到这两个系统。
- agent_state.py新增goals、task_progress、agent_state_requests表；tasks仅增加goal_id、updated_at、source_id、updated_source_id。旧ID、标题、备注、时间、状态不变；旧来源标为legacy，不伪造聊天来源。
- 目标、任务与进度本身就是本轮的结构化持久记忆，可读取、编辑与删除；不增加向量库、画像或聊天总结。
- 不向providers.TOOLS注册新工具，connectors.py与typed_tools.py现有校验继续复用。未来Agent只能经明确授权的接口访问；记录文字不能授予权限。
- 移除context()自动附带任务标题的行为，新目标、关联、进度及备注不自动加入本地或云模型上下文。用户自己发出的聊天原文仍遵循现有聊天历史机制，此改动不等于从历史中删除用户说过的内容。
- 模型create_task仍使用现有工具，但协调器只接受当前消息中明确的保存任务指令；否定、引述、示例或仅生成计划不能触发保存。措辞不匹配时可在原计划页手动保存，不通过模型声称“已确认”来授权。普通文字回复不是结构化写入证据。

## 本机接口

均沿用本机页面会话与JSON请求体；无远程接口或任意命令入口。只有事务提交后HTTP接口才返回成功。不存在的记录/错误字段返回400，不泄漏原始数据库异常；数据库故障返回500且不报告完成。

| 操作 | 接口 |
| --- | --- |
| 创建/列出目标 | POST / GET `/api/goals` |
| 读取/修改/删除目标 | GET / PATCH / DELETE `/api/goals/{id}` |
| 读取目标关联任务 | GET `/api/goals/{id}/tasks` |
| 创建/列出任务 | POST / GET `/api/tasks` |
| 读取/修改/删除任务 | GET / PATCH / DELETE `/api/tasks/{id}` |
| 新增/读取某任务进度 | POST / GET `/api/tasks/{id}/progress` |
| 读取/纠正/删除某条进度 | GET / PATCH / DELETE `/api/progress/{id}` |

目标写入字段：title（必填，1–200字）、details（最多2000字）、deadline（可留空，ISO日期时间）、status。

任务写入字段：title（创建必填）、details、scheduled_at、status、goal_id。goal_id为空解除关联，非空必须为已存在目标；不能创建另一套待办。原有创建接口默认pending，PATCH保留ok字段并返回task供界面回读。

状态：pending待开始、active进行中、paused暂停、deferred延期、done完成、cancelled取消。原任务状态值均保留；原计划页下拉框增加延期/取消，取消条目可在“全部”中查看。状态由明确写入决定，100%进度不会自动完成任务，全部任务完成也不会自动完成目标。

进度字段：note（最多2000字）、percent（0–100或null）、minutes（0–1000000整数分钟或null）、recorded_at（可选ISO日期时间，默认本次记录时间）。创建必须至少有备注、百分比或时长之一。minutes是该条记录的用户报告实际时长，不启动计时器；不自动叠加到任务或推断学习成果。进度按记录创建时间列出，recorded_at可保存补记的执行时间。

每条新记录均有id、created_at、updated_at、source_id、updated_source_id；服务生成UTC时间与来源。来源local_api表示经过本机会话的显式接口操作，user_message包含相应聊天消息ID；不允许请求体覆盖来源或创建时间。legacy仅表示迁移记录的原来源未知。目标详情额外返回task_ids。

删除目标会解除任务关联并更新这些任务的修改来源，不删除任务。删除任务会删除其进度；删除进度不会删除任务。更正使用PATCH，不把错误文本另存成新事实。

## 重复请求与持久化

所有写接口可传request_id（1–64个英文字母/数字/下划线/短横线）。同ID同内容重试返回当时提交的回执，不重做操作；同ID不同操作、目标或内容返回400。要进行下一次修改应使用新ID。回执是历史快照，当前状态用GET核对；旧回执重试不会覆盖后续修改。

状态和回执在同一BEGIN IMMEDIATE事务提交；跨连接并发重复请求只产生一条记录。数据库错误会整体回滚，无自动重试。旧客户端可以不传request_id；此时每次POST都是独立新记录，不能仅按标题猜测重复。模型同消息同参数的create_task调用使用服务派生的稳定请求ID。

删除时将该实体相关回执的正文替换为仅含ID的删除标记，避免通过重复请求复活已删除记录，也不在回执中继续保留已删标题/备注。请求指纹和删除标记仍留本机用于去重；SQLite物理页、系统备份和原聊天的清除不在此接口范围内。

迁移在下次正常server.init()时进行，无清库、重建、覆盖用户数据库操作。本轮没有启动真实服务或对私人数据库执行迁移，使用临时数据库验证了旧结构迁移、重复初始化、连接关闭重开与独立Python进程读取。

## 本机验证

在PowerShell执行：

```powershell
Set-Location D:/StudyLifePlan/companion-app
python -m unittest test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime test_models -q
node --check web/app.js
node test_chat_retry.js
```

测试全部使用独立临时数据/合成模型响应，不调用真实付费API。test_agent_state覆盖目标、关联、状态、进度、纠正/删除、旧表迁移、跨进程读取、并发去重、非法输入、事务失败回滚、HTTP故障/权限和上下文隔离。

需要实际体验时，正常启动/重启应用，在原计划页创建任务，切换延期/取消并重启核对。目标和进度本轮没有新增表单，使用上表接口；不要把接口测试通过等同于已有目标管理界面。

尚未实际验收：真实私人数据库启动迁移、Windows桌面宿主/WebView2操作、DPAPI与显卡/本地模型联调、真实模型返回；未重验音乐、语音、地图、Live2D和前端WIP。没有新增提醒、后台任务、学习业务、同步或旧反馈桥修改，没有提交/推送或变更版本号。
