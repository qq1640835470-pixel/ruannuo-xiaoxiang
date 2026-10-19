# 软糯小祥 · 0.3.4

当前版本包含学习计划管理、学习成果检验和人工确认的动态调整；最新范围、验证与未验收事项见[交接说明](HANDOFF.md)。

Windows本地学习生活助手：对话、计划、带白名单的本地工具、天气/地图工作区、网易云播放器、Q版/原比例Live2D及可选本地Qwen/Gemma多模态。

这是从实际运行项目导出的源码快照（用户选择公开仓库）。用户数据和凭据没有上传，克隆后不会继承原机器账号或聊天内容。

## 目录
- `companion-app/`：Python本机HTTP后端、Web前端、原生双WebView2宿主、测试与宠物素材。
- `api-hub/hub.py`：现有API适配器的加密凭据/余额查询依赖；不包含密钥或余额快照。
- `HANDOFF.md`：网页端继续开发时的起点、已验证范围与待办。

## 本机运行
建议Python 3.11/3.12、Node.js 18+；桌面宿主仅Windows，依赖Edge WebView2 Runtime。

```powershell
python -m pip install -r requirements.txt
cd companion-app/music-runtime
npm ci --ignore-scripts
cd ..
python launch.py
```

仅开发Web界面时可运行 `python companion-app/server.py`，浏览器访问 `http://127.0.0.1:18764/`。Windows应用启动、DPAPI账号票据、原生WebView2和GPU运行时需要在Windows本机验收。请勿把服务公开到公网。

本地Qwen4B/8B是可选项，权重与llama.cpp不在仓库中。设置可自动/手动选择，两个模型单实例交替加载。经用户同意后可在本机运行 `python companion-app/local_runtime_setup.py` 下载官方模型与运行时；实际文件约数GB，脚本默认会联网下载，普通测试不会调用它。8B可运行 `python companion-app/local_runtime_setup.py --model 8b --model-only` 下载约5.03GB官方GGUF，需先有运行时。原机器已将模型统一存放D:/StudyLifePlan/companion-data/models；克隆项目按app_paths使用项目旁目录，不硬编码C盘。

API凭据与网易云登录应在目标Windows机器重新配置。原机器使用Windows当前用户DPAPI，不能把加密文件当成可跨机器登录资料。

## 验证
```powershell
cd companion-app
python -m unittest discover -p "test_*.py"
node test_chat_retry.js
node test_speech_v031.js
node test_music_v031.js
node test_pet_v031.js
```
交付时Windows运行111项Python测试、11个Node测试文件通过；全套含Windows DPAPI夹具，Linux环境不能照搬声称全部通过。实际模型烟雾测试需明确传入 `--run-real`，不要默认运行付费外部API测试。

## 素材许可
人物与Live2D素材来自用户提供资源包，尚未核实再分发许可，仅用于本账号私有开发备份，请保持仓库私有。Core/Pixi/字体等各自许可证随资源保留，不能统一宣称整个仓库为MIT。详见 `companion-app/web/assets/pet/NOTICE.md`。
