# P0 学习真实使用修复 / P1 OpenRouter模型中心（2026-10-19）

## 基线、约束与诊断事实

运行源码D:/StudyLifePlan/companion-app，版本保持0.3.4。开始只读fetch并核对GitHub main、origin/main和导出HEAD为95d4742977506d86917613ac0c8a9b2a93fb58c6，导出工作区干净；128份已跟踪Python/Web JS/CSS/HTML运行源码按行尾规范化与导出一致。两处交接是原机与公开版各自维护，不把正文差异当运行代码不一致。

经用户授权，只读检查指定历史请求的脱敏诊断字段。旧记录表明模型返回后处理失败，但底层错误类别未保留，无法据此确定是JSON、结构、范围依据或保存失败，也不能断言其他模型不具备能力。未复制或上传原始日志、私人请求编号、题目、答案或凭据。

先完成P0并通过173项回归及P0页面闭环，再实施P1。所有数据库/模型自动化均为临时库、合成目录和模拟HTTP；最终完整Python回归另保护凭据加载，只允许临时合成DPAPI文件。未启动正式服务、修改/迁移私人数据库、读取真实模型Key、调用真实付费API、修改反馈桥或无关音乐/语音/地图/Live2D业务代码。开发阶段未提交或推送；随后按用户明确“同步至git”的指令导出本轮代码、测试及脱敏说明。正式版本号保持0.3.4，提交状态以Git记录为准。

## P0：已确认的代码缺陷和修复

### 任务开始

旧学习页仅PATCH active后重绘列表，无任务回读、当前学习区或高亮；已active也再次写入，确实存在成功后反馈不明显的路径。没有访问用户SQLite，不能断言此前每次真实点击均已写入或均失败。

现在点击显示处理反馈，先GET当前任务；已是目标状态则提示并跳过PATCH。否则使用固定request_id写入，验证ok/任务ID/状态回执，再GET回读；只有当前数据库仍为目标状态才报告成功。失败显示原因并滚动到状态提示，不把旧回执当当前状态。待核任务请求可跨刷新保留、核对或明确结束跟踪；结束跟踪不改任务。

学习页显示“当前正在学习”区，active任务卡片突出，提供完成、暂停及定位实际分钟/收获记录的入口。更新后定位对应任务，不因重绘丢失焦点。阶段05提醒仍用原事务/回执/回读和定位事件；已active时不再更新任务行，仅处理提醒交互。点击开始不创建进度、不计时、不完成任务或推断掌握。

### 自选知识点

旧任务与topic共用evidence必须逐字成为title/content/outcome子串的规则。已用模拟结果复现：短主题配“围绕零状态响应的基本概念”之类正常解释引用会被拒绝。此代码缺陷已确认，但不是对指定历史请求根因的反推。

自选topic仍独立保存，goal_id/task_id均为空。对空白、过短及少量明确泛化输入（如学习、课程、电路、随便）提前要求补充，不调用模型。其他范围不明确时模型可返回error，归类为范围待补充。不能用有限关键词穷尽所有模糊主题。

任务入口继续要求原范围逐字引用。topic入口允许Unicode NFKC、大小写、空白及标点差异，允许简短解释中包含完整主题；仍要求至少两字符的引用锚定输入，拒绝泛用“自选知识点”或无关依据。提示强调只围绕输入、不关联其他课程，练习假设数值须明确，不伪称用户教材或考试事实。

自动引用校验不能证明语义范围和参考答案正确。仍需用户核对，mastery保持未知；没有通过删去校验或模型自称正确来解决问题。

### 有限JSON及模型兼容

learning.parse_model接受JSON前BOM、首尾空白、完整的json/JSON/无语言Markdown围栏。仍只接受完整JSON对象，不从任意说明中猜取对象，不改缺失逗号、单引号、缺答案/解释等实质内容。

题目允许确定映射：single_choice/multiple_choice→choice、short_answer→short；question/correct_answer/rationale字段名映射（重名冲突拒绝）；有序A至E选项对象转数组；明确A至E答案转对应下标、0至4数字字符串转零基下标；简答options=null转空数组；可忽略模型附加的标识ID。题数3至5、字段、长度、唯一选项、答案类型/边界、解释及范围校验继续执行。不猜测整数答案是否一基，不补造答案、解释或评分依据。

Gemini、OpenRouter/DeepSeek及本机适配分别处理完成原因、正文为空和长度/过滤失败；只用正文，reasoning/thought不作为题目。支持明确的text/output_text内容块。OpenRouter沿用目录声明选择max_tokens或max_completion_tokens；只在声明response_format时请求JSON对象，否则一次文字请求后本机解析。目录参数不兼容直接报错，API拒绝参数也不自动第二次请求、换模或改提供方。Gemini不强迫加入未知的JSON参数。

成功、空/截断等路径尽量保留请求/返回型号、已提供Token、结束原因和用量元数据；失败有用量时保留元数据，沿用原未知费用预留机制，不把未知Token/费用编造成0。模型调用已成功但题目校验失败时，原已结算用量不抹去。不宣称除3.8 Flash外的模型已经通过真实出题。

### 安全诊断与恢复

learning_diagnostics.py只含固定中文说明和恢复建议：model_request、auth_quota（本机预算不足另给固定说明）、parameters、empty_truncated、invalid_json、question_schema、scope_evidence、scope_unclear、database、pending。

学习HTTP错误返回安全category与原X-Request-ID/错误请求编号；数据库错误返回500，其余分类400。runtime_log新增category/operation/finish_reason白名单，不记录HTTP正文、Key、题目或答案。原前端api错误展示已能显示中文说明、建议和请求编号，因此无需重写web/learning-checks.js。

learning_check_requests复用原response保存安全失败类别；同ID失败后恢复仍返回原失败类别，pending不补调用，成功/删除回执不重做。有效测验及完成回执仍原子提交；数据库失败不假报。辅助简答评价失败仍按原规则保存答案与客观结果、主观项未可靠评价，不伪造评分。

## P1：模型中心

复用providers.model_catalogue/normalize_models、原JSON元数据缓存与model-settings.js选模/保存路径；没有第二套目录、自动推荐模型或生成调用。打开中心只读本机缓存；显式目录刷新仍由原按钮执行。下拉框限制前100项及当前选择，完整目录可搜索分页，模型中心每页24张卡片。修复目录显示逐行反复读取缓存算价格的开销，复用当前行价格，不改原保护估算系数。

分类可多选归属：日常聊天、学习候选、声明推理参数、上游视觉、免费、低成本、收藏、最近使用。推理分类只据reasoning参数声明，不据名称/规模宣称数学强；视觉只是上游声明，当前小祥OpenRouter未适配图片直传。原系统仍只列支持文字输入输出的目录候选。

学习出题基础候选：文字输入/输出、可用长度参数、上下文至少8192和最大输出至少4096；学习计划另显示16384/8192门槛。未知字段为待验证，硬性不足显示原因；实际输入仍须经过提供方原预算/上下文检查。基础门槛不是准确率、账号权限或所有任务长度保证。

支持名称/准确ID搜索、厂商/分类、免费/付费/未知价格、输入/输出价格上限及升降序、最低上下文、结构化参数筛选、收藏、最近使用、一键全部和分页。卡片显示ID、目录名称、厂商、USD/百万Token输入输出价格、上下文/输出、声明参数、模态、当前适配边界、计划/出题限制和验证状态。未知价格不是免费；免费须输入输出均明确0。低成本标签阈值明确为≤1/≤4 USD每百万Token，不是实时账单或最佳性推荐。手动准确ID入口保留，选用后需用户保存设置，不隐式换提供方或自动请求。

## 本机收藏、近期与验证数据

只在现有settings表新增model_center_preferences键，不新增表/列或私人迁移；收藏最多200、最近20、结果记录最多200。包含模型ID、请求/返回型号、task（文字聊天/学习计划/学习出题）、结果、固定失败类别、测试时间、应用版本、规则版本及能力签名；出题可带本机check_id，不存题目/答案/Key。近期包含保存选择及成功调用，并不等于已实际生成。

自动记录的成功默认来源unverified，模拟可明确记simulated，均不成为“本机已验证”。只有用户在中心选中有效已保存的出题记录、确认“真实模型生成并已核对、绝非模拟”后才记为用户确认真实。已知模拟记录拒绝升格；旧测验缺少版本记录时拒绝冒充当前规则验证。此为用户测试声明，不是软件对网络真实性、答案正确率或普遍能力的独立证明。

确认保留原测试时间、应用版本、规则和目录能力签名，另记确认时间；不重新盖当前版本。版本/规则或相关目录能力变化标记旧验证可能过期，同ID模型后台无可见元数据变更仍无法自动识别。单次真实成功不保证其他范围正确。文件、配置及SQLite不加入Git或云上下文。

新增本机会话接口：GET /api/models/center读目录/偏好/记录；POST同路径仅favorite或verify，带request_id，事务去重。聊天、计划和出题生成流程仍用原选模，没有新自动调度。

独立聊天/学习模型配置本轮暂不实现：它牵涉shared learning_selection、调整预览提供方一致性、预算与所有学习入口/显示，超出仅选择体验的安全小改范围。作为下一阶段建议，不在本轮悄悄分流。

## 文件清单

新增业务：learning_diagnostics.py、model_center.py、web/model-center.js、web/model-center.css。
修改业务：learning.py、learning_checks.py、learning_reminders.py、providers.py、local_runtime.py、runtime_log.py、server.py、web/learning.js、web/learning.css、web/model-settings.js、web/index.html。
新增测试：test_learning_repairs.py、test_learning_repairs_ui.py/.cjs、test_model_center.py、test_model_center_ui.py/.cjs。
修改测试：test_learning_system_034_ui.cjs（完成后当前任务会自动定位并展开，测试只在未展开时打开，避免反向折叠）。
公开更新本说明与两处HANDOFF.md；本机续接记录和源码快照不上传。

## 验证结果

- 静态检查：上述Python业务/测试编译，以及改动的Web JS和CJS的node --check通过；聊天重试检查通过。
- Python3.12.14：完整181项通过（原168项+P0七项+模型中心六项），最终新专项13项复核通过。真实凭据路径拒绝，临时合成DPAPI库允许；未访问正式私人SQLite。
- Edge：P0完整生产页验证开始/回读/高亮/进行中入口/暂停/不重复写入/不推断分钟、原任务与三个具体topic生成/提交/评分/历史；模型中心1202条合成缓存目录验证分页/受限下拉/搜索/收藏与近期重载/选用保存/未知非免费/厂商价格上下文JSON筛选及390px。中心测试生成API调用为0。
- 原计划、检验、动态调整、提醒、OpenRouter设置页和0.3.4完整学习链Edge通过；脚本无异常。一次浏览器刷新取消在途只读请求产生测试服务连接中止提示，不作为业务数据失败，也未为此改无关模块。
- 整合时先后发现旧预算文案断言、旧完成区折叠前提，以及新验证记录测试在同一事务中嵌套BEGIN的问题；已分别保持明确预算说明、修正测试前提和测试连接边界，最终通过。没有通过移除业务校验来消除失败。
- Windows真实界面：未验收。
- 真实模型API、认证/账号/账单、题目范围和正确性质量：未验收，不能据模拟判断各具体型号已验证或无能力。

复现使用现有3.12.14解释器，以下命令仅临时夹具，不运行launch.py或正式迁移：

```powershell
$repairPython='C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location D:/StudyLifePlan/companion-app
& $repairPython -m unittest test_model_center test_learning_repairs test_learning_reminders test_learning_system_034 test_learning_adjustments test_learning_checks test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
& $repairPython test_learning_repairs_ui.py
& $repairPython test_model_center_ui.py
& $repairPython test_learning_system_034.py --ui
& $repairPython test_learning_reminders_ui.py
& $repairPython test_learning_ui.py
& $repairPython test_learning_checks_ui.py
& $repairPython test_learning_adjustments_ui.py
& $repairPython test_openrouter_ui.py
node test_chat_retry.js
```

## 本机验收与下一步

由用户决定接受此前待验收的正常初始化并用匹配3.12的原方式重启；本轮不代为启动、迁移或修改系统Python。开始/暂停、实际记录、目录筛选/收藏均不需生成API调用。

先点任务开始，观察处理提示、当前学习区及进行中卡片；再次点开始核对“不重复写入”，暂停/完成/记录入口正常。点击任务检验，或切换自选知识点填上述三个topic，生成时查看具体错误类别/编号；作答后关闭简答辅助评价即可零额外模型调用地提交客观判分。失败/待核先核对同ID，不自动重新生成。

设置选择OpenRouter后打开模型中心，按ID搜索、筛选并收藏；选用仍需保存设置，手动ID保留。未真实测过的项目不得标已验证；模拟成功不能勾成真实，已保存真实测验经人工检查后才确认其本机声明。

若用户另行授权真实比较，最低方案为同一具体topic在Gemini基线和一个选定OpenRouter型号各生成一次，共2次生成请求；不先调用需求分析、不勾选简答辅助评价，不自动重试。若只验证一个新型号，最低1次。填写账号/Key走原本机配置，不贴入聊天；分别核对请求/返回型号、用量、结束原因、生成结构/范围/参考答案及提交历史。真实题目质量需要人工判读，不能因测验可保存就宣称模型普遍可靠。本轮未执行这些调用。

下一阶段建议：先完成上述受控真实出题矩阵和Windows交互验收，再决定独立学习模型配置。没有自动开始新阶段。本轮未发生真实模型切换。
