# 独立学习模型配置 MVP（0.3.4，2026-10-19）

本次在5225254暂停/继续修复基线上同步此前保留的独立学习模型WIP和续接补全，版本仍0.3.4。仅发布源码、合成测试与本说明，不包含运行设置、数据库、凭据、日志、截图或本机验收备份。旧交接中“独立学习模型留待后续”的描述是历史状态。

## 已实现

- 默认跟随聊天模型，旧用户不必重新选模；也可独立指定已有Gemini、DeepSeek、OpenRouter或准确本机型号。独立设置不修改聊天/桌宠选择。
- 复用原settings，新增learning_model_config和learning_selection_revision，重启保留；不新建配置库或第二套模型目录。
- 原OpenRouter模型中心提供“用作聊天模型”和“用作学习模型”，选择后须保存。继续复用搜索、分类、价格筛选、收藏、最近使用、分页和按任务验证记录。未验证候选有风险提示，目录元数据不等于真实兼容或账单。
- 学习需求分析、计划生成、自选知识点出题、已有任务成果检验、明确授权简答辅助评价、动态调整统一使用learning_selection/learning_model。自选出题与任务检验共用生成路径，但按两个实际入口分别验模。
- 保留任务开始反馈、暂停提示、继续入口、终态保护、回执/状态回读、提醒联动和原分钟记录。换模不删除计划、测验、任务进度或调整历史。

## 设置与请求数据流

```text
settings.learning_model_config + learning_selection_revision
→ learning_selection统一解析
→ model-preview或adjustments/preview中的资料hash和准确型号快照
→ 用户明确确认
→ 原request_id事务占位或回执恢复
→ learning_model在预算预留前重新校验快照、开关与本机型号
→ 原reserve → 单次providers.chat → 原settle
→ 结构/范围校验 → 草稿、测验或调整回执
```

配置为 `{mode:"follow",provider:"",model:""}` 或 `{mode:"independent",provider:"openrouter",model:"厂商/准确ID"}`。学习配置由原设置接口保存；客户端概览、确认框、请求与结果分别显示提供方和型号。聊天/桌宠不读取学习独立配置。

学习选择变化即递增revision，包括切回原型号；独立模式只改聊天不会改变学习快照。跟随本机时，本机选模控制接口也会先更新revision再写原选择文件，避免中断或往返切换使旧授权复活。失败的本机选模可能保守地使旧预览失效，但不会调用模型。客户端本机换模后清除旧调整预览并刷新学习摘要。

本机auto在预览时按已有规则解析成准确型号，本次请求固定该型号。动态调整保留原资料范围和明确确认，预览hash包含学习快照；实际调用前仍重验，其他窗口换模也会被拒绝。已完成回执优先按原ID恢复，不因之后换模重新生成。

分析/计划请求复用agent_state_requests；检验/简答/调整复用各自原事务和去重。失败、超时、待核或回执丢失不自动重试；无快照的旧未完成生成须重新确认。不得靠清空用量预留或创建新ID自动重发。

requested_model与returned_model分别保留。专用本机学习响应也记录实际返回ID，缺失为null；普通聊天/桌宠路径保持原行为。返回未知或不一致不能让请求型号获得“已验证”标记。

预算、凭据、云生成开关、资料发送确认和原请求去重均保留。OpenRouter继续require_parameters=true、allow_fallbacks=false，不自动跨提供方或换用其他付费型号。模型只接收本页明确输入/所选资料，不自动附带全部聊天、画像或未选历史。

## 本次代码与测试范围

业务：server.py、learning_checks.py、learning_diagnostics.py、model_center.py、local_runtime.py；web/index.html、web/model-settings.js、web/model-center.js、web/learning.js、web/learning-checks.js、web/learning-adjustments.js、web/local-model-settings.js、新增web/learning-model-settings.js。

新增专项：test_learning_models.py、test_learning_models_ui.py、test_learning_models_ui.cjs。兼容夹具：test_learning.py、test_learning_checks.py、test_learning_adjustments.py、test_learning_system_034.py；test_learning_ui.cjs、test_learning_checks_ui.py/.cjs、test_learning_adjustments_ui.cjs、test_learning_repairs_ui.cjs、test_learning_system_034_ui.cjs、test_model_center_ui.cjs、test_openrouter_ui.cjs。共28份代码/测试文件，任务暂停/继续逻辑没有退回旧版。

## 验证与边界

运行源码修改前实际复跑201项，通过；补六入口和历史保护后202项，通过；本机往返预览失效与真实返回ID补全后最终204项通过，其中独立选模专项18项。所有数据/目录/凭据/模型响应均为临时合成夹具，没有真实API调用。

覆盖：旧设置默认跟随、独立与聊天隔离、持久恢复、六个入口、调整预览/调用一致、变化再切回拒绝旧预览、本机auto固定、预算不足/云关闭/无Key/404/能力不足、请求待核/失败/丢回执去重、返回ID不伪造、验证不串型号、换模重启后五类学习历史表逐行保留。

12组Edge模拟验收：独立选模、1202候选模型中心、原P0任务反馈/自选主题、0.3.4完整学习链、提醒、计划、检验、动态调整、OpenRouter设置、任务状态专项、SQLite写入失败专项、固定旧基线问题复现。另聊天重试与相关Python AST/JS语法通过。模型中心操作不生成；新本机选模摘要更新也在Edge中检查。

测试曾因范围字段断言、同秒用量排序及折叠摘要等待可见而失败，修正相应夹具后通过，没有删除保护断言。页面刷新取消只读请求可能产生Windows连接取消提示，不能据此自动重发付费调用。

原生Windows WebView2在隔离临时服务、临时SQLite和独立profile中检查了跟随默认、独立型号保存、聊天/学习分离与关闭重开恢复；生成调用0。后补的本机边界由Python/Edge验证，没有在原生窗口重复全部模型中心与故障矩阵。正式用户数据和服务未启动、未迁移；不以合成通过宣称真实OpenRouter兼容或题目正确。

本次同步在导出副本重新验证：204项Python、上述12组Edge、聊天重试、Python AST/JS语法及Git差异检查通过。额外进程级保护下，正式私人路径访问尝试0；28份代码/测试与运行源码逐字节一致。原生WebView2证据沿用运行源码本轮隔离验收，未对导出副本重复原生宿主测试。

## Windows与最低真实验收步骤

1. 用户自行决定是否在已备份的正式数据或可丢弃副本启动应用。正常启动可能执行既有初始化，正式私人库升级尚未验收。
2. 设置→学习模型：核对默认跟随；保存独立选择后改变聊天型号，学习型号应不变。重开后再次核对。模型中心选择、保存和查看候选不生成。
3. 已有任务开始→暂停→继续，检查真实状态与可见反馈；完成任务不能重新激活，暂停/继续不增加分钟。核对原进度/测验/调整历史保留。
4. 调整先预览，再去另一窗口改变学习型号：旧确认必须拒绝；重新预览才可使用新型号。独立模式只改聊天不应使学习选择变化。
5. 真实比较须用户明确指定OpenRouter准确ID。以Gemini 3.8 Flash为对照，两型号在同一自选知识点各生成3题一次，共2次生成；不勾选简答辅助评价。若指定ID不可用则停止核对，不擅自替换。
6. 分别核对requested_model、returned_model、题数/选项/答案/解释、结构化结果、Token和待核用量，并在平台核对账单。估算不等于账单；回执不明先按原请求核对，不自动再次生成。

真实模型账号权限、实际质量/费用、完整原生故障矩阵及正式私人库迁移仍待用户验收。本次不开发长期记忆、RAG、复杂推荐或子模块分别选模；完成同步后停止。
