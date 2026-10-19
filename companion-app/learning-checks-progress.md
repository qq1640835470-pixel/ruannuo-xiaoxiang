# 学习成果检验 MVP（2026-10-19）

## 实现与边界

版本仍为0.3.3。本阶段仅增加学习成果检验，用户已授权将源码、合成测试与本公开说明同步GitHub；提交以Git记录为准。未重做状态底座、学习计划或OpenRouter；没有自动重排、创建任务、长期记忆、RAG、后台督促、多Agent或同步功能。未启动正式服务或访问私人数据库、画像、聊天文件、凭据、模型权重与备份。

- 学习任务卡片增加“检验学习成果”。显示将发送的任务标题、内容和预期成果；用户主动点击生成后，读取该任务并核对范围快照。任务内容已被修改则拒绝发送，要求刷新。
- 也可明确切换“自选知识点”，不关联目标或任务，不发送任务栏以外内容。默认3题，可选3至5题；支持单选和简答。
- 复用server.learning_model与现有providers/local_runtime：使用设置所选提供方、型号、预算预留、用量结算和脱敏日志，禁用工具，无自动重试、换模或付费回退。本次没有修改providers或local_runtime。
- 模型仅获得选中任务的title/content/outcome或自选知识点；不发送整个目标、其他任务、进度、聊天、画像、历史测验。简答评价仅发送本次简答题、参考答案、解释与用户答案，用户需单独勾选授权，默认关闭。前端显示当前提供方与型号及可能计费说明。
- 题目严格校验数量、字段、题型、长度、选项唯一性、答案下标；每题附逐字来自所选范围的evidence。失败或结构无效不会保存有效测验，不提供伪造题目。提示与原文引用不能证明题目语义范围和事实正确性，仍需人工核对；模型可能产生有原文引用但不相关或错误的问题。
- 生成题目时保存完整版本快照，未提交时接口隐藏标准答案和解释。用户逐题作答后提交，单选由程序依据固定快照确定性判分。模型评价不接收客观题，也无法改标准答案。
- 简答辅助评价给出依据、遗漏/错误和改进建议；调用失败或反馈字段不合法时仍保存答案及客观题结果，将简答标为“未可靠评价”，无伪造评分。未勾选时不调用评价模型，可对照参考要点自行核对。
- 本次结果、逐题原题/作答/参考答案/解释、原始反馈、待复习建议、历史、下次复习建议均可查看。任务状态、测验表现、真实掌握程度分别表示，mastery始终为null。
- 用户可逐题更正结论并填写原因，保留原始结果及更正来源/时间；更正不修改客观题答案快照。原始模型问题有误时可标为“未可靠评价”并记录正确解释。可删除整份测验记录。

## SQLite 增量与请求一致性

新增两张独立表，不把测验塞入任务备注，不新建目标或任务系统：

| 表 | 保存内容 |
| --- | --- |
| learning_checks | id、schema_version=1、原goal_id/task_id、所选范围快照、题目与参考答案/解释、生成模型元数据、用户答案、客观结果/主观反馈及待复习标记、评价模型元数据、状态、生成/提交/更新时间、来源、更正列表 |
| learning_check_requests | 请求ID、操作及内容指纹、测验ID、pending/done/failed/deleted状态、仅含ID的回执、创建时间 |

新增task_id/created_at索引；server.init在agent_state.init后执行可重复的CREATE TABLE/INDEX IF NOT EXISTS。旧目标、任务、进度、ID与状态不改变。临时旧结构迁移、重复初始化、进程重开及独立Python进程读取通过；正式私人库未迁移。

题目、范围、答案和反馈的JSON属于版本1记录快照。与原任务/目标通过ID关联，删除原任务或目标后仍保留当时快照，不创建平行任务，也不靠外键级联悄悄删除历史检验。删除测验可在历史区独立操作。

模型调用前先提交pending请求占位，事务内防并发。相同ID和内容只核对原请求；不同内容拒绝。生成记录与完成回执在同一事务提交；提交答案与结果也原子提交。并发提交不同ID亦会阻止重复评价。失败/中断的请求不会因重试或服务重启再调用模型；若进程在调用后中断，无法保证拿回模型响应，明确保留待核状态，不以自动补调用弥补。

浏览器保留待核请求ID/正文及当前作答草稿；回执不明时锁定作答输入，刷新后可“核对同一请求”。如果失败或中断无法恢复，先查看历史，再主动“结束本次请求”。新生成明确意味着一次新调用。中断留下的提交占位可通过删除测验结束，不能自动重复付费评价。

删除会清除题目、答案、反馈、更正，并把相关旧请求回执变为删除标记，防旧请求复活；请求指纹、ID仍用于去重。SQLite物理页、浏览器/系统备份不属于安全擦除保证；浏览器当前测验草稿在删除回执成功后清除。

未来本机调整模块可调用learning_checks.selected_results(connection, ids)，必须明确选择1至20条已提交记录；返回所选原始结果与更正信息，调用方须理解更正优先、模型建议非事实。没有自动调用方、模型上下文注入或计划写入。将来若向云模型发送，还必须实现可见的逐条选择与发送确认，当前接口不构成云发送授权。

## 接口

均沿用本机会话Cookie、Host/Origin和JSON检查，异常数据库细节不向页面暴露。

| 操作 | 接口与主要字段 |
| --- | --- |
| 生成并保存有效题目 | POST /api/learning/checks：request_id、task_id或topic、count（默认3），任务入口另带scope_snapshot核对已展示范围 |
| 本机历史与详情 | GET /api/learning/checks；GET /api/learning/checks/{id} |
| 提交与可选评价 | POST /api/learning/checks/{id}/submit：request_id、answers（题号到选项下标/文本）、evaluate_short（默认false） |
| 更正评价 | PATCH /api/learning/checks/{id}：request_id、question_id、verdict（supported/needs_review/uncertain）、note |
| 删除测验 | DELETE /api/learning/checks/{id}：request_id |

仅提交后的GET返回完整参考答案和解释；原题与原判分不可通过更正接口覆盖。不新增可供聊天模型调用的工具。

## 文件

新增：learning_checks.py、web/learning-checks.js、test_learning_checks.py、test_learning_checks_ui.py、test_learning_checks_ui.cjs、本说明。

修改：server.py、web/learning.js、web/learning.css、web/index.html、仓库根目录HANDOFF.md；本机历史交接与续接文档不上传。

本机测试产物：artifacts/learning-checks-fixture.png；原学习页回归重新生成artifacts/learning-mvp-fixture.png。仅合成资料，不用于证明真实桌面验收，不同步Git。

## 验证

```powershell
Set-Location ./companion-app
python -m unittest test_learning_checks test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
python test_learning_checks_ui.py
python test_learning_ui.py
node test_chat_retry.js
node --check web/learning-checks.js
node --check web/learning.js
node --check test_learning_checks_ui.cjs
python -m py_compile learning_checks.py server.py test_learning_checks.py test_learning_checks_ui.py
```

最终127项Python离线回归通过，包括专项18项与原109项。专项涵盖范围隔离、独立知识点、3至5题、无效题目不保存、客观判分、简答失败无假评分、参考依据、保存/读取/更正/删除、删除回执、并发去重、不重复调用、失败/中断重试、事务失败、旧结构迁移/重复初始化、跨进程读取、原状态/学习记录保留、HTTP权限/脱敏及未来明确选择接口。

无界面Edge连接真实临时HTTP服务/SQLite，模型为合成夹具：任务入口→范围预览→生成后丢失回执→刷新同ID核对→逐题作答→勾选辅助评价→提交后丢失回执→锁定输入→刷新同ID核对→反馈→更正→重载→删除并确认浏览器作答草稿清除及刷新无旧题→独立知识点；390px无横向溢出、无脚本异常。模型实际模拟调用为3次：任务出题、所选简答评价、独立知识点出题；两次丢失回执均未增加调用。

原学习页Edge、OpenRouter设置页Edge流程与聊天重试、相关JS/Python静态检查通过。没有真实付费API请求，没有真实Key/私人库/桌面验收。

## 本机体验与未验收

1. 用户决定开始正式体验后，按原方式启动/重启应用加载运行源码；启动会执行先前状态底座及本轮新增表迁移。本轮未对私人库执行该操作。
2. 在设置选择可用模型；使用云模型时自行核对Key、生成开关与预算。Key仍使用已有本机隐藏输入流程，不贴到聊天里。
3. 学习页选择已保存任务，点击“检验学习成果”，核对显示的任务内容和预期成果，再点“发送所选范围，生成测验”。可改选3至5题；也可切换为独立知识点。
4. 作答。仅在愿意发送本次简答材料/答案并接受可能费用时勾选辅助评价；提交后核对参考答案、解释、反馈及待复习建议。
5. 更正有争议的评价；刷新/正常重启后打开历史，核对结果仍在。可删除测验，任务状态和学习进度不会随之修改。回执不明先核对原请求，不反复新建。

再次核对最新OpenRouter交接：真实Key配置、账号权限、真实聊天/学习JSON/测验生成、实际账单、Windows桌面宿主/WebView2体验及私人数据库迁移仍没有验收证据。本轮不读取凭据来推断Key有效，不将公开目录访问、临时合成DPAPI测试或离线模型夹具算作真实认证/生成通过。真实模型的题目事实、范围相关性与简答评价质量也尚待用户核对。

完成本轮后停止，等待下一阶段指令；无自动学习计划调整或其他后续开发。
