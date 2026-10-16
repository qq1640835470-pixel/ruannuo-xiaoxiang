# 当前0.3.3

先读companion-app/feedback-43ca7c7a-progress.md。Gemma 3 4B本机文本+mmproj完整校验并实测；工具里可选择本机图片，不上传云端。模型权重不在仓库，路径统一companion-data/models，克隆后需要官方源重新安装。
窄范围监测默认未授权的全新机器不开启；原机本地配置已本人授权启用。Fish仅指定免费型号，期限过后暂停；无API密钥上传。地图Key保存在原机DPAPI，未上传。个人活动库、音频缓存和原始反馈不在此仓库。
0.3.3的子代理实际配置缺乏独立平台元数据；不要把实模测试记录误当子代理身份认证。

---
# 0.3.2新增：双本机模型与经验适配

- local_models.py：官方4B/8B目录、自动复杂度判断、3分钟8B保温避免抖动、手动固定选择；单个llama-server，不同时加载两套权重。显存计划按可用显存和16K F16 KV估算，不能保证不影响游戏；失败可CPU运行。
- local_runtime.py/local_persona.py：共享小祥精简角色提示、只读引用记忆、工具白名单；自动模式4B输出格式失效时可在工具执行前升级8B一次，不重复执行工具。不会因为本地失败而自动付费调用云端。
- local_adaptation.py：本机明确偏好/纠错/人类示例检索，默认启用，可看/删/关闭/手动教；本机权重未训练，不把模型答案喂回去，不声称完成LoRA。真实用户适配记录未上传。
- API：GET /api/local/model；POST /api/local/model/control {operation:select,model:auto或qwen3-4b-q4_k_m或qwen3-8b-q4_k_m}；GET/PATCH /api/local/adaptation，POST /api/local/adaptation/teach，DELETE /api/local/adaptation/{id}。
- 8B官方元信息assets/qwen8b-official.json；实际下载与最终验收状态以本地交付记录为准，不从存在安装代码推断模型已装。

---
# 开发续接

## 先读
- 本版0.3.2；此前已实际运行，不要当成纯样图重建。
- Python服务 `companion-app/server.py`，前端 `web/app.js`，布局 `web/style.css`/`experience.css`，窗口宿主 `workspace_host.py`。
- 音乐 `music_service.py`、`music_bridge.cjs`、`web/netease-player.js`、`music-pet.js`；宠物 `companion.js`、`pet-motion.js`、`pet-physics.js`、`live2d-pet.js`。
- `app_paths.py` 统一数据到仓库旁 `companion-data/`（ignored）；原机器项目目录为D:/StudyLifePlan，但不要依赖该绝对目录。

## 本版已有
朗读停止；带幂等ID/回执的失败重试；SQLite聊天历史搜索/分页，主界面最多30条；网易云DPAPI登录恢复/搜索播放/气泡控制；Q版和5套Live2D切换；快速11次摸头阈值、真实背影及午餐/耳机/困倦图；圆润字体/设置折叠/同窗浏览器；高德百度路线适配；可选Qwen3-4B Q4_K_M本地推理、白名单工具及远程失败接续。

## 待解决
1. 通用联网搜索稳定性/结果质量；不能把验证码页当有效结果。
2. 高德/百度实际路线待配置Key；Google及手机连续GPS导航尚未启用。
3. SillyTavern预设、角色卡、世界书、数据库、语音包已在原机静态解析，整套原始私人资料未上传。仅选取的人设知识可在companion_knowledge.py/web数据中查看；没有通用插件执行器。
4. 原作台词来源核验、新Q图细边、原比例模型专用坐/挂/后背动作仍有限。
5. 可选本地模型能力不等同云端大模型；不声称具有全系统自主学习/任意改源码权限。

## 工作规则
- 默认中文，简洁；不添加装饰口号。
- 不上传/打印密钥、账号票据、私人聊天/定位/个人画像；不读取外部浏览器密码或凭据。
- 保留实际使用记录，不伪造余额；原机器已解除本机预算上限，但该设置不在源码备份内。不要把样例默认预算当成原机器用户的当前授权。
- 不自动发送QQ/邮件，不进行无授权付费调用；不要启动持续监测或日程催促。
- 模型配置只有实际调度参数与平台运行元数据才能证实，不凭自述认定模型身份。
- 重大修改先备份并记录，避免额度中断丢失进度；不要把Linux静态验证冒充Windows桌面验收。

## 复核证据
本机111项Python测试及11个Node文件通过。实际Edge夹具验证五套Live2D及快速摸头/裁切；实际网易云搜索并播放后暂停；实际Qwen中文和typed health工具成功。相关个人日志/截图未上传，证据仅在原机，不宣称克隆后已经复验。
