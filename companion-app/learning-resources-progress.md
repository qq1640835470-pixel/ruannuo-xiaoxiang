## 2026-10-20 真实资源搜索验收与额度兼容修复（0.3.4）

真实Basic搜索3次返回23条中文候选，筛后推荐8条，含2条主题对应B站视频及讲义/习题；搜索响应各报告1 credit，合计3，无重试或额外模型。分类漏识别、泛词误收、播放/PDF访问及usage计数差异仍待核实，整体仅部分通过。未将原始响应或账户快照公开。

最小修复nullable Key限额与内部精确免费额度确认，默认页面未知PAYG仍保守停止，没有持久自动放行。19项资源隔离回归及静态/文档检查通过；导出验证不再调用真实API。正式私人数据库未读取/迁移，未开发内容读取、RAG或教学引擎。详情见[真实验收报告](learning-resources-real-acceptance-20261020.md)。

---

## 2026-10-20 资源搜索离线与原生验收记录（仅文档）

业务仍为88111ff、版本0.3.4，本次只同步4份脱敏文档。18项资源离线测试及实际Windows临时DPAPI/原生WebView2流程已验证；原生搜索使用合成响应，保存/任务关联/关闭重开和GET回执恢复通过。没有进行真实Tavily、用量、账单、搜索质量或正式数据库迁移验收。

已记录但未修复：key.limit=null兼容、400/422/500错误分类、混合资源类型及主题误收风险。真实验收需另行明确授权只读usage、受限免费搜索和公开链接抽查；公开HTML/文字PDF读取只是最小方案，未开发。本次导出副本18项资源测试及新增文档链接检查通过，正式私人路径访问尝试0；业务源码未变化，不重复宣称执行原生宿主或完整学习回归。

本次不发布凭据状态、原始证据、私人数据库/日志、截图、profile或备份，不启动正式服务或任何真实付费调用。详见[验收记录](learning-resources-acceptance-20261020.md)。完成同步后停止。

---

# 学习资源自主搜索 MVP（0.3.4，2026-10-20）

## 已实现

在原独立学习页面加入“寻找学习资源”折叠入口，不新增学习/待办系统。支持自然语言需求整理或手动填写课程、具体知识点、基础及视频/教材讲义/练习类型。需求整理通过原学习模型选项与发送前预览，只发送本次输入；复用选模 revision、预算、请求/返回型号，无工具权限。模型不返回资源标题或链接。

搜索关键词由本机按已核对课程、知识点及类型生成，可编辑后明确确认发送；基础留在本机。每次1至3次 Tavily Basic 查询，每次最多8条候选，最终最多8条推荐。固定 API 地址，不执行模型生成的命令，不自动切换来源、不重试或升级搜索深度。关闭 auto_parameters、自动答案、原文与图片获取。依次核对免费额度，查询均串行；中途失败保留已取得的结果并报告缺失类型。

本机以标题/搜索摘录做关键词相关性、类型分类、轮流选取类型、URL去重及初步难度判断。保留真实响应中的原始链接；仅去重键移除已知跟踪参数，保留分P等语义参数。来源展示链接域名，简介标明搜索摘录，推荐理由展示命中词与类型线索；不承诺语义质量。未匹配或类型证据不足的结果不展示，不补造稀缺类型。难度仅依据标题，标注低置信度或未知。

用户勾选后保存来源、摘录、真实URL、搜索词、搜索时间及判断标记，可独立保存或关联现有学习任务。保存端只接受已完成搜索回执中的资源ID，不接受用户/模型自行上传的新资源元数据。事务提交后才返回成功；规范化URL防重复，已有资源保留首次保存的来源快照，可关联多个任务。任务被删除后资源保留，关联标注“原任务已删除”。不改任务内容、状态、进度、计划、测验或调整。

已保存资源展示最近100条。源网页、视频、PDF及字幕均未下载/读取；可访问性、登录/付费/地区限制未核验。没有教学会话、RAG、通用爬虫、多Agent、跨设备同步或长期记忆变更。

## 数据、凭据与费用边界

- 原 SQLite 新增 learning_resources、learning_resource_tasks、learning_search_calls 三张小表；请求占位、结果、失败和保存回执复用 agent_state_requests，实体以 resource_ 区分。只在临时测试库实际初始化/重启验证。代码在正式启动时会建表，本轮未启动正式服务，正式迁移须另行批准。
- 需求整理仅一次原学习模型请求，按原模型预算结算；可手动填写以避免模型请求。结果筛选与推荐理由均为本机规则，无搜索后云模型精排。
- Tavily 每次搜索前通过 GET /usage 检查账户与Key额度。仅接受已知 Researcher/Free 套餐、正数且不超过1000的套餐额度、paygo_usage=0且paygo_limit=0；字段缺失/未知、付费套餐或额度不足直接停止。Key limit=0按无Key单独上限处理，仍受免费账户上限约束。免费状态只反映查询时供应商返回，其他客户端改变账号配置或并发用量不受本应用控制；真实账户返回格式仍未验收，未知时不会放宽限制。
- 搜索信用点独立记入 learning_search_calls，不伪装成模型token或人民币账单。每次Basic按最多1 credit预览，仅供应商明确报告1时记录已知用量；缺失/异常即停止后续查询并标待核。请求中断留pending/unknown，不自动重发。只读usage请求不发送查询内容。
- Key通过 configure_tavily.py 本机隐藏输入，复用 providers.hub 的当前Windows用户DPAPI库，合并原Key、加密往返校验及临时文件替换；不通过网页、命令参数、聊天或日志传入。配置操作本身不联网、不读写数据库。此脚本本轮未对真实凭据运行，DPAPI实际保存待验收。
- 未来用户配置：在 Tavily 创建免费 Researcher 账户，保持按量付费关闭并核对控制台限额；在本机交互式终端进入 companion-app 后运行 `python configure_tavily.py`，按隐藏提示输入Key。不要把Key发到聊天。缺Key时界面返回明确失败，手动填知识点不会绕过凭据或费用检查。
- 发往搜索商的仅为预览且明确确认的关键词；不附带基础、任务内容、私人画像、聊天或学习历史。供应商会处理外发查询，因此不输入私人资料。HTTP仅允许固定 Tavily /usage和/search、12秒超时、1MiB响应上限且拒绝重定向。真实HTTP错误体及密钥不进入回执/日志。
- 外部摘录不再交给模型，不能触发任何系统/工具调用；结果按textContent渲染，链接限制HTTP(S)公共域名并拒绝IP、认证信息及危险端口，打开使用noopener/noreferrer。应用从不请求任意结果URL。这不是对源网站安全性或版权的背书。

官方资料（2026-10-20查阅）：[价格](https://docs.tavily.com/documentation/api-credits)、[Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[Usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage)、[平台条款](https://www.tavily.com/terms)。当前官方每月1000免费credits，无需信用卡；Basic每请求1 credit，按量$0.008/credit，但本MVP拒绝付费套餐/PAYG。费用、免费资格及可存储的第三方内容范围应以实际账号与条款为准，不下载、转载完整教材/视频。

## 回执恢复

浏览器仅保存本次输入、请求编号/载荷及最近搜索编号。生成、搜索、保存前先写本机待核对标记。同ID同载荷回读原回执，同ID异载荷拒绝；并发相同请求只有一份占位。断网/关闭重开后用户点击“核对原请求回执”，仅GET，不重新POST。未完成/已中断请求不自动恢复执行。用户可以明确放弃本地待核对标记，但不会取消服务端请求，界面提示新请求可能再次消耗额度。即使原学习页面的按钮恢复逻辑重新启用资源按钮，资源事件处理仍拦截待核对期间的新请求。

## 文件与接口

新增 learning_resources.py、configure_tavily.py、web/learning-resources.js、web/learning-resources.css，以及test_learning_resources.py、test_learning_resources_ui.py、test_learning_resources_ui.cjs。server.py仅添加模块初始化、资源模型预览分支和资源端点；web/index.html只添加资源入口和脚本/样式引用。另更新两处HANDOFF及continuation。版本仍0.3.4，不改providers、聊天、Live2D、音乐、长期记忆或模型路由实现。

- GET /api/learning/resources、/api/learning/resources/receipt?id=...
- POST /api/learning/resources/preview、/analyze、/search、/save
- 原 POST /api/learning/model-preview 增加 resource_analyze 操作。

沿用本机Cookie、Host/Origin、JSON及请求体长度检查。资源搜索/解析失败也是持久回执，不冒充成功结果；部分成功明确标partial。

## 已执行验证（合成数据与模拟网络）

- 新增18项Python专项：真实本机HTTP接口及原模型适配器配合合成响应，覆盖需求解析、选模变更/预算、关键词预览、三类分类与去重、来源/时间/难度标记、相同请求并发去重、无Key、无结果/无关结果、未知/付费套餐与额度不足、超时/网络/限流/认证失败、部分成功、用量缺失、无效/超大响应、拒绝重定向、恶意内容、危险URL、保存防伪、任务关联、重复保存、重启、任务删除、数据库失败回滚和模拟DPAPI更新保留原Key。
- 相关182项Python回归通过：test_app、test_agent_state、test_learning、test_learning_checks、test_learning_adjustments、test_learning_reminders、test_learning_repairs、test_model_center、test_learning_task_state、test_learning_system_034、test_learning_models、test_openrouter、test_models、test_web_tools、test_learning_resources。
- 首次扩大回归182项中3项被正式路径保护拦截，原因是旧测试默认读取正式模型目录缓存；未实际读取。将测试启动器中的providers.CATALOG_PATH指向临时空目录后182项通过，最终正式私人路径访问尝试0。未修改业务或旧断言绕过保护，首轮失败不作通过。
- 4组Edge通过：新增资源页、原0.3.4完整链、独立学习选模、学习提醒。资源页覆盖模型整理、关键词预览/取消、实际本机服务配模拟搜索、搜索与保存两种丢回执后刷新/GET恢复且不重复POST、关联任务、无结果/超时、重复保存、恶意HTML不执行、390px布局；原学习计划快照前后相同。其他三组分别验证计划/测验/调整完整链、独立选模与提醒不受影响。最终正式私人路径访问尝试0。
- Python AST与相关JavaScript语法检查；截图已查看桌面和390px布局。截图artifacts/learning-resources-desktop-fixture.png、artifacts/learning-resources-fixture.png仅为本机合成界面，未公开上传。

## 未验收与后续边界

尚未配置/读取真实Tavily Key、执行真实互联网资源搜索、验证真实免费账户usage字段、API账单、中文/B站检索质量、平台兼容性、源链接可访问性、内容正确性或难度质量；真实模型需求解析也未验收。模拟搜索成功绝不等于真实搜索验收。Windows原生WebView2未测试，正式私人数据库迁移未执行。

下次如获授权：先配置免费Key并只读核对套餐/用量，再另行明确允许真实搜索及正式库迁移范围。真实验收可用“模拟电子技术·差分放大电路”一次综合搜索，对照供应商用量与返回URL，并人工抽查链接和三类覆盖；缺失或失败如实记录，不补链接、不自动重试/换源/付费。迁移批准前保持隔离测试库。

本次按用户后续“同步git”指令发布资源搜索MVP的源码、合成测试与公开交接。开发阶段未发布的状态为历史。公开版本不包含私人数据库、Key、设置、聊天/日志、截图、profile或备份；不启动正式服务、执行正式迁移或真实付费测试。发布验收见根目录HANDOFF。完成后停止，不自动进入下一阶段。

## 公开导出验收（2026-10-20）

导出副本另行执行182项Python、资源页/完整学习链/独立选模/提醒共4组Edge、聊天重试及Python AST/相关JavaScript语法检查，均通过；使用临时SQLite和模拟模型/网络，正式私人及导出数据路径访问尝试0。9份代码/合成测试与运行源码逐字节一致；仅另外整理3份公开交接文档，截图与验证报告留在本机。暂存白名单、凭据模式、忽略规则及git diff --cached --check在提交前核对；真实服务、账单、搜索质量、原生宿主与正式迁移仍未验收。
