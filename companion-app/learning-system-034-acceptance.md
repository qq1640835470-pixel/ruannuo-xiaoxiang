# 0.3.4 学习系统集成验收（2026-10-19，公开版）

## 结论与边界

本次只修复可复现缺陷并补齐隔离验收，版本保持0.3.4。开始时运行目录与GitHub main的133份已跟踪Python/JS/CSS/HTML源码按行尾规范化比较一致，基线提交为ee18c1a。

自动化全部使用临时数据库、合成凭据和模拟模型传输响应，禁止非回环网络。没有启动正式服务、调用真实付费API或修改原始私人数据库。公开记录不包含私人表数量、内容指纹、数据库副本、诊断或截图。

## 实际修复

1. providers.chat和local_runtime._chat_once对学习专用结构化输入也执行普通聊天每条3000字截断。复现中3597字合法JSON被截断，所选依据尾部丢失。现在带instruction的专用调用保留调用方已校验输入，普通聊天限制不变，脱敏、上下文和预算检查继续生效；不自动切换模型或重试付费请求。
2. 测验题目生成后原提示“结果已保存”，容易误认为答案已提交。现明确显示“测验题目已生成并保存，尚未提交答案”，提交成功才提示结果保存。

## 数据库演练

原库只读，使用SQLite backup API生成独立一致性快照，再复制工作库执行正式server.init初始化路径。演练期间阻止网络及凭据加载。检查迁移前后完整性、所有旧表数量及旧列内容指纹、恢复读取、重复初始化幂等性，以及原库与已有sidecar未变。

这些检查全部通过；本次副本仅新增learning_checks、learning_check_requests、learning_adjustments及索引，旧任务、聊天、反馈、请求与用量记录保留。当前副本已有状态底座，无需新增旧表列。历史一致性数据库备份的清单哈希与完整性核对通过，未重验完整备份文件集、模型或系统加密凭据恢复。

正式启动预计新增上述三表及索引，并仍执行原有请求状态恢复、用量对账、记忆保留等初始化规则；本次副本旧表没有变化。正式启动及原库迁移时机由用户决定。演练通过不等于原库正式迁移已验收。

rehearse_migration_034.py要求显式source和新的独立destination，拒绝覆盖已有目录；不要把它作为例行测试传入正式库。checkpoint默认的脱敏副本不能替代逐字数据恢复证据。

## 自动化与覆盖

跨模块HTTP测试复用真实Handler、学习模块、learning_model、预算和模型适配器，仅替换最后一层HTTP传输。覆盖：需求整理→草稿→确认保存→记录学习→完成任务→关联测验→客观判分及辅助反馈→人工更正→明确选择记录→调整草稿→确认修改原目标→重新初始化→独立进程读取。

断言原目标/任务ID、完成项、进度、测验及更正保留；未选记录不进入模型。校验超过3000字的完整输入、准确model ID、JSON参数、各阶段输出上限、禁止工具和禁用提供方回退；请求/返回型号分开记录，Token及供应商cost保存但不标记账单已确认。

完整生产HTML及全部脚本的Edge测试另覆盖模型设置、计划和调整已写入但回执丢失后的刷新核对，保证同请求不重复写入或调用模型；验证出题/提交提示与实际状态一致，页面无脚本异常。

149项Python测试通过（原146项、两项完整输入回归、一项跨模块闭环）；完整生产页面、原计划/检验/调整/OpenRouter设置页Edge及聊天重试通过。执行方式：

```powershell
python -m unittest test_learning_system_034 test_learning_adjustments test_learning_checks test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
python test_learning_system_034.py --ui
python test_learning_adjustments_ui.py
python test_learning_checks_ui.py
python test_learning_ui.py
python test_openrouter_ui.py
node test_chat_retry.js
```

## Windows宿主

原双WebView2宿主指向带ISOLATED-034标记的独立合成服务、DATA与浏览器profile，未连接私人迁移副本。

实际操作通过：输入学习需求并分析、生成草稿、查看OpenRouter准确型号；开关设置后草稿保留；切换主聊天并获得模拟回复，返回学习草稿保留；关闭重开后读取独立闭环数据中的目标、完成项、进度、调整后任务及检验历史。

全部作答和确认调整的逐步输入仅在无界面Edge验证，不能称全流程Windows人工验收。隔离宿主与服务均已关闭。

默认Python 3.10与现有.runtime的cp312 cffi依赖不兼容，随后coreclr回退失败；使用本机已有Python 3.12.14启动实际宿主成功。未安装依赖或修改系统默认Python。正式启动应使用匹配3.12的解释器或已确认使用它的快捷方式。

隔离人工复现：用test_learning_system_034.py --serve创建全新合成目录，再用匹配3.12运行--host，传入同一目录及control.json中的URL。工具验证标记和回环地址；不要传正式数据目录或正式服务地址。

## 用户亲自完成的最小真实OpenRouter测试

以下未执行。用户自行决定正式启动并接受可能费用后，选择准确OpenRouter型号，核对云开关和预算；型号须支持应用8192输出预算及足够上下文。Key仅留在本机隐藏输入流程，不贴到聊天或报告。

| 调用 | 操作 | 核对 |
| --- | --- | --- |
| 1 | 主聊天发送不含私人内容的短文本 | 成功回复、请求/返回型号 |
| 2 | 手填合成课程、明确知识范围、两天及每日120分钟，直接生成计划草稿 | 合法结构化输出、型号；自行确认保存合成计划供后续测试 |
| 3 | 为该计划任务生成3题，作答提交，关闭简答辅助评价 | 选项、参考答案、解释、客观判分及历史关联 |
| 4 | 动态调整仅选择该合成测验，补充小范围调整要求，预览提供方和正文后生成草稿 | 有依据的可比较草稿、原ID/完成项保护；可取消 |

直接手填且不启用简答模型评价时最少4次模型调用。每次核对回复来源、结构化结果、实际错误和本机会话/api/usage中的requested_model、returned_model、input_tokens、output_tokens、provider_reported_cost_usd、billing_amount_confirmed。缺失用量/费用保持未知，供应商cost与保护估算不能代替账户账单。目录获取成功不代表账号认证成功。

回执不明只核对同一请求，重新生成可能再次计费。真实模型内容、长JSON、辅助评价质量、真实认证与用量账单仍待上述人工验证；不要为制造错误额外付费。

## 文件与未解决事项

修复providers.py、local_runtime.py、web/learning-checks.js；补充test_openrouter.py、test_local_runtime.py，新增test_learning_system_034.py、test_learning_system_034_ui.cjs、rehearse_migration_034.py。更新README、HANDOFF与更新日志。

尚需用户决定正式启动时间、确认匹配Python并完成真实OpenRouter测试和完整Windows逐项操作。本次合成闭环及当前数据库副本未发现未修复的阻塞缺陷。未开发新功能、后台督促或长期记忆。

本次同步前在Git导出副本重新执行上述全部测试及Python/JS静态检查，结果通过；13文件白名单、9份运行文件逐字节比较及凭据/私人报告模式检查通过。
