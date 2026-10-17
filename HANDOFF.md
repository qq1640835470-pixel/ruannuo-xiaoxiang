# 软糯小祥 · 项目交接

更新：2026-10-17（前端源码与交接同步）

## 0. 当前范围与状态
**本次按用户明确指令同步六个前端文件、两份相关测试及安全交接文档到 GitHub main。** 此同步不等于发布或用户体验验收；不清理或覆盖私人数据库，不恢复QQ发送任务。此后每次只处理一个明确任务，更新交接文档后停止。

- 实际运行源码：D:/StudyLifePlan/companion-app，无.git；统一数据：D:/StudyLifePlan/companion-data。
- Git导出工作副本：D:/StudyLifePlan/github-export/ruannuo-xiaoxiang；用户选择公开仓库。本次同步后的提交以 Git 记录为准，运行目录没有 `.git`，后续两处改动需核对后同步。
- server.py声明VERSION=0.3.3；实际源码为0.3.3基线+反馈596d20ab未验收前端改动，不应称为已发布0.3.4。
- 前端六个文件已复制并核对哈希：web/activity-speech-settings.js、web/music-pet.css、web/music-pet.js、web/workspace-tools.js、web/assets/pet/xiaoxiang-cursor-link.svg、web/assets/pet/xiaoxiang-cursor.svg。另同步 test_music_v031.js 和 test_music_layout_v033.cjs。
- 缩小音乐气泡、默认及记忆音乐音量、语音临时压低与恢复、两个 SVG 光标通过定向夹具与解析。前端撤下了后端不支持的多语言选择及翻译承诺；多语言语音尚未实现。
- 用户在本机关闭了普通主聊的按任务提供方路由；个人设置值不进入仓库。朗读跳过 `*` 和聊天附件入口尚未实现。

## 1. 软件架构与数据流
- Python本机HTTP服务：server.py，127.0.0.1:18764；launch.py/restart_local.py用于识别本项目服务后启动/更新，不能关闭别的进程。
- Windows桌面宿主workspace_host.py：Microsoft Edge WebView2同窗双栏，左侧对话、右侧网页/文件。远程网页无Python/系统工具桥。
- Web前端web/app.js及模块：对话/任务、反馈草稿、音乐、宠物、设置；Q版Canvas精灵与5套原比例Live2D。
- providers.py与api-hub/hub.py：云模型适配、DPAPI凭据、模型列表与估算用量；平台真实余额可能未知，估算不等于账单。
- local_models.py/local_runtime.py：同一llama.cpp进程按需加载，回环端口18766、临时会话认证；Qwen3 4B/8B自动/手动选择，Gemma3 4B手动文本与视觉投影。模型与运行时存D盘companion-data/models。
- connectors.py/typed_tools.py/local_intents.py：受限工具与参数校验，不是任意命令执行或任意插件运行器。
- maps_routes.py/maps_service.py/location_service.py：地点/步行公交路线/可选位置天气；music_service.py+music_bridge.cjs通过社区网易云适配器和本机加密会话访问有权播放的音源。
- companion_knowledge.py/assets/companion-worldbook.json/local_adaptation.py/persistent_memory.py：有界角色资料和来源记忆。经验检索不等于训练权重，不执行导入卡片中的脚本/指令。

## 2. 0.3.3基线已验收能力（历史验收，不代表本次重验）
- SQLite聊天保存、分页/搜索、主界面限制渲染数量；任务记录；折叠工具回执、幂等请求ID与结果核对。
- 支持清单内的本地程序启动、地图/天气等接口；Windows同窗浏览器。
- 网易云扫码凭据DPAPI保存、歌单/歌曲搜索、本地音乐与播放控制；音乐子页、气泡显示/暂停隐藏。
- Q版/原比例Live2D切换、右键形象菜单、尺寸、拖动站立与边缘探头；真实Live2D坐挂/背面缺相应绑定。
- 指定Fish免费型号s2.1-pro-free与提供音色成功生成、缓存、停止；历史官方资料免费期至2026-11-30，调用前仍须核实资格，不回退付费。自动闲聊文本仅本地模型。
- 窄范围本机活动采样：前台程序名、时长、系统闲置；5秒采样、运行期14天清理、可暂停，不采窗口正文/截图/键盘、不上传模型。
- 两家地图步行公交真实调用；高德POI匹配校园/车站。模糊匹配和连续导航仍有明显限制。
- D盘Qwen3 4B/8B与Gemma3 4B+视觉投影完整校验。Gemma文本/合成图、本机看图HTTP端点曾实测通过，自动路由仍Qwen4B/8B。

## 3. 未完成反馈596d20ab（不得伪装已解决）
1. 地点模糊查询：用户对话出现学校/车站唯一匹配失败；普通maps_service仍使用Photon，与已配高德不一致。分析提出的官方POI候选方案未落盘完成。
2. 缩小音乐气泡：前端改动已通过定向 Edge 夹具；用户实际界面体验待确认。
3. “聊聊这首歌”使用对话选定模型：后端仍固定本地模型，未修改。
4. 中/日/粤/英语音：撤下未生效的前端选项及翻译承诺；翻译/音色方案未实施。
5. 小小祥光标更可爱：SVG 已更新并通过 XML 解析及 Edge 指针切换夹具；视觉体验待用户确认。
6. xy读“叉歪”：尚未接入语音发音处理。
7. 默认适中音量并记忆：前端默认 40%，本机记忆及临时语音压低后恢复已通过定向夹具；用户体验待确认。
8. “随便播放几首钢琴曲”：已查相关对话，存在只口头答应/错误否认播放器能力；明确命令正则过窄，风格推荐/队列逻辑未实现。
9. 聊天框图片/文件附件按钮：未实现；现有仅工具页单图入口，不等于通用聊天附件。

上一轮子代理额度中断，没有完成整体验收。本次只同步已明确处理的前端文件与相关测试，不接着改其他功能。

## 4. 日志、反馈与私人数据
- companion-data/companion-v01/assistant.sqlite3：聊天、任务、反馈、反馈发送状态、暂存与本地草稿备份、预算/用量、请求回执等。不得重建、覆盖、清零或上传。
- 同目录activity.sqlite3及activity-settings.json：活动汇总与开关；local_adaptation.json为本机经验；logs/runtime.jsonl及轮转文件为诊断元数据。
- 同目录speech-cache、workspace-app-profile、workspace-remote-profile、native-status、workspace-queue等均为运行状态/用户数据，不是源码素材。
- companion-data/secrets/providers.dpapi；companion-v01下routes/location/netease-cookie等DPAPI文件为当前Windows用户绑定的加密数据。不能导出明文、发到新会话或上传；换机器/Windows账号不保证可解密。
- 新私人画像：D:/StudyLifePlan/companion-data/private_user_profile.md。仅本机、按需访问，禁止Git跟踪/公开世界书复制/自动云端转发。Cloud会话缺此文件时保持未知，不能从公开代码重建私人画像。
- 旧公开世界书含少量静态用户偏好；本轮没有修改业务代码或重写历史，不能据“完整画像未上传”声称从未公开过任何个人信息。后续如需迁移这些偏好到私人层，应另行授权开发。

### 固定旧Codex反馈通道：本轮不改
feedback_bridge.py的THREAD_ID常量固定绑定旧Codex聊天；通过codex queue --thread发送。已检查原运行源码与导出副本，本轮保持逐字不变。切换会话不会自动迁移反馈目标。
未来需将反馈目标改为可配置，显示目标、进行测试反馈、保留离线暂存与失败回执，避免反馈丢失或发错会话。**这只是待办，不得本轮实施或发送测试消息。**

## 5. 测试证据与限制
0.3.3历史记录为128项Python回归通过、音乐/宠物真实Edge夹具与5套Live2D加载通过；双地图真实路线、Fish免费型号、Gemma文字与图像/HTTP曾实测。证据原机companion-app/artifacts/及feedback-43ca7c7a-progress.md等，不随公开源码上传。
六个前端文件未完成实际应用的用户体验验收，不能继承基线测试结论。本次已执行音乐及宠物定向 Edge 夹具、JS 语法与 SVG XML 检查；未调用付费模型或语音接口。同步前核对了目录差异、待提交文件和隐私排除规则。
Windows DPAPI、WebView2、进程行为与显卡必须在Windows实测；Cloud/Linux静态检查不能替代。尚无手机/手表同步、支付闭环、全系统操作、自主改源码、健康分析或夜间常驻云任务。未来愿景见VISION.md。

## 6. 恢复与下一次工作
本地完整备份位置见D:/StudyLifePlan/handoff-backups/latest.json；含源代码WIP、api-hub、全部companion-data（包括模型/日志/反馈/加密状态）、一致性数据库快照与Git bundle。该目录为私人备份，绝不能push。
恢复只在新的独立目录中进行，先验证manifest与数据库integrity_check；不要覆盖原私人数据库或原文件。恢复后再由用户验收，必要时重新登录；详情见备份内RESTORE.md。
先读本 HANDOFF、VISION、AGENTS 及本轮交接清单。GitHub 源码同步不代表 WIP 验收或发布；下一次只按用户明确指定的一项任务继续，完成后更新交接文档并停止。
