# 阶段05：主动学习督促 MVP（2026-10-19）

## 当前状态与范围

实际运行源码D:/StudyLifePlan/companion-app，版本保持0.3.4。开发阶段只做应用内学习提醒及今日回顾，未启动正式服务或迁移私人数据库；之后按用户“同步至git”指令同步本阶段代码、合成测试与公开说明，提交以Git记录为准。没有模型调用、系统通知、后台服务、开机自启、监控、跨设备推送、自动调整计划或长期画像。OpenRouter/模型路由、音乐、语音、地图、Live2D业务代码不改。

已核对现有Python 3.12.14：C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；本轮自动化使用该解释器，未修改系统默认Python。

## 使用流程

- 学习页增加“应用内学习提醒（默认关闭）”设置及今日学习回顾。用户主动勾选并保存后启用；提醒显示在现有主界面的单个轻量区域，不打开模态弹窗。
- 默认提醒时段09:00至21:00、勿扰22:00至08:00。可修改时段和每日上限（默认4次，允许1至8次）。支持跨午夜；起止相同拒绝，结束边界不属于对应区间。采用运行设备本地日历和时区。
- 提醒聚合今日及逾期待开始、进行中、暂停、延期任务，显示真实课程/任务/状态和今日完成计数。优先进行中，其次按日期和ID排序；最多展开3项，其余以数量提示，可到学习页查看全部。已完成/取消任务及已完成/取消目标不参与提醒。
- “开始学习”只有明确点击才更新任务为active；服务使用Agent原校验及事务，再返回已提交回执。客户端还GET回读当前任务状态，必须仍为active才显示核对成功并定位对应卡片。旧卡片上的任务内容/时间/状态或目标信息改变时拒绝旧操作，不覆盖更改。
- “15分钟后提醒”“60分钟后提醒”仅延后整条聚合提醒；“跳过/关闭”仅处理该条提醒；“今天不再提醒”和设置中的“今日暂停”暂停当天所有主动学习提示。“恢复今日提醒”恢复开关下的正常判断，但不清除已处理记录或频率上限。
- “查看计划”定位对应任务并关闭当前提醒，不写任务事实。所有提醒关闭、忽略、暂停和稍后都不等于完成、取消或延期任务。
- 今日回顾显示按当前安排日期计算的计划数、完成数、剩余数，另列延期及逾期提示。实际分钟只累加执行记录recorded_at转换本机时间后属于今天且明确填写的minutes；0是用户明确填写的0，无分钟则未知/未填写。部分未填、执行日期无效/空的记录另提示，不补造时长，不读取备注正文，不根据任务或测验推断掌握。

## 触发与频率

1. 启动页面、打开学习页、学习数据刷新、页面恢复可见/焦点时检查；另有60秒低频检查，页面不可见时跳过。无服务端调度线程。检查在进行时合并后续强制检查，不堆叠请求。
2. 每次检查在同一BEGIN IMMEDIATE事务中选取候选、核对已处理状态、记录一条聚合送达。并发页面/连接只产生一份相同任务的主动送达。同一任务每天最多主动出现一次，只有用户显式稍后可再次出现；所有送达（含稍后）共用每日上限。
3. 新主动提醒间隔至少30分钟；显式15分钟稍后可不受这30分钟间隔约束，但仍受勿扰、时段、今日暂停及日上限约束。稍后时间是最早允许再次提示的时刻，不保证在关闭、隐藏或勿扰期间准点出现。
4. 休眠或勿扰结束后，将已到期稍后与新候选合成一条，不回放逐条积压队列。完成、删除、取消或内容改变的旧稍后任务不复活。跨午夜按新本地日计算上限及暂停；跨日稍后仍重新校验当前任务。
5. 送达在返回HTTP之前持久记录；刷新/重启不重新展示同一已处理任务。响应丢失可能少显示一次，优先避免重复打扰。页面隐藏会放下当前卡片，后续不自动复现同一条。
6. 保存动作在浏览器保留同一request_id，回执不明时仅显示“核对同一提醒操作”，刷新后也不自动补发。状态回执与任务操作同事务，重复请求不重做，冲突ID拒绝。
7. 最后送达时间采用持久化epoch防止时钟回拨造成重复。若系统曾被大幅调快后调回，主动提醒可能暂时受抑制，直到时间追上最后送达时刻；不擅自清除去重数据。页面检查也重新计算本地日期、时段及勿扰，不依赖堆积的定时器次数。

软件关闭后不继续检查或提醒。WebView2最小化/休眠恢复的真实事件行为仍须用户验收，不能用无界面Edge替代。

## 数据结构与接口

复用learning_adjustments.reminder_view的显式本机只读入口、goals/tasks及task_progress；不访问测验题目/答案、完整聊天、私人画像、健康或无关活动资料，不向模型注册工具。SQL权限测试禁止读取进度note/percent、聊天和检验表，提醒仍能正常形成。

仅新增learning_reminders表及day/delivered_at索引：id、day、delivered_at(epoch)、state、wake_at(epoch或null)、snapshot（任务ID→内容版本哈希）。状态包括open/snoozed/consumed/dismissed/started/paused；只表示提醒交互。snapshot不保存课程/标题/备注正文，显示内容每次从当前计划读取。版本哈希覆盖任务和目标元数据，不仅依赖可能重复的更新时间。

提醒设置保存在原settings表的learning_reminder_settings键；enabled默认false，与旧未实现的系统提醒reminders_enabled分开。操作回执继续使用agent_state_requests，来源learning_reminder:request_id；不建立第二套任务库。task写入和提醒状态/回执同事务提交，写失败全回滚，HTTP成功在事务提交之后返回。

| 接口 | 行为 |
| --- | --- |
| GET /api/learning/reminders | 只读设置与今日回顾，不发出提醒 |
| POST /api/learning/reminders/check | 接受可选current_id，检查并领取至多一条聚合提醒 |
| PATCH /api/learning/reminders/settings | request_id及受限开关/时段/每日上限 |
| POST /api/learning/reminders/action | request_id、action；支持start/snooze/dismiss/pause/resume，按操作接受reminder_id/task_id/minutes |

均沿用会话Cookie、Host/Origin、JSON、字段校验和数据库异常脱敏；无远程接口。新表/设置仅挂接正常server.init；本轮只对独立临时库执行，包括已有结构重复初始化，不触及正式私人库。旧0.3.4尚待验收的初始化迁移也没有在原库执行。

## 文件清单

新增：learning_reminders.py、web/learning-reminders.js、web/learning-reminders.css、test_learning_reminders.py、test_learning_reminders_ui.py、test_learning_reminders_ui.cjs、本说明。

修改：server.py（初始化及本机接口）、web/index.html（组件/设置/回顾容器）、web/learning.js（任务定位标识、焦点及学习数据刷新事件）。

仅测试修正：test_agent_state.py、test_chat_attachments.py显式关闭旧迁移夹具的SQLite连接，避免Python3.12/Windows临时文件清理占用；test_openrouter_ui.py明确替换凭据加载为空字典。未修改这些模块的业务实现或模型路由。

公开同步更新两级HANDOFF.md及本说明；原机continuation.md、合成截图和源码快照不上传。

## 验证结果及隔离说明

- Python 3.12.14最终168项通过（旧149项+提醒19项）。覆盖待开始/进行中/延期/逾期、无任务、完成/取消、15/60分钟、每日上限/新任务间隔、跨午夜及普通勿扰、跨午夜提醒窗口、休眠恢复聚合、时钟回拨、刷新/重初始化/独立进程去重、旧任务编辑（包括更新时间相同）/完成/删除拒绝操作、开始事务回滚/真实回执/同ID重试、实际分钟/日期/更正、SQL隐私读取边界及HTTP权限/脱敏故障。
- 最后完整回归额外保护hub.load_keys：只允许临时目录中的合成DPAPI测试文件，拒绝真实凭据库路径，168项通过。普通明文模型响应均合成，提醒专项及提醒页面模型调用为0。
- 新提醒完整生产HTML/全部脚本、真实临时HTTP/SQLite、可控时间的Edge自动化通过：主动启用、未知时长、15分钟稍后、失败不假报、丢回执/重载/同ID核对、回读进行中后定位任务、今日暂停持久化、外部修改拒绝、聚合关闭及查看计划、重载去重、390px、脚本无异常。没有仅用DOM假按钮代替数据库状态验证。
- 原计划/检验/调整/OpenRouter设置页Edge及0.3.4完整学习链生产页Edge通过；聊天Node重试通过。静态JS与Python编译检查通过。
- 首轮新测试夹具忘记关闭连接，修正后19项通过；3.12回归另暴露上述两份旧夹具清理问题，修正后完整回归通过。提醒页测试还补齐了检查在途时事件合并、查看计划动作顺序与状态回读覆盖。

凭据隔离限制须如实保留：首次复跑旧test_openrouter_ui.py时，旧夹具的其他提供方列表刷新存在未替换的hub.load_keys路径，可能触及真实凭据读取，无法把首次运行称作完全隔离；HTTP始终由合成Response替换，没有输出、上传或真实API发送密钥。随后为该夹具加入强制空凭据，复跑通过；最后回归再加仅允许临时合成凭据文件的路径保护。此问题是测试隔离缺口，不应声称本轮从未可能触及真实加载路径。

复现（均在运行源码目录，使用上述3.12解释器，不启动正式服务）：

```powershell
$stage05Python = 'C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location D:/StudyLifePlan/companion-app
& $stage05Python -m unittest test_learning_reminders test_learning_system_034 test_learning_adjustments test_learning_checks test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
& $stage05Python test_learning_reminders_ui.py
& $stage05Python test_learning_system_034.py --ui
& $stage05Python test_learning_ui.py
& $stage05Python test_learning_checks_ui.py
& $stage05Python test_learning_adjustments_ui.py
& $stage05Python test_openrouter_ui.py
node test_chat_retry.js
node --check web/learning-reminders.js
node --check web/learning.js
node --check test_learning_reminders_ui.cjs
& $stage05Python -m py_compile learning_reminders.py server.py test_learning_reminders.py test_learning_reminders_ui.py test_agent_state.py test_chat_attachments.py test_openrouter_ui.py
```

## 本机体验与未验收

1. 本轮没有启动正式18764服务，用户决定接受正式迁移后才使用匹配3.12的原启动方式。正常初始化将新增上述提醒表/索引和设置键，并仍会执行原0.3.4学习检验/调整初始化；不能把临时库结果当私人库验收。
2. 打开学习页查看今日回顾；无实际分钟应显示未知。展开提醒设置，核对设备本地时间，主动勾选启用并保存时段、勿扰及每日上限。
3. 在已有合成或用户自行选择的真实任务上体验提醒；点击开始后核对“进行中”及卡片定位。用稍后15/60分钟、关闭、今日暂停及重启验证不重复打扰，确认这些操作没有完成/取消/延期任务。
4. 在其他页面更改/完成任务，返回学习页核对回顾；在提醒展示后从另一入口编辑/删除任务，确认旧按钮被拒绝。主动查看计划只定位，不自动改计划或检验结果。

未验收：真实Windows/WebView2提醒布局及前后台/休眠事件、正式私人库迁移；真实OpenRouter/模型/账单仍维持此前待验收状态，本阶段不依赖模型。时段内已无待处理任务时不主动弹“全完成”提示，今日回顾仍可查看。没有系统通知或程序关闭后的提醒能力。

本阶段开发完成；本次仅按用户后续指令同步Git，完成后停止，不开展下一阶段。本轮未发生真实模型切换。
