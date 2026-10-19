# 学习计划动态调整 MVP（2026-10-19）

## 基线与实际范围

本阶段基于b3d78a8171b5e331b77662b55859f68f32f8d205开发，开始前核对129份已跟踪运行源码与Git导出一致。用户后续明确授权同步源码、合成测试和公开说明，并将版本更新为0.3.4；提交以Git记录为准。版本更新不代表真实模型、桌面或私人库迁移已经验收。

实现闭环：已有学习计划→选择依据→本机预览资料和提供方→明确确认后调用所选模型→结构化有限调整草稿→原安排与建议比较→人工修改/取消→确认后更新原计划→查看确认记录。

没有自动提醒、后台Agent、自主修改计划、全局长期记忆、学习画像、RAG、同步或多Agent；未改无关音乐/宠物/语音/地图模块，也没有重构OpenRouter或模型路由。

## 数据选择与模型边界

- 原计划卡片增加“调整学习计划”。目标与原安排/完成标记需明确勾选，另外可选剩余任务详细状态，默认都不勾选。
- 进度候选索引仅列本计划记录ID、任务、报告时间和分钟，不读取候选备注正文；测验候选索引仅列本计划已提交记录的ID、任务和时间，不读取题目或答案。正文只按用户选择的ID读取。原学习页自身已有的本机进度展示行为不变。
- 最多选50条用户自报进度、20条已提交测验，可补充最多2000字要求。拒绝跨计划记录、无关联知识点测验、重复/不存在ID、未提交测验。资料总量超过150000 UTF-8字节时要求减量，不静默截断。
- 模型只接收本次明确选中的目标/原任务安排、可选剩余状态、选中进度、选中测验及其人工更正、补充要求；无聊天、画像、其他课程或全部检验历史。未选择剩余详细状态时只保留完成/取消标记，其他状态统一标为remaining。
- 页面先显示提供方/选模、目标与范围、记录数量、所选备注和测验摘要；可展开完整发送内容。再次勾选确认后才能生成。预览不调用模型，也不写正式计划。
- 服务端重新构建所选资料并比较预览指纹，资料或模型变更即拒绝发送。learning_model新增可选expected_selection，在实际预留预算和调用前检查提供方/选模仍与预览一致；原调用默认行为不变，本机auto选择以现有选模策略为准。
- 复用learning_model、预算、providers/local_runtime、禁工具及脱敏日志；单次最多8192输出Token，不自动重试、不换付费型号或提供方。未发生真实模型切换或真实付费调用。
- 区分程序客观判分、用户自报时长/自评、模型辅助评价及人工更正。提示要求更正优先，单次测验不等于掌握，不编造时长/成绩/教材/偏好；每项建议引用明确选中的plan/progress/check/user依据。引用存在不证明语义或事实正确，仍需用户核对。

## 有限变更、兼容校验与历史保护

- 模型输出summary及1至12项changes，不生成另一套完整计划。每项为update/add/cancel，含受限任务字段、原因和1至5个所选依据引用。拒绝未知字段、外来任务ID、重复操作同一任务、无实际变化的修改及未选依据引用。
- 已完成和已取消任务锁定。其余不涉及的任务也跳过写入，保留原行（包括时间、状态、来源）；不会因为重新序列化而覆盖完成项或历史时间。修改保留原ID与状态，新增才创建任务；取消仅将原未完成任务标cancelled。
- 动态调整不修改课程、基础、目标内容、原起止日期或每日预算。新增/修改任务不能排在生成当日之前。原目标仍是同一个ID，不生成重复目标。若当前日期/剩余时间无法满足约束则明确失败，可取消草稿或在原编辑入口人工核对约束后重新选择。
- 复用learning.plan校验任务日期、1至31天窗口、2至93项有效任务、字段长度、每日分钟总预算及review/practice要求。最小兼容改动仅是：已有计划允许空出的休息日，新计划仍要求每天有安排。既有非法或相互冲突的安排不通过此模块绕过校验。
- 学习页显示所有原任务的保持/修改/取消情况、建议新增项、前后日期/分钟/内容及原因。草稿支持改字段和原因、移除某项建议或手动增加建议任务；保存时再次执行同样校验。窄屏改为逐项纵向比较。
- 正式保存复用learning.save、agent_state.mutate、原agent_state_requests及BEGIN IMMEDIATE事务，不复制任务/目标系统。learning.save增加内部begin=False接入外层事务及preserve_ids跳过未改变的任务；默认原保存路径保留。
- 用户最初选择的revision贯穿生成与保存；保存时在事务内重读目标和任务，过期版本拒绝。选中的进度/测验（含更正）若变化也拒绝，要求重选；未选中的学习记录变化不会影响调整，也不读取其正文。
- 目标/任务更新、新增与取消、原去重回执、调整记录的confirmed状态在同一事务提交。故障全部回滚；服务只在连接提交成功后返回保存成功。
- 同保存request_id重试核对原回执，不新增任务、不重复写确认记录；不同任务内容或原因拒绝使用旧ID。已保存后即使其他入口再修改计划，旧回执也不会覆盖新状态。目标删除沿用底座回执删除标记。
- 已完成任务、task_progress、学习检验题目/答案/反馈及人工更正均不被更新或删除；测试对完成行（含日期时间）和历史逐项比较。

## SQLite 与请求恢复

只新增learning_adjustments表及goal_id/created_at索引：id、goal_id、revision、生成请求fingerprint、state、selection、evidence、original、proposal、model、final_changes、save_request_id、created_at、confirmed_at。

该表保存有明确来源的草稿/确认记录与历史快照，不是平行计划库。正式当前计划仍只在goals/tasks，进度与测验仍在原表。CREATE TABLE/INDEX IF NOT EXISTS在正常server.init执行，旧库不清空或重建；本轮只验证临时旧结构迁移和重复初始化，没有迁移正式私人数据库。

生成前先保存generating请求占位，成功后才成为draft；同ID重试仅读取原草稿，处理中/失败/中断不会补调用。失败保留最少请求元数据并清除资料快照。取消会清除草稿、依据和模型内容，留ID/指纹/状态去重；不改正式目标、任务或确认历史。这里的草稿元数据持久化不等于计划已经保存。

浏览器仅保留当前调整ID、用户编辑的变更及待核请求；服务端保留草稿，可刷新恢复。生成/保存回执丢失时固定同请求内容，保存草稿锁定，只允许“核对同一调整请求”；不会自动重做。明确返回400/500时释放本次待核状态，允许修改后重新确认。生成请求已中断且无法恢复时，可明确结束跟踪后重新预览生成（新调用可能计费）；不后台补发。

## 接口与未来读取入口

均继承本机会话Cookie、Host/Origin、JSON及错误脱敏；不注册聊天工具。

| 操作 | 接口 |
| --- | --- |
| 本计划候选索引/原安排 | GET /api/learning/adjustments/options?goal_id=... |
| 本机依据与提供方预览 | POST /api/learning/adjustments/preview，selection |
| 明确确认后单次生成 | POST /api/learning/adjustments/generate，request_id/selection/preview_hash/model/confirmed=true |
| 恢复指定草稿 | GET /api/learning/adjustments/{id} |
| 比较编辑后确认保存 | POST /api/learning/adjustments/confirm，request_id/adjustment_id/changes |
| 取消草稿 | POST /api/learning/adjustments/{id}/cancel，空对象 |
| 已确认历史 | GET /api/learning/adjustments?goal_id=... |

selection字段：goal_id、初始revision、include_plan、include_remaining、progress_ids、check_ids、note。每次预览从本机明确所选ID重建资料，指纹绑定提供方与型号，不信任浏览器伪造版本或记录归属。

未来提醒模块可显式调用learning_adjustments.reminder_view(connection, goal_id, today)：返回当前目标、今日及逾期任务、后续任务与已确认调整摘要，不读取进度备注/测验题答、不调用模型、不启动提醒。尚无自动调用方；进一步云端发送或后台提醒仍须单独实现授权与可见提示。

## 文件清单

新增learning_adjustments.py、web/learning-adjustments.js、test_learning_adjustments.py、test_learning_adjustments_ui.py、test_learning_adjustments_ui.cjs、本说明。

修改learning.py、server.py、web/learning.js、web/index.html、web/learning.css；更新仓库README、AGENTS与两处HANDOFF；本机历史交接和continuation不整份公开。本机测试截图artifacts/learning-adjustments-fixture.png为合成资料，原学习/检验/设置页回归也会重写其合成截图；不上传。

## 验证结果

```powershell
Set-Location ./companion-app
python -m unittest test_learning_adjustments test_learning_checks test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
python test_learning_adjustments_ui.py
python test_learning_ui.py
python test_learning_checks_ui.py
python test_openrouter_ui.py
node test_chat_retry.js
node --check web/learning-adjustments.js
node --check web/learning.js
node --check test_learning_adjustments_ui.cjs
python -m py_compile learning_adjustments.py learning.py server.py test_learning_adjustments.py test_learning_adjustments_ui.py
```

146项Python离线回归通过，其中动态调整专项19项。覆盖选择索引不读取正文、只发所选进度/测验及更正、跨计划/超限拒绝、预览和提供方变更、有效草稿、取消不改正式计划、原目标和任务ID、完成行/进度/检验/人工更正保留、休息日及原约束、冲突、事务失败整体回滚、并发去重、新增不重复、重启和独立进程读取、失效模型/预算不足、生成去重/中断不重试、HTTP权限及数据库错误脱敏、未来读取接口。最终小改确认回执只读路径后专项19项再次通过。

无界面Edge连接真实临时HTTP/SQLite：选择记录→预览/确认→生成→比较修改→取消→模拟生成丢回执/刷新同ID核对→模拟保存故障→保存丢回执/锁定/刷新同ID核对→确认摘要和历史→无效模型/预算失败→并发版本冲突→390px通过，无脚本异常。模拟5次独立生成，两次丢回执没有增加调用。初轮模型夹具按随机ID选中同一任务进行修改和取消，导致结构校验拒绝；已改为按日期明确选取，并按报告分钟选择唯一学习记录，复跑通过。

原学习页、检验页、OpenRouter设置页Edge、聊天重试及静态检查通过。全部使用临时库与合成模型；没有真实付费请求或正式服务操作。源码阶段快照仅限本机，跳过私人数据库。

## Windows 实际体验与未验收

1. 用户决定开始正式验收后，按原方式启动/重启应用加载运行源码；正常启动会执行已有状态/检验迁移与新增调整表初始化。本轮未操作私人库，临时迁移测试不代表它已验收。
2. 设置选择可用模型，云模型自行核对已有Key配置、生成开关和预算；不把Key贴入聊天。真实账号认证和实际费用仍须平台核对。
3. 学习页打开已有计划，点击“调整学习计划”，明确勾选原计划，按需选择剩余详细状态、若干学习记录/测验，填写调整要求。
4. 点击预览，核对将发送的内容、记录及提供方；确认后生成。先尝试取消，核对原计划未变；再生成，比较保持/改期/分钟/新增/取消项，编辑不合适内容。
5. 确认保存，核对“已实际保存”摘要、原目标ID、原完成项及学习/测验历史；刷新或正常重启后重新打开该计划的调整入口查看确认历史。
6. 若版本冲突，取消草稿并重新打开计划选择依据；若回执不明，先核对同一请求，不能连续点击新生成或用新保存请求代替核对。

仍未验收：真实Windows桌面宿主/WebView2、真实所选云/本机模型的结构化调整与事实/范围质量、真实Key/权限/账单、私人数据库历次迁移。日期、任务量或预算无法满足时本版拒绝草稿/保存，不自动延长计划、调整预算或修改已完成历史。模型原因及依据引用仅是建议，需人工核对。未重验无关外部平台功能。

完成本轮后立即停止，等待下一阶段指令；不继续主动督促或长期记忆。

## 0.3.4 同步验证

导出副本0.3.4验证：146项Python、动态调整/原学习/检验/OpenRouter设置页Edge、聊天重试及静态检查全部通过；18文件白名单、12份运行源码/测试/README逐字节比较及凭据模式检查通过。仅使用临时库与模拟模型，未启动正式服务或迁移私人数据库。
