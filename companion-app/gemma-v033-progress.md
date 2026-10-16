# Gemma 3 4B · 0.3.3

## 已完成

- `local_models.py`新增手动选项`gemma3-4b-it-q4_0`。自动选择仍只在Qwen3 4B/8B间路由；Gemma不进入4B输出失败升级链。明确手动指定Qwen4B也不再被自动升级。
- 使用D:/StudyLifePlan/companion-data/models/gemma3-4b内QAT Q4_0文本模型与F16 mmproj；两文件均需长度与SHA校验记录匹配才可选。
- 复用已验证llama.cpp b11690，按需单进程、127.0.0.1:18766、随机本机会话密钥。Gemma使用8192上下文、batch512、ubatch512、单图256 token；GPU预算额外预留mmproj和512MiB计算空间，CPU回退禁用mmproj GPU卸载。Qwen保留16K上下文和原推理参数，不传Gemma专用参数。
- Gemma文字请求使用现有小祥人设和明确确认的本机经验参考，不传`tools`、`enable_thinking`或`/no_think`，不声称原生工具调用能力，不修改权重。
- 新接口`local_runtime.analyze_images(prompt, images, context='', model=local_models.GEMMA)`：images为`[{'data':bytes,'mime_type':'image/png|image/jpeg|image/webp'}]`，1–2张、合计≤8MiB。只接调用方已经读入的图片，编码为本机data URI；不接路径或远程URL。结果保持`{text,calls:[],model,usage}`结构，purpose=image_analysis，不改变手动/自动选择。文件选择、解码与上传端点由主代理接入。
- status.models保留现有字段，新增capabilities、auto_routing和assets；下载进度包含分段文件，model_bytes为该型号文本模型+投影总大小。
- 官方README、Google公开Terms of Use和Prohibited Use Policy原文、NOTICE与含SHA来源清单已存入上述D盘模型目录。未登录或接受Hugging Face门禁，未执行远程代码。

## 来源

- [ggml-org QAT GGUF镜像](https://huggingface.co/ggml-org/gemma-3-4b-it-qat-GGUF/tree/bbcac0d065076c47042838c0675c602411b0dd4c)，固定revision`bbcac0d065076c47042838c0675c602411b0dd4c`。
- 模型`gemma-3-4b-it-qat-Q4_0.gguf`：2526080992字节，SHA256`ee91c3e7a4ab95d8c95672f9fcb58bf236b257e9f217966bcf53a5a6df4ab49a`。
- 投影`mmproj-model-f16-4B.gguf`：851251744字节，SHA256`c5271cab492e27cd123f808e9115a677b2ecfdb21c8152c1ad45cc455f3b592b`。
- [llama.cpp多模态文档](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)；已核对本机b11690 --help支持mmproj、禁用投影卸载和图像token参数。
- [Gemma条款](https://ai.google.dev/gemma/terms)、[使用政策](https://ai.google.dev/gemma/prohibited_use_policy)。Google模型仓库LICENSE访问返回401，保留公开官方条款快照；不把代码Apache许可误当模型许可。

## 验证与限制

- `python -m unittest test_gemma_runtime test_local_models test_local_runtime`：30项通过（含8项新增Gemma测试）。覆盖双文件完整性、Qwen自动链不变、手动不升级、Gemma/Qwen启动参数隔离、CPU投影、GPU预算、Gemma无原生工具请求、嵌入图片与错误输入先拒绝。
- 五个改动/新增Python文件编译通过。
- 原session16858完成两文件校验，未重启/重复下载。`python test_gemma_runtime_smoke.py --run-real`真实通过，证据`artifacts/gemma-smoke-033.json`，测试图片`artifacts/gemma-synthetic-033.png`由简单几何合成、不含个人资料。
- 文本7×8返回`56`；图片准确返回“图片左边是一个红色的正方形，右边是一个蓝色的圆形。”文本首次含加载3.422秒（1049输入/4输出token），图片0.891秒（772输入/35输出token），零云端费用。烟测结束已释放自有推理进程，selection前后均为auto。
- 首次图像烟测真实触发b11690断言`non-causal attention requires n_ubatch >= n_tokens`；原ubatch128低于Gemma图像块256 token，已仅将Gemma batch/ubatch调为512/512后重跑通过，并加回归断言。没有把首次失败记成通过。
- 实际运行backend显示`llama.cpp`：当前b11690默认日志未打印`offloaded`层数，代码不把请求了CUDA层数当作已经验证GPU卸载。CPU启动参数和含mmproj的GPU预算通过独立单测；不宣称实测CPU图像吞吐或已独立确认CUDA卸载层数。
- 本子任务实际请求为父会话继承配置，未请求具体模型覆盖。宿主未提供可独立核实的有效运行模型/推理配置元数据；本轮未发生真实模型切换，不把任务委派当作已验证切换。

主代理统一更新continuation与checkpoint。
