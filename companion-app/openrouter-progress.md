# OpenRouter 接入交接（2026-10-19）

## 基线与范围

已 fetch 并核对 Git 导出 main 与 origin/main 均为 a2ef9573390d27bf5c2d32cbdf2c72f24419c7bf，导出工作区干净；实现位于本机最新运行源码 D:/StudyLifePlan/companion-app。开发阶段未同步 Git 导出、提交或推送；用户后续已明确授权同步至 Git，提交状态以 Git 记录为准。正式版本号仍0.3.3。没有启动正式服务、读取私人记录/完整画像或迁移私人数据库。反馈桥、音乐、语音、地图、本机Qwen/Gemma实现未改。

只接入 OpenRouter，不开发学习成果检验或其他学习模块。现有学习 MVP 的 JSON 解析、内容校验与确认保存流程直接复用。

## 架构核对与最小实现

- providers.py 已有 ModelAdapter 和 DeepSeek 的 OpenAI Chat Completions 传输，新增 OpenRouter 固定官方地址，沿用 post、禁重定向、45秒超时、请求/返回型号、脱敏日志、预算预留与结算。没有新增平行模型管理系统。
- api-hub/hub.py 已有当前 Windows 用户 DPAPI protect/load_keys、NoRedirect；直接复用，hub.py 本身未改。原余额查询仍查询原三家，不增加 OpenRouter 余额推断。
- configure_openrouter.py 是本机隐藏输入入口，仅更新现有 companion-data/secrets/providers.dpapi 中的 openrouter 项。保留其他凭据，验证加解密后用加密临时文件原子替换；不接受 Key 参数或管道，不请求网络，不回显 Key，也不尝试恢复其他机器/账号的凭据。未运行真实凭据配置。
- 设置→对话方式新增 OpenRouter、准确 ID 与名称、上下文和输出上限提示。Key 不经过浏览器或普通设置。现有提供方/自动路由默认值不变；不预选任意 OpenRouter 型号。settings 在读取时合并默认型号映射，不新增表或迁移。
- 修复设置保存时误将本机陪伴型号纳入云模型映射的问题；只发送非空云模型选择。OpenRouter 仅加入主聊选择，不扩展桌宠选项。
- model_routing.choose 原手动路径直接识别所选提供方；learning_model 仍读取主聊 provider/chat_models、禁止工具，不受聊天可选成本路由覆盖。学习只发送该页明确输入与专用提示，不发送聊天记录、已有计划或私人画像。

## 模型目录与能力

依据 [模型列表文档](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)、[Chat Completions 文档](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)、[用量文档](https://openrouter.ai/docs/cookbook/administration/usage-accounting) 和 [参数能力路由文档](https://openrouter.ai/docs/guides/routing/provider-selection)核对。

本轮真实公开 GET https://openrouter.ai/api/v1/models 返回471条记录；不带凭据，没有生成请求。只查看公开模型元数据，未把完整目录硬编码进源码或写入正式缓存。自动化测试使用独立合成目录，与这次公开读取分开。

应用显式刷新时读取公开目录，不需要解密 Key。缓存复用现有目录，失败保留旧列表；上限8MiB。只列 text 输入且 text 输出的候选。名称仅展示，选择和请求使用 id；支持厂商/型号及 :free 等后缀，拒绝路径越界、查询参数、名称和疑似密钥。手动入口只验证 ID 格式，不能证明型号存在、账号权限或能力；目录不可用时仍可保存，真实调用的失败明确提示。用户应从官方模型页复制准确 ID。

从目录读取 supported_parameters、context_length、top_provider.max_completion_tokens。只发送声明支持的 max_tokens/max_completion_tokens；未声明长度支持的已知型号报错。按 UTF-8 字节作保守输入 token 上界检查，加输出和封装余量，超过上下文/输出上限直接报错，不静默缩短输出；可能比实际分词更保守。手动且无元数据型号以 max_tokens 请求，服务端 require_parameters=true 要求能力匹配，能力与限制仍未知。

学习按模型声明决定是否发送 response_format=json_object；未声明则按文本请求 JSON，依旧必须通过原 learning.parse_model 及计划字段、日期、时间预算校验。不是所有模型保证产生有效 JSON；本轮不新增 JSON Schema 或语义修复重试。

不发送 DeepSeek 专用 thinking 参数给 OpenRouter。不启用 OpenRouter 工具/多模态直传/音频/流式，也没有宣称这些能力兼容。现有聊天附件仍走本机提取后发送文字摘要的原路径；本轮没有验证附件真实云联调。推理 Token 包含在供应商 completion_tokens 口径中，不另行重复计数。

## 用量、预算与失败

- input_tokens/output_tokens 来自响应 usage，不用估算伪装实际 Token。缺失用量标为 unavailable。
- estimate_cny 仅按目录 prompt/completion 单价与响应 Token 算，美元仍沿用现有10人民币保护系数，绝非实时汇率或真实扣款。存在动态 overrides、附加请求等费用时不按简单价格结算，按未知价格保留预留。
- usage.cost 如有，单独记 provider_reported_cost_usd；billing_amount_confirmed=false，不当作已核对账单，不查询或伪造余额。模型目录最低报价不保证实际服务商收费；费用仍须在平台核对。
- 未知价格、缺失用量或未取得完整回复，保留原预算待核机制；已有不限预算设置照常沿用。失败后不自动返还或清除用量。截断/过滤/生成错误不作为完整计划采用，即便带用量也保留待核。
- HTTP 401/403认证权限、402额度、404型号、400参数/上下文、408/504超时、429限流、502/503上游不可用分别提供固定提示；网络/本机超时有明确提示。错误正文、异常消息、认证头与 Key 不写日志。
- 不自动重试，不请求其他型号，OpenRouter provider.allow_fallbacks=false。原先由用户显式启用的本机聊天接管规则保留；学习仍不自动接管或换模型。公开目录成功不表示 Key 有效或模型生成成功。

## 实际修改清单

运行目录修改：providers.py、server.py、runtime_log.py、web/index.html、web/model-settings.js、test_core_runtime.py、HANDOFF.md，以及上级 HANDOFF.md、continuation.md。Git仅同步上述6个代码/测试修改、下列5个新增文件及仓库根HANDOFF.md；不复制本机历史交接全文、continuation.md或截图。

新增：configure_openrouter.py、test_openrouter.py、test_openrouter_ui.py、test_openrouter_ui.cjs、本交接文件。学习界面测试重新生成本机 artifacts/learning-mvp-fixture.png（合成资料，不作为交付源码）。阶段快照仅本机源码，不复制私人数据库。

## 自动化验证（全部模拟，无真实付费 API）

```powershell
Set-Location D:/StudyLifePlan/companion-app
python -m unittest test_openrouter test_models test_learning test_agent_state test_app test_core_runtime test_conversation_v031 test_local_adaptation test_chat_attachments test_local_runtime -q
python test_openrouter_ui.py
python test_learning_ui.py
node test_chat_retry.js
node --check web/model-settings.js
node --check test_openrouter_ui.cjs
node --check web/app.js
python -m py_compile providers.py server.py runtime_log.py configure_openrouter.py test_openrouter.py test_openrouter_ui.py
```

109项Python通过（其中OpenRouter专项15项）：临时库/临时DPAPI库、模拟HTTP成功/常见错误/内嵌错误/超时/网络失败、禁重定向、无自动重试、用量缺失/截断、Key不回显、原凭据保留、目录刷新失败与手动ID、能力长度边界、预算、主聊路由及学习JSON贯通且不保存正式计划。真实Windows DPAPI仅对合成凭据加解密验证，不读取正式库。

无界面Edge：OpenRouter名称/ID、公开目录刷新、保存/重载、手动格式校验、390px、无脚本异常通过。原学习流程（草稿/确认/任务状态/进度/重载/失败/窄屏）与原聊天重试检查通过。静态检查通过。

首次回归需将旧的“两家启用提供方”断言更新为三家；首次新设置界面测试揭示本机陪伴映射导致保存拒绝，已修正并复跑通过。无界面浏览器通过不等于正式Windows桌面验收。

## 本机设置及真实 API 验收（仅由用户执行）

1. 撤销已贴在对话中的 Key，重新生成。不要将新 Key 再贴到对话。
2. 在本机 PowerShell 运行以下命令，在隐藏输入提示处粘贴新 Key 并回车；Key不出现在命令或历史中。不将 Key 作为命令行参数。

```powershell
Set-Location D:/StudyLifePlan/companion-app
python configure_openrouter.py
```

3. 用户决定开始正式本机体验后，按原方式启动/重启软糯小祥加载新源码。本轮未运行正式服务；正常启动可能执行先前学习/状态底座已有迁移，这不是本轮私人库验收结果。
4. 设置→对话方式→OpenRouter→刷新API模型列表→选择名称对应的准确ID；失败则从官方模型页复制厂商/型号到手动栏，校验格式并选用。确认预算、允许云模型生成开关，再保存设置。首次配置不触发付费生成。
5. 自行发送一条不含私人信息的短文本（例如“只回复连接成功”），检查操作记录、/api/usage中的请求/返回型号和用量；只有成功回执才能算真实调用通过。平台余额和账单单独核对。
6. 再在学习页用合成课程需求分析并生成短计划草稿，核对 JSON 校验和所选型号；无需确认保存。较长计划要求所选模型输出上限至少8192；上下文检查保守，报不足时选择更大上下文型号。
7. 如需验收真实错误，可自行用无效临时Key/不存在ID核对明确提示，然后恢复配置；网络失败/限额行为已离线覆盖，不必为验收故意消耗额度。失败不得当作成功，也不要重复点击制造多次付费请求。

尚未完成：真实Key配置、真实聊天和学习JSON、实际账单、账号权限及Windows桌面体验。没有发起真实付费调用，不报告真实模型调用成功。本阶段停止，等待用户反馈，不开始下一阶段。

## Git同步复核

用户后续明确授权同步至Git。导出副本重新通过109项Python、OpenRouter设置页与原学习页Edge、聊天重试和静态检查。首次导出设置页测试因尚未等初始化完成即操作而超时，测试已增加等待连接完成，并同步回运行源码，复跑通过；不改变产品功能。10份代码/测试与运行源码逐字节一致，12文件白名单及凭据模式检查通过。同步不包括本机历史交接全文、私人数据、截图或备份。
